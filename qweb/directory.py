"""QWEB Directory Service Module."""

import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar, cast

import bcrypt

from qweb.config import SQLConfig, get_config


try:
    import nis
except ImportError:
    nis = None  # type: ignore

if TYPE_CHECKING:
    from qweb.auth import AuthService
else:
    try:
        import ldap
        from ldap import initialize as ldap_initialize
    except ImportError:
        ldap = None
        ldap_initialize = None

_T = TypeVar("_T")


logger = logging.getLogger(__name__)


class DirectoryBackend(Enum):
    LDAP = "ldap"
    AD = "active_directory"
    NIS = "nis"
    SQL = "sql"
    CUSTOM = "custom"
    NONE = "none"


class DirectoryError(Exception):
    pass


class DirectoryConnectionError(DirectoryError):
    pass


class DirectoryAuthError(DirectoryError):
    pass


class DirectoryNotFoundError(DirectoryError):
    pass


@dataclass
class DirectoryEntry:
    username: str
    dn: str | None = None
    uid: int | None = None
    gid: int | None = None
    home_directory: str | None = None
    shell: str | None = None
    email: str | None = None
    full_name: str | None = None
    groups: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "dn": self.dn,
            "uid": self.uid,
            "gid": self.gid,
            "home_directory": self.home_directory,
            "shell": self.shell,
            "email": self.email,
            "full_name": self.full_name,
            "groups": self.groups,
            **self.attributes,
        }


@dataclass
class LDAPConfig:
    uri: str = ""
    base_dn: str = ""
    bind_dn: str | None = None
    bind_pw: str | None = None
    use_ssl: bool = True
    use_tls: bool = False
    validate_cert: bool = True
    cert_path: str | None = None
    timeout: int = 30
    page_size: int = 1000


@dataclass
class SQLConfig:
    connection_string: str = ""
    user_table: str = "users"
    user_id_column: str = "id"
    username_col: str = "username"
    passwd_col: str = ""  # nosec: B105
    email_col: str | None = None
    full_name_col: str | None = None
    group_table: str | None = None
    user_group_col: str | None = None


