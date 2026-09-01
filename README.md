# FocusLock

Windows website blocker with lock mode. Blocks selected sites through the hosts file so it applies across browsers.

## Download for Windows

1. Open the latest **[Release](https://github.com/neerajjoshi-github/FocusLock/releases/latest)**.
2. Download `FocusLock-Windows.zip`.
3. Extract the zip, then right-click `install.ps1` and run it in PowerShell **as Administrator**.

After install, open FocusLock from the desktop shortcut. It should not ask for permission every time.

You can also download `FocusLock.exe` and run it directly. The zip install adds the shortcut and avoids a permission prompt on every launch.

## Features

- Block popular platforms and custom domains
- Enable blocking persistently across reboots
- Lock mode: sites stay blocked until a chosen time
- While locked, you can still add and enable more sites

## Build from source

Requires Python 3.11+.

```
pip install -r requirements.txt
pyinstaller --noconfirm FocusLock.spec
```

Copy `dist\FocusLock.exe` into this folder, then run `install.ps1` as Administrator.
