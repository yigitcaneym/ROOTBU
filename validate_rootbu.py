from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile

import rootbu_logic as logic


PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_FILES = [
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "installer.py",
    PROJECT_ROOT / "root_installer.py",
    PROJECT_ROOT / "rootbu_logic.py",
    PROJECT_ROOT / "validate_rootbu.py",
]
LICENSE_FILE = PROJECT_ROOT / "LICENSE"
BUILD_REQUIREMENTS_FILE = PROJECT_ROOT / "requirements-build.txt"
RELEASE_FILE = PROJECT_ROOT / "RELEASE.md"
BUILD_WORKFLOW_FILE = PROJECT_ROOT / ".github" / "workflows" / "build-distributables.yml"
APP_FILES = [
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "installer.py",
    PROJECT_ROOT / "root_installer.py",
    PROJECT_ROOT / "rootbu_logic.py",
]


def parse_python_files() -> None:
    for path in PYTHON_FILES:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def assert_safe_environment_name() -> None:
    assert logic.ENV_NAME == "rootbu_root_env"
    for path in APP_FILES:
        source = path.read_text(encoding="utf-8")
        assert "-n root_env" not in source
        assert "activate root_env" not in source
        assert "root_env && root" not in source


def assert_conda_env_parser() -> None:
    env_list = """
# conda environments:
#
base                  *  /opt/miniconda3
rootbu_root_env          /opt/miniconda3/envs/rootbu_root_env
analysis                 /opt/miniconda3/envs/analysis
"""
    names = logic.parse_conda_env_names(env_list)
    assert {"base", "rootbu_root_env", "analysis"}.issubset(names)


def assert_install_plans() -> None:
    linux_report = logic.SystemReport(
        os_name="Linux",
        platform_label="Linux-test",
        native_conda=["conda"],
        native_env_exists=False,
    )
    linux_plan = logic.build_install_plan(linux_report)
    assert linux_plan.commands == [["conda", "create", "-y", "-n", "rootbu_root_env", "-c", "conda-forge", "root"]]

    windows_without_wsl = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=False,
    )
    windows_plan = logic.build_install_plan(windows_without_wsl)
    assert windows_plan.commands == []
    assert any("Use Install Prerequisites" in message for message in windows_plan.messages)


def assert_setup_guidance() -> None:
    assert logic.user_friendly_platform_label("Darwin").startswith("macOS / Darwin ")
    assert "macOS-" not in logic.user_friendly_platform_label("Darwin")

    mac_arm_commands = logic.macos_miniforge_commands("arm64")
    assert "Miniforge3-MacOSX-arm64.sh" in mac_arm_commands[0]
    assert mac_arm_commands[1] == "bash Miniforge3.sh"

    mac_intel_commands = logic.macos_miniforge_commands("x86_64")
    assert "Miniforge3-MacOSX-x86_64.sh" in mac_intel_commands[0]

    linux_report = logic.SystemReport(os_name="Linux", platform_label="Linux-test")
    linux_guidance = logic.build_setup_guidance(linux_report)
    assert linux_guidance.has_commands
    assert "Miniforge3-Linux-x86_64.sh" in linux_guidance.commands[0]
    assert any("Conda was not found" in message for message in linux_guidance.messages)

    windows_without_wsl = logic.SystemReport(os_name="Windows", platform_label="Windows-test")
    windows_guidance = logic.build_setup_guidance(windows_without_wsl)
    assert windows_guidance.commands == ["wsl --install"]
    assert any("Administrator" in message for message in windows_guidance.messages)
    assert any("Install Prerequisites" in message for message in windows_guidance.messages)
    assert not any("will not run wsl --install automatically" in message for message in windows_guidance.messages)

    windows_without_wsl_distro = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=False,
    )
    distro_guidance = logic.build_setup_guidance(windows_without_wsl_distro)
    assert distro_guidance.commands == ["wsl --install -d Ubuntu"]
    assert any("Ubuntu" in message for message in distro_guidance.messages)
    assert any("no Linux distribution" in message for message in distro_guidance.messages)

    windows_without_wsl_conda = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=True,
        wsl_conda_available=False,
    )
    wsl_guidance = logic.build_setup_guidance(windows_without_wsl_conda)
    assert "Miniforge3-Linux-x86_64.sh" in wsl_guidance.commands[0]
    assert any("inside WSL" in message for message in wsl_guidance.messages)

    root_available_report = logic.SystemReport(
        os_name="Darwin",
        platform_label="macOS-test",
        native_conda=["conda"],
        native_root_available=True,
    )
    root_available_guidance = logic.build_setup_guidance(root_available_report)
    assert root_available_guidance.commands == []
    assert any("Open ROOT" in message for message in root_available_guidance.messages)

    wsl_root_available_report = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=True,
        wsl_conda_available=True,
        wsl_root_available=True,
    )
    wsl_root_available_guidance = logic.build_setup_guidance(wsl_root_available_report)
    assert wsl_root_available_guidance.commands == []
    assert any("Open ROOT" in message for message in wsl_root_available_guidance.messages)


