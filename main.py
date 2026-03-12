import customtkinter as ctk
import threading
from installer import run_installation

class RootSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ROOT Easy Setup")
        self.geometry("600x400")

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)

        # Top frame for button
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        self.top_frame.grid_columnconfigure(0, weight=1)
        self.top_frame.grid_rowconfigure(0, weight=1)

        self.install_button = ctk.CTkButton(
            self.top_frame,
            text="Install and Setup ROOT",
            command=self.start_installation,
            font=ctk.CTkFont(size=20, weight="bold"),
            height=60
        )
        self.install_button.grid(row=0, column=0, padx=20, pady=20)

        # Bottom frame for log text
        self.log_textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.log_textbox.insert(ctk.END, "Welcome to ROOT Easy Setup.\nPress 'Install and Setup ROOT' to begin...\n")
        self.log_textbox.configure(state="disabled")

    def log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert(ctk.END, f"{message}\n")
        self.log_textbox.see(ctk.END)
        self.log_textbox.configure(state="disabled")

    def start_installation(self):
        self.install_button.configure(state="disabled")
        self.log("Starting installation process...")
        threading.Thread(target=self._run_installation_thread, daemon=True).start()

    def _run_installation_thread(self):
        try:
            for line in run_installation():
                # Use after to schedule GUI updates from the background thread safely
                self.after(0, self.log, line)
        except Exception as e:
            self.after(0, self.log, f"Error: {str(e)}")
        finally:
            self.after(0, self.log, "Installation thread finished.")
            self.after(0, lambda: self.install_button.configure(state="normal"))

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app = RootSetupApp()
    app.mainloop()
