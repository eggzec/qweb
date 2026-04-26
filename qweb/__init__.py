# QWEB - Sun Grid Engine Web Interface
#
# For more information about this module, see PEP 324.
#
# Copyright (c) 2025 EGGZEC
#
# Licensed to PSF under a Contributor Agreement.

r"""QWEB - Sun Grid Engine Web Interface.

A comprehensive web-based wrapper for Sun Grid Engine providing:
- RESTful API for job submission (qsub)
- Job monitoring and control (qstat, qdel, qmod)
- Authentication and authorization
- Generic directory service support (LDAP/Active Directory)
"""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"

from qweb.api import QWebApp
from qweb.auth import AuthLevel, AuthService, User
from qweb.config import ConfigLoader, QWebConfig, get_config, reload_config
from qweb.directory import DirectoryBackend, DirectoryService
from qweb.logger import QWebLogger, get_logger, setup_logger
from qweb.sge import Host, Job, Queue, SGEClient


__all__ = [
    "AuthLevel",
    "AuthService",
    "ConfigLoader",
    "DirectoryBackend",
    "DirectoryService",
    "Host",
    "Job",
    "QWebApp",
    "QWebConfig",
    "QWebLogger",
    "Queue",
    "SGEClient",
    "User",
    "__version__",
    "get_config",
    "get_logger",
    "reload_config",
    "setup_logger",
]
