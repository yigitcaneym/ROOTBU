"""Headless end-to-end driver for CI.

Drives the exact plan chain the ROOTBU GUI uses — collect_system_report →
build_prerequisite_plan / build_install_plan → execute the planned commands —
until ROOT is installed and verified inside WSL 2, without any UI. Exit codes:
0 = ROOT verified, 78 = blocked by a required Windows restart (neutral on a
CI runner), anything else = failure.
"""

from __future__ import annotations

import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rootbu_logic as logic

MAX_ITERATIONS = 8
RESTART_BLOCKED_EXIT = 78


def run_command(command) -> tuple[int, str]:
    print(f"+ {logic.command_to_text(command)}", flush=True)
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=logic.windows_creation_flags(),
    )
    output = logic.normalize_wsl_output((process.stdout or "") + (process.stderr or ""))
    for line in logic.clean_command_output_lines(output):
        print(f"  | {line}", flush=True)
    return process.returncode, output


def print_report(report) -> None:
    for item in report.checks:
        print(f"[{item.status}] {item.name}: {item.detail}", flush=True)


def verify_root(report) -> int:
    distro = report.wsl_distribution_name or "Ubuntu"
    print("== ROOT is reported installed — verifying inside WSL", flush=True)
    verify_script = (
        "source ~/miniforge3/etc/profile.d/conda.sh && "
        f"conda activate {logic.ENV_NAME} && "
        "root -l -b -q -e 'printf(\"ROOT_E2E_OK %s\\n\", gROOT->GetVersion());'"
    )
    code, output = run_command(logic.wsl_shell_command(verify_script, distro))
    # ROOT uses the value of the -e expression as its exit code (printf
    # returns the number of characters written), so the marker in the output
    # is the success signal, not the exit code.
    if "ROOT_E2E_OK" in output:
        print(f"E2E RESULT: SUCCESS — ROOT runs inside WSL 2 (verify exit code {code})", flush=True)
        return 0
    print(f"E2E RESULT: FAILURE — verification exited {code} without the marker", flush=True)
    return 1


def main() -> int:
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n===== iteration {iteration}: system scan =====", flush=True)
        report = logic.collect_system_report()
        print_report(report)

        plan = logic.build_prerequisite_plan(report)
        state = logic.build_action_state(report)

        if plan.needed and plan.can_run:
            print(f"== prerequisite plan: {plan.title}", flush=True)
            for step in plan.steps:
                print(f":: {step.label}", flush=True)
                code, output = run_command(step.command)
                if code == 3010 or logic.has_wsl_restart_required_marker(output):
                    print("BLOCKED: a Windows restart is required — cannot continue on this runner", flush=True)
                    return RESTART_BLOCKED_EXIT
                if code != 0:
                    if logic.has_wsl_kernel_update_error(output):
                        print("DETECTED: WSL 2 kernel update error", flush=True)
                    if logic.has_wsl_virtualization_error(output):
                        print("DETECTED: virtualization unavailable on this runner", flush=True)
                    print(f"FAILED: step exited with {code}", flush=True)
                    return 1
            continue

        if plan.needed and not plan.can_run:
            print(f"BLOCKED: manual prerequisite required — {plan.title}", flush=True)
            for message in plan.messages:
                print(f"  {message}", flush=True)
            return 1

        if state.install_root_enabled:
            install_plan = logic.build_install_plan(report)
            print("== install plan: ROOT via conda-forge", flush=True)
            for command in install_plan.commands:
                code, _ = run_command(command)
                if code != 0:
                    print(f"FAILED: ROOT install exited with {code}", flush=True)
                    return 1
            continue

        if state.open_root_enabled:
            return verify_root(report)

        print("FAILED: no runnable action from this state", flush=True)
        return 1

    print("FAILED: iteration limit reached without ROOT", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
