from __future__ import annotations

from rootbu_logic import build_install_plan, collect_system_report, command_to_text


def run_installation():
    """Compatibility dry run for older callers of installer.run_installation."""
    report = collect_system_report()
    yield "ROOTBU compatibility installer is running in check-only mode."

    for item in report.checks:
        yield f"[{item.status}] {item.name}: {item.detail}"

    plan = build_install_plan(report)
    for message in plan.messages:
        yield message

    if not plan.has_commands:
        yield "No installation command is planned."
        return

    yield "Dry run only. Open the ROOTBU app and confirm Install ROOT to run:"
    for command in plan.commands:
        yield f"$ {command_to_text(command)}"
