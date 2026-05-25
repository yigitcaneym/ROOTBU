# ROOTBU

ROOTBU is a beginner-friendly desktop app for checking a computer, installing CERN ROOT through conda, and opening ROOT with minimal terminal usage.

The current MVP is intentionally conservative: it checks first, shows the planned command, asks for confirmation, and uses a project-specific conda environment named `rootbu_root_env`.

## Supported Platforms

- Windows 10/11 with WSL already installed.
- Linux with an existing Miniconda, Anaconda, Miniforge, or Mambaforge installation.
- macOS with an existing Miniconda, Anaconda, Miniforge, or Mambaforge installation.

On Windows, ROOTBU uses WSL for ROOT setup. It detects native conda too, but the install flow targets conda inside WSL.

## Run the App

```bash
python -m pip install -r requirements.txt
python main.py
```

You can also launch the same app with `python root_installer.py`.

Use **Check System** first. It logs the detected OS, WSL status, conda status, ROOT availability, and whether the `rootbu_root_env` environment already exists.

If prerequisites are missing, ROOTBU prints a **Next Steps** section with manual commands. The app does not run these prerequisite installers for you.

## If Conda Is Missing

ROOTBU needs conda before it can install ROOT. The recommended beginner path is Miniforge because it is focused on conda-forge packages.

After installing Miniforge, close and reopen your terminal. If `conda` still is not found, run `conda init`, close and reopen the terminal again, then restart ROOTBU and run **Check System**.

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

If WSL is present but conda is missing inside WSL, open your Ubuntu/WSL terminal and use the Linux x86_64 Miniforge commands above.

## Safety Notes

- ROOTBU does not run `wsl --install`.
- ROOTBU does not install Miniconda or Anaconda.
- ROOTBU does not remove existing conda environments.
- ROOTBU does not remove existing ROOT installations.
- The **Install ROOT** button performs checks, prints a dry-run command, and asks before running conda.
- Installation is limited to creating or updating `rootbu_root_env`.

## Troubleshooting

- If WSL is missing on Windows, install WSL manually first, then run **Check System** again.
- If conda is missing, install Miniconda, Anaconda, Miniforge, or Mambaforge manually first.
- If conda is installed but not detected, open the app from a terminal where `conda --version` works.
- If ROOT is already installed outside ROOTBU, ROOTBU will leave it alone.
- If installation fails, copy the failing command from the log and run it in a terminal to see the full conda error.

## Validation

The validation script checks the Python files and the safe command planning logic. It does not install ROOT.

```bash
python validate_rootbu.py
```
