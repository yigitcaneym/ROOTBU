from __future__ import annotations

from dataclasses import dataclass, field
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable

ENV_NAME = "rootbu_root_env"
CONDA_CHANNEL = "conda-forge"
ROOT_PACKAGE = "root"

STATUS_OK = "OK"
STATUS_INFO = "INFO"
STATUS_WARN = "WARN"
STATUS_ERROR = "ERROR"

Command = list[str]


@dataclass
class ProbeResult:
    returncode: int
    stdout: str = ""
    timed_out: bool = False


@dataclass
class CheckItem:
    name: str
    status: str
    detail: str


@dataclass
class SystemReport:
    os_name: str
    platform_label: str
    checks: list[CheckItem] = field(default_factory=list)
    native_conda: Command | None = None
    native_conda_detail: str = ""
    native_env_exists: bool = False
    native_root_in_env: bool = False
    native_root_available: bool = False
    native_root_command: Command | None = None
    wsl_available: bool = False
    wsl_conda_available: bool = False
    wsl_env_exists: bool = False
    wsl_root_in_env: bool = False
    wsl_root_available: bool = False


@dataclass
class InstallPlan:
    context: str
    messages: list[str]
    commands: list[Command]

    @property
    def has_commands(self) -> bool:
        return bool(self.commands)


@dataclass
class OpenPlan:
    context: str
    messages: list[str]
    command: Command | None

    @property
    def can_open(self) -> bool:
        return self.command is not None


Runner = Callable[[Command, int], ProbeResult]


def windows_creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def run_probe(command: Command, timeout: int = 12) -> ProbeResult:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=windows_creation_flags(),
        )
    except (FileNotFoundError, OSError) as exc:
        return ProbeResult(127, str(exc))
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return ProbeResult(124, output, timed_out=True)

    output = (result.stdout or "") + (result.stderr or "")
    return ProbeResult(result.returncode, output.strip())


