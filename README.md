# ROOTBU

ROOTBU is a beginner-friendly desktop app for checking a computer, installing CERN ROOT through conda, and opening ROOT with minimal terminal usage.

The current MVP is intentionally conservative: it checks first, shows the planned command, asks for confirmation, and uses a project-specific conda environment named `rootbu_root_env`.

## Supported Platforms

- Windows 10/11 with WSL for the ROOT setup flow.
- Linux with conda, or with permission to install Miniforge into `~/miniforge3`.
- macOS with conda, or with permission to install Miniforge into `~/miniforge3`.

On Windows, ROOTBU uses WSL for ROOT setup. It detects native conda too, but the install flow targets conda inside WSL.

## Download ROOTBU

Normal users can download ROOTBU from the GitHub Releases page once release assets are published.

- Windows: download `ROOTBU-windows.exe` and double-click it.
- macOS: download `ROOTBU-macos.zip`, unzip it, and open `ROOTBU.app`.

The Windows `.exe` may show Microsoft Defender SmartScreen warnings because ROOTBU is unsigned. The macOS app may show Gatekeeper warnings because ROOTBU is unsigned and not notarized.

### macOS unsigned build note

`ROOTBU.app` is currently unsigned and not notarized. macOS may show: "Apple could not verify ROOTBU is free of malware."

For artifacts downloaded from this repository's own GitHub Actions or Releases, users can open it with either option below.

Option A - Finder:

- Unzip `ROOTBU-macos.zip`.
- Control-click or right-click `ROOTBU.app`.
- Choose **Open**.
- Click **Open** again if macOS asks.

Option B - Terminal:

```bash
xattr -dr com.apple.quarantine /path/to/ROOTBU.app
open /path/to/ROOTBU.app
```

ROOTBU does not bundle CERN ROOT, Miniforge, conda, WSL, Ubuntu, or any external installer. It bundles only the ROOTBU Python app and UI dependencies. ROOTBU still asks before installing prerequisites.

## Run from Source

```bash
python -m pip install -r requirements.txt
python main.py
```

You can also launch the same app with `python root_installer.py`.

Use **Check System** first. It logs the detected OS, WSL status, conda status, ROOT availability, and whether the `rootbu_root_env` environment already exists.

If prerequisites are missing, ROOTBU prints a **Next Steps** section and enables **Install Prerequisites** when it can help. ROOTBU always shows a confirmation dialog before running anything.

## Build Distributables

Distributable builds are made with PyInstaller through GitHub Actions.

- Manual build: run the **Build Distributables** workflow from the GitHub Actions tab.
- Pull request build: opening or updating a PR into `main` builds test artifacts without creating a GitHub Release.
- Release build: push a tag such as `v0.1.0`; the workflow builds Windows and macOS artifacts and attaches them to a GitHub Release.
- Artifacts:
  - `ROOTBU-windows` contains `ROOTBU-windows.exe`.
  - `ROOTBU-macos` contains `ROOTBU-macos.zip`.
- Distributable builds include the ROOTBU app icon, bundled only into the ROOTBU executable/app.

For release steps and smoke testing notes, see [RELEASE.md](RELEASE.md).

## If Conda Is Missing

ROOTBU needs conda before it can install ROOT. The recommended beginner path is Miniforge because it is focused on conda-forge packages.

On macOS and Linux, **Install Prerequisites** can download Miniforge and install it to `~/miniforge3` after confirmation. ROOTBU will stop if `~/miniforge3` already exists, will not use `sudo`, will not remove anything, and will not run `conda init` automatically.

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

If WSL is missing, **Install Prerequisites** can run the WSL installer after showing a confirmation dialog:

```powershell
wsl --install
```

If ROOTBU is not already running as Administrator, it may ask Windows to open an elevated PowerShell window. The WSL installer may require Administrator permission and a restart. ROOTBU does not restart Windows automatically.

You can still copy the command and run it manually in Administrator PowerShell. Restart Windows if the WSL installer asks you to. Then open ROOTBU and run **Check System** again.

If WSL is installed but no Linux distribution is installed yet, **Install Prerequisites** can install the recommended Ubuntu distribution after confirmation:

```powershell
wsl --install -d Ubuntu
```

Ubuntu may ask for a Linux username and password on first launch. Finish that setup, then reopen ROOTBU and run **Check System** again.

If WSL is present but conda is missing inside WSL, **Install Prerequisites** can install Miniforge inside WSL to `~/miniforge3` after confirmation. ROOTBU will stop if that path already exists and will not use `sudo`.

## Safety Notes

- ROOTBU runs `wsl --install` only after confirmation, and does not restart Windows automatically.
- ROOTBU installs an Ubuntu WSL distribution only after confirmation, and does not continue to Miniforge until a distribution exists.
- ROOTBU can install Miniforge only after showing the exact plan and getting confirmation.
- ROOTBU does not install Miniconda or Anaconda.
- ROOTBU does not remove existing conda environments.
- ROOTBU does not remove existing ROOT installations.
- ROOTBU does not use `sudo`.
- ROOTBU does not run `conda init` automatically.
- **Install Prerequisites** installs only missing prerequisites.
- The **Install ROOT** button performs checks, prints a dry-run command, and asks before running conda.
- Installation is limited to creating or updating `rootbu_root_env`.

## Troubleshooting

- If WSL is missing on Windows, use **Install Prerequisites** or run `wsl --install` manually in Administrator PowerShell, then run **Check System** again.
- If WSL is installed but no Linux distribution exists, use **Install Prerequisites** or run `wsl --install -d Ubuntu` manually, finish Ubuntu first-run setup, then run **Check System** again.
- If conda is missing, run **Check System**, then use **Install Prerequisites** or follow the manual Miniforge commands in the log.
- If conda is installed but not detected, open the app from a terminal where `conda --version` works.
- If `~/miniforge3` already exists but conda is not detected, ROOTBU will not overwrite it. Check whether `~/miniforge3/bin/conda --version` works in a terminal.
- If ROOT is already installed outside ROOTBU, ROOTBU will leave it alone.
- If installation fails, copy the failing command from the log and run it in a terminal to see the full conda error.

### WSL2 virtualization errors on Windows VMs

If Ubuntu installation fails with `HCS_E_HYPERV_NOT_INSTALLED`, or says WSL2 is unable to start because virtualization is not enabled, the Windows environment cannot start WSL2. Make sure Windows Virtual Machine Platform is enabled.

On UTM, Parallels, VMware, or other virtual machines, WSL2 may require nested virtualization and it may not be supported or enabled. A physical Windows machine is recommended for full Windows ROOTBU testing.

### Windows/WSL Miniforge install errors

If Miniforge inside WSL fails with `Could not create directory: ''`, open Ubuntu once and finish the username/password first-run setup. Then reopen ROOTBU and run **Check System** again.

Also check that WSL has enough disk space. ROOTBU does not use `sudo` and does not overwrite an existing `~/miniforge3` directory.

## Validation

The validation script checks the Python files and the safe command planning logic. It does not install ROOT.

```bash
python validate_rootbu.py
```

## Author

ROOTBU was created and is maintained by Yiğitcan Koç with AI-assisted development.

## Copyright

Copyright © 2026 Yiğitcan Koç.

## License

ROOTBU is released under the MIT License.

## Third-party tools

ROOTBU does not bundle CERN ROOT, Miniforge, conda, or WSL. It only guides or runs installer commands after user confirmation. CERN ROOT, Miniforge, conda, and WSL remain the property of their respective projects.
