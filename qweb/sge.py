"""SGE - Sun Grid Engine Python client.

For more information about this module, see PEP 324.

Copyright (c) 2025 EGGZEC

Licensed to PSF under a Contributor Agreement.
See http://www.python.org/2/4/license for licensing details

Main API
=======
"""

import inspect
import re
import shutil
import subprocess  # noqa S404
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import xmltodict

from qweb.config import SGEConfig, get_config


_BASH_PATH = shutil.which("bash") or "/bin/bash"

_MIN_HOST_FIELDS = 3


class SGEError(RuntimeError):
    def __init__(self, msg: str) -> None:
        frame = inspect.stack()[2]
        caller = frame.function
        msg = f"<SGE::{caller}> {msg}"
        super().__init__(msg)


JobState = Literal[
    "r", "s", "q", "w", "t", "qw", "hqw", "hRr", "dr", "E", "R", "dt"
]
QueueState = Literal[
    "a", "o", "A", "C", "D", "c", "d", "s", "S", "u", "E", "au"
]


class JobStatus(Enum):
    RUNNING = "r"
    SUSPENDED = "s"
    QUEUED = "q"
    WAITING = "w"
    TRANSFERRING = "t"
    QUEUED_WAITING = "qw"
    HELD_QUEUED = "hqw"
    HELD_RUNNING = "hRr"
    DELETED_RUNNING = "dr"
    ERROR = "E"
    RESTARTED = "R"
    DEFAULT = "dt"


class QueueStatus(Enum):
    LOAD_ALARM = "a"
    ORPHANED = "o"
    SUSPEND_ALARM = "A"
    SUSPENDED_CALENDAR = "C"
    DISABLED_CALENDAR = "D"
    CONFIG_AMBIGUOUS = "c"
    DISABLED = "d"
    SUSPENDED = "s"
    SUSPENDED_SUBORD = "S"
    UNKNOWN = "u"
    ERROR = "E"
    ALARM_UNREACHABLE = "au"


@dataclass
class Job:
    job_id: int
    name: str
    owner: str
    state: str
    priority: float = 0.0
    submission_time: datetime | None = None
    start_time: datetime | None = None
    queue: str | None = None
    slots: int = 1
    task_id: int | None = None
    project: str | None = None
    department: str | None = None
    cpu_time: str | None = None
    memory: str | None = None
    io: str | None = None
    tickets: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        job_id = int(data.get("JB_job_number", 0))
        return cls(
            job_id=job_id,
            name=data.get("JB_name", "unknown"),
            owner=data.get("JB_owner", "unknown"),
            state=data.get("state", "qw"),
            priority=float(data.get("JAT_prio", 0.0)),
            submission_time=cls._parse_time(data.get("JB_submission_time")),
            start_time=cls._parse_time(data.get("JAT_start_time")),
            queue=data.get("queue_name", ""),
            slots=int(data.get("slots", 1)),
            task_id=int(data.get("ja_task_id", 0))
            if data.get("ja_task_id")
            else None,
            project=data.get("JB_project"),
            department=data.get("JB_department"),
            cpu_time=data.get("cpu"),
            memory=data.get("mem"),
            io=data.get("io"),
            tickets=int(data.get("tckts", 0)) if data.get("tckts") else None,
        )

    @staticmethod
    def _parse_time(time_str: str | None) -> datetime | None:
        if not time_str:
            return None
        try:
            if "T" in time_str:
                return datetime.fromisoformat(time_str.replace("T", " "))
            return datetime.strptime(time_str, "%m/%d/%Y %H:%M:%S")
        except (ValueError, TypeError):
            return None


@dataclass
class Queue:
    name: str
    qtype: str = ""
    used_slots: int = 0
    free_slots: int = 0
    load_avg: float = 0.0
    arch: str = ""
    state: str = ""
    jobs: list[Job] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, jobs: list[Job] | None = None) -> "Queue":
        name = data.get("name", "unknown")
        qtype = data.get("qtype", "BIP")
        used_match = re.search(r"(\d+)/(\d+)", data.get("slots", "0/0"))
        used = int(used_match.group(1)) if used_match else 0
        free = int(used_match.group(2)) if used_match else 0
        return cls(
            name=name,
            qtype=qtype,
            used_slots=used,
            free_slots=free,
            load_avg=float(data.get("load_avg", 0.0)),
            arch=data.get("arch", ""),
            state=data.get("state", ""),
            jobs=jobs or [],
        )


