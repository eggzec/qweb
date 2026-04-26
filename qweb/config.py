"""QWEB Configuration Module.

For more information about this module, see PEP 324.

Copyright (c) 2025 EGGZEC

Licensed to PSF under a Contributor Agreement.
See http://www.python.org/2/4/license for licensing details
"""

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG_LOCATIONS = [
    "~/.qweb.conf",
    "~/.config/qweb.conf",
    "/etc/qweb.conf",
]


@dataclass
class SGEConfig:
    source_settings: str = ""
    sge_root: str = "sge/"
    sge_cell: str = "default"
    default_queue: str = ""
    default_pe: str = ""


@dataclass
class JobConfig:
    cwd: bool = True
    merge_output: bool = False
    output_dir: str = ""
    error_dir: str = ""
    mail_options: str = ""


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    cors_enabled: bool = True
    cors_origins: str = "*"
    rate_limit: int = 100
    rate_limit_period: int = 60


@dataclass
class AuthConfig:
    secret_key: str = ""
    session_ttl: int = 3600
    jwt_algorithm: str = "HS256"


@dataclass
class LDAPConfig:
    uri: str = ""
    base_dn: str = ""
    bind_dn: str = ""
    bind_password: str = ""
    use_ssl: bool = True
    use_tls: bool = False
    validate_cert: bool = True
    timeout: int = 30


@dataclass
class NISConfig:
    ypserver: str = ""
    domain: str = ""


@dataclass
class SQLConfig:
    connection_string: str = ""
    user_table: str = "users"
    username_column: str = "username"
    password_column: str = ""
    email_column: str = ""
    full_name_column: str = ""
    group_table: str = ""


@dataclass
class DirectoryConfig:
    backend: str = "none"
    ldap: LDAPConfig = field(default_factory=LDAPConfig)
    nis: NISConfig = field(default_factory=NISConfig)
    sql: SQLConfig = field(default_factory=SQLConfig)


@dataclass
class QWebConfig:
    sge: SGEConfig = field(default_factory=SGEConfig)
    job_defaults: JobConfig = field(default_factory=JobConfig)
    web: WebConfig = field(default_factory=WebConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    directory: DirectoryConfig = field(default_factory=DirectoryConfig)


class ConfigLoader:
    _instance: Optional["QWebConfig"] = None
    _config_path: Path | None = None

    @classmethod
    def get_config_path(cls) -> Path | None:
        if cls._config_path:
            return cls._config_path
        env_path = os.environ.get("QWEB_CONFIG")
        if env_path:
            cls._config_path = Path(env_path).expanduser()
            if cls._config_path.exists():
                return cls._config_path
        for loc in DEFAULT_CONFIG_LOCATIONS:
            path = Path(loc).expanduser()
            if path.exists():
                cls._config_path = path
                return cls._config_path
        return None

    @classmethod
    def load(cls, config_path: str | None = None) -> QWebConfig:
        path = None
        if config_path:
            path = Path(config_path).expanduser()
        else:
            path = cls.get_config_path()
        if not path or not path.exists():
            return QWebConfig()
        config = configparser.ConfigParser()
        config.read(path)
        qweb = QWebConfig()
        if config.has_section("sge"):
            qweb.sge = SGEConfig(
                source_settings=config.get(
                    "sge", "source_settings", fallback=""
                ),
                sge_root=config.get("sge", "sge_root", fallback="sge/"),
                sge_cell=config.get("sge", "sge_cell", fallback="default"),
                default_queue=config.get("sge", "default_queue", fallback=""),
                default_pe=config.get("sge", "default_pe", fallback=""),
            )
        if config.has_section("job_defaults"):
            qweb.job_defaults = JobConfig(
                cwd=config.getboolean("job_defaults", "cwd", fallback=True),
                merge_output=config.getboolean(
                    "job_defaults", "merge_output", fallback=False
                ),
                output_dir=config.get(
                    "job_defaults", "output_dir", fallback=""
                ),
                error_dir=config.get("job_defaults", "error_dir", fallback=""),
                mail_options=config.get(
                    "job_defaults", "mail_options", fallback=""
                ),
            )
        if config.has_section("web"):
            qweb.web = WebConfig(
                host=config.get("web", "host", fallback="127.0.0.1"),
                port=config.getint("web", "port", fallback=8080),
                debug=config.getboolean("web", "debug", fallback=False),
                cors_enabled=config.getboolean(
                    "web", "cors_enabled", fallback=True
                ),
                cors_origins=config.get("web", "cors_origins", fallback="*"),
                rate_limit=config.getint("web", "rate_limit", fallback=100),
                rate_limit_period=config.getint(
                    "web", "rate_limit_period", fallback=60
                ),
            )
        if config.has_section("auth"):
            qweb.auth = AuthConfig(
                secret_key=config.get("auth", "secret_key", fallback=""),
                session_ttl=config.getint("auth", "session_ttl", fallback=3600),
                jwt_algorithm=config.get(
                    "auth", "jwt_algorithm", fallback="HS256"
                ),
            )
        if config.has_section("directory"):
            qweb.directory.backend = config.get(
                "directory", "backend", fallback="none"
            )
        if config.has_section("ldap"):
            qweb.directory.ldap = LDAPConfig(
                uri=config.get("ldap", "uri", fallback=""),
                base_dn=config.get("ldap", "base_dn", fallback=""),
                bind_dn=config.get("ldap", "bind_dn", fallback=""),
                bind_password=config.get("ldap", "bind_password", fallback=""),
                use_ssl=config.getboolean("ldap", "use_ssl", fallback=True),
                use_tls=config.getboolean("ldap", "use_tls", fallback=False),
                validate_cert=config.getboolean(
                    "ldap", "validate_cert", fallback=True
                ),
                timeout=config.getint("ldap", "timeout", fallback=30),
            )
        if config.has_section("nis"):
            qweb.directory.nis = NISConfig(
                ypserver=config.get("nis", "ypserver", fallback=""),
                domain=config.get("nis", "domain", fallback=""),
            )
        if config.has_section("sql"):
            qweb.directory.sql = SQLConfig(
                connection_string=config.get(
                    "sql", "connection_string", fallback=""
                ),
                user_table=config.get("sql", "user_table", fallback="users"),
                username_column=config.get(
                    "sql", "username_column", fallback="username"
                ),
                password_column=config.get(
                    "sql", "password_column", fallback=""
                ),
                email_column=config.get("sql", "email_column", fallback=""),
                full_name_column=config.get(
                    "sql", "full_name_column", fallback=""
                ),
                group_table=config.get("sql", "group_table", fallback=""),
            )
        cls._instance = qweb
        return qweb

    @classmethod
    def get(cls) -> QWebConfig:
        if cls._instance is None:
            cls._instance = cls.load()
        return cls._instance

    @classmethod
    def reload(cls, config_path: str | None = None) -> QWebConfig:
        cls._instance = None
        return cls.load(config_path)


def get_config() -> QWebConfig:
    return ConfigLoader.get()


def reload_config(path: str | None = None) -> QWebConfig:
    return ConfigLoader.reload(path)
