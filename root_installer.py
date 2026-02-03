import platform
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

WINDOWS_INSTALL_COMMAND = ["powershell", "-Command", "wsl --install"]
LINUX_INSTALL_SCRIPT = """
set -e
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
~/miniconda3/bin/conda init zsh
~/miniconda3/bin/conda config --set channel_priority strict
~/miniconda3/bin/conda create -y -n root_env -c conda-forge root
~/miniconda3/bin/conda config --env --add channels conda-forge
"""
LINUX_OPEN_ROOT_COMMAND = "source ~/miniconda3/bin/activate root_env && root"


def run_command(command, log_widget, button_to_disable=None, shell=False):
    def worker():
        if button_to_disable:
            button_to_disable.config(state=tk.DISABLED)
        try:
            log_widget.insert(tk.END, f"$ {command if isinstance(command, str) else ' '.join(command)}\n")
            log_widget.see(tk.END)
            result = subprocess.run(
                command,
                shell=shell,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if result.stdout:
                log_widget.insert(tk.END, result.stdout)
        except subprocess.CalledProcessError as exc:
            log_widget.insert(tk.END, f"Command failed with exit code {exc.returncode}.\n")
            if exc.stdout:
                log_widget.insert(tk.END, exc.stdout)
        finally:
            log_widget.insert(tk.END, "\n")
            log_widget.see(tk.END)
            if button_to_disable:
                button_to_disable.config(state=tk.NORMAL)

    threading.Thread(target=worker, daemon=True).start()


def install_windows(log_widget, button):
    if platform.system() != "Windows":
        messagebox.showinfo("Not on Windows", "Windows installation is only available on Windows 10 (19041+) or later.")
        return
    run_command(WINDOWS_INSTALL_COMMAND, log_widget, button)


def install_linux(log_widget, button):
    if platform.system() != "Linux":
        messagebox.showinfo("Not on Linux", "Linux installation is only available on Ubuntu/Linux.")
        return
    run_command(LINUX_INSTALL_SCRIPT, log_widget, button, shell=True)


def open_root_linux(log_widget, button):
    if platform.system() != "Linux":
        messagebox.showinfo("Not on Linux", "ROOT can be launched from Linux after installation.")
        return
    run_command(f"bash -lc '{LINUX_OPEN_ROOT_COMMAND}'", log_widget, button, shell=True)


def main():
    root = tk.Tk()
    root.title("ROOT Installer")
    root.geometry("720x480")

    header = tk.Label(
        root,
        text="ROOT tek-tuş kurulum ve açma aracı",
        font=("Helvetica", 16, "bold"),
    )
    header.pack(pady=12)

    info_text = (
        "Windows 10 (19041+) için: WSL kurulumu PowerShell üzerinden yapılır.\n"
        "Linux için: Miniconda ve ROOT kurulumu yapılır. Terminali kapatıp açmanız gerekir.\n"
        "ROOT'u her açışta: conda activate root_env && root"
    )
    info = tk.Label(root, text=info_text, justify=tk.LEFT)
    info.pack(pady=8)

    button_frame = tk.Frame(root)
    button_frame.pack(pady=8)

    log_widget = tk.Text(root, height=15, width=90)
    log_widget.pack(padx=12, pady=10, fill=tk.BOTH, expand=True)

    windows_button = tk.Button(
        button_frame,
        text="Windows WSL Kurulumu",
        width=25,
        command=lambda: install_windows(log_widget, windows_button),
    )
    windows_button.grid(row=0, column=0, padx=8, pady=4)

    linux_button = tk.Button(
        button_frame,
        text="Linux ROOT Kurulumu",
        width=25,
        command=lambda: install_linux(log_widget, linux_button),
    )
    linux_button.grid(row=0, column=1, padx=8, pady=4)

    open_root_button = tk.Button(
        button_frame,
        text="ROOT'u Aç (Linux)",
        width=25,
        command=lambda: open_root_linux(log_widget, open_root_button),
    )
    open_root_button.grid(row=0, column=2, padx=8, pady=4)

    root.mainloop()


if __name__ == "__main__":
    main()