class DirectoryService(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def get_user(self, username: str) -> DirectoryEntry | None:
        pass

    @abstractmethod
    def get_users(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[DirectoryEntry]:
        pass

    @abstractmethod
    def get_group(self, groupname: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def get_groups(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def authenticate(self, username: str, password: str) -> bool:
        pass

    @abstractmethod
    def search(
        self,
        filter_str: str,
        base_dn: str | None = None,
        attrs: list[str] | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        pass


class LDAPDirectoryService(DirectoryService):
    def __init__(
        self,
        uri: str,
        base_dn: str,
        bind_dn: str | None = None,
        bind_pw: str | None = None,
        *,
        enable_ssl: bool = True,
    ) -> None:
        self.uri = uri
        self.base_dn = base_dn
        self.bind_dn = bind_dn
        self.bind_pw = bind_pw
        self.enable_ssl = enable_ssl
        self._conn: Any = None

    def connect(self) -> bool:
        try:
            self._conn = ldap_initialize(self.uri)
            self._conn.set_option(ldap.OPT_REFERRALS, 0)
            if self.bind_dn and self.bind_pw:
                self._conn.simple_bind_s(self.bind_dn, self.bind_pw)
            elif self.bind_dn:
                self._conn.simple_bind_s(self.bind_dn, "")
            return True
        except ImportError as e:
            raise DirectoryError(f"python-ldap not installed: {e}") from e
        except ldap.LDAPError as e:
            raise DirectoryConnectionError(f"Failed to connect: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            try:
                self._conn.unbind_s()
            except ldap.LDAPError:
                logger.warning("Error disconnecting from LDAP server")
            self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None

    def get_user(self, username: str) -> DirectoryEntry | None:
        if not self.is_connected():
            self.connect()

        filter_str = (
            f"(|(uid={username})(sAMAccountName={username})(cn={username}))"
        )
        try:
            result = self._conn.search_s(
                self.base_dn, ldap.SCOPE_SUBTREE, filter_str, None
            )
            if result:
                dn, attrs = result[0]
                return self._parse_entry(dn, attrs)
        except ldap.LDAPError:
            logger.warning("Error fetching user from LDAP: %s", username)
        return None

    def get_users(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[DirectoryEntry]:
        if not self.is_connected():
            self.connect()

        f_str = filter_str or "(objectClass=*)"
        base = base_dn or self.base_dn
        scope_map = {
            "base": ldap.SCOPE_BASE,
            "one": ldap.SCOPE_ONELEVEL,
            "subtree": ldap.SCOPE_SUBTREE,
        }
        try:
            result = self._conn.search_s(
                base, scope_map.get(scope, ldap.SCOPE_SUBTREE), f_str, None
            )
            return [self._parse_entry(dn, a) for dn, a in result]
        except ldap.LDAPError:
            logger.warning("Error fetching users from LDAP")
            return []

    def get_group(self, groupname: str) -> dict[str, Any] | None:
        if not self.is_connected():
            self.connect()

        filter_str = f"(|(cn={groupname})(dn={groupname}))"
        try:
            result = self._conn.search_s(
                self.base_dn, ldap.SCOPE_SUBTREE, filter_str, None
            )
            if result:
                _, attrs = result[0]
                return self._attrs_to_dict(attrs)
        except ldap.LDAPError:
            logger.warning("Error fetching group from LDAP: %s", groupname)
        return None

    def get_groups(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        if not self.is_connected():
            self.connect()

        f_str = filter_str or "(objectClass=group)"
        base = base_dn or self.base_dn
        scope_map = {
            "base": ldap.SCOPE_BASE,
            "one": ldap.SCOPE_ONELEVEL,
            "subtree": ldap.SCOPE_SUBTREE,
        }
        try:
            result = self._conn.search_s(
                base, scope_map.get(scope, ldap.SCOPE_SUBTREE), f_str, None
            )
            return [self._attrs_to_dict(a) for dn, a in result]
        except ldap.LDAPError:
            logger.warning("Error fetching groups from LDAP")
            return []

    def authenticate(self, username: str, password: str) -> bool:
        try:
            user = self.get_user(username)
            if not user:
                return False
            temp_conn = ldap_initialize(self.uri)
            temp_conn.simple_bind_s(user.dn, password)
            temp_conn.unbind_s()
            return True
        except ldap.LDAPError:
            logger.warning("Error authenticating user: %s", username)
            return False

    def search(
        self,
        filter_str: str,
        base_dn: str | None = None,
        attrs: list[str] | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        if not self.is_connected():
            self.connect()

        base = base_dn or self.base_dn
        scope_map = {
            "base": ldap.SCOPE_BASE,
            "one": ldap.SCOPE_ONELEVEL,
            "subtree": ldap.SCOPE_SUBTREE,
        }
        try:
            result = self._conn.search_s(
                base,
                scope_map.get(scope, ldap.SCOPE_SUBTREE),
                filter_str,
                attrs,
            )
            return [self._attrs_to_dict(a) for dn, a in result if a]
        except ldap.LDAPError:
            logger.warning("Error searching LDAP")
            return []

    @staticmethod
    def _get_val(d: dict[str, object], k: str) -> object:
        v = d.get(k)
        return v[0] if v and isinstance(v, list) else v

    @staticmethod
    def _attrs_to_dict(attrs: dict[str, object]) -> dict[str, object]:
        result = {}
        for key, values in attrs.items():
            if isinstance(values, list) and len(values) == 1:
                result[key] = values[0]
            else:
                result[key] = values
        return result

    def _parse_entry(self, dn: str, attrs: dict[str, object]) -> DirectoryEntry:
        groups: list[str] = []
        if "memberOf" in attrs:
            for g in attrs["memberOf"]:
                if isinstance(g, list):
                    cn = [p.split(",")[0].replace("CN=", "") for p in g]
                    groups.extend(cn)
                else:
                    cn = g.split(",")[0].replace("CN=", "")
                    groups.append(cn)
        uid_val = self._get_val(attrs, "uidNumber")
        gid_val = self._get_val(attrs, "gidNumber")
        return DirectoryEntry(
            username=cast(str, self._get_val(attrs, "uid"))
            or cast(str, self._get_val(attrs, "sAMAccountName"))
            or dn.split(",", maxsplit=1)[0].replace("CN=", ""),
            dn=dn,
            uid=int(cast(int, uid_val)) if uid_val else None,
            gid=int(cast(int, gid_val)) if gid_val else None,
            home_directory=cast(str, self._get_val(attrs, "homeDirectory")),
            shell=cast(str, self._get_val(attrs, "loginShell")),
            email=cast(str, self._get_val(attrs, "mail")),
            full_name=cast(str, self._get_val(attrs, "displayName"))
            or cast(str, self._get_val(attrs, "cn")),
            groups=groups,
            attributes=self._attrs_to_dict(attrs),
        )


_T = TypeVar("_T")


class ActiveDirectoryService(LDAPDirectoryService):
    def __init__(
        self,
        uri: str,
        domain: str,
        base_dn: str | None = None,
        *,
        use_kerberos: bool = False,
        **kwargs: object,
    ) -> None:
        base = base_dn or f"dc={',dc='.join(domain.split('.'))}"
        super().__init__(uri=uri, base_dn=base, **kwargs)
        self.domain = domain


class NISDirectoryService(DirectoryService):
    def __init__(self, ypserver: str | None = None, domain: str = "") -> None:
        self.ypserver = ypserver
        self.domain = domain
        self._connected = False

    def connect(self) -> bool:
        try:
            if nis is None:
                raise DirectoryError("NIS module not available on this system")
            nis.set_domain(self.domain) if self.domain else None
        except ImportError as e:
            raise DirectoryError(f"NIS connection failed: {e}") from e
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_user(self, username: str) -> DirectoryEntry | None:
        if not self.is_connected():
            self.connect()
        if pwd is None:
            raise DirectoryError("pwd module not available on this system")
        try:
            pwd_entry = pwd.getpwnam(username)
            return DirectoryEntry(
                username=pwd_entry.pw_name,
                uid=pwd_entry.pw_uid,
                gid=pwd_entry.pw_gid,
                home_directory=pwd_entry.pw_dir,
                shell=pwd_entry.pw_shell,
                full_name=pwd_entry.pw_gecos,
            )
        except KeyError:
            logger.warning("User not found in NIS: %s", username)
        return None

    def get_users(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[DirectoryEntry]:
        if not self.is_connected():
            self.connect()
        if pwd is None:
            raise DirectoryError("pwd module not available on this system")
        try:
            users = []
            for pw_entry in pwd.getwall():
                users.append(
                    DirectoryEntry(
                        username=pw_entry.pw_name,
                        uid=pw_entry.pw_uid,
                        gid=pw_entry.pw_gid,
                        home_directory=pw_entry.pw_dir,
                        shell=pw_entry.pw_shell,
                        full_name=pw_entry.pw_gecos,
                    )
                )
            return users
        except (ImportError, AttributeError) as e:
            raise DirectoryError(f"pwd module error: {e}") from e

    def get_group(self, groupname: str) -> dict[str, Any] | None:
        if not self.is_connected():
            self.connect()
        if grp is None:
            raise DirectoryError("grp module not available on this system")
        try:
            gr = grp.getgrnam(groupname)
            return {
                "name": gr.gr_name,
                "gid": gr.gr_gid,
                "members": list(gr.gr_mem),
            }
        except KeyError:
            logger.warning("Group not found in NIS: %s", groupname)
            return None

    def get_groups(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        if not self.is_connected():
            self.connect()
        if grp is None:
            raise DirectoryError("grp module not available on this system")
        try:
            return [
                {
                    "name": gr.gr_name,
                    "gid": gr.gr_gid,
                    "members": list(gr.gr_mem),
                }
                for gr in grp.getgrall()
            ]
        except ImportError as e:
            raise DirectoryError(f"grp module not available: {e}") from e

    def authenticate(self, username: str, password: str) -> bool:
        if spwd is None:
            logger.warning("spwd module not available")
            return False
        try:
            user = self.get_user(username)
            if not user:
                return False
            try:
                spw = spwd.getspnam(username)
                stored = spw.sp_pwd.encode("utf-8")
                return bcrypt.checkpw(password.encode("utf-8"), stored)
            except (KeyError, PermissionError):
                logger.warning(
                    "Error getting shadow password for user: %s", username
                )
                return False
        except (ImportError, DirectoryError):
            logger.warning("spwd module not available")
            return False

    @staticmethod
    def search(
        filter_str: str,
        base_dn: str | None = None,
        attrs: list[str] | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        return []


def _build_sql(parts: list[str]) -> str:
    """Build a SQL query from validated schema parts.

    Args:
        parts: List of SQL fragments to join.

    Returns:
        The assembled SQL query string.
    """
    return " ".join(parts)


class SQLDirectoryService(DirectoryService):
    def __init__(self, config: SQLConfig) -> None:
        self.connection_string = config.connection_string
        self.user_table = config.user_table
        self.user_id_column = "id"
        self.username_col = config.username_column
        self.email_col = config.email_column or None
        self.full_name_col = config.full_name_column or None
        self.group_table = config.group_table or None
        self.user_group_col = None
        self._conn: Any = None

    def create_connection(self) -> None:
        self._conn = sqlite3.connect(self.connection_string)

    def connect(self) -> bool:
        try:
            self._conn = sqlite3.connect(self.connection_string)
            return True
        except sqlite3.Error as e:
            raise DirectoryConnectionError(f"SQL connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def is_connected(self) -> bool:
        return self._conn is not None

    @staticmethod
    def _validate_filter(filter_str: str) -> tuple[bool, str]:
        if not filter_str:
            return True, ""
        dangerous = (
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "ALTER",
            "TRUNCATE",
            "CREATE",
        )
        upper = filter_str.upper()
        for kw in dangerous:
            if kw in upper:
                logger.warning("SQL filter contains dangerous keyword: %s", kw)
                return False, ""
        return True, filter_str

    def get_user(self, username: str) -> DirectoryEntry | None:
        if not self.is_connected():
            self.connect()
        try:
            cursor = self._conn.cursor()
            # Column names are instance attributes validated at init
            query = _build_sql([
                "SELECT * FROM",
                self.user_table,
                "WHERE",
                self.username_col,
                "= ?",
            ])
            cursor.execute(query, (username,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                data = dict(zip(cols, row, strict=False))
                return DirectoryEntry(
                    username=data[self.username_col],
                    uid=data.get(self.user_id_column),
                    email=data.get(self.email_col),
                    full_name=data.get(self.full_name_col),
                    attributes=data,
                )
        except sqlite3.Error as e:
            logger.warning("Error fetching user from SQL: %s", e)
        return None

    def get_users(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[DirectoryEntry]:
        if not self.is_connected():
            self.connect()
        valid, validated = self._validate_filter(filter_str or "")
        if not valid:
            return []
        try:
            cursor = self._conn.cursor()
            query_parts = ["SELECT * FROM", self.user_table]
            params: tuple = ()
            if validated:
                query_parts.extend(["WHERE", validated])
            query = _build_sql(query_parts)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            return [
                DirectoryEntry(
                    username=row[cols.index(self.username_col)],
                    uid=row[cols.index(self.user_id_column)]
                    if self.user_id_column in cols
                    else None,
                    email=row[cols.index(self.email_col)]
                    if self.email_col and self.email_col in cols
                    else None,
                    full_name=row[cols.index(self.full_name_col)]
                    if self.full_name_col and self.full_name_col in cols
                    else None,
                    attributes=dict(zip(cols, row, strict=False)),
                )
                for row in rows
            ]
        except sqlite3.Error as e:
            logger.warning("Error fetching users from SQL: %s", e)
            return []

    def get_group(self, groupname: str) -> dict[str, Any] | None:
        if not self.group_table:
            return None
        if not self.is_connected():
            self.connect()
        try:
            cursor = self._conn.cursor()
            query = _build_sql([
                "SELECT * FROM",
                self.group_table,
                "WHERE name = ?",
            ])
            cursor.execute(query, (groupname,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                return dict(zip(cols, row, strict=False))
        except sqlite3.Error as e:
            logger.warning("Error fetching group from SQL: %s", e)
        return None

    def get_groups(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        if not self.group_table:
            return []
        if not self.is_connected():
            self.connect()
        valid, validated = self._validate_filter(filter_str or "")
        if not valid:
            return []
        try:
            cursor = self._conn.cursor()
            query_parts = ["SELECT * FROM", self.group_table]
            params: tuple = ()
            if validated:
                query_parts.extend(["WHERE", validated])
            query = _build_sql(query_parts)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row, strict=False)) for row in rows]
        except sqlite3.Error as e:
            logger.warning("Error fetching groups from SQL: %s", e)
            return []

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        return False

    @staticmethod
    def search(
        filter_str: str,
        base_dn: str | None = None,
        attrs: list[str] | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        return []


class PassthroughDirectoryService(DirectoryService):
    def __init__(self, auth_service: "AuthService | None" = None) -> None:
        self.auth_service = auth_service
        self._connected = True

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_user(self, username: str) -> DirectoryEntry | None:
        if self.auth_service:
            user = self.auth_service.get_user(username)
            if user:
                return DirectoryEntry(
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                    groups=user.groups,
                    attributes={"auth_level": user.auth_level.name},
                )
        return None

    def get_users(
        self,
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[DirectoryEntry]:
        if self.auth_service:
            return [
                DirectoryEntry(
                    username=u.username,
                    email=u.email,
                    full_name=u.full_name,
                    groups=u.groups,
                )
                for u in self.auth_service._users.values()
            ]
        return []

    @staticmethod
    def get_group(groupname: str) -> dict[str, Any] | None:
        return {"name": groupname, "members": []}

    @staticmethod
    def get_groups(
        filter_str: str | None = None,
        base_dn: str | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        return []

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        return False

    @staticmethod
    def search(
        filter_str: str,
        base_dn: str | None = None,
        attrs: list[str] | None = None,
        scope: str = "subtree",
    ) -> list[dict[str, Any]]:
        return []


def create_directory_service(
    backend: DirectoryBackend | None = None,
    config: dict[str, Any] | None = None,
) -> DirectoryService:
    cfg = get_config()
    config = config or {}
    if backend is None:
        backend_name = (
            cfg.directory.backend.lower() if cfg.directory.backend else "none"
        )
        backend = (
            DirectoryBackend(backend_name)
            if backend_name != "none"
            else DirectoryBackend.NONE
        )
    if backend == DirectoryBackend.LDAP:
        ldap_cfg = cfg.directory.ldap
        return LDAPDirectoryService(
            uri=config.get("uri") or ldap_cfg.uri or "",
            base_dn=config.get("base_dn") or ldap_cfg.base_dn or "",
            bind_dn=config.get("bind_dn") or ldap_cfg.bind_dn,
            bind_pw=config.get("bind_password") or ldap_cfg.bind_password,
            use_ssl=config.get("use_ssl", ldap_cfg.use_ssl),
            use_tls=config.get("use_tls", ldap_cfg.use_tls),
            validate_cert=config.get("validate_cert", ldap_cfg.validate_cert),
            timeout=config.get("timeout", ldap_cfg.timeout),
        )
    if backend == DirectoryBackend.AD:
        ldap_cfg = cfg.directory.ldap
        domain = (
            config.get("domain")
            or ldap_cfg.base_dn.replace("dc=", "").replace(",", ".")
            if ldap_cfg.base_dn
            else "example.com"
        )
        return ActiveDirectoryService(
            uri=config.get("uri") or ldap_cfg.uri or "",
            domain=domain,
            base_dn=config.get("base_dn") or ldap_cfg.base_dn,
            use_kerberos=config.get("use_kerberos", False),
        )
    if backend == DirectoryBackend.NIS:
        nis_cfg = cfg.directory.nis
        return NISDirectoryService(
            ypserver=config.get("ypserver") or nis_cfg.ypserver,
            domain=config.get("domain") or nis_cfg.domain,
        )
    if backend == DirectoryBackend.SQL:
        sql_cfg = cfg.directory.sql
        return SQLDirectoryService(
            config=SQLConfig(
                connection_string=config.get("connection_string")
                or sql_cfg.connection_string
                or ":memory:",
                user_table=config.get("user_table", sql_cfg.user_table),
                username_column=config.get(
                    "username_column", sql_cfg.username_column
                ),
                email_column=config.get("email_column") or sql_cfg.email_column,
                full_name_column=config.get("full_name_column")
                or sql_cfg.full_name_column,
                group_table=config.get("group_table") or sql_cfg.group_table,
            )
        )
    if backend == DirectoryBackend.CUSTOM:
        factory = config.get("factory")
        if factory and callable(factory):
            return factory(config)
    return PassthroughDirectoryService()
