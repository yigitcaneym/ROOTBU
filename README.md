# ROOTBU

ROOTBU is a beginner-friendly desktop app for checking a computer, installing CERN ROOT through conda, and opening ROOT with minimal terminal usage.

The current MVP is intentionally conservative: it checks first, shows the planned command, asks for confirmation, and uses a project-specific conda environment named `rootbu_root_env`.

## Supported Platforms

- Windows 10/11 with WSL for the ROOT setup flow.
- Linux with conda, or with permission to install Miniforge into `~/miniforge3`.
- macOS with conda, or with permission to install Miniforge into `~/miniforge3`.

On Windows, ROOTBU uses WSL for ROOT setup. It detects native conda too, but the install flow targets conda inside WSL.

## Run the App

```bash
python -m pip install -r requirements.txt
python main.py
```

You can also launch the same app with `python root_installer.py`.

Use **Check System** first. It logs the detected OS, WSL status, conda status, ROOT availability, and whether the `rootbu_root_env` environment already exists.

If prerequisites are missing, ROOTBU prints a **Next Steps** section and enables **Install Missing Prerequisites** when it can help. ROOTBU always shows a confirmation dialog before running anything.

## If Conda Is Missing

ROOTBU needs conda before it can install ROOT. The recommended beginner path is Miniforge because it is focused on conda-forge packages.

On macOS and Linux, **Install Missing Prerequisites** can download Miniforge and install it to `~/miniforge3` after confirmation. ROOTBU will stop if `~/miniforge3` already exists, will not use `sudo`, will not remove anything, and will not run `conda init` automatically.

After installing Miniforge, run **Check System** again. If `conda` still is not found in a terminal, close and reopen the terminal. If needed, run `conda init`, close and reopen the terminal again, then restart ROOTBU and run **Check System**.

Manual commands are still shown in the log for users who prefer to run the setup themselves.

### macOS Apple Silicon

Open Terminal and run:

```bash
curl -fsSLo Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
bash Miniforge3.sh
```

### macOS Intel

Open Terminal and run:

```bash
curl -fsSLo Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
bash Miniforge3.sh
```

### Linux x86_64

Open a terminal and run:

```bash
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
bash Miniforge3-Linux-x86_64.sh
```

### Windows

ROOTBU expects WSL for the ROOT setup flow on Windows.

If WSL is missing, open PowerShell as Administrator and run:

```powershell
wsl --install
```

Restart Windows if the WSL installer asks you to. Then open ROOTBU and run **Check System** again.

ROOTBU does not run `wsl --install` automatically because WSL installation can require Administrator permission and a restart.

If WSL is present but conda is missing inside WSL, **Install Missing Prerequisites** can install Miniforge inside WSL to `~/miniforge3` after confirmation. ROOTBU will stop if that path already exists and will not use `sudo`.

## Safety Notes

- ROOTBU does not run `wsl --install`.
- ROOTBU can install Miniforge only after showing the exact plan and getting confirmation.
- ROOTBU does not install Miniconda or Anaconda.
- ROOTBU does not remove existing conda environments.
- ROOTBU does not remove existing ROOT installations.
- ROOTBU does not use `sudo`.
- ROOTBU does not run `conda init` automatically.
- **Install Missing Prerequisites** installs only missing prerequisites.
- The **Install ROOT** button performs checks, prints a dry-run command, and asks before running conda.
- Installation is limited to creating or updating `rootbu_root_env`.

## Troubleshooting

- If WSL is missing on Windows, install WSL manually first, then run **Check System** again.
- If conda is missing, run **Check System**, then use **Install Missing Prerequisites** or follow the manual Miniforge commands in the log.
- If conda is installed but not detected, open the app from a terminal where `conda --version` works.
- If `~/miniforge3` already exists but conda is not detected, ROOTBU will not overwrite it. Check whether `~/miniforge3/bin/conda --version` works in a terminal.
- If ROOT is already installed outside ROOTBU, ROOTBU will leave it alone.
- If installation fails, copy the failing command from the log and run it in a terminal to see the full conda error.

## Validation

The validation script checks the Python files and the safe command planning logic. It does not install ROOT.

```bash
python validate_rootbu.py
```