@dataclass
class Host:
    hostname: str
    arch: str = ""
    load_avg: float = 0.0
    state: str = ""
    slots_total: int = 0
    slots_used: int = 0
    slots_free: int = 0


@dataclass
class QsubOptions:
    """Options for qsub job submission."""

    job_name: str | None = None
    cwd: bool = True
    output_file: str | None = None
    error_file: str | None = None
    merge_output: bool = False
    pe_name: str | None = None
    pe_slots: int = 1
    resource_list: dict[str, str] | None = None
    queue: str | None = None
    project: str | None = None
    array_range: str | None = None
    hold_jid: int | str | None = None
    priority: int | None = None
    mail_user: str | None = None
    mail_options: str | None = None
    binary: bool = False
    native_specs: str | None = None


@dataclass
class QstatOptions:
    """Options for qstat query."""

    job_id: int | str | None = None
    user: str | None = None
    full: bool = False
    extended: bool = False
    show_resources: bool = False
    state_filter: str | None = None
    xml: bool = True


@dataclass
class QmodOptions:
    """Options for qmod modification."""

    job_id: int | str | None = None
    queue: str | None = None
    suspend: bool = False
    unsuspend: bool = False
    enable: bool = False
    disable: bool = False
    clear_error: bool = False
    force: bool = False


# Simple flag mapping: option attr -> SGE flag
_QSUB_SIMPLE_FLAGS: dict[str, str] = {
    "job_name": "-N",
    "output_file": "-o",
    "error_file": "-e",
    "queue": "-q",
    "project": "-P",
    "array_range": "-t",
    "hold_jid": "-hold_jid",
    "mail_user": "-M",
    "mail_options": "-m",
    "native_specs": "-l",
}


def _build_qsub_parts(opts: QsubOptions) -> list[str]:
    """Build qsub command argument list from options.

    Args:
        opts: The qsub submission options.

    Returns:
        List of command-line argument strings.
    """
    parts: list[str] = ["qsub"]
    for attr, flag in _QSUB_SIMPLE_FLAGS.items():
        val = getattr(opts, attr)
        if val is not None:
            parts.append(f"{flag} {val}")
    if opts.cwd:
        parts.append("-cwd")
    if opts.merge_output:
        parts.append("-j y")
    if opts.pe_name:
        parts.append(f"-pe {opts.pe_name} {opts.pe_slots}")
    if opts.priority is not None:
        parts.append(f"-p {opts.priority}")
    if opts.binary:
        parts.append("-b y")
    if opts.resource_list:
        resources = ",".join(f"{k}={v}" for k, v in opts.resource_list.items())
        parts.append(f"-l {resources}")
    return parts


def _build_qstat_parts(opts: QstatOptions) -> list[str]:
    """Build qstat command argument list from options.

    Args:
        opts: The qstat query options.

    Returns:
        List of command-line argument strings.
    """
    parts: list[str] = ["qstat"]
    if opts.user:
        parts.append(f"-u {opts.user}")
    elif opts.job_id is None:
        parts.append("-u *")
    flag_map = {"full": "-f", "extended": "-ext", "show_resources": "-r"}
    for attr, flag in flag_map.items():
        if getattr(opts, attr):
            parts.append(flag)
    if opts.state_filter:
        parts.append(f"-s {opts.state_filter}")
    if opts.xml:
        parts.append("-xml")
    if opts.job_id and str(opts.job_id).isdigit():
        parts.append(f"-j {opts.job_id}")
    return parts


