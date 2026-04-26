# QWEB - Sun Grid Engine Web Interface
#
# For more information about this module, see PEP 324.
#
# Copyright (c) 2025 EGGZEC
#
# Licensed to PSF under a Contributor Agreement.

"""QWEB - Sun Grid Engine Web Interface.

A comprehensive web-based wrapper for Sun Grid Engine providing:
- RESTful API for job submission (qsub)
- Job monitoring and control (qstat, qdel, qmod)
- Authentication and authorization
- Generic directory service support (LDAP/Active Directory)
"""

import argparse
import json
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Any, TypeVar

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi as get_fastapi_schema
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


try:
    __version__ = version("qweb")
except PackageNotFoundError:
    __version__ = "unknown"

from qweb.auth import AuthService
from qweb.config import reload_config
from qweb.directory import create_directory_service
from qweb.logger import get_logger
from qweb.sge import SGEClient


class APIFramework(Enum):
    FLASK = "flask"
    FASTAPI = "fastapi"
    STARLETTE = "starlette"


@dataclass
class APIRoute:
    path: str
    method: str = "GET"
    handler: str = ""
    description: str = ""
    requires_auth: bool = True


@dataclass
class APIConfig:
    bind_address: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    cors_enabled: bool = True
    cors_origins: list = field(default_factory=lambda: ["*"])
    rate_limit: int = 100
    rate_limit_period: int = 60
    max_request_size: int = 10 * 1024 * 1024
    api_key_header: str = "X-API-Key"
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expiry: int = 3600


ClientType = TypeVar("ClientType")
AuthType = TypeVar("AuthType")
DirType = TypeVar("DirType")


