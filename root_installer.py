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
    build_setup_guidance,
    collect_system_report,
    command_to_text,
    windows_creation_flags,
)


class RootBUApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("ROOTBU")
        self.geometry("900x620")
        self.minsize(760, 520)
        self.is_busy = False
        self.task_buttons: list[ctk.CTkButton] = []
        self.suggested_commands: list[str] = []
        self.copy_button: ctk.CTkButton | None = None

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
        self.copy_button = self._add_copy_button(actions, 3)

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
        self.update_copy_button_state()

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

    def _add_copy_button(self, parent: ctk.CTkFrame, column: int) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text="Copy Suggested Commands",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.copy_suggested_commands,
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
        self.update_copy_button_state()

    def update_copy_button_state(self) -> None:
        if not self.copy_button:
            return
        state = "normal" if self.suggested_commands and not self.is_busy else "disabled"
        self.copy_button.configure(state=state)

    def set_suggested_commands(self, commands: list[str]) -> None:
        self.suggested_commands = commands
        self.update_copy_button_state()

    def copy_suggested_commands(self) -> None:
        if not self.suggested_commands:
            self.log(STATUS_WARN, "No suggested commands are available to copy yet.")
            return

        self.clipboard_clear()
        self.clipboard_append("\n".join(self.suggested_commands))
        self.log(STATUS_OK, "Suggested command(s) copied to the clipboard.")

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

    def _check_system_task(self):
        report = collect_system_report()
        self._log_report(report)
        guidance = build_setup_guidance(report)
        self._log_guidance(guidance)

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
        self.after(0, self.set_suggested_commands, guidance.commands)
        self.log(STATUS_INFO, guidance.title)
        for message in guidance.messages:
            self.log(STATUS_INFO, message)
        if guidance.commands:
            self.log(STATUS_INFO, "Suggested command(s):")
            for command in guidance.commands:
                self.log(STATUS_INFO, f"$ {command}")

    def ask_yes_no(self, title: str, message: str) -> bool:
        done = threading.Event()
        answer = {"value": False}

        def ask() -> None:
            answer["value"] = bool(messagebox.askyesno(title, message, parent=self))
            done.set()

        self.after(0, ask)
        done.wait()
        return answer["value"]

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
