from __future__ import annotations

import ast
from pathlib import Path

import rootbu_logic as logic


PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_FILES = [
    PROJECT_ROOT / "main.py",
    PROJECT_ROOT / "root_installer.py",
    PROJECT_ROOT / "rootbu_logic.py",
    PROJECT_ROOT / "validate_rootbu.py",
]
APP_FILES = [
    PROJECT_ROOT / "main.py",
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


def main() -> None:
    parse_python_files()
    assert_safe_environment_name()
    assert_conda_env_parser()
    assert_install_plans()
    print("ROOTBU validation passed.")


if __name__ == "__main__":
    main()
