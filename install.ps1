# Run this script as Administrator.
$ErrorActionPreference = "Stop"
$AppName = "FocusLock"
$InstallDir = Join-Path $env:ProgramFiles $AppName
$StartupDir = [Environment]::GetFolderPath("CommonStartup")
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ExePath = Join-Path $InstallDir "FocusLock.exe"
$LaunchScript = Join-Path $InstallDir "launch.vbs"
$Who = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$IcoPath = Join-Path $InstallDir "focuslock.ico"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Get-Process FocusLock -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Copy-Item -Path (Join-Path $PSScriptRoot "FocusLock.exe") -Destination $ExePath -Force
Copy-Item -Path (Join-Path $PSScriptRoot "launch.vbs") -Destination $LaunchScript -Force
$icoSource = Join-Path $PSScriptRoot "assets\focuslock.ico"
if (Test-Path -LiteralPath $icoSource) {
    Copy-Item -Path $icoSource -Destination $IcoPath -Force
}

$oldStartup = Join-Path $StartupDir "FocusLock.lnk"
if (Test-Path -LiteralPath $oldStartup) {
    Remove-Item -LiteralPath $oldStartup -Force
}

foreach ($taskName in @("FocusLock", "FocusLockBackground")) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
}

$principal = New-ScheduledTaskPrincipal `
    -UserId $Who `
    -LogonType Interactive `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$guiAction = New-ScheduledTaskAction -Execute $ExePath -WorkingDirectory $InstallDir
Register-ScheduledTask `
    -TaskName "FocusLock" `
    -Action $guiAction `
    -Principal $principal `
    -Settings $settings `
    -Description "Launch FocusLock with administrator rights without a UAC prompt." `
    -Force | Out-Null

$bgAction = New-ScheduledTaskAction -Execute $ExePath -Argument "--background" -WorkingDirectory $InstallDir
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $Who
Register-ScheduledTask `
    -TaskName "FocusLockBackground" `
    -Action $bgAction `
    -Trigger $logonTrigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Start FocusLock website blocking at sign-in." `
    -Force | Out-Null

$WScriptShell = New-Object -ComObject WScript.Shell
$desktopShortcut = $WScriptShell.CreateShortcut((Join-Path $DesktopDir "FocusLock.lnk"))
$desktopShortcut.TargetPath = "$env:SystemRoot\System32\wscript.exe"
$desktopShortcut.Arguments = "//nologo `"$LaunchScript`""
$desktopShortcut.WorkingDirectory = $InstallDir
$desktopShortcut.WindowStyle = 7
$shortcutIcon = $ExePath
if (Test-Path -LiteralPath $IcoPath) {
    $shortcutIcon = $IcoPath
}
$desktopShortcut.IconLocation = "$shortcutIcon,0"
$desktopShortcut.Description = "FocusLock"
$desktopShortcut.Save()

Write-Host "Installed FocusLock 2.6."
Write-Host "Open it from the desktop shortcut. It should no longer ask for permission each time."