def command_texts(plan: logic.PrerequisitePlan) -> list[str]:
    return [logic.command_to_text(step.command) for step in plan.steps]


def assert_no_destructive_prerequisite_commands(plan: logic.PrerequisitePlan) -> None:
    for text in command_texts(plan):
        assert "sudo" not in text
        assert " rm " not in text
        assert "rm -rf" not in text
        assert "conda init" not in text


def assert_prerequisite_plans() -> None:
    no_prereq_report = logic.SystemReport(
        os_name="Darwin",
        platform_label="macOS-test",
        native_conda=["conda"],
    )
    no_prereq_plan = logic.build_prerequisite_plan(no_prereq_report)
    assert not no_prereq_plan.needed
    assert not no_prereq_plan.can_run

    mac_arm_report = logic.SystemReport(os_name="Darwin", platform_label="macOS-test")
    mac_arm_plan = logic.build_prerequisite_plan(
        mac_arm_report,
        machine="arm64",
        native_miniforge_exists=False,
    )
    mac_arm_text = "\n".join(command_texts(mac_arm_plan))
    assert mac_arm_plan.needed
    assert mac_arm_plan.can_run
    assert mac_arm_plan.install_location == logic.MINIFORGE_INSTALL_DIR
    assert "Miniforge3-MacOSX-arm64.sh" in mac_arm_text
    assert 'bash "$HOME/.rootbu/Miniforge3-MacOSX-arm64.sh" -b -p "$TARGET"' in mac_arm_text
    assert_no_destructive_prerequisite_commands(mac_arm_plan)

    mac_intel_plan = logic.build_prerequisite_plan(
        mac_arm_report,
        machine="x86_64",
        native_miniforge_exists=False,
    )
    assert "Miniforge3-MacOSX-x86_64.sh" in "\n".join(command_texts(mac_intel_plan))
    assert_no_destructive_prerequisite_commands(mac_intel_plan)

    existing_path_plan = logic.build_prerequisite_plan(
        mac_arm_report,
        machine="arm64",
        native_miniforge_exists=True,
    )
    assert existing_path_plan.needed
    assert not existing_path_plan.can_run
    assert any("will not overwrite" in message for message in existing_path_plan.messages)

    linux_report = logic.SystemReport(os_name="Linux", platform_label="Linux-test")
    linux_plan = logic.build_prerequisite_plan(
        linux_report,
        native_miniforge_exists=False,
    )
    linux_text = "\n".join(command_texts(linux_plan))
    assert linux_plan.needed
    assert linux_plan.can_run
    assert "Miniforge3-Linux-x86_64.sh" in linux_text
    assert 'bash "$HOME/.rootbu/Miniforge3-Linux-x86_64.sh" -b -p "$TARGET"' in linux_text
    assert_no_destructive_prerequisite_commands(linux_plan)

    windows_without_wsl = logic.SystemReport(os_name="Windows", platform_label="Windows-test")
    windows_plan = logic.build_prerequisite_plan(windows_without_wsl, windows_is_admin=False)
    windows_text = "\n".join(command_texts(windows_plan))
    assert windows_plan.needed
    assert windows_plan.can_run
    assert windows_plan.requires_admin
    assert windows_plan.opens_elevated
    assert windows_plan.summary_command == "wsl --install"
    assert windows_plan.manual_commands == ["wsl --install"]
    assert "Start-Process" in windows_text
    assert "wsl --install" in windows_text
    assert_no_destructive_prerequisite_commands(windows_plan)

    windows_admin_plan = logic.build_prerequisite_plan(windows_without_wsl, windows_is_admin=True)
    assert windows_admin_plan.needed
    assert windows_admin_plan.can_run
    assert not windows_admin_plan.opens_elevated
    assert command_texts(windows_admin_plan) == ["wsl --install"]

    windows_without_wsl_distro = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=False,
    )
    distro_plan = logic.build_prerequisite_plan(windows_without_wsl_distro, windows_is_admin=False)
    distro_text = "\n".join(command_texts(distro_plan))
    assert distro_plan.needed
    assert distro_plan.can_run
    assert distro_plan.requires_admin
    assert distro_plan.opens_elevated
    assert distro_plan.install_name == "WSL Linux distribution"
    assert distro_plan.summary_command == "wsl --install -d Ubuntu"
    assert distro_plan.manual_commands == ["wsl --install -d Ubuntu"]
    assert "Start-Process" in distro_text
    assert "wsl --install -d Ubuntu" in distro_text
    assert "Miniforge" not in distro_plan.title
    assert_no_destructive_prerequisite_commands(distro_plan)

    distro_admin_plan = logic.build_prerequisite_plan(windows_without_wsl_distro, windows_is_admin=True)
    assert distro_admin_plan.needed
    assert distro_admin_plan.can_run
    assert not distro_admin_plan.opens_elevated
    assert command_texts(distro_admin_plan) == ["wsl --install -d Ubuntu"]

    windows_without_wsl_conda = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=True,
        wsl_conda_available=False,
    )
    wsl_plan = logic.build_prerequisite_plan(windows_without_wsl_conda)
    wsl_text = "\n".join(command_texts(wsl_plan))
    assert wsl_plan.needed
    assert wsl_plan.can_run
    assert "wsl bash -lc" in wsl_text
    assert "Miniforge3-Linux-x86_64.sh" in wsl_text
    assert_no_destructive_prerequisite_commands(wsl_plan)