def sge_exec(
    cmd: str, output_path: Path | None = None, timeout: int = 300
) -> list[str]:
    """Execute an SGE command.

    Args:
        cmd: The command to execute.
        output_path: Optional file to write output to.
        timeout: Timeout in seconds.

    Returns:
        List of output lines.

    Raises:
        SGEError: If the command returns a non-zero exit code.
    """
    proc = subprocess.Popen(  # noqa S603
        [_BASH_PATH, "-c", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
    )
    output_lines = []
    try:
        if output_path:
            output_path.write_text("")
            with output_path.open("a", encoding="utf-8") as f:
                for line in proc.stdout:
                    f.write(line)
                    output_lines.append(line.rstrip())
        else:
            for line in proc.stdout:
                output_lines.append(line.rstrip())
        proc.wait(timeout=timeout)
    finally:
        if proc.stdout:
            proc.stdout.close()
    if proc.returncode != 0:
        raise SGEError(f"Command failed: '{cmd}' returned {proc.returncode}")
    return output_lines


class SGEClient:
    def __init__(
        self,
        sge_root: str | None = None,
        cell: str | None = None,
        config: SGEConfig | None = None,
    ) -> None:
        cfg = config or get_config().sge
        self.sge_root = sge_root or cfg.sge_root or "sge/"
        self.cell = cell or cfg.sge_cell or "default"
        if cfg.source_settings:
            self._source_cmd = cfg.source_settings
        else:
            self._source_cmd = (
                f"source {self.sge_root}/{self.cell}/common/settings.sh"
            )

    def _build_cmd(self, sge_cmd: str) -> str:
        return f"{self._source_cmd};{sge_cmd}"

    def qsub(
        self, script_path: str | Path, options: QsubOptions | None = None
    ) -> int:
        """Submit a job to SGE.

        Args:
            script_path: Path to the job script.
            options: Submission options.

        Returns:
            The job ID assigned by SGE.

        Raises:
            SGEError: If job submission fails.
        """
        opts = options or QsubOptions()
        cmd_parts = _build_qsub_parts(opts)
        cmd_parts.append(str(script_path))
        cmd = self._build_cmd(" ".join(cmd_parts))
        output = sge_exec(cmd)
        for line in output:
            match = re.search(r"Your job (\d+)", line)
            if match:
                return int(match.group(1))
        raise SGEError("Job submission failed - no job ID returned")

    def qstat(self, options: QstatOptions | None = None) -> dict[str, Any]:
        """Query job status from SGE.

        Args:
            options: Query options.

        Returns:
            Dictionary with queue_info and job_info lists.

        Raises:
            SGEError: If the qstat command fails.
        """
        opts = options or QstatOptions()
        cmd_parts = _build_qstat_parts(opts)
        cmd = self._build_cmd(" ".join(cmd_parts))
        try:
            output = sge_exec(cmd)
        except SGEError as e:
            if "no jobs" in str(e).lower():
                return {"queue_info": [], "job_info": []}
            raise
        if opts.xml:
            return self._parse_qstat_xml(output)
        return {"raw": output}

    @staticmethod
    def _parse_qstat_xml(output: list[str]) -> dict[str, Any]:
        """Parse qstat XML output into structured data.

        Args:
            output: Lines of XML output from qstat.

        Returns:
            Dictionary with queue_info and job_info lists.
        """
        xml_str = "\n".join(output)
        data = xmltodict.parse(xml_str)
        result: dict[str, Any] = {"queue_info": [], "job_info": []}
        queue_info = data.get("job_info", {}).get("queue_info", {})
        job_info = data.get("job_info", {}).get("job_info", {})
        if queue_info:
            queue_list = queue_info.get("job_list", [])
            if isinstance(queue_list, dict):
                queue_list = [queue_list]
            result["queue_info"] = (
                [Job.from_dict(j) for j in queue_list] if queue_list else []
            )
        if job_info:
            job_list = job_info.get("job_list", [])
            if isinstance(job_list, dict):
                job_list = [job_list]
            result["job_info"] = (
                [Job.from_dict(j) for j in job_list] if job_list else []
            )
        return result

    def qdel(self, job_id: int | str, *, force: bool = False) -> bool:
        """Delete a job from SGE.

        Args:
            job_id: The job ID(s) to delete.
            force: Whether to force deletion.

        Returns:
            True if deletion was successful.
        """
        job_ids = str(job_id).replace(",", " ")
        cmd_parts = ["qdel"]
        if force:
            cmd_parts.append("-f")
        cmd_parts.append(job_ids)
        cmd = self._build_cmd(" ".join(cmd_parts))
        sge_exec(cmd)
        return True

    def qmod(self, options: QmodOptions | None = None) -> bool:
        """Modify job or queue state in SGE.

        Args:
            options: Modification options.

        Returns:
            True if modification was successful.

        Raises:
            SGEError: If neither job_id nor queue is specified.
        """
        opts = options or QmodOptions()
        cmd_parts = ["qmod"]
        if opts.force:
            cmd_parts.append("-f")
        if opts.clear_error:
            cmd_parts.append("-c")
        if opts.suspend:
            cmd_parts.append("-s")
        elif opts.unsuspend:
            cmd_parts.append("-us")
        elif opts.enable:
            cmd_parts.append("-e")
        elif opts.disable:
            cmd_parts.append("-d")
        if opts.job_id:
            cmd_parts.append(str(opts.job_id))
        elif opts.queue:
            cmd_parts.append(opts.queue)
        else:
            raise SGEError("Either job_id or queue must be specified")
        cmd = self._build_cmd(" ".join(cmd_parts))
        sge_exec(cmd)
        return True

    def qalter(
        self,
        job_id: int,
        priority: int | None = None,
        resource_list: dict[str, str] | None = None,
        *,
        hold: bool = False,
        release: bool = False,
    ) -> bool:
        cmd_parts = [f"qalter -w v {job_id}"]
        if priority is not None:
            cmd_parts.append(f"-p {priority}")
        if resource_list:
            resources = ",".join(f"{k}={v}" for k, v in resource_list.items())
            cmd_parts.append(f"-l {resources}")
        if hold:
            cmd_parts.append(f"-h {job_id}")
        if release:
            cmd_parts.append(f"-r {job_id}")
        cmd = self._build_cmd(" ".join(cmd_parts))
        try:
            sge_exec(cmd)
        except SGEError:
            pass
        return True

    def qhold(self, job_id: int | str) -> bool:
        cmd = self._build_cmd(f"qhold {job_id}")
        sge_exec(cmd)
        return True

    def qrls(self, job_id: int | str) -> bool:
        cmd = self._build_cmd(f"qrls {job_id}")
        sge_exec(cmd)
        return True

    def qhost(self, host_filter: str | None = None) -> list[Host]:
        cmd_parts = ["qhost"]
        if host_filter:
            cmd_parts.append(host_filter)
        cmd = self._build_cmd(" ".join(cmd_parts))
        output = sge_exec(cmd)
        hosts = []
        min_output_lines = 2
        for line in output[min_output_lines:]:
            if not line or line.startswith("="):
                continue
            parts = line.split()
            if len(parts) >= _MIN_HOST_FIELDS:
                hosts.append(Host(hostname=parts[0]))
        return hosts

    def qconf(self, action: str, target: str | None = None) -> str | list[str]:
        cmd_parts = ["qconf", action]
        if target:
            cmd_parts.append(target)
        cmd = self._build_cmd(" ".join(cmd_parts))
        output = sge_exec(cmd)
        return output

    def qacct(
        self, job_id: int | None = None, user: str | None = None
    ) -> dict[str, Any]:
        cmd_parts = ["qacct"]
        if job_id:
            cmd_parts.extend([f"-j {job_id}"])
        if user:
            cmd_parts.extend([f"-o {user}"])
        cmd = self._build_cmd(" ".join(cmd_parts))
        output = sge_exec(cmd)
        return {"raw": output}

    def list_queues(self) -> list[str]:
        result = self.qconf("-sql")
        return result if isinstance(result, list) else [result]

    def get_queue_info(self, queue_name: str) -> dict[str, Any]:
        result = self.qconf(f"-sq {queue_name}")
        return {"config": result}

    def list_hosts(self) -> list[str]:
        result = self.qconf("-sel")
        return result if isinstance(result, list) else [result]

    def list_projects(self) -> list[str]:
        result = self.qconf("-sprjl")
        return result if isinstance(result, list) else [result]

    def list_users(self, acl_name: str) -> list[str]:
        result = self.qconf(f"-su {acl_name}")
        return result if isinstance(result, list) else [result]
