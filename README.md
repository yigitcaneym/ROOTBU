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