def assert_prerequisite_dialog_ui() -> None:
    source = (PROJECT_ROOT / "root_installer.py").read_text(encoding="utf-8")
    assert "class PrerequisiteConfirmationDialog" in source
    assert 'self.title("Install Missing Prerequisite")' in source
    assert 'text="Install Prerequisites"' in source
    assert '"Copy Commands"' in source
    assert '"Copy Command"' in source
    assert '"Install Miniforge"' in source
    assert '"Install WSL"' in source
    assert '"Install Ubuntu"' in source
    assert "WSL Linux distribution" in source
    assert "messagebox.askyesno(\"Confirm prerequisite installation\"" not in source


def assert_log_formatting() -> None:
    assert logic.status_icon(logic.STATUS_OK) == "✅"
    assert logic.status_icon(logic.STATUS_WARN) == "⚠️"
    assert logic.status_icon(logic.STATUS_ERROR) == "❌"
    assert logic.status_icon(logic.STATUS_INFO) == "ℹ️"

    transaction = "\x1b[2KPreparing transaction: ...working...\rPreparing transaction: done\x1b[0m"
    assert logic.clean_command_output_lines(transaction) == ["Preparing transaction: done"]

    spinner = "Solving environment: \\"
    assert logic.clean_command_output_lines(spinner) == []

    backspace_spinner = "Executing transaction: -\b\\\b|\b done"
    assert logic.clean_command_output_lines(backspace_spinner) == ["Executing transaction: done"]

    cursor_sequence = "\x1b[?25lVerifying transaction: done\x1b[?25h"
    assert logic.clean_command_output_lines(cursor_sequence) == ["Verifying transaction: done"]

    source = (PROJECT_ROOT / "root_installer.py").read_text(encoding="utf-8")
    assert "status_icon(level)" in source
    assert "decorate=False" in source


def assert_wsl_virtualization_error_detection() -> None:
    messages = [
        "WSL2 is unable to start since virtualization is not enabled on this machine.",
        "Please ensure the Virtual Machine Platform optional component is enabled.",
        "virtualization is turned on in your computer's firmware settings.",
        "Error code: Wsl/InstallDistro/Service/RegisterDistro/CreateVm/HCS/HCS_E_HYPERV_NOT_INSTALLED",
    ]
    for message in messages:
        assert logic.has_wsl_virtualization_error(message)

    guidance = "\n".join(logic.wsl_virtualization_error_guidance())
    assert "Virtual Machine Platform" in guidance
    assert "UTM/Parallels/VMware" in guidance
    assert "physical Windows machine" in guidance


