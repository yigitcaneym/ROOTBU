# ROOTBU Release Checklist

Use this checklist when preparing a GitHub Release with downloadable ROOTBU builds.

## Before Building

- Update README or release notes if user-facing behavior changed.
- Run validation locally:

```bash
python -B validate_rootbu.py
python -m py_compile main.py installer.py root_installer.py rootbu_logic.py validate_rootbu.py
```

- Confirm ROOTBU still does not bundle CERN ROOT, Miniforge, conda, WSL, Ubuntu, or external installers.

## Build Artifacts

- Trigger the **Build Distributables** workflow manually from GitHub Actions, open or update a PR into `main` for test artifacts, or push a tag such as `v0.1.0` for release artifacts.
- The workflow builds:
  - `ROOTBU-windows` containing `ROOTBU-windows.exe`
  - `ROOTBU-macos` containing `ROOTBU-macos.zip`
- Distributable builds include the ROOTBU app icon, bundled only into the ROOTBU executable/app.
- Download both artifacts and smoke test them on clean Windows and macOS machines when possible.

## GitHub Release

- For a tag like `v0.1.0`, the workflow creates or updates a GitHub Release and attaches the built artifacts.
- For pull request builds, the workflow uploads test artifacts only and does not create or update a GitHub Release.
- If you build manually with `workflow_dispatch`, create a GitHub Release manually and attach:
  - `ROOTBU-windows.exe`
  - `ROOTBU-macos.zip`

## Known Warnings

- Windows builds are unsigned and may show Microsoft Defender SmartScreen warnings.
- macOS builds are unsigned and not notarized, so Gatekeeper may warn that "Apple could not verify ROOTBU is free of malware."
- ROOTBU still asks before installing prerequisites and does not install ROOT automatically.
- If WSL Miniforge setup fails with `Could not create directory: ''`, open Ubuntu once, finish username/password setup, rerun **Check System**, and confirm WSL has enough disk space. ROOTBU does not use `sudo` or overwrite `~/miniforge3`.
- If WSL user detection fails even though Ubuntu opens normally, run `wsl -d Ubuntu --exec bash -lc 'whoami; id -un; echo HOME=$HOME; pwd'`. A `pwd` under `/mnt/c` is normal when launching ROOTBU from a Windows folder.

## Opening Unsigned macOS Builds

For `ROOTBU-macos.zip` artifacts downloaded from this repository's own GitHub Actions or Releases:

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
