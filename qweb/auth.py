"""QWEB Authentication Module.

For more information about this module, see PEP 324.

Copyright (c) 2025 EGGZEC

Licensed to PSF under a Contributor Agreement.
See http://www.python.org/2.4/license for licensing details
"""

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


logger = logging.getLogger(__name__)


class DirectoryServiceProtocol(Protocol):
    def get_user(self, username: str) -> dict[str, str]: ...
    def get(self, key: str) -> str: ...


class AuthLevel(Enum):
    USER = 1
    OPERATOR = 2
    MANAGER = 3
    ADMIN = 4


class AuthError(Exception):
    pass


class AuthDisabledError(AuthError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthInvalidCredentialsError(AuthError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthPermissionDeniedError(AuthError):
    pass


@dataclass
class User:
    username: str
    auth_level: AuthLevel = AuthLevel.USER
    email: str | None = None
    full_name: str | None = None
    groups: list[str] = field(default_factory=list)
    project_list: list[str] = field(default_factory=list)
    queue_acl: str | None = None
    enabled: bool = True
    created_at: float | None = None
    last_login: float | None = None

    def can_submit_jobs(self) -> bool:
        return self.enabled and self.auth_level.value >= AuthLevel.USER.value

    def can_delete_jobs(self, job_owner: str) -> bool:
        if not self.enabled:
            return False
        if self.auth_level in {
            AuthLevel.OPERATOR,
            AuthLevel.MANAGER,
            AuthLevel.ADMIN,
        }:
            return True
        return job_owner == self.username

    def can_modify_jobs(self, job_owner: str) -> bool:
        if not self.enabled:
            return False
        if self.auth_level in {
            AuthLevel.OPERATOR,
            AuthLevel.MANAGER,
            AuthLevel.ADMIN,
        }:
            return True
        return job_owner == self.username

    def can_manage_queues(self) -> bool:
        return (
            self.enabled and self.auth_level.value >= AuthLevel.OPERATOR.value
        )

    def can_manage_configuration(self) -> bool:
        return self.enabled and self.auth_level.value >= AuthLevel.MANAGER.value

    def can_admin(self) -> bool:
        return self.enabled and self.auth_level.value >= AuthLevel.ADMIN.value


@dataclass
class Session:
    session_id: str
    user: User
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    ip_address: str | None = None
    user_agent: str | None = None

    def is_valid(self) -> bool:
        return time.time() < self.expires_at

    def refresh(self, ttl: int = 3600) -> None:
        self.expires_at = time.time() + ttl

    def invalidate(self) -> None:
        self.expires_at = 0


@dataclass
class UserUpdate:
    auth_level: AuthLevel | None = field(default=None)
    email: str | None = field(default=None)
    full_name: str | None = field(default=None)
    enabled: bool | None = field(default=None, compare=True)
    groups: list[str] | None = field(default=None)

    def has_changes(self) -> bool:
        return (
            self.auth_level is not None
            or self.email is not None
            or self.full_name is not None
            or self.enabled is not None
            or self.groups is not None
        )


def _apply_user_update(user: User, update: UserUpdate) -> User:
    if update.auth_level is not None:
        user.auth_level = update.auth_level
    if update.email is not None:
        user.email = update.email
    if update.full_name is not None:
        user.full_name = update.full_name
    if update.enabled is not None:
        user.enabled = update.enabled
    if update.groups is not None:
        user.groups = update.groups
    return user


class AuthService:
    def __init__(
        self,
        secret_key: str | None = None,
        session_ttl: int = 3600,
        algorithm: str = "sha256",
    ) -> None:
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.session_ttl = session_ttl
        self.algorithm = algorithm
        self._sessions: dict[str, Session] = {}
        self._users: dict[str, User] = {}
        self._password_cache: dict[str, tuple] = {}

    def set_secret_key(self, key: str) -> None:
        self.secret_key = key

    def hash_password(self, password: str, salt: str | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            self.algorithm, password.encode(), salt.encode(), 100000
        )
        return f"{salt}${key.hex()}"

    def verify_password(
        self, username: str, password: str, password_hash: str
    ) -> bool:
        try:
            salt, key = password_hash.split("$")
            expected = hashlib.pbkdf2_hmac(
                self.algorithm, password.encode(), salt.encode(), 100000
            )
            return hmac.compare_digest(expected.hex(), key)
        except (ValueError, AttributeError):
            return False

    def verify(
        self,
        username: str,
        password: str,
        directory_service: "DirectoryServiceProtocol | None" = None,
    ) -> User:
        if not username:
            msg = "Username cannot be empty"
            raise AuthInvalidCredentialsError(msg)
        user = self._users.get(username)
        if not user and directory_service:
            user = directory_service.get_user(username)
        if not user:
            msg = f"User '{username}' not found"
            raise AuthInvalidCredentialsError(msg)
        if not user.enabled:
            msg = f"Account '{username}' is disabled"
            raise AuthDisabledError(msg)
        try:
            dir_user = (
                directory_service.get_user(username)
                if directory_service
                else None
            )
            password_hash = None
            if dir_user:
                password_hash = dir_user.get("password")
                if password_hash and self.verify_password(
                    username, password, password_hash
                ):
                    user.last_login = time.time()
                    return user
        except (KeyError, TypeError, AttributeError) as e:
            logger.debug("Error verifying credentials for %s: %s", username, e)
        msg = "Invalid credentials"
        raise AuthInvalidCredentialsError(msg)

    def create_session(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        session_id = secrets.token_urlsafe(32)
        session = Session(
            session_id=session_id,
            user=user,
            expires_at=time.time() + self.session_ttl,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and session.is_valid():
            return session
        if session:
            del self._sessions[session_id]
        return None

    def refresh_session(self, session_id: str, ttl: int | None = None) -> bool:
        session = self.get_session(session_id)
        if session:
            session.refresh(ttl or self.session_ttl)
            return True
        return False

    def destroy_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def register_user(
        self,
        username: str,
        auth_level: AuthLevel = AuthLevel.USER,
        email: str | None = None,
        full_name: str | None = None,
        groups: list[str] | None = None,
    ) -> User:
        user = User(
            username=username,
            auth_level=auth_level,
            email=email,
            full_name=full_name,
            groups=groups or [],
            created_at=time.time(),
        )
        self._users[username] = user
        return user

    def get_user(self, username: str) -> User | None:
        return self._users.get(username)

    def update_user(self, username: str, update: UserUpdate) -> User | None:
        user = self._users.get(username)
        if not user:
            return None
        if not update.has_changes():
            return user
        return _apply_user_update(user, update)

    @staticmethod
    def check_permission(
        user: User, permission: str, *, check_admin: bool = False
    ) -> bool:
        permission_map = {
            "submit_jobs": user.can_submit_jobs,
            "delete_any_job": lambda: (
                user.auth_level.value >= AuthLevel.OPERATOR.value
            ),
            "modify_any_job": lambda: (
                user.auth_level.value >= AuthLevel.OPERATOR.value
            ),
            "manage_queues": user.can_manage_queues,
            "manage_config": user.can_manage_configuration,
            "admin": user.can_admin,
        }
        check_func = permission_map.get(permission)
        if check_func:
            return check_func()
        return False