def assert_wsl_distribution_post_install_ui() -> None:
    source = (PROJECT_ROOT / "root_installer.py").read_text(encoding="utf-8")
    assert "verify_wsl_distribution_after_install" in source
    assert "Ubuntu distribution installation has not completed yet." in source
    assert "wsl -d Ubuntu" in source
    assert "If Windows asked for a restart, restart Windows first." in source
    assert "has_wsl_virtualization_error" in source


def assert_posix_conda_paths_are_platform_neutral() -> None:
    examples = {
        "/Users/example/miniforge3/bin/conda": "/Users/example/miniforge3/bin/activate",
        "/home/example/miniforge3/bin/conda": "/home/example/miniforge3/bin/activate",
        "$HOME/miniforge3/bin/conda": "$HOME/miniforge3/bin/activate",
    }

    for conda_path, activate_path in examples.items():
        assert logic.activation_script_from_conda_command([conda_path]) == activate_path
        command = logic.interactive_conda_root_command([conda_path])
        assert command == f"source {activate_path} rootbu_root_env && root"
        assert "\\Users\\example" not in command
        assert "\\home\\example" not in command


def assert_interactive_open_plans() -> None:
    mac_report = logic.SystemReport(
        os_name="Darwin",
        platform_label="macOS-test",
        native_conda=["/Users/example/miniforge3/bin/conda"],
        native_root_in_env=True,
    )
    mac_plan = logic.build_open_plan(mac_report)
    assert mac_plan.opens_terminal
    assert mac_plan.command is not None
    assert mac_plan.command[0] == "osascript"
    assert "Terminal" in " ".join(mac_plan.command)
    assert "source /Users/example/miniforge3/bin/activate rootbu_root_env && root" == mac_plan.manual_command
    assert "conda run" not in " ".join(mac_plan.command)

    linux_report = logic.SystemReport(
        os_name="Linux",
        platform_label="Linux-test",
        native_conda=["/home/example/miniforge3/bin/conda"],
        native_root_in_env=True,
    )
    linux_plan = logic.build_open_plan(
        linux_report,
        terminal_finder=lambda name: "/usr/bin/xterm" if name == "xterm" else None,
    )
    assert linux_plan.opens_terminal
    assert linux_plan.command == [
        "/usr/bin/xterm",
        "-e",
        "bash",
        "-lc",
        "source /home/example/miniforge3/bin/activate rootbu_root_env && root; exec bash",
    ]

    linux_manual_plan = logic.build_open_plan(linux_report, terminal_finder=lambda _name: None)
    assert not linux_manual_plan.can_open
    assert linux_manual_plan.manual_command == "source /home/example/miniforge3/bin/activate rootbu_root_env && root"
    assert any("No supported terminal emulator" in message for message in linux_manual_plan.messages)

    windows_report = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
        wsl_distribution_available=True,
        wsl_conda_available=True,
        wsl_root_in_env=True,
    )
    windows_plan = logic.build_open_plan(windows_report)
    assert windows_plan.opens_terminal
    assert windows_plan.command is not None
    assert windows_plan.command[:5] == ["cmd.exe", "/c", "start", "ROOTBU ROOT", "wsl.exe"]
    assert "source \"$HOME/miniforge3/bin/activate\" rootbu_root_env" in windows_plan.manual_command
    assert "conda run" not in " ".join(windows_plan.command)


