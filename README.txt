
FOCUSLOCK — WINDOWS WEBSITE BLOCKER

WHAT IT DOES
- Stores your blocked website list persistently.
- If blocking is enabled, it re-applies blocking every time Windows starts.
- Uses the Windows hosts file, so the block applies across normal browsers.
- The app itself can be opened from Program Files after installation.

BUILD THE EXE
1. Install Python 3.11+.
2. Open Command Prompt in this folder.
3. Run:
   pip install pyinstaller
   pyinstaller --noconsole --onefile --name FocusLock focuslock.py
4. Copy dist\FocusLock.exe into this folder.
5. Right-click install.ps1 and run with PowerShell as Administrator.

IMPORTANT
This is version 1. It is a persistent blocker, not an anti-tamper system.
A Windows administrator can still bypass it by editing the hosts file, changing
the configuration, disabling startup, or modifying the program.

For a stronger version, the next step is a Windows Service plus a separate
standard Windows user account for daily use, while keeping the administrator
credentials out of your everyday workflow.
