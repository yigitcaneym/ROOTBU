from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from rootbu_logic import (
    STATUS_ERROR,
    STATUS_INFO,
    STATUS_OK,
    STATUS_WARN,
    build_action_state,
    build_install_plan,
    build_open_plan,
    build_prerequisite_plan,
    build_setup_guidance,
    clean_command_output_lines,
    collect_system_report,
    command_to_text,
    status_icon,
    windows_creation_flags,
)

APP_FOOTER_TEXT = "ROOTBU — Created by Yiğitcan Koç © 2026"
ABOUT_TEXT = "\n".join(
    [
        "ROOTBU",
        "A beginner-friendly CERN ROOT installer.",
        "Created and maintained by Yiğitcan Koç with AI-assisted development.",
        "Copyright © 2026 Yiğitcan Koç.",
        "License: MIT License.",
    ]
)


class PrerequisiteConfirmationDialog(ctk.CTkToplevel):
    def __init__(self, parent: "RootBUApp", plan, commands_text: str, platform_label: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.commands_text = commands_text
        self.copy_text = plan.summary_command or commands_text
        self.result = False

        self.title("Install Missing Prerequisite")
        self.geometry("760x640")
        self.minsize(680, 560)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Install Missing Prerequisite",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, padx=22, pady=(20, 8), sticky="ew")

        summary = ctk.CTkFrame(self)
        summary.grid(row=1, column=0, padx=22, pady=(0, 12), sticky="ew")
        summary.grid_columnconfigure(1, weight=1)
        for row_index, (label_text, value_text) in enumerate(self.summary_rows(plan, platform_label)):
            self._add_summary_row(summary, row_index, label_text, value_text)

        safety = ctk.CTkFrame(self)
        safety.grid(row=2, column=0, padx=22, pady=(0, 12), sticky="ew")
        safety.grid_columnconfigure((0, 1), weight=1)
        safety_title = ctk.CTkLabel(
            safety,
            text="Safety",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        safety_title.grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 4), sticky="ew")
        safety_points = self.safety_points(plan)
        for index, point in enumerate(safety_points):
            label = ctk.CTkLabel(safety, text=f"- {point}", anchor="w", justify="left")
            label.grid(row=1 + index // 2, column=index % 2, padx=14, pady=2, sticky="ew")

        preview = ctk.CTkFrame(self)
        preview.grid(row=3, column=0, padx=22, pady=(0, 12), sticky="nsew")
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)

        preview_label = ctk.CTkLabel(
            preview,
            text="Command Preview",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        preview_label.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew")

        command_box = ctk.CTkTextbox(
            preview,
            wrap="word",
            font=ctk.CTkFont(family="Menlo", size=12),
            height=170,
        )
        command_box.grid(row=1, column=0, padx=14, pady=(4, 14), sticky="nsew")
        command_box.insert(tk.END, commands_text)
        command_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, padx=22, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="",
            text_color=("gray30", "gray75"),
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        copy_button = ctk.CTkButton(
            footer,
            text="Copy Command" if self.is_single_windows_command_plan(plan) else "Copy Commands",
            width=140,
            command=self.copy_commands,
        )
        copy_button.grid(row=0, column=2, padx=(8, 0), sticky="e")

        cancel_button = ctk.CTkButton(
            footer,
            text="Cancel",
            width=110,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.cancel,
        )
        cancel_button.grid(row=0, column=3, padx=(8, 0), sticky="e")

        install_button = ctk.CTkButton(
            footer,
            text=self.install_button_label(plan),
            width=150,
            command=self.confirm,
        )
        install_button.grid(row=0, column=4, padx=(8, 0), sticky="e")

        self.after(100, self.lift)
        self.after(120, self.focus_force)

    def is_wsl_plan(self, plan) -> bool:
        return plan.summary_command == "wsl --install"

    def is_wsl_distribution_plan(self, plan) -> bool:
        return plan.summary_command == "wsl --install -d Ubuntu"

    def is_single_windows_command_plan(self, plan) -> bool:
        return self.is_wsl_plan(plan) or self.is_wsl_distribution_plan(plan)

    def install_button_label(self, plan) -> str:
        if self.is_wsl_plan(plan):
            return "Install WSL"
        if self.is_wsl_distribution_plan(plan):
            return "Install Ubuntu"
        return "Install Miniforge"

    def summary_rows(self, plan, platform_label: str) -> list[tuple[str, str]]:
        if self.is_wsl_plan(plan):
            return [
                ("Missing prerequisite", "Windows Subsystem for Linux (WSL)"),
                ("Command", plan.summary_command),
                ("Platform", platform_label),
            ]
        if self.is_wsl_distribution_plan(plan):
            return [
                ("Missing prerequisite", "WSL Linux distribution"),
                ("Recommended distribution", "Ubuntu"),
                ("Command", plan.summary_command),
            ]

        return [
            ("Missing prerequisite", "Conda / Miniforge"),
            ("Target location", plan.install_location or "~/miniforge3"),
            ("Platform", platform_label),
        ]

    def safety_points(self, plan) -> list[str]:
        if self.is_wsl_plan(plan):
            return [
                "This may require Administrator permission",
                "This may require a Windows restart",
                "ROOTBU will not install ROOT in this step",
                "After restart, open ROOTBU again and run Check System",
            ]
        if self.is_wsl_distribution_plan(plan):
            return [
                "This may require a restart",
                "Ubuntu may ask for a Linux username/password on first launch",
                "ROOTBU will not install ROOT in this step",
                "After Ubuntu setup finishes, reopen ROOTBU and run Check System",
            ]

        return [
            "No sudo",
            "No deletion",
            "No overwrite of existing ~/miniforge3",
            "ROOT will not be installed in this step",
            "conda init will not be run automatically",
        ]

    def _add_summary_row(self, parent: ctk.CTkFrame, row: int, label_text: str, value_text: str) -> None:
        label = ctk.CTkLabel(
            parent,
            text=label_text,
            text_color=("gray30", "gray75"),
            anchor="w",
        )
        label.grid(row=row, column=0, padx=(14, 12), pady=(10 if row == 0 else 4, 10 if row == 2 else 4), sticky="w")

        value = ctk.CTkLabel(
            parent,
            text=value_text,
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            justify="left",
        )
        value.grid(row=row, column=1, padx=(0, 14), pady=(10 if row == 0 else 4, 10 if row == 2 else 4), sticky="ew")

    def copy_commands(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.copy_text)
        self.status_label.configure(text="Commands copied.")

    def cancel(self) -> None:
        self.result = False
        self.destroy()

    def confirm(self) -> None:
        self.result = True
        self.destroy()


class RootBUApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("ROOTBU")
        self.geometry("900x620")
        self.minsize(760, 520)
        self.is_busy = False
        self.current_report = None
        self.task_buttons: list[ctk.CTkButton] = []
        self.prerequisite_plan = None
        self.prerequisite_button: ctk.CTkButton | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(22, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="ROOTBU",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew")

        subtitle = ctk.CTkLabel(
            header,
            text="A beginner-friendly way to install, check, and open CERN ROOT.",
            font=ctk.CTkFont(size=14),
            text_color=("gray25", "gray75"),
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        actions = ctk.CTkFrame(self)
        actions.grid(row=1, column=0, padx=24, pady=(6, 14), sticky="ew")
        actions.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="actions")

        self.check_button = self._add_task_button(actions, 0, "Check System", self.check_system)
        self.install_button = self._add_task_button(actions, 1, "Install ROOT", self.install_root)
        self.open_button = self._add_task_button(actions, 2, "Open ROOT", self.open_root)
        self.prerequisite_button = self._add_prerequisite_button(actions, 3)

        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, padx=24, pady=(0, 10), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_label = ctk.CTkLabel(
            log_frame,
            text="Log",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        log_label.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew")

        self.log_box = ctk.CTkTextbox(
            log_frame,
            wrap="word",
            font=ctk.CTkFont(family="Menlo", size=12),
        )
        self.log_box.grid(row=1, column=0, padx=14, pady=(4, 14), sticky="nsew")
        self.log_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, padx=24, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        footer_label = ctk.CTkLabel(
            footer,
            text=APP_FOOTER_TEXT,
            font=ctk.CTkFont(size=12),
            text_color=("gray35", "gray65"),
            anchor="w",
        )
        footer_label.grid(row=0, column=0, sticky="ew")

        about_button = ctk.CTkButton(
            footer,
            text="About",
            width=86,
            height=30,
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            command=self.show_about,
        )
        about_button.grid(row=0, column=1, padx=(12, 0), sticky="e")

        self.log(STATUS_INFO, "Ready. Run Check System before installing ROOT.")
        self.update_action_states()

    def _add_task_button(self, parent: ctk.CTkFrame, column: int, text: str, command) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=command,
        )
        button.grid(row=0, column=column, padx=8, pady=12, sticky="ew")
        self.task_buttons.append(button)
        return button

    def _add_prerequisite_button(self, parent: ctk.CTkFrame, column: int) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text="Install Prerequisites",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.install_prerequisites,
        )
        button.grid(row=0, column=column, padx=8, pady=12, sticky="ew")
        return button

    def log(self, level: str, message: str, *, decorate: bool = False) -> None:
        self.after(0, self._append_log, level, message, decorate)

    def _append_log(self, level: str, message: str, decorate: bool = False) -> None:
        lines = clean_command_output_lines(message)
        if not lines:
            return

        icon = status_icon(level) if decorate else ""
        suffix = f" {icon}" if icon else ""
        self.log_box.configure(state="normal")
        for line in lines:
            self.log_box.insert(tk.END, f"[{level}] {line}{suffix}\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        self.update_action_states()

    def update_action_states(self) -> None:
        if self.is_busy:
            for button in self.task_buttons:
                button.configure(state="disabled")
            if self.prerequisite_button:
                self.prerequisite_button.configure(state="disabled")
            return

        self.check_button.configure(state="normal")
        state = build_action_state(self.current_report)
        self.install_button.configure(
            text=state.install_root_label,
            state="normal" if state.install_root_enabled else "disabled",
        )
        self.open_button.configure(
            text=state.open_root_label,
            state="normal" if state.open_root_enabled else "disabled",
        )

        if self.prerequisite_button:
            self.prerequisite_button.configure(
                text=state.install_prerequisites_label,
                state="normal" if state.install_prerequisites_enabled else "disabled",
            )

    def set_current_report(self, report) -> None:
        self.current_report = report
        self.prerequisite_plan = build_prerequisite_plan(report)
        self.update_action_states()

    def run_task(self, name: str, target) -> None:
        if self.is_busy:
            self.log(STATUS_WARN, "A task is already running.")
            return

        self.set_busy(True)
        self.log(STATUS_INFO, f"Starting: {name}")
        thread = threading.Thread(target=self._task_wrapper, args=(name, target), daemon=True)
        thread.start()

    def _task_wrapper(self, name: str, target) -> None:
        try:
            target()
        except Exception as exc:
            self.log(STATUS_ERROR, f"{name} failed: {exc}", decorate=True)
        finally:
            self.log(STATUS_INFO, f"Finished: {name}")
            self.after(0, self.set_busy, False)

    def check_system(self) -> None:
        self.run_task("Check System", self._check_system_task)

    def install_root(self) -> None:
        self.run_task("Install ROOT", self._install_root_task)

    def open_root(self) -> None:
        self.run_task("Open ROOT", self._open_root_task)

    def install_prerequisites(self) -> None:
        self.run_task("Install Prerequisites", self._install_prerequisites_task)

    def _check_system_task(self):
        self.refresh_system_state()

    def refresh_system_state(self):
        report = collect_system_report()
        self._log_report(report)
        guidance = build_setup_guidance(report)
        self._log_guidance(guidance)
        self.after(0, self.set_current_report, report)
        return report

    def _install_prerequisites_task(self):
        report = self.refresh_system_state()
        plan = build_prerequisite_plan(report)
        self._log_prerequisite_plan(plan)

        if not plan.needed:
            self.log(STATUS_OK, "No missing prerequisites were detected.", decorate=True)
            return

        if not plan.can_run:
            message = self._prerequisite_confirmation_text(plan, manual=True)
            if plan.has_manual_commands:
                copy_commands = self.ask_yes_no(plan.title, message + "\n\nCopy the manual command(s) to the clipboard?")
                if copy_commands:
                    self.copy_text_to_clipboard("\n".join(plan.manual_commands))
                    self.log(STATUS_OK, "Manual prerequisite command(s) copied to the clipboard.", decorate=True)
            else:
                self.show_info(plan.title, message)
            return

        confirmed = self.ask_prerequisite_confirmation(plan)
        if not confirmed:
            self.log(STATUS_WARN, "Prerequisite installation cancelled before running commands.", decorate=True)
            return

        for step in plan.steps:
            self.log(STATUS_INFO, step.label)
            exit_code = self.stream_command(step.command)
            if exit_code != 0:
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.", decorate=True)
                return

        self.log(STATUS_OK, "Finished prerequisite installation.", decorate=True)
        if plan.summary_command == "wsl --install":
            self.log(
                STATUS_INFO,
                "WSL installation may require a restart. Please restart Windows if prompted, then reopen ROOTBU and run Check System.",
            )
        if plan.summary_command == "wsl --install -d Ubuntu":
            self.log(
                STATUS_INFO,
                "Ubuntu setup may require a restart or first-run username/password setup. Finish Ubuntu setup, then reopen ROOTBU and run Check System.",
            )
        self.log(STATUS_INFO, "Refreshing Check System after prerequisite installation.")
        self.refresh_system_state()

    def _install_root_task(self):
        report = collect_system_report()
        self._log_report(report)
        self.after(0, self.set_current_report, report)
        plan = build_install_plan(report)

        self.log(STATUS_INFO, f"Install context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.has_commands:
            if report.os_name == "Windows":
                conda_missing = not report.wsl_conda_available
            else:
                conda_missing = report.native_conda is None
            if conda_missing:
                self.log(STATUS_WARN, "Install ROOT is disabled until conda is detected. Run Check System or Install Prerequisites first.", decorate=True)
            else:
                self.log(STATUS_WARN, "No installation command will be run.", decorate=True)
            return

        self.log(STATUS_INFO, "Dry run: ROOTBU would run the following command.")
        for command in plan.commands:
            self.log(STATUS_INFO, f"$ {command_to_text(command)}")

        confirmed = self.ask_yes_no(
            "Confirm ROOT installation",
            "ROOTBU will run only the command shown in the log. Continue?",
        )
        if not confirmed:
            self.log(STATUS_WARN, "Installation cancelled before running commands.", decorate=True)
            return

        for command in plan.commands:
            exit_code = self.stream_command(command)
            if exit_code != 0:
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.", decorate=True)
                return

        self.log(STATUS_OK, "ROOT installation command finished successfully.", decorate=True)
        self.log(STATUS_INFO, "Refreshing Check System after ROOT installation.")
        self.refresh_system_state()

    def _open_root_task(self):
        report = collect_system_report()
        self.after(0, self.set_current_report, report)
        plan = build_open_plan(report)

        self.log(STATUS_INFO, f"Open context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.can_open or plan.command is None:
            if plan.manual_command:
                self.log(STATUS_WARN, "ROOTBU could not find a terminal launcher for this platform.", decorate=True)
                self.log(STATUS_INFO, f"Manual command: {plan.manual_command}")
                return
            self.log(STATUS_ERROR, "ROOT is not available. Run Check System or Install ROOT first.", decorate=True)
            return

        if plan.manual_command:
            self.log(STATUS_INFO, f"Interactive ROOT command: {plan.manual_command}")
        self.log(STATUS_INFO, f"Launcher command: {command_to_text(plan.command)}")
        try:
            subprocess.Popen(
                plan.command,
                creationflags=windows_creation_flags(),
                start_new_session=True,
            )
        except OSError as exc:
            self.log(STATUS_ERROR, f"Could not open ROOT: {exc}", decorate=True)
            return

        self.log(STATUS_OK, "Interactive ROOT terminal launch command started.", decorate=True)

    def _log_report(self, report) -> None:
        self.log(STATUS_INFO, f"Detected OS: {report.platform_label}", decorate=True)
        for item in report.checks:
            self.log(item.status, f"{item.name}: {item.detail}", decorate=True)

    def _log_guidance(self, guidance) -> None:
        self.log(STATUS_INFO, guidance.title)
        for message in guidance.messages:
            self.log(STATUS_INFO, message)
        if guidance.commands:
            self.log(STATUS_INFO, "Suggested command(s):")
            for command in guidance.commands:
                self.log(STATUS_INFO, f"$ {command}")

    def _log_prerequisite_plan(self, plan) -> None:
        self.log(STATUS_INFO, plan.title)
        for message in plan.messages:
            self.log(STATUS_INFO, message)
        if plan.manual_commands and not plan.can_run:
            self.log(STATUS_INFO, "Manual command(s):")
            for command in plan.manual_commands:
                self.log(STATUS_INFO, f"$ {command}")
        if plan.can_run:
            self.log(STATUS_INFO, "Prerequisite command(s) ROOTBU will run after confirmation:")
            for step in plan.steps:
                self.log(STATUS_INFO, f"{step.label} {command_to_text(step.command)}")

    def _prerequisite_confirmation_text(self, plan, manual: bool = False) -> str:
        lines = [
            f"Prerequisite: {plan.install_name or plan.title}",
            f"Where: {plan.install_location or plan.context}",
        ]
        if plan.download_url:
            lines.append(f"Download: {plan.download_url}")
        lines.extend(
            [
                "",
                "Safety:",
                "- ROOTBU will not use sudo.",
                "- ROOTBU will not remove anything.",
                "- ROOTBU will not overwrite an existing conda installation.",
                "- ROOTBU will not install ROOT in this step.",
                "- ROOTBU will not run conda init automatically.",
            ]
        )
        if manual:
            lines.append("")
            lines.append("ROOTBU will not run this system-level prerequisite automatically.")
            if plan.manual_commands:
                lines.append("Manual command(s):")
                lines.extend(f"$ {command}" for command in plan.manual_commands)
            return "\n".join(lines)

        lines.append("")
        lines.append("ROOTBU will run these command(s):")
        for step in plan.steps:
            lines.append(f"$ {command_to_text(step.command)}")
        lines.append("")
        lines.append("Continue?")
        return "\n".join(lines)

    def prerequisite_commands_text(self, plan) -> str:
        return "\n".join(command_to_text(step.command) for step in plan.steps)

    def prerequisite_platform_label(self, plan) -> str:
        if plan.context == "Windows / WSL":
            if plan.summary_command == "wsl --install":
                return "Windows"
            if plan.summary_command == "wsl --install -d Ubuntu":
                return "Windows / WSL"
            return "WSL"
        if plan.context == "Linux":
            return "Linux"
        if plan.context == "macOS":
            if "MacOSX-arm64" in plan.download_url:
                return "macOS Apple Silicon"
            if "MacOSX-x86_64" in plan.download_url:
                return "macOS Intel"
            return "macOS"
        return plan.context

    def ask_prerequisite_confirmation(self, plan) -> bool:
        done = threading.Event()
        answer = {"value": False}

        def ask() -> None:
            dialog = PrerequisiteConfirmationDialog(
                self,
                plan,
                self.prerequisite_commands_text(plan),
                self.prerequisite_platform_label(plan),
            )

            def finish() -> None:
                answer["value"] = bool(dialog.result)
                done.set()

            dialog.bind("<Destroy>", lambda event: finish() if event.widget is dialog and not done.is_set() else None)

        self.after(0, ask)
        done.wait()
        return answer["value"]

    def ask_yes_no(self, title: str, message: str) -> bool:
        done = threading.Event()
        answer = {"value": False}

        def ask() -> None:
            answer["value"] = bool(messagebox.askyesno(title, message, parent=self))
            done.set()

        self.after(0, ask)
        done.wait()
        return answer["value"]

    def show_info(self, title: str, message: str) -> None:
        done = threading.Event()

        def show() -> None:
            messagebox.showinfo(title, message, parent=self)
            done.set()

        self.after(0, show)
        done.wait()

    def show_about(self) -> None:
        messagebox.showinfo("About ROOTBU", ABOUT_TEXT, parent=self)

    def copy_text_to_clipboard(self, text: str) -> None:
        done = threading.Event()

        def copy() -> None:
            self.clipboard_clear()
            self.clipboard_append(text)
            done.set()

        self.after(0, copy)
        done.wait()

    def stream_command(self, command: list[str]) -> int:
        self.log(STATUS_INFO, f"Running: {command_to_text(command)}")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=windows_creation_flags(),
        )

        if process.stdout:
            for line in process.stdout:
                clean = line.rstrip()
                if clean:
                    self.log(STATUS_INFO, clean, decorate=False)

        return process.wait()


def main() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = RootBUApp()
    app.mainloop()


if __name__ == "__main__":
    main()