def assert_immediate_miniforge_detection() -> None:
    original_home = os.environ.get("HOME")
    original_which = logic.shutil.which

    def fake_which(_name: str) -> str | None:
        return None

    logic.shutil.which = fake_which
    try:
        os.environ["HOME"] = "/tmp/rootbu-home"
        expected_posix_conda = "/tmp/rootbu-home/miniforge3/bin/conda"

        def posix_runner(command: list[str], _timeout: int) -> logic.ProbeResult:
            if command == [expected_posix_conda, "--version"]:
                return logic.ProbeResult(0, "conda 26.3.2")
            if command == [expected_posix_conda, "env", "list"]:
                return logic.ProbeResult(0, "# conda environments:\nbase  *  /tmp/miniforge3\n")
            return logic.ProbeResult(127, "")

        posix_report = logic.collect_system_report(runner=posix_runner, os_name="Darwin")
        assert posix_report.native_conda == [expected_posix_conda]
        assert posix_report.native_conda_detail == "conda 26.3.2"
        assert any(item.name == "Conda (native)" and item.status == logic.STATUS_OK for item in posix_report.checks)

        windows_home = r"C:\Users\RootBU"
        os.environ["HOME"] = windows_home
        expected_windows_conda = logic.command_home_path("Windows", "miniforge3", "Scripts", "conda.exe")

        def windows_runner(command: list[str], _timeout: int) -> logic.ProbeResult:
            if command == [expected_windows_conda, "--version"]:
                return logic.ProbeResult(0, "conda 26.3.2")
            if command == [expected_windows_conda, "env", "list"]:
                return logic.ProbeResult(0, "# conda environments:\nbase  *  C:\\Users\\RootBU\\miniforge3\n")
            return logic.ProbeResult(127, "")

        windows_report = logic.collect_system_report(runner=windows_runner, os_name="Windows")
        assert windows_report.native_conda == [expected_windows_conda]
        assert windows_report.native_conda_detail == "conda 26.3.2"
        assert any(item.name == "Conda (native)" and item.status == logic.STATUS_OK for item in windows_report.checks)
    finally:
        logic.shutil.which = original_which
        if original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = original_home


def assert_windows_wsl_without_distribution_detection() -> None:
    commands: list[list[str]] = []
    original_which = logic.shutil.which

    def fake_which(name: str) -> str | None:
        if name == "wsl":
            return r"C:\Windows\System32\wsl.exe"
        return None

    def runner(command: list[str], _timeout: int) -> logic.ProbeResult:
        commands.append(command)
        if command == ["wsl", "--status"]:
            return logic.ProbeResult(0, "Default Version: 2")
        if command == ["wsl", "--list", "--quiet"]:
            return logic.ProbeResult(0, "")
        return logic.ProbeResult(127, "")

    logic.shutil.which = fake_which
    try:
        report = logic.collect_system_report(runner=runner, os_name="Windows")
    finally:
        logic.shutil.which = original_which

    assert report.wsl_available
    assert not report.wsl_distribution_available
    assert not report.wsl_conda_available
    assert any(
        item.name == "WSL distribution"
        and item.status == logic.STATUS_WARN
        and "no Linux distribution is installed yet" in item.detail
        for item in report.checks
    )
    assert ["wsl", "--list", "--quiet"] in commands
    assert not any(command[:3] == ["wsl", "bash", "-lc"] for command in commands)


def assert_action_states() -> None:
    original_home = os.environ.get("HOME")
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["HOME"] = tmpdir

        startup = logic.build_action_state(None)
        assert not startup.install_prerequisites_enabled
        assert not startup.install_root_enabled
        assert not startup.open_root_enabled

        missing_conda = logic.SystemReport(os_name="Darwin", platform_label="macOS-test")
        missing_state = logic.build_action_state(missing_conda)
        assert missing_state.install_prerequisites_enabled
        assert not missing_state.install_root_enabled
        assert not missing_state.open_root_enabled

        missing_wsl = logic.SystemReport(os_name="Windows", platform_label="Windows-test", wsl_available=False)
        missing_wsl_state = logic.build_action_state(missing_wsl)
        assert missing_wsl_state.install_prerequisites_enabled
        assert missing_wsl_state.install_prerequisites_label == "Install Prerequisites"
        assert not missing_wsl_state.install_root_enabled
        assert not missing_wsl_state.open_root_enabled

        missing_wsl_distro = logic.SystemReport(
            os_name="Windows",
            platform_label="Windows-test",
            wsl_available=True,
            wsl_distribution_available=False,
        )
        missing_wsl_distro_state = logic.build_action_state(missing_wsl_distro)
        assert missing_wsl_distro_state.install_prerequisites_enabled
        assert missing_wsl_distro_state.install_prerequisites_label == "Install Prerequisites"
        assert not missing_wsl_distro_state.install_root_enabled
        assert not missing_wsl_distro_state.open_root_enabled

        conda_no_root = logic.SystemReport(
            os_name="Darwin",
            platform_label="macOS-test",
            native_conda=["/tmp/miniforge3/bin/conda"],
            native_env_exists=False,
        )
        conda_state = logic.build_action_state(conda_no_root)
        assert not conda_state.install_prerequisites_enabled
        assert conda_state.install_root_enabled
        assert not conda_state.open_root_enabled

        root_in_env = logic.SystemReport(
            os_name="Darwin",
            platform_label="macOS-test",
            native_conda=["/tmp/miniforge3/bin/conda"],
            native_env_exists=True,
            native_root_in_env=True,
        )
        root_state = logic.build_action_state(root_in_env)
        assert not root_state.install_root_enabled
        assert root_state.install_root_label == "ROOT Installed"
        assert root_state.open_root_enabled

    if original_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = original_home


