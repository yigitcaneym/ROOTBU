from __future__ import annotations

import ast
from pathlib import Path

import rootbu_logic as logic


PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_FILES = [
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "installer.py",
    PROJECT_ROOT / "root_installer.py",
    PROJECT_ROOT / "rootbu_logic.py",
    PROJECT_ROOT / "validate_rootbu.py",
]
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
    assert any("will not run wsl --install" in message for message in windows_plan.messages)


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

    windows_without_wsl_conda = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
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
    windows_plan = logic.build_prerequisite_plan(windows_without_wsl)
    assert windows_plan.needed
    assert not windows_plan.can_run
    assert windows_plan.manual_commands == ["wsl --install"]

    windows_without_wsl_conda = logic.SystemReport(
        os_name="Windows",
        platform_label="Windows-test",
        wsl_available=True,
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
    assert 'text="Copy Commands"' in source
    assert 'text="Install Miniforge"' in source
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


def main() -> None:
    parse_python_files()
    assert_safe_environment_name()
    assert_conda_env_parser()
    assert_install_plans()
    assert_setup_guidance()
    assert_prerequisite_plans()
    assert_prerequisite_dialog_ui()
    assert_log_formatting()
    print("ROOTBU validation passed.")


if __name__ == "__main__":
    main()