class QWebApp:
    def __init__(
        self,
        sge_client: ClientType | None = None,
        auth_service: AuthType | None = None,
        directory_service: DirType | None = None,
        config: APIConfig | None = None,
        framework: APIFramework = APIFramework.FLASK,
    ) -> None:
        self.sge = sge_client or SGEClient()
        self.auth = auth_service or AuthService()
        self.directory = directory_service or create_directory_service()
        self.config = config or APIConfig()
        self.framework = framework
        self._app = None
        self._routes: list[APIRoute] = []
        self._flask_app: Flask | None = None
        self._fastapi_app: FastAPI | None = None

    def _create_app(self) -> None:
        if self.framework == APIFramework.FLASK:
            self._create_flask_app()
        elif self.framework == APIFramework.FASTAPI:
            self._create_fastapi_app()

    def _create_flask_app(self) -> None:
        app = Flask(__name__)
        if self.config.cors_enabled:
            CORS(app, origins=self.config.cors_origins)
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[
                f"{self.config.rate_limit} per {self.config.rate_limit_period}"
            ],
        )
        app.config["MAX_CONTENT_LENGTH"] = self.config.max_request_size
        self._flask_app = app
        self._register_flask_routes(app, limiter)

    def _register_flask_routes(
        self, flask_app: Flask, limiter: Limiter
    ) -> None:
        @flask_app.route("/api/health", methods=["GET"])
        def health() -> dict[str, str]:
            return jsonify({"status": "healthy", "service": "qweb"})

        @flask_app.route("/api/v1/jobs", methods=["GET"])
        @limiter.limit(
            f"{self.config.rate_limit} per {self.config.rate_limit_period}"
        )
        def list_jobs() -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            user = auth["user"]
            jobs = self.sge.qstat(user=user.username if user else None)
            return jsonify({
                "jobs": [
                    j.to_dict() if hasattr(j, "to_dict") else j.__dict__
                    for j in jobs.get("job_info", [])
                ],
                "running": [
                    j.to_dict() if hasattr(j, "to_dict") else j.__dict__
                    for j in jobs.get("queue_info", [])
                ],
            })

        @flask_app.route("/api/v1/jobs/<int:job_id>", methods=["GET"])
        def get_job(job_id: int) -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            job = self.sge.qstat(job_id=job_id)
            return jsonify(job)

        @flask_app.route("/api/v1/jobs", methods=["POST"])
        @limiter.limit("10 per minute")
        def submit_job() -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            auth["user"]
            data = request.get_json() or {}
            script_path = data.get("script")
            if not script_path:
                return jsonify({"error": "script is required"}), 400
            try:
                job_id = self.sge.qsub(
                    script_path=script_path,
                    job_name=data.get("name"),
                    cwd=data.get("cwd", True),
                    output_file=data.get("output"),
                    error_file=data.get("error"),
                    merge_output=data.get("merge_output", False),
                    pe_name=data.get("pe"),
                    pe_slots=data.get("pe_slots", 1),
                    resource_list=data.get("resources"),
                    queue=data.get("queue"),
                    project=data.get("project"),
                )
                return jsonify({"job_id": job_id, "status": "submitted"}), 201
            except OSError as e:
                return jsonify({"error": str(e)}), 500

        @flask_app.route("/api/v1/jobs/<int:job_id>", methods=["DELETE"])
        def delete_job(job_id: int) -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            user = auth["user"]
            if not user.can_delete_jobs("") and user.username != "admin":
                return jsonify({"error": "Permission denied"}), 403
            force = request.args.get("force", "false").lower() == "true"
            self.sge.qdel(job_id, force=force)
            return jsonify({"job_id": job_id, "status": "deleted"})

        @flask_app.route("/api/v1/jobs/<int:job_id>/hold", methods=["POST"])
        def hold_job(job_id: int) -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            self.sge.qhold(job_id)
            return jsonify({"job_id": job_id, "status": "held"})

        @flask_app.route("/api/v1/jobs/<int:job_id>/release", methods=["POST"])
        def release_job(job_id: int) -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            self.sge.qrls(job_id)
            return jsonify({"job_id": job_id, "status": "released"})

        @flask_app.route("/api/v1/queues", methods=["GET"])
        def list_queues() -> dict[str, Any]:
            queues = self.sge.list_queues()
            return jsonify({"queues": queues})

        @flask_app.route("/api/v1/queues/<queue_name>", methods=["GET"])
        def get_queue(queue_name: str) -> dict[str, Any]:
            queue_info = self.sge.get_queue_info(queue_name)
            return jsonify(queue_info)

        @flask_app.route("/api/v1/hosts", methods=["GET"])
        def list_hosts() -> dict[str, Any]:
            hosts = self.sge.list_hosts()
            return jsonify({"hosts": hosts})

        @flask_app.route("/api/v1/users/<username>", methods=["GET"])
        def get_user(username: str) -> dict[str, Any]:
            auth = self._check_auth(request)
            if not auth:
                return jsonify({"error": "Unauthorized"}), 401
            user_obj = self.directory.get_user(username)
            if user_obj:
                return jsonify(user_obj.to_dict())
            return jsonify({"error": "User not found"}), 404

        @flask_app.route("/api/v1/auth/login", methods=["POST"])
        def login() -> dict[str, Any]:
            data = request.get_json() or {}
            username = data.get("username")
            password = data.get("password")
            if not username or not password:
                return jsonify({"error": "Username and password required"}), 400
            try:
                user = self.auth.verify(username, password, self.directory)
                session_obj = self.auth.create_session(
                    user, request.remote_addr, request.headers.get("User-Agent")
                )
                return jsonify({
                    "session_id": session_obj.session_id,
                    "user": user.username,
                    "expires_at": session_obj.expires_at,
                })
            except OSError as e:
                return jsonify({"error": str(e)}), 401

        @flask_app.route("/api/v1/auth/logout", methods=["POST"])
        def logout() -> dict[str, Any]:
            session_id = request.headers.get(
                "X-Session-ID"
            ) or request.cookies.get("session_id")
            if session_id:
                self.auth.destroy_session(session_id)
            return jsonify({"status": "logged_out"})

        @flask_app.route("/api/v1/auth/refresh", methods=["POST"])
        def refresh() -> dict[str, Any]:
            session_id = request.headers.get("X-Session-ID")
            if not session_id:
                return jsonify({"error": "Session required"}), 400
            if self.auth.refresh_session(session_id):
                return jsonify({"status": "refreshed"})
            return jsonify({"error": "Invalid session"}), 401

    def _create_fastapi_app(self) -> None:
        app = FastAPI(title="QWEB API", version="1.0.0")
        if self.config.cors_enabled:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        self._fastapi_app = app
        self._register_fastapi_routes(app)

    def _register_fastapi_routes(self, fastapi_app: FastAPI) -> None:
        @fastapi_app.get("/api/health")
        def health() -> dict[str, str]:
            return {
                "status": "healthy",
                "service": "qweb",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        @fastapi_app.get("/api/v1/jobs")
        def list_jobs(user: str | None = None) -> dict[str, Any]:
            jobs = self.sge.qstat(user=user)
            return {
                "jobs": [j.__dict__ for j in jobs.get("job_info", [])],
                "running": [j.__dict__ for j in jobs.get("queue_info", [])],
            }

        @fastapi_app.get("/api/v1/jobs/{job_id}")
        def get_job(job_id: int) -> dict[str, Any]:
            return self.sge.qstat(job_id=job_id)

        @fastapi_app.post("/api/v1/jobs")
        def submit_job(data: dict[str, Any]) -> dict[str, Any]:
            script_path = data.get("script")
            if not script_path:
                raise HTTPException(
                    status_code=400, detail="script is required"
                )
            try:
                job_id = self.sge.qsub(**data)
                return {"job_id": job_id, "status": "submitted"}
            except OSError as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @fastapi_app.delete("/api/v1/jobs/{job_id}")
        def delete_job(job_id: int, *, force: bool = False) -> dict[str, Any]:
            self.sge.qdel(job_id, force=force)
            return {"job_id": job_id, "status": "deleted"}

        @fastapi_app.post("/api/v1/jobs/{job_id}/hold")
        def hold_job(job_id: int) -> dict[str, Any]:
            self.sge.qhold(job_id)
            return {"job_id": job_id, "status": "held"}

        @fastapi_app.post("/api/v1/jobs/{job_id}/release")
        def release_job(job_id: int) -> dict[str, Any]:
            self.sge.qrls(job_id)
            return {"job_id": job_id, "status": "released"}

        @fastapi_app.get("/api/v1/queues")
        def list_queues() -> dict[str, Any]:
            return {"queues": self.sge.list_queues()}

        @fastapi_app.get("/api/v1/queues/{queue_name}")
        def get_queue(queue_name: str) -> dict[str, Any]:
            return self.sge.get_queue_info(queue_name)

        @fastapi_app.get("/api/v1/hosts")
        def list_hosts() -> dict[str, Any]:
            return {"hosts": self.sge.list_hosts()}

    def _check_auth(self, req: object) -> dict[str, Any] | None:
        if not hasattr(req, "headers") or not hasattr(req, "cookies"):
            return None
        req_headers = getattr(req, "headers", None)
        req_cookies = getattr(req, "cookies", None)
        session_id = None
        if req_headers:
            session_id = req_headers.get("X-Session-ID")
        if not session_id and req_cookies:
            session_id = req_cookies.get("session_id")
        if session_id:
            session_obj = self.auth.get_session(session_id)
            if session_obj:
                return {"user": session_obj.user, "session": session_obj}
        api_key = ""
        if req_headers:
            api_key = req_headers.get(self.config.api_key_header)
        if api_key and api_key == os.environ.get("QWEB_API_KEY"):
            return {"user": None, "api_key": api_key}
        return None

    @staticmethod
    def _is_bindable(host: str, port: int) -> bool:
        if host == socket.INADDR_ANY or not host:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result != 0
        except OSError:
            return True

    def run(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        debug: bool | None = None,
    ) -> None:
        actual_host = host or self.config.bind_address
        actual_port = port or self.config.port

        if not self._is_bindable(actual_host, actual_port):
            actual_host = "127.0.0.1"

        actual_debug = debug if debug is not None else self.config.debug
        if not self._app:
            self._create_app()
        if self.framework == APIFramework.FLASK and self._flask_app:
            self._flask_app.run(
                host=actual_host, port=actual_port, debug=actual_debug
            )
        elif self.framework == APIFramework.FASTAPI and self._fastapi_app:
            uvicorn.run(self._fastapi_app, host=actual_host, port=actual_port)

    def get_routes(self) -> list[APIRoute]:
        return self._routes

    def add_route(
        self,
        path: str,
        method: str,
        handler: Callable[..., Any],
        description: str = "",
        *,
        requires_auth: bool = True,
    ) -> None:
        route = APIRoute(
            path=path,
            method=method,
            handler=handler.__name__ if callable(handler) else "",
            description=description,
            requires_auth=requires_auth,
        )
        self._routes.append(route)

    def enable_swagger(self) -> bool:
        return self.framework == APIFramework.FASTAPI

    def get_openapi_schema(self) -> dict[str, Any]:
        if self.framework == APIFramework.FASTAPI and self._fastapi_app:
            return get_fastapi_schema(
                title="QWEB API",
                version="1.0.0",
                routes=self._fastapi_app.routes,
            )
        return {}

    def export_config(self, path: str) -> dict[str, Any]:
        config = {
            "host": self.config.bind_address,
            "port": self.config.port,
            "debug": self.config.debug,
            "cors": {
                "enabled": self.config.cors_enabled,
                "origins": self.config.cors_origins,
            },
            "rate_limit": {
                "requests": self.config.rate_limit,
                "period": self.config.rate_limit_period,
            },
            "routes": [
                {
                    "path": r.path,
                    "method": r.method,
                    "description": r.description,
                    "requires_auth": r.requires_auth,
                }
                for r in self._routes
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="QWEB - Sun Grid Engine Web Interface"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to bind to"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    parser.add_argument("--config", type=str, help="Config file path")
    args = parser.parse_args()

    logger = get_logger()
    logger.print_version(__version__)

    if args.config:
        reload_config(args.config)

    app = QWebApp()
    logger.info(f"Starting QWEB server on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