def assert_attribution_and_license() -> None:
    app_source = (PROJECT_ROOT / "root_installer.py").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    license_text = LICENSE_FILE.read_text(encoding="utf-8")

    assert "ROOTBU — Created by Yiğitcan Koç © 2026" in app_source
    assert "Created and maintained by Yiğitcan Koç with AI-assisted development." in app_source
    assert "License: MIT License." in app_source

    assert "## Author" in readme
    assert "ROOTBU was created and is maintained by Yiğitcan Koç with AI-assisted development." in readme
    assert "## Copyright" in readme
    assert "Copyright © 2026 Yiğitcan Koç." in readme
    assert "## License" in readme
    assert "ROOTBU is released under the MIT License." in readme
    assert "## Third-party tools" in readme
    assert "ROOTBU does not bundle CERN ROOT, Miniforge, conda, or WSL." in readme
    assert "remain the property of their respective projects" in readme

    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 Yiğitcan Koç" in license_text


def assert_distributable_build_files() -> None:
    build_requirements = BUILD_REQUIREMENTS_FILE.read_text(encoding="utf-8")
    workflow = BUILD_WORKFLOW_FILE.read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    release = RELEASE_FILE.read_text(encoding="utf-8")

    assert "pyinstaller" in build_requirements.lower()

    assert "workflow_dispatch" in workflow
    assert "pull_request" in workflow
    assert 'branches: ["main"]' in workflow
    assert "windows-latest" in workflow
    assert "macos-latest" in workflow
    assert "pyinstaller --noconfirm --clean --windowed" in workflow
    assert "--onefile --name ROOTBU" in workflow
    assert "--collect-all customtkinter" in workflow
    assert "--hidden-import darkdetect" in workflow
    assert "ROOTBU-windows.exe" in workflow
    assert "ROOTBU-macos.zip" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "gh release create" in workflow
    assert "gh release upload" in workflow
    assert "if: startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "refs/tags/v" in workflow

    assert "## Download ROOTBU" in readme
    assert "ROOTBU-windows.exe" in readme
    assert "ROOTBU-macos.zip" in readme
    assert "SmartScreen" in readme
    assert "Gatekeeper" in readme
    assert "does not bundle CERN ROOT, Miniforge, conda, WSL, Ubuntu, or any external installer" in readme
    assert "Build Distributables" in readme
    assert "PR into `main` builds test artifacts without creating a GitHub Release" in readme
    assert "RELEASE.md" in readme

    assert "ROOTBU Release Checklist" in release
    assert "Build Distributables" in release
    assert "workflow_dispatch" in release
    assert "PR into `main` for test artifacts" in release
    assert "does not create or update a GitHub Release" in release
    assert "v0.1.0" in release
    assert "unsigned" in release


def main() -> None:
    parse_python_files()
    assert_safe_environment_name()
    assert_conda_env_parser()
    assert_install_plans()
    assert_setup_guidance()
    assert_prerequisite_plans()
    assert_prerequisite_dialog_ui()
    assert_log_formatting()
    assert_wsl_virtualization_error_detection()
    assert_wsl_distribution_post_install_ui()
    assert_posix_conda_paths_are_platform_neutral()
    assert_interactive_open_plans()
    assert_immediate_miniforge_detection()
    assert_windows_wsl_without_distribution_detection()
    assert_action_states()
    assert_attribution_and_license()
    assert_distributable_build_files()
    print("ROOTBU validation passed.")


if __name__ == "__main__":
    main()
