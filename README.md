# PC Cleaner

A simple Windows utility that cleans junk files, updates device drivers, and updates your installed software — all in one easy app.

## Download

Get the installer from the [Releases page](../../releases): **PC-Cleaner-Setup.exe**.
Run it, follow the wizard, then launch **PC Cleaner** from the Start Menu.
(The app asks for administrator rights because cleaning system folders and installing drivers needs them.)

## Features

- **Dashboard** — Windows version, CPU / RAM / disk usage at a glance.
- **Disk Cleanup** — fast multi-threaded scanner over safe junk locations only:
  Windows Temp, user Temp, Recycle Bin, Prefetch, thumbnail cache,
  Delivery Optimization files, Windows Update cleanup, Chrome & Edge caches.
  Tick categories, see exactly how much you'll free, confirm, then clean.
- **Drivers** — lists every installed driver (name, version, date) via WMI,
  checks Windows Update for driver updates, and installs them for you.
- **Software** — lists available app updates via `winget`, update selected or all.

Safety first: the cleaner only ever touches whitelisted safe folders,
everything destructive asks for confirmation, and every action is logged
in the activity log.

## Build from source (Windows)

```bat
pip install -r requirements.txt
pyinstaller pc_cleaner.spec --noconfirm
```

The app is in `dist\PC Cleaner\`. To build the installer, install
[Inno Setup 6](https://jrsoftware.org/isinfo.php) and run:

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
```

## Automatic builds

Pushing a tag like `v1.0.0` triggers the GitHub Actions workflow
(`.github/workflows/build.yml`), which builds the app with PyInstaller,
packages `PC-Cleaner-Setup.exe` with Inno Setup, and attaches it to a
GitHub Release automatically.
