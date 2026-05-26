from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import os
import platform
import re
import shlex
import shutil
import subprocess
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Callable, Iterable

ENV_NAME = "rootbu_root_env"
CONDA_CHANNEL = "conda-forge"
ROOT_PACKAGE = "root"
MINIFORGE_INSTALL_DIR = "~/miniforge3"
MINIFORGE_DOWNLOAD_DIR = "~/.rootbu"
MINIFORGE_LINUX_INSTALLER = "Miniforge3-Linux-x86_64.sh"
MINIFORGE_RELEASE_BASE = "https://github.com/conda-forge/miniforge/releases/latest/download"

STATUS_OK = "OK"
STATUS_INFO = "INFO"
STATUS_WARN = "WARN"
STATUS_ERROR = "ERROR"
STATUS_ICONS = {
    STATUS_OK: "✅",
    STATUS_WARN: "⚠️",
    STATUS_ERROR: "❌",
    STATUS_INFO: "ℹ️",
}

ANSI_ESCAPE_RE = re.compile(
    r"(?:"
    r"\x1B\[[0-?]*[ -/]*[@-~]"
    r"|\x1B\][^\x07]*(?:\x07|\x1B\\)"
    r"|\x1B[@-_]"
    r")"
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CONDENSED_SPACE_RE = re.compile(r" {2,}")
SPINNER_ONLY = {"-", "\\", "|", "/", ".", "..", "..."}
CONDENSED_PROGRESS_PREFIXES = (
    "collecting package metadata",
    "solving environment",
    "downloading and extracting packages",
)
WSL_VIRTUALIZATION_ERROR_PATTERNS = (
    "wsl2 is unable to start since virtualization is not enabled",
    "hcs_e_hyperv_not_installed",
    "virtual machine platform",
    "virtualization is turned on",
    "createvm",
)

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
    wsl_distribution_available: bool = False
    wsl_distribution_detail: str = ""
    wsl_conda_available: bool = False
    wsl_conda_command: str = ""
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
    manual_command: str = ""
    opens_terminal: bool = False

    @property
    def can_open(self) -> bool:
        return self.command is not None


@dataclass
class CommandStep:
    label: str
    command: Command


@dataclass
class PrerequisitePlan:
    context: str
    title: str
    needed: bool
    messages: list[str]
    install_name: str = ""
    install_location: str = ""
    download_url: str = ""
    summary_command: str = ""
    requires_admin: bool = False
    opens_elevated: bool = False
    steps: list[CommandStep] = field(default_factory=list)
    manual_commands: list[str] = field(default_factory=list)

    @property
    def can_run(self) -> bool:
        return bool(self.steps)

    @property
    def has_manual_commands(self) -> bool:
        return bool(self.manual_commands)


@dataclass
class SetupGuidance:
    title: str
    messages: list[str]
    commands: list[str] = field(default_factory=list)

    @property
    def has_commands(self) -> bool:
        return bool(self.commands)


@dataclass
class ActionState:
    install_prerequisites_enabled: bool = False
    install_prerequisites_label: str = "Install Prerequisites"
    install_root_enabled: bool = False
    install_root_label: str = "Install ROOT"
    open_root_enabled: bool = False
    open_root_label: str = "Open ROOT"


Runner = Callable[[Command, int], ProbeResult]


def windows_creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def is_windows_admin() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


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


def home_dir_text() -> str:
    return os.environ.get("HOME") or os.path.expanduser("~")


def home_dir() -> Path:
    return Path(home_dir_text())


def native_miniforge_dir() -> Path:
    return home_dir() / "miniforge3"


def command_home_path(os_name: str, *parts: str) -> str:
    if os_name == "Windows":
        return str(PureWindowsPath(home_dir_text(), *parts))
    return str(PurePosixPath(home_dir_text(), *parts))


def native_miniforge_conda_path(os_name: str | None = None) -> str:
    system = os_name or platform.system()
    if system == "Windows":
        return command_home_path(system, "miniforge3", "Scripts", "conda.exe")
    return command_home_path(system, "miniforge3", "bin", "conda")


def status_icon(level: str) -> str:
    return STATUS_ICONS.get(level, "")


def apply_backspaces(text: str) -> str:
    cleaned: list[str] = []
    for char in text:
        if char == "\b":
            if cleaned:
                cleaned.pop()
            continue
        cleaned.append(char)
    return "".join(cleaned)


def is_spinner_artifact(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped in SPINNER_ONLY:
        return True

    lowered = stripped.lower()
    if "done" in lowered or "error" in lowered or "warning" in lowered:
        return False
    return lowered.startswith(CONDENSED_PROGRESS_PREFIXES) and stripped[-1] in "-\\|/"


def clean_command_output_lines(text: str) -> list[str]:
    cleaned_text = ANSI_ESCAPE_RE.sub("", str(text))
    cleaned_text = apply_backspaces(cleaned_text)
    lines: list[str] = []

    for raw_line in cleaned_text.split("\n"):
        segments = raw_line.split("\r")
        visible = next((segment for segment in reversed(segments) if segment.strip()), "")
        visible = CONTROL_CHAR_RE.sub("", visible)
        visible = CONDENSED_SPACE_RE.sub(" ", visible).strip()
        if not visible or is_spinner_artifact(visible):
            continue
        lines.append(visible)

    return lines


def has_wsl_virtualization_error(output: str) -> bool:
    lowered = output.lower()
    return any(pattern in lowered for pattern in WSL_VIRTUALIZATION_ERROR_PATTERNS)


def wsl_virtualization_error_guidance() -> list[str]:
    return [
        "WSL2 could not start because virtualization / Virtual Machine Platform is not available in this Windows environment.",
        "On a physical Windows PC: enable virtualization in BIOS/UEFI and make sure Windows Virtual Machine Platform is enabled.",
        "In a virtual machine such as UTM/Parallels/VMware: WSL2 may require nested virtualization, and it may not be supported or enabled.",
        "Try the same ROOTBU flow on a physical Windows machine if WSL2 cannot start inside the VM.",
    ]


def first_output_line(output: str) -> str:
    for line in output.splitlines():
        clean = line.strip()
        if clean:
            return clean
    return ""


def first_conda_version_line(output: str) -> str:
    for line in output.splitlines():
        clean = line.strip()
        if clean and not clean.startswith("__ROOTBU_CONDA__="):
            return clean
    return ""


def wsl_conda_probe_script() -> str:
    return (
        'if command -v conda >/dev/null 2>&1; then '
        'CONDA_CMD="$(command -v conda)"; '
        'elif [ -x "$HOME/miniforge3/bin/conda" ]; then '
        'CONDA_CMD="$HOME/miniforge3/bin/conda"; '
        'else exit 127; fi; '
        'printf "__ROOTBU_CONDA__=%s\\n" "$CONDA_CMD"; '
        '"$CONDA_CMD" --version'
    )


def parse_wsl_conda_command(output: str) -> str:
    for line in output.splitlines():
        clean = line.strip()
        if clean.startswith("__ROOTBU_CONDA__="):
            return clean.split("=", 1)[1]
    return "conda"


def shell_expr(text: str) -> str:
    if text.startswith("$HOME/"):
        return f'"{text}"'
    return shlex.quote(text)


def wsl_conda_shell_expr(report: SystemReport) -> str:
    return shell_expr(report.wsl_conda_command or "conda")


def user_friendly_platform_label(os_name: str | None = None) -> str:
    system = os_name or platform.system()
    machine = platform.machine() or "unknown architecture"

    if system == "Darwin":
        mac_version = platform.mac_ver()[0] or platform.release()
        return f"macOS / Darwin {mac_version} / {machine}"
    if system == "Linux":
        release = platform.release()
        return f"Linux / {release} / {machine}"
    if system == "Windows":
        release = platform.release()
        version = platform.version()
        detail = f"{release} {version}".strip()
        return f"Windows / {detail} / {machine}"

    return f"{system} / {machine}"


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
    candidates: list[Command] = []
    path_conda = shutil.which("conda")
    if path_conda:
        candidates.append([path_conda])

    candidates.append([native_miniforge_conda_path(system)])

    if system == "Windows":
        known_paths = [
            command_home_path(system, "miniconda3", "Scripts", "conda.exe"),
            command_home_path(system, "miniconda3", "condabin", "conda.bat"),
            command_home_path(system, "anaconda3", "Scripts", "conda.exe"),
            command_home_path(system, "anaconda3", "condabin", "conda.bat"),
            command_home_path(system, "miniforge3", "condabin", "conda.bat"),
            command_home_path(system, "mambaforge", "Scripts", "conda.exe"),
        ]
    else:
        known_paths = [
            command_home_path(system, "miniconda3", "bin", "conda"),
            command_home_path(system, "anaconda3", "bin", "conda"),
            command_home_path(system, "miniforge3", "bin", "conda"),
            command_home_path(system, "mambaforge", "bin", "conda"),
        ]

    for path in known_paths:
        candidates.append([path])

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
    return None, "Conda was not found. ROOTBU cannot install ROOT yet. Install Miniforge or Miniconda first, then restart ROOTBU and run Check System again."


def missing_wsl_conda_message() -> str:
    return "Conda was not found inside WSL. ROOTBU cannot install ROOT yet. Install Miniforge or Miniconda in WSL first, then restart ROOTBU and run Check System again."


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
    if "no installed distributions" in status.stdout.lower():
        return True
    distributions = runner(["wsl", "--list", "--quiet"], 10)
    if distributions.returncode == 0:
        return True
    return "no installed distributions" in distributions.stdout.lower()


def parse_wsl_distribution_names(output: str) -> list[str]:
    names: list[str] = []
    for raw_line in output.splitlines():
        name = raw_line.replace("\x00", "").strip().lstrip("*").strip()
        if not name:
            continue
        lowered = name.lower()
        if "no installed distributions" in lowered or "wsl.exe --install" in lowered:
            continue
        names.append(name)
    return names


def check_wsl_distribution_available(runner: Runner) -> tuple[bool, str]:
    result = runner(["wsl", "--list", "--quiet"], 10)
    names = parse_wsl_distribution_names(result.stdout)
    if result.returncode == 0 and names:
        return True, f"Installed distribution(s): {', '.join(names)}"

    return False, "WSL is installed, but no Linux distribution is installed yet."


def run_wsl_probe(script: str, runner: Runner, timeout: int = 15) -> ProbeResult:
    return runner(["wsl", "bash", "-lc", script], timeout)


def collect_system_report(runner: Runner = run_probe, os_name: str | None = None) -> SystemReport:
    os_name = os_name or platform.system()
    platform_label = user_friendly_platform_label(os_name)
    report = SystemReport(os_name=os_name, platform_label=platform_label)

    report.checks.append(CheckItem("Operating system", STATUS_OK, platform_label))

    if os_name == "Windows":
        report.wsl_available = check_wsl_available(runner)
        if report.wsl_available:
            report.checks.append(CheckItem("WSL", STATUS_OK, "WSL command is available."))
            report.wsl_distribution_available, report.wsl_distribution_detail = check_wsl_distribution_available(runner)
            report.checks.append(
                CheckItem(
                    "WSL distribution",
                    STATUS_OK if report.wsl_distribution_available else STATUS_WARN,
                    report.wsl_distribution_detail,
                )
            )
        else:
            report.checks.append(
                CheckItem("WSL", STATUS_WARN, "WSL was not detected. ROOTBU can run wsl --install after confirmation.")
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
        status = STATUS_INFO if os_name == "Windows" else STATUS_WARN
        detail = "Native conda was not found. ROOTBU uses conda inside WSL for ROOT on Windows." if os_name == "Windows" else native_detail
        report.checks.append(CheckItem("Conda (native)", status, detail))

    native_root, root_command, root_detail = check_direct_root(runner)
    report.native_root_available = native_root
    report.native_root_command = root_command
    if report.native_root_in_env:
        report.checks.append(CheckItem("ROOT (native)", STATUS_OK, f"ROOT is available in {ENV_NAME}."))
    elif native_root:
        report.checks.append(CheckItem("ROOT (native)", STATUS_OK, root_detail))
    else:
        report.checks.append(CheckItem("ROOT (native)", STATUS_WARN, root_detail))

    if os_name == "Windows" and report.wsl_available and report.wsl_distribution_available:
        wsl_conda = run_wsl_probe(wsl_conda_probe_script(), runner)
        report.wsl_conda_available = wsl_conda.returncode == 0
        if report.wsl_conda_available:
            report.wsl_conda_command = parse_wsl_conda_command(wsl_conda.stdout)
            report.checks.append(CheckItem("Conda (WSL)", STATUS_OK, first_conda_version_line(wsl_conda.stdout) or "Conda is available in WSL."))
            wsl_env_list = run_wsl_probe(f"{wsl_conda_shell_expr(report)} env list", runner)
            report.wsl_env_exists = ENV_NAME in parse_conda_env_names(wsl_env_list.stdout) if wsl_env_list.returncode == 0 else False
            env_detail = f"Project environment {ENV_NAME} exists in WSL." if report.wsl_env_exists else f"{ENV_NAME} does not exist in WSL yet."
            report.checks.append(CheckItem("Project env (WSL)", STATUS_OK if report.wsl_env_exists else STATUS_INFO, env_detail))
            if report.wsl_env_exists:
                report.wsl_root_in_env = run_wsl_probe(f"{wsl_conda_shell_expr(report)} run -n {ENV_NAME} root --version", runner, 20).returncode == 0
        else:
            report.checks.append(CheckItem("Conda (WSL)", STATUS_WARN, missing_wsl_conda_message()))

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
        messages.append("Windows installs are handled through WSL. Use Install Prerequisites first if WSL is missing.")
        if not report.wsl_available:
            messages.append("Install WSL first, then run Check System again.")
            return InstallPlan("Windows / WSL", messages, [])
        if not report.wsl_distribution_available:
            messages.append("Install a WSL Linux distribution first, then run Check System again.")
            return InstallPlan("Windows / WSL", messages, [])
        if not report.wsl_conda_available:
            messages.append("Install Miniforge or Miniconda inside WSL first, then run Check System again.")
            return InstallPlan("Windows / WSL", messages, [])
        if report.wsl_root_in_env:
            messages.append(f"ROOT is already available in WSL environment {ENV_NAME}.")
            return InstallPlan("Windows / WSL", messages, [])
        if report.wsl_env_exists:
            command = ["wsl", "bash", "-lc", f"{wsl_conda_shell_expr(report)} install -y -n {ENV_NAME} -c {CONDA_CHANNEL} {ROOT_PACKAGE}"]
            messages.append(f"{ENV_NAME} exists in WSL; ROOTBU will add ROOT to that project environment.")
        else:
            command = ["wsl", "bash", "-lc", f"{wsl_conda_shell_expr(report)} create -y -n {ENV_NAME} -c {CONDA_CHANNEL} {ROOT_PACKAGE}"]
            messages.append(f"ROOTBU will create the WSL conda environment {ENV_NAME}.")
        return InstallPlan("Windows / WSL", messages, [command])

    if report.os_name not in {"Linux", "Darwin"}:
        messages.append(f"{report.os_name} is not supported by this MVP.")
        return InstallPlan(report.os_name, messages, [])

    if not report.native_conda:
        messages.append("Install Miniforge or Miniconda first, then run Check System again.")
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


def shell_quote_path(path: str) -> str:
    if path.startswith("$HOME/"):
        return path
    return shlex.quote(path)


def pure_path_for_command(raw_path: str) -> PurePath:
    expanded = os.path.expanduser(raw_path) if raw_path.startswith("~") else raw_path
    if expanded.startswith("/") or expanded.startswith("$HOME/") or ("/" in expanded and "\\" not in expanded):
        return PurePosixPath(expanded)
    if "\\" in expanded or re.match(r"^[A-Za-z]:[\\/]", expanded):
        return PureWindowsPath(expanded)
    return PurePosixPath(expanded)


def activation_script_from_conda_command(conda_command: Command | None) -> str:
    if not conda_command:
        return "$HOME/miniforge3/bin/activate"

    raw_path = conda_command[0]
    if raw_path == "conda" or raw_path == "conda.exe":
        return "$HOME/miniforge3/bin/activate"

    path = pure_path_for_command(raw_path)
    parent = path.parent
    if parent.name == "condabin":
        return str(parent.parent / "bin" / "activate")
    if parent.name in {"bin", "Scripts"}:
        return str(parent / "activate")

    return "$HOME/miniforge3/bin/activate"


def interactive_conda_root_command(conda_command: Command | None) -> str:
    activate_script = activation_script_from_conda_command(conda_command)
    return f"source {shell_quote_path(activate_script)} {shlex.quote(ENV_NAME)} && root"


def interactive_wsl_conda_root_command() -> str:
    env_name = shlex.quote(ENV_NAME)
    return (
        'if [ -f "$HOME/miniforge3/bin/activate" ]; then '
        f'source "$HOME/miniforge3/bin/activate" {env_name}; '
        'else CONDA_EXE="$(command -v conda)"; '
        f'source "$(dirname "$CONDA_EXE")/activate" {env_name}; '
        "fi; root"
    )


def applescript_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def macos_terminal_command(shell_command: str) -> Command:
    return [
        "osascript",
        "-e",
        f'tell application "Terminal" to do script "{applescript_escape(shell_command)}"',
        "-e",
        'tell application "Terminal" to activate',
    ]


LINUX_TERMINAL_CANDIDATES = ("gnome-terminal", "xterm", "konsole", "x-terminal-emulator")


def find_linux_terminal(terminal_finder: Callable[[str], str | None] = shutil.which) -> str | None:
    for terminal in LINUX_TERMINAL_CANDIDATES:
        path = terminal_finder(terminal)
        if path:
            return path
    return None


def linux_terminal_command(terminal: str, shell_command: str) -> Command:
    interactive_script = f"{shell_command}; exec bash"
    name = Path(terminal).name
    if name == "gnome-terminal":
        return [terminal, "--", "bash", "-lc", interactive_script]
    return [terminal, "-e", "bash", "-lc", interactive_script]


def wsl_terminal_command(shell_command: str) -> Command:
    interactive_script = f"{shell_command}; exec bash"
    return ["cmd.exe", "/c", "start", "ROOTBU ROOT", "wsl.exe", "bash", "-lc", interactive_script]


def build_open_plan(
    report: SystemReport,
    terminal_finder: Callable[[str], str | None] = shutil.which,
) -> OpenPlan:
    messages: list[str] = []
    if report.os_name == "Windows":
        if report.wsl_root_in_env:
            shell_command = interactive_wsl_conda_root_command()
            command = wsl_terminal_command(shell_command)
            messages.append(f"Opening ROOT in a new interactive WSL terminal using {ENV_NAME}.")
            return OpenPlan("Windows / WSL", messages, command, shell_command, True)
        if report.wsl_root_available:
            shell_command = "root"
            command = wsl_terminal_command(shell_command)
            messages.append("Opening the existing ROOT command in a new interactive WSL terminal.")
            return OpenPlan("Windows / WSL", messages, command, shell_command, True)
        messages.append("ROOT is not available in WSL yet.")
        return OpenPlan("Windows / WSL", messages, None)

    if report.native_root_in_env and report.native_conda:
        shell_command = interactive_conda_root_command(report.native_conda)
        if report.os_name == "Darwin":
            messages.append(f"Opening ROOT in Terminal.app using conda environment {ENV_NAME}.")
            return OpenPlan("macOS", messages, macos_terminal_command(shell_command), shell_command, True)
        if report.os_name == "Linux":
            terminal = find_linux_terminal(terminal_finder)
            if terminal:
                messages.append(f"Opening ROOT in {Path(terminal).name} using conda environment {ENV_NAME}.")
                return OpenPlan("Linux", messages, linux_terminal_command(terminal, shell_command), shell_command, True)
            messages.append("No supported terminal emulator was found.")
            messages.append("Run the manual command below in a terminal.")
            return OpenPlan("Linux", messages, None, shell_command)

        messages.append(f"Interactive ROOT launch is not supported on {report.os_name}.")
        return OpenPlan(report.os_name, messages, None, shell_command)

    if report.native_root_available and report.native_root_command:
        shell_command = "root"
        if report.os_name == "Darwin":
            messages.append("Opening the existing ROOT command in Terminal.app.")
            return OpenPlan("macOS", messages, macos_terminal_command(shell_command), shell_command, True)
        if report.os_name == "Linux":
            terminal = find_linux_terminal(terminal_finder)
            if terminal:
                messages.append(f"Opening the existing ROOT command in {Path(terminal).name}.")
                return OpenPlan("Linux", messages, linux_terminal_command(terminal, shell_command), shell_command, True)
            messages.append("No supported terminal emulator was found.")
            messages.append("Run this manual command in a terminal: root")
            return OpenPlan("Linux", messages, None, shell_command)

        messages.append("Opening the existing ROOT command from PATH.")
        return OpenPlan(report.os_name, messages, report.native_root_command, shell_command)

    messages.append("ROOT is not available yet.")
    return OpenPlan(report.os_name, messages, None)


def conda_available_for_root_install(report: SystemReport) -> bool:
    if report.os_name == "Windows":
        return report.wsl_available and report.wsl_distribution_available and report.wsl_conda_available
    return report.native_conda is not None


def root_available_for_open(report: SystemReport) -> bool:
    if report.os_name == "Windows":
        return report.wsl_root_in_env or report.wsl_root_available
    return report.native_root_in_env or report.native_root_available


def root_installed_in_project_env(report: SystemReport) -> bool:
    return report.wsl_root_in_env if report.os_name == "Windows" else report.native_root_in_env


def build_action_state(report: SystemReport | None) -> ActionState:
    if report is None:
        return ActionState()

    prerequisite_plan = build_prerequisite_plan(report)
    prerequisite_enabled = prerequisite_plan.needed and prerequisite_plan.can_run
    if prerequisite_enabled:
        prerequisite_label = "Install Prerequisites"
    elif prerequisite_plan.needed and prerequisite_plan.has_manual_commands:
        prerequisite_label = "Manual Setup Needed"
    else:
        prerequisite_label = "No Prerequisites Needed"

    root_installed = root_installed_in_project_env(report)
    conda_available = conda_available_for_root_install(report)
    open_available = root_available_for_open(report)

    return ActionState(
        install_prerequisites_enabled=prerequisite_enabled,
        install_prerequisites_label=prerequisite_label,
        install_root_enabled=conda_available and not root_installed,
        install_root_label="ROOT Installed" if root_installed else "Install ROOT",
        open_root_enabled=open_available,
        open_root_label="Open ROOT",
    )


def miniforge_installer_name(os_name: str, machine: str | None = None) -> str:
    arch = machine or platform.machine()
    if os_name == "Darwin":
        if arch == "arm64":
            return "Miniforge3-MacOSX-arm64.sh"
        return "Miniforge3-MacOSX-x86_64.sh"
    return MINIFORGE_LINUX_INSTALLER


def miniforge_url(os_name: str, machine: str | None = None) -> str:
    return f"{MINIFORGE_RELEASE_BASE}/{miniforge_installer_name(os_name, machine)}"


def macos_miniforge_commands(machine: str | None = None) -> list[str]:
    installer = miniforge_installer_name("Darwin", machine)
    return [
        f'curl -fsSLo Miniforge3.sh "{miniforge_url("Darwin", machine)}"',
        "bash Miniforge3.sh",
    ]


def linux_miniforge_commands() -> list[str]:
    installer = MINIFORGE_LINUX_INSTALLER
    return [
        f'curl -L -O "{miniforge_url("Linux")}"',
        f"bash {installer}",
    ]


def shell_command(script: str) -> Command:
    return ["bash", "-lc", script]


def wsl_shell_command(script: str) -> Command:
    return ["wsl", "bash", "-lc", script]


def powershell_single_quote(text: str) -> str:
    return text.replace("'", "''")


def elevated_powershell_command(admin_command: str) -> Command:
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$adminCommand = '{powershell_single_quote(admin_command)}'; "
        "$process = Start-Process powershell.exe -Verb RunAs -Wait -PassThru "
        "-ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $adminCommand); "
        "exit $process.ExitCode"
    )
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


def elevated_wsl_install_command(command: str, completion_message: str) -> Command:
    admin_command = (
        f"{command}; "
        'Write-Host ""; '
        f'Write-Host "{completion_message}"; '
        'Read-Host "Press Enter to close this window"'
    )
    return elevated_powershell_command(admin_command)


def build_wsl_install_steps(*, windows_is_admin: bool) -> list[CommandStep]:
    if windows_is_admin:
        return [CommandStep("Installing WSL...", ["wsl", "--install"])]
    message = "WSL installation may require a restart. Please restart Windows if prompted, then reopen ROOTBU and run Check System."
    return [CommandStep("Opening elevated PowerShell for WSL installation...", elevated_wsl_install_command("wsl --install", message))]


def build_wsl_distribution_steps(*, windows_is_admin: bool) -> list[CommandStep]:
    command = "wsl --install -d Ubuntu"
    if windows_is_admin:
        return [CommandStep("Installing Ubuntu WSL distribution...", ["wsl", "--install", "-d", "Ubuntu"])]
    message = "Ubuntu setup may require a restart or first-run username/password setup. Reopen ROOTBU and run Check System afterward."
    return [CommandStep("Opening elevated PowerShell for Ubuntu installation...", elevated_wsl_install_command(command, message))]


def miniforge_download_script(url: str, installer_name: str) -> str:
    return (
        'set -e; '
        'TARGET="$HOME/miniforge3"; '
        'if [ -e "$TARGET" ]; then echo "Install target already exists: $TARGET"; exit 10; fi; '
        'mkdir -p "$HOME/.rootbu"; '
        'echo "Downloading Miniforge..."; '
        f'curl -fsSLo "$HOME/.rootbu/{installer_name}" "{url}"'
    )


def miniforge_install_script(installer_name: str) -> str:
    return (
        'set -e; '
        'TARGET="$HOME/miniforge3"; '
        'if [ -e "$TARGET" ]; then echo "Install target already exists: $TARGET"; exit 10; fi; '
        'echo "Installing Miniforge..."; '
        f'bash "$HOME/.rootbu/{installer_name}" -b -p "$TARGET"'
    )


def build_miniforge_steps(os_name: str, machine: str | None = None, *, inside_wsl: bool = False) -> list[CommandStep]:
    installer_name = miniforge_installer_name("Linux" if inside_wsl else os_name, machine)
    url = miniforge_url("Linux" if inside_wsl else os_name, machine)
    command_builder = wsl_shell_command if inside_wsl else shell_command
    return [
        CommandStep("Downloading Miniforge...", command_builder(miniforge_download_script(url, installer_name))),
        CommandStep("Installing Miniforge...", command_builder(miniforge_install_script(installer_name))),
    ]


def build_prerequisite_plan(
    report: SystemReport,
    *,
    machine: str | None = None,
    native_miniforge_exists: bool | None = None,
    windows_is_admin: bool | None = None,
) -> PrerequisitePlan:
    if report.os_name == "Windows":
        if not report.wsl_available:
            admin = is_windows_admin() if windows_is_admin is None else windows_is_admin
            return PrerequisitePlan(
                context="Windows / WSL",
                title="Install WSL",
                needed=True,
                install_name="Windows Subsystem for Linux (WSL)",
                install_location="Windows system feature",
                summary_command="wsl --install",
                requires_admin=True,
                opens_elevated=not admin,
                messages=[
                    "ROOTBU expects WSL for the ROOT setup flow on Windows.",
                    "ROOTBU can run wsl --install after confirmation.",
                    "WSL installation may require Administrator permission and a Windows restart.",
                    "ROOTBU will not install ROOT in this step.",
                    "After restart, open ROOTBU again and run Check System.",
                ],
                steps=build_wsl_install_steps(windows_is_admin=admin),
                manual_commands=["wsl --install"],
            )

        if not report.wsl_distribution_available:
            admin = is_windows_admin() if windows_is_admin is None else windows_is_admin
            return PrerequisitePlan(
                context="Windows / WSL",
                title="Install Ubuntu",
                needed=True,
                install_name="WSL Linux distribution",
                install_location="Ubuntu inside WSL",
                summary_command="wsl --install -d Ubuntu",
                requires_admin=True,
                opens_elevated=not admin,
                messages=[
                    "WSL is installed, but no Linux distribution is installed yet.",
                    "ROOTBU can install the recommended Ubuntu distribution after confirmation.",
                    "Ubuntu may ask for a Linux username and password on first launch.",
                    "ROOTBU will not install ROOT in this step.",
                    "After Ubuntu setup finishes, reopen ROOTBU and run Check System.",
                ],
                steps=build_wsl_distribution_steps(windows_is_admin=admin),
                manual_commands=["wsl --install -d Ubuntu"],
            )

        if not report.wsl_conda_available:
            return PrerequisitePlan(
                context="Windows / WSL",
                title="Install Miniforge inside WSL",
                needed=True,
                install_name="Miniforge",
                install_location="~/miniforge3 inside the default WSL distribution",
                download_url=miniforge_url("Linux"),
                messages=[
                    "ROOTBU can install Miniforge inside WSL after confirmation.",
                    "The installer target is ~/miniforge3 inside WSL.",
                    "ROOTBU will stop if ~/miniforge3 already exists.",
                    "ROOTBU will not use sudo, remove anything, or install ROOT in this step.",
                ],
                steps=build_miniforge_steps("Linux", inside_wsl=True),
                manual_commands=linux_miniforge_commands(),
            )

        return PrerequisitePlan(
            context="Windows / WSL",
            title="No prerequisites needed",
            needed=False,
            messages=["WSL and conda are available. Use Install ROOT when you are ready."],
        )

    if report.os_name not in {"Darwin", "Linux"}:
        return PrerequisitePlan(
            context=report.os_name,
            title="Unsupported platform",
            needed=False,
            messages=[f"Prerequisite installation is not available for {report.os_name}."],
        )

    if report.native_conda:
        return PrerequisitePlan(
            context=report.os_name,
            title="No prerequisites needed",
            needed=False,
            messages=["Conda is available. Use Install ROOT when you are ready."],
        )

    target_exists = native_miniforge_dir().exists() if native_miniforge_exists is None else native_miniforge_exists
    if target_exists:
        return PrerequisitePlan(
            context=report.os_name,
            title="Miniforge path already exists",
            needed=True,
            install_name="Miniforge",
            install_location=MINIFORGE_INSTALL_DIR,
            messages=[
                "Conda was not found, but ~/miniforge3 already exists.",
                "ROOTBU will not overwrite that folder.",
                "Open a terminal and check whether ~/miniforge3/bin/conda works, or choose a manual repair path.",
                "After fixing conda, restart ROOTBU and run Check System again.",
            ],
        )

    return PrerequisitePlan(
        context="macOS" if report.os_name == "Darwin" else "Linux",
        title="Install Miniforge",
        needed=True,
        install_name="Miniforge",
        install_location=MINIFORGE_INSTALL_DIR,
        download_url=miniforge_url(report.os_name, machine),
        messages=[
            "Conda was not found. ROOTBU can install Miniforge after confirmation.",
            "Miniforge is recommended because it is focused on conda-forge packages.",
            "The installer target is ~/miniforge3.",
            "ROOTBU will stop if ~/miniforge3 already exists.",
            "ROOTBU will not use sudo, remove anything, run conda init, or install ROOT in this step.",
        ],
        steps=build_miniforge_steps(report.os_name, machine),
        manual_commands=macos_miniforge_commands(machine) if report.os_name == "Darwin" else linux_miniforge_commands(),
    )


def conda_restart_messages(scope: str = "terminal") -> list[str]:
    return [
        f"After the installer finishes, close and reopen your {scope}.",
        "If conda is still not found, run conda init in that terminal, close it, reopen it, then run ROOTBU Check System again.",
        "ROOTBU will not run conda init automatically.",
    ]


def native_conda_missing_guidance(report: SystemReport) -> SetupGuidance:
    if report.os_name == "Darwin":
        messages = [
            "Conda was not found. ROOTBU cannot install ROOT yet.",
            "Recommended: install Miniforge because it is focused on conda-forge packages.",
            "Use Install Prerequisites to let ROOTBU download and install Miniforge after confirmation.",
            "Or open Terminal and run these commands manually:",
        ] + conda_restart_messages("terminal")
        return SetupGuidance("Next Steps", messages, macos_miniforge_commands())

    if report.os_name == "Linux":
        messages = [
            "Conda was not found. ROOTBU cannot install ROOT yet.",
            "Recommended: install Miniforge because it is focused on conda-forge packages.",
            "Use Install Prerequisites to let ROOTBU download and install Miniforge after confirmation.",
            "Or open a terminal and run these commands manually:",
        ] + conda_restart_messages("terminal")
        return SetupGuidance("Next Steps", messages, linux_miniforge_commands())

    return SetupGuidance("Next Steps", [])


def build_setup_guidance(report: SystemReport) -> SetupGuidance:
    if report.os_name == "Windows":
        if not report.wsl_available:
            return SetupGuidance(
                "Next Steps",
                [
                    "ROOTBU expects WSL for the ROOT setup flow on Windows.",
                    "WSL was not detected. Use Install Prerequisites to run wsl --install after confirmation.",
                    "The WSL installer may ask for Administrator permission and a Windows restart.",
                    "You can also run this command manually in Administrator PowerShell:",
                    "After restart, open ROOTBU again and run Check System.",
                ],
                ["wsl --install"],
            )

        if not report.wsl_distribution_available:
            return SetupGuidance(
                "Next Steps",
                [
                    "WSL is installed, but no Linux distribution is installed yet.",
                    "Use Install Prerequisites to install the recommended Ubuntu distribution after confirmation.",
                    "Ubuntu may ask for a Linux username and password on first launch.",
                    "You can also run this command manually in Administrator PowerShell:",
                    "After Ubuntu setup finishes, reopen ROOTBU and run Check System.",
                ],
                ["wsl --install -d Ubuntu"],
            )

        if not report.wsl_conda_available:
            messages = [
                "WSL is available, but conda was not found inside WSL.",
                "Use Install Prerequisites to let ROOTBU install Miniforge inside WSL after confirmation.",
                "Recommended: Miniforge is focused on conda-forge packages.",
                "Or run these commands manually inside WSL:",
            ] + conda_restart_messages("WSL terminal")
            return SetupGuidance("Next Steps", messages, linux_miniforge_commands())

        if report.wsl_root_in_env or report.wsl_root_available:
            return SetupGuidance("Next Steps", ["ROOT is already available in WSL. You can use Open ROOT."])

        return SetupGuidance(
            "Next Steps",
            [
                "WSL and conda are available.",
                f"You can use Install ROOT to create or update {ENV_NAME}. ROOTBU will show a dry run and ask before running conda.",
            ],
        )

    if report.os_name in {"Darwin", "Linux"} and not report.native_conda:
        return native_conda_missing_guidance(report)

    if report.native_root_in_env or report.native_root_available:
        return SetupGuidance("Next Steps", ["ROOT is already available. You can use Open ROOT."])

    if report.native_conda:
        return SetupGuidance(
            "Next Steps",
            [
                "Conda is available.",
                f"You can use Install ROOT to create or update {ENV_NAME}. ROOTBU will show a dry run and ask before running conda.",
            ],
        )

    return SetupGuidance("Next Steps", ["No setup guidance is available for this platform yet."])