def command_to_text(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def first_output_line(output: str) -> str:
    for line in output.splitlines():
        clean = line.strip()
        if clean:
            return clean
    return ""


def parse_conda_env_names(output: str) -> set[str]:
    names: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        first_column = line.split()[0].rstrip("*")
        if first_column and not first_column.startswith(("/", "\\")):
            names.add(first_column)
    return names


def conda_candidates(os_name: str | None = None) -> list[Command]:
    system = os_name or platform.system()
    home = Path.home()
    candidates: list[Command] = []
    path_conda = shutil.which("conda")
    if path_conda:
        candidates.append([path_conda])

    if system == "Windows":
        known_paths = [
            home / "miniconda3" / "Scripts" / "conda.exe",
            home / "miniconda3" / "condabin" / "conda.bat",
            home / "anaconda3" / "Scripts" / "conda.exe",
            home / "anaconda3" / "condabin" / "conda.bat",
            home / "miniforge3" / "Scripts" / "conda.exe",
            home / "mambaforge" / "Scripts" / "conda.exe",
        ]
    else:
        known_paths = [
            home / "miniconda3" / "bin" / "conda",
            home / "anaconda3" / "bin" / "conda",
            home / "miniforge3" / "bin" / "conda",
            home / "mambaforge" / "bin" / "conda",
        ]

    for path in known_paths:
        if path.exists():
            candidates.append([str(path)])

    unique: list[Command] = []
    seen: set[str] = set()
    for command in candidates:
        key = command[0].lower() if system == "Windows" else command[0]
        if key not in seen:
            unique.append(command)
            seen.add(key)
    return unique


def find_native_conda(os_name: str, runner: Runner) -> tuple[Command | None, str]:
    for command in conda_candidates(os_name):
        result = runner(command + ["--version"], 10)
        if result.returncode == 0:
            detail = first_output_line(result.stdout) or command[0]
            return command, detail
    return None, "No conda executable found in PATH or common Miniconda/Anaconda locations."


def check_env_exists(conda_command: Command, runner: Runner) -> bool:
    result = runner(conda_command + ["env", "list"], 15)
    if result.returncode != 0:
        return False
    return ENV_NAME in parse_conda_env_names(result.stdout)


def check_root_in_env(conda_command: Command, runner: Runner) -> bool:
    result = runner(conda_command + ["run", "-n", ENV_NAME, "root", "--version"], 20)
    return result.returncode == 0


def check_direct_root(runner: Runner) -> tuple[bool, Command | None, str]:
    root_path = shutil.which("root")
    if not root_path:
        return False, None, "ROOT was not found in PATH."

    command = [root_path, "--version"]
    result = runner(command, 12)
    if result.returncode == 0:
        return True, [root_path], first_output_line(result.stdout) or root_path
    return False, None, first_output_line(result.stdout) or "ROOT command exists but did not respond cleanly."


def check_wsl_available(runner: Runner) -> bool:
    if not shutil.which("wsl"):
        return False
    status = runner(["wsl", "--status"], 10)
    if status.returncode == 0:
        return True
    distributions = runner(["wsl", "--list", "--quiet"], 10)
    return distributions.returncode == 0


def run_wsl_probe(script: str, runner: Runner, timeout: int = 15) -> ProbeResult:
    return runner(["wsl", "bash", "-lc", script], timeout)


def collect_system_report(runner: Runner = run_probe) -> SystemReport:
    os_name = platform.system()
    platform_label = platform.platform()
    report = SystemReport(os_name=os_name, platform_label=platform_label)

    report.checks.append(CheckItem("Operating system", STATUS_OK, platform_label))

    if os_name == "Windows":
        report.wsl_available = check_wsl_available(runner)
        if report.wsl_available:
            report.checks.append(CheckItem("WSL", STATUS_OK, "WSL command is available."))
        else:
            report.checks.append(
                CheckItem("WSL", STATUS_WARN, "WSL was not detected. ROOTBU will not run wsl --install automatically.")
            )
    else:
        report.checks.append(CheckItem("WSL", STATUS_INFO, f"Not required on {os_name}."))

    native_conda, native_detail = find_native_conda(os_name, runner)
    report.native_conda = native_conda
    report.native_conda_detail = native_detail
    if native_conda:
        report.checks.append(CheckItem("Conda (native)", STATUS_OK, native_detail))
        report.native_env_exists = check_env_exists(native_conda, runner)
        env_detail = f"Project environment {ENV_NAME} exists." if report.native_env_exists else f"{ENV_NAME} does not exist yet."
        report.checks.append(CheckItem("Project env (native)", STATUS_OK if report.native_env_exists else STATUS_INFO, env_detail))
        if report.native_env_exists:
            report.native_root_in_env = check_root_in_env(native_conda, runner)
    else:
        report.checks.append(CheckItem("Conda (native)", STATUS_WARN, native_detail))

    native_root, root_command, root_detail = check_direct_root(runner)
    report.native_root_available = native_root
    report.native_root_command = root_command
    if report.native_root_in_env:
        report.checks.append(CheckItem("ROOT (native)", STATUS_OK, f"ROOT is available in {ENV_NAME}."))
    elif native_root:
        report.checks.append(CheckItem("ROOT (native)", STATUS_OK, root_detail))
    else:
        report.checks.append(CheckItem("ROOT (native)", STATUS_WARN, root_detail))

    if os_name == "Windows" and report.wsl_available:
        wsl_conda = run_wsl_probe("command -v conda >/dev/null 2>&1 && conda --version", runner)
        report.wsl_conda_available = wsl_conda.returncode == 0
        if report.wsl_conda_available:
            report.checks.append(CheckItem("Conda (WSL)", STATUS_OK, first_output_line(wsl_conda.stdout) or "Conda is available in WSL."))
            wsl_env_list = run_wsl_probe("conda env list", runner)
            report.wsl_env_exists = ENV_NAME in parse_conda_env_names(wsl_env_list.stdout) if wsl_env_list.returncode == 0 else False
            env_detail = f"Project environment {ENV_NAME} exists in WSL." if report.wsl_env_exists else f"{ENV_NAME} does not exist in WSL yet."
            report.checks.append(CheckItem("Project env (WSL)", STATUS_OK if report.wsl_env_exists else STATUS_INFO, env_detail))
            if report.wsl_env_exists:
                report.wsl_root_in_env = run_wsl_probe(f"conda run -n {ENV_NAME} root --version", runner, 20).returncode == 0
        else:
            report.checks.append(CheckItem("Conda (WSL)", STATUS_WARN, "Conda was not found inside WSL."))

        wsl_root = run_wsl_probe("command -v root >/dev/null 2>&1 && root --version", runner, 12)
        report.wsl_root_available = wsl_root.returncode == 0
        if report.wsl_root_in_env:
            report.checks.append(CheckItem("ROOT (WSL)", STATUS_OK, f"ROOT is available in WSL environment {ENV_NAME}."))
        elif report.wsl_root_available:
            report.checks.append(CheckItem("ROOT (WSL)", STATUS_OK, first_output_line(wsl_root.stdout) or "ROOT is available in WSL."))
        else:
            report.checks.append(CheckItem("ROOT (WSL)", STATUS_WARN, "ROOT was not found inside WSL."))

    return report


def build_install_plan(report: SystemReport) -> InstallPlan:
    messages: list[str] = [
        f"Installation target environment: {ENV_NAME}",
        "ROOTBU only creates or updates its own conda environment.",
        "Existing conda and ROOT installations are left untouched.",
    ]

    if report.os_name == "Windows":
        messages.append("Windows installs are handled through WSL. ROOTBU will not run wsl --install.")
        if not report.wsl_available:
            messages.append("Install WSL manually first, then run Check System again.")
            return InstallPlan("Windows / WSL", messages, [])
        if not report.wsl_conda_available:
            messages.append("Install Miniconda or Anaconda inside WSL first, then run Check System again.")
            return InstallPlan("Windows / WSL", messages, [])
        if report.wsl_root_in_env:
            messages.append(f"ROOT is already available in WSL environment {ENV_NAME}.")
            return InstallPlan("Windows / WSL", messages, [])
        if report.wsl_env_exists:
            command = ["wsl", "bash", "-lc", f"conda install -y -n {ENV_NAME} -c {CONDA_CHANNEL} {ROOT_PACKAGE}"]
            messages.append(f"{ENV_NAME} exists in WSL; ROOTBU will add ROOT to that project environment.")
        else:
            command = ["wsl", "bash", "-lc", f"conda create -y -n {ENV_NAME} -c {CONDA_CHANNEL} {ROOT_PACKAGE}"]
            messages.append(f"ROOTBU will create the WSL conda environment {ENV_NAME}.")
        return InstallPlan("Windows / WSL", messages, [command])

    if report.os_name not in {"Linux", "Darwin"}:
        messages.append(f"{report.os_name} is not supported by this MVP.")
        return InstallPlan(report.os_name, messages, [])

    if not report.native_conda:
        messages.append("Install Miniconda or Anaconda first, then run Check System again.")
        return InstallPlan(report.os_name, messages, [])

    if report.native_root_in_env:
        messages.append(f"ROOT is already available in {ENV_NAME}.")
        return InstallPlan(report.os_name, messages, [])

    if report.native_env_exists:
        command = report.native_conda + ["install", "-y", "-n", ENV_NAME, "-c", CONDA_CHANNEL, ROOT_PACKAGE]
        messages.append(f"{ENV_NAME} exists; ROOTBU will add ROOT to that project environment.")
    else:
        command = report.native_conda + ["create", "-y", "-n", ENV_NAME, "-c", CONDA_CHANNEL, ROOT_PACKAGE]
        messages.append(f"ROOTBU will create the conda environment {ENV_NAME}.")

    return InstallPlan(report.os_name, messages, [command])


def build_open_plan(report: SystemReport) -> OpenPlan:
    messages: list[str] = []
    if report.os_name == "Windows":
        if report.wsl_root_in_env:
            command = ["wsl", "bash", "-lc", f"conda run -n {ENV_NAME} root"]
            messages.append(f"Opening ROOT from WSL environment {ENV_NAME}.")
            return OpenPlan("Windows / WSL", messages, command)
        if report.wsl_root_available:
            command = ["wsl", "bash", "-lc", "root"]
            messages.append("Opening the existing ROOT command inside WSL.")
            return OpenPlan("Windows / WSL", messages, command)
        messages.append("ROOT is not available in WSL yet.")
        return OpenPlan("Windows / WSL", messages, None)

    if report.native_root_in_env and report.native_conda:
        command = report.native_conda + ["run", "-n", ENV_NAME, "root"]
        messages.append(f"Opening ROOT from conda environment {ENV_NAME}.")
        return OpenPlan(report.os_name, messages, command)

    if report.native_root_available and report.native_root_command:
        messages.append("Opening the existing ROOT command from PATH.")
        return OpenPlan(report.os_name, messages, report.native_root_command)

    messages.append("ROOT is not available yet.")
    return OpenPlan(report.os_name, messages, None)
