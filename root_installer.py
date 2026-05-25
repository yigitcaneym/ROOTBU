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
    build_install_plan,
    build_open_plan,
    build_prerequisite_plan,
    build_setup_guidance,
    collect_system_report,
    command_to_text,
    windows_creation_flags,
)


class PrerequisiteConfirmationDialog(ctk.CTkToplevel):
    def __init__(self, parent: "RootBUApp", plan, commands_text: str, platform_label: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.commands_text = commands_text
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
        self._add_summary_row(summary, 0, "Missing prerequisite", "Conda / Miniforge")
        self._add_summary_row(summary, 1, "Target location", plan.install_location or "~/miniforge3")
        self._add_summary_row(summary, 2, "Platform", platform_label)

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
        safety_points = [
            "No sudo",
            "No deletion",
            "No overwrite of existing ~/miniforge3",
            "ROOT will not be installed in this step",
            "conda init will not be run automatically",
        ]
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
            text="Copy Commands",
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
            text="Install Miniforge",
            width=150,
            command=self.confirm,
        )
        install_button.grid(row=0, column=4, padx=(8, 0), sticky="e")

        self.after(100, self.lift)
        self.after(120, self.focus_force)

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
        self.clipboard_append(self.commands_text)
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
            text="CERN ROOT setup with checks, confirmation, and a project conda environment.",
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
        log_frame.grid(row=2, column=0, padx=24, pady=(0, 24), sticky="nsew")
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

        self.log(STATUS_INFO, "Ready. Run Check System before installing ROOT.")
        self.update_prerequisite_button_state()

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

    def log(self, level: str, message: str) -> None:
        self.after(0, self._append_log, level, message)

    def _append_log(self, level: str, message: str) -> None:
        self.log_box.configure(state="normal")
        for line in str(message).splitlines() or [""]:
            self.log_box.insert(tk.END, f"[{level}] {line}\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        for button in self.task_buttons:
            button.configure(state=state)
        self.update_prerequisite_button_state()

    def update_prerequisite_button_state(self) -> None:
        if not self.prerequisite_button:
            return
        if self.is_busy:
            self.prerequisite_button.configure(state="disabled")
            return

        if self.prerequisite_plan is None:
            self.prerequisite_button.configure(text="Install Prerequisites", state="disabled")
            return

        if self.prerequisite_plan.needed:
            self.prerequisite_button.configure(text="Install Prerequisites", state="normal")
        else:
            self.prerequisite_button.configure(text="No Prerequisites Needed", state="disabled")

    def set_prerequisite_plan(self, plan) -> None:
        self.prerequisite_plan = plan
        self.update_prerequisite_button_state()

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
            self.log(STATUS_ERROR, f"{name} failed: {exc}")
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
        report = collect_system_report()
        self._log_report(report)
        guidance = build_setup_guidance(report)
        self._log_guidance(guidance)
        prerequisite_plan = build_prerequisite_plan(report)
        self.after(0, self.set_prerequisite_plan, prerequisite_plan)

    def _install_prerequisites_task(self):
        report = collect_system_report()
        self._log_report(report)
        guidance = build_setup_guidance(report)
        self._log_guidance(guidance)
        plan = build_prerequisite_plan(report)
        self.after(0, self.set_prerequisite_plan, plan)
        self._log_prerequisite_plan(plan)

        if not plan.needed:
            self.log(STATUS_OK, "No missing prerequisites were detected.")
            return

        if not plan.can_run:
            message = self._prerequisite_confirmation_text(plan, manual=True)
            if plan.has_manual_commands:
                copy_commands = self.ask_yes_no(plan.title, message + "\n\nCopy the manual command(s) to the clipboard?")
                if copy_commands:
                    self.copy_text_to_clipboard("\n".join(plan.manual_commands))
                    self.log(STATUS_OK, "Manual prerequisite command(s) copied to the clipboard.")
            else:
                self.show_info(plan.title, message)
            return

        confirmed = self.ask_prerequisite_confirmation(plan)
        if not confirmed:
            self.log(STATUS_WARN, "Prerequisite installation cancelled before running commands.")
            return

        for step in plan.steps:
            self.log(STATUS_INFO, step.label)
            exit_code = self.stream_command(step.command)
            if exit_code != 0:
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.")
                return

        self.log(STATUS_OK, "Finished prerequisite installation.")
        self.log(STATUS_INFO, "Please run Check System again.")
        self.after(0, self.set_prerequisite_plan, None)

    def _install_root_task(self):
        report = collect_system_report()
        self._log_report(report)
        plan = build_install_plan(report)

        self.log(STATUS_INFO, f"Install context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.has_commands:
            self.log(STATUS_WARN, "No installation command will be run.")
            return

        self.log(STATUS_INFO, "Dry run: ROOTBU would run the following command.")
        for command in plan.commands:
            self.log(STATUS_INFO, f"$ {command_to_text(command)}")

        confirmed = self.ask_yes_no(
            "Confirm ROOT installation",
            "ROOTBU will run only the command shown in the log. Continue?",
        )
        if not confirmed:
            self.log(STATUS_WARN, "Installation cancelled before running commands.")
            return

        for command in plan.commands:
            exit_code = self.stream_command(command)
            if exit_code != 0:
                self.log(STATUS_ERROR, f"Command exited with code {exit_code}.")
                return

        self.log(STATUS_OK, "ROOT installation command finished successfully.")

    def _open_root_task(self):
        report = collect_system_report()
        plan = build_open_plan(report)

        self.log(STATUS_INFO, f"Open context: {plan.context}")
        for message in plan.messages:
            self.log(STATUS_INFO, message)

        if not plan.can_open or plan.command is None:
            self.log(STATUS_ERROR, "ROOT is not available. Run Check System or Install ROOT first.")
            return

        self.log(STATUS_INFO, f"$ {command_to_text(plan.command)}")
        try:
            subprocess.Popen(
                plan.command,
                creationflags=windows_creation_flags(),
                start_new_session=True,
            )
        except OSError as exc:
            self.log(STATUS_ERROR, f"Could not open ROOT: {exc}")
            return

        self.log(STATUS_OK, "ROOT launch command started.")

    def _log_report(self, report) -> None:
        self.log(STATUS_INFO, f"Detected OS: {report.platform_label}")
        for item in report.checks:
            self.log(item.status, f"{item.name}: {item.detail}")

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
                    self.log(STATUS_INFO, clean)

        return process.wait()


def main() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = RootBUApp()
    app.mainloop()


if __name__ == "__main__":
    main()
