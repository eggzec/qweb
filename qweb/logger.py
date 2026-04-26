"""QWEB Logging Module.

For more information about this module, see PEP 324.

Copyright (c) 2025 EGGZEC

Licensed to PSF under a Contributor Agreement.
See http://www.python.org/2.4/license for licensing details

Main API
=======
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import pyfiglet
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


CONTACT_MESSAGE = "For more info contact: support@qweb.example.com"

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DETAILED_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)


def _redact_secrets(message: str) -> str:
    """Redact sensitive information from log records.

    Args:
        message: The log message to redact.

    Returns:
        The redacted message.
    """
    sensitive_keys = [
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "bind_password",
    ]
    for key in sensitive_keys:
        message = re.sub(
            rf"(['\"]*{key}['\"]*)\s*([=:])?\s*\S+",
            r"\1 \2[REDACTED]",
            message,
            flags=re.IGNORECASE,
        )
    return message


def _truncate_path(text: str) -> str:
    """Replace full file paths with only filenames.

    Args:
        text: The text containing file paths.

    Returns:
        The text with file paths truncated to filenames.
    """
    path_pattern = r"((?:/\w+)+\.\w+|\w:(?:\\\w+)+\.\w+)"

    def replacer(match: "re.Match[str]") -> str:
        full_path = match.group(0)
        unix_path = full_path.replace(os.sep, "/")
        return Path(unix_path).name

    return re.sub(path_pattern, replacer, text)


class QWebLogger:
    def __init__(
        self,
        name: str = "qweb",
        level: int = logging.INFO,
        log_file: Path | None = None,
        *,
        console: bool = True,
        rich_output: bool = True,
        redact_secrets: bool = True,
    ) -> None:
        self.name = name
        self.level = level
        self.log_file = log_file
        self.console = console
        self.rich_output = rich_output
        self.redact_secrets = redact_secrets
        self._logger = logging.getLogger(name)
        self._console = Console()
        self._setup_logger()

    def _setup_logger(self) -> None:
        self._logger.setLevel(self.level)
        self._logger.handlers = []

        formatter = logging.Formatter(
            DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
        )
        detailed_formatter = logging.Formatter(
            DETAILED_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
        )

        if self.rich_output:
            rich_handler = RichHandler(
                console=self._console,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_time=True,
                show_path=False,
            )
            rich_handler.setLevel(self.level)
            self._logger.addHandler(rich_handler)

        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                self.log_file, maxBytes=10 * 1024 * 1024, backupCount=5
            )
            file_handler.setFormatter(detailed_formatter)
            file_handler.setLevel(logging.DEBUG)
            self._logger.addHandler(file_handler)

        if not self._logger.handlers and self.console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self.level)
            self._logger.addHandler(console_handler)

        if self.redact_secrets:
            for handler in self._logger.handlers:
                original_emit = handler.emit

                def new_emit(
                    record: logging.LogRecord,
                    orig: logging.Handler = original_emit,
                ) -> None:
                    record.msg = _redact_secrets(record.getMessage())
                    return orig(record)

                handler.emit = new_emit

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying logger instance.

        Returns:
            The logging.Logger instance.
        """
        return self._logger

    def debug(self, msg: str, *args: object) -> None:
        """Log a debug message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.debug(msg, *args)

    def info(self, msg: str, *args: object) -> None:
        """Log an info message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.info(msg, *args)

    def warning(self, msg: str, *args: object) -> None:
        """Log a warning message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.warning(msg, *args)

    def error(self, msg: str, *args: object) -> None:
        """Log an error message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.error(msg, *args)

    def critical(self, msg: str, *args: object) -> None:
        """Log a critical message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.critical(msg, *args)

    def exception(self, msg: str, *args: object) -> None:
        """Log an exception message.

        Args:
            msg: The message to log.
            *args: Arguments for message formatting.
        """
        self._logger.exception(msg, *args)

    def print_banner(
        self, title: str = "", char: str = "=", color: str = "cyan"
    ) -> None:
        if not self.rich_output:
            return
        width = (
            min(os.get_terminal_size().columns, 120)
            if hasattr(os, "get_terminal_size")
            else 80
        )
        line = char * width
        self._console.print(Panel(line, style=color, expand=False))
        if title:
            self._console.print(Panel(title, style=color, expand=False))
            self._console.print(Panel(line, style=color, expand=False))

    def print_table(self, title: str, data: dict[str, Any]) -> None:
        if not self.rich_output:
            for key, value in data.items():
                self._logger.info(f"{key}: {value}")
            return
        table = Table(
            title=title, show_header=True, header_style="bold magenta"
        )
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        for key, value in data.items():
            table.add_row(str(key), str(value))
        self._console.print(table)

    def print_tree(
        self, data: dict[str, Any], title: str = "Structure"
    ) -> None:
        if not self.rich_output:
            return
        tree = Tree(f"[bold magenta]{title}[/bold magenta]")
        for key, value in data.items():
            tree.add(f"[cyan]{key}[/cyan]: [green]{value}[/green]")
        self._console.print(tree)

    def print_panel(
        self, content: str, title: str = "", style: str = "cyan"
    ) -> None:
        if not self.rich_output:
            self._logger.info(content)
            return
        panel = Panel(content, title=title, style=style, expand=False)
        self._console.print(panel)

    def print_version(self, version: str = "1.0.0") -> None:
        if self.rich_output:
            try:
                figlet = pyfiglet.Figlet(font="block")
                ascii_art = figlet.renderText("QWEB")
                for line in ascii_art.rstrip().split("\n"):
                    self._logger.info(line)
            except ValueError as e:
                self._logger.info(f"QWEB v{version} (figlet error: {e})")
        else:
            self._logger.info(f"QWEB v{version}")


_LOGGER: QWebLogger | None = None


def get_logger(
    name: str = "qweb",
    level: int = logging.INFO,
    log_file: Path | None = None,
    *,
    console: bool = True,
    rich_output: bool = True,
    redact_secrets: bool = True,
) -> QWebLogger:
    """Get or create the global logger instance.

    Args:
        name: Logger name.
        level: Log level.
        log_file: Optional file to log to.
        console: Whether to log to console.
        rich_output: Whether to use rich formatting.
        redact_secrets: Whether to redact sensitive data.

    Returns:
        The QWebLogger instance.
    """
    global _LOGGER  # pylint: disable=global-statement
    if _LOGGER is None:
        _LOGGER = QWebLogger(
            name=name,
            level=level,
            log_file=log_file,
            console=console,
            rich_output=rich_output,
            redact_secrets=redact_secrets,
        )
    return _LOGGER


def setup_logger(
    name: str = "qweb",
    level: int = logging.INFO,
    log_file: Path | None = None,
    *,
    console: bool = True,
    rich_output: bool = True,
    redact_secrets: bool = True,
) -> QWebLogger:
    """Setup and return a QWebLogger instance.

    Args:
        name: Logger name.
        level: Log level.
        log_file: Optional file to log to.
        console: Whether to log to console.
        rich_output: Whether to use rich formatting.
        redact_secrets: Whether to redact sensitive data.

    Returns:
        The configured QWebLogger instance.
    """
    return get_logger(
        name=name,
        level=level,
        log_file=log_file,
        console=console,
        rich_output=rich_output,
        redact_secrets=redact_secrets,
    )


def debug(msg: str, *args: object) -> None:
    """Log a debug message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().debug(msg, *args)


def info(msg: str, *args: object) -> None:
    """Log an info message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().info(msg, *args)


def warning(msg: str, *args: object) -> None:
    """Log a warning message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().warning(msg, *args)


def error(msg: str, *args: object) -> None:
    """Log an error message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().error(msg, *args)


def critical(msg: str, *args: object) -> None:
    """Log a critical message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().critical(msg, *args)


def exception(msg: str, *args: object) -> None:
    """Log an exception message.

    Args:
        msg: The message to log.
        *args: Arguments for message formatting.

    Returns:
        None.
    """
    return get_logger().exception(msg, *args)
