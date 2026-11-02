# Installs the Capri USB trigger for the current Windows user. No admin rights needed.
# Run from this folder:   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Optional:               powershell -ExecutionPolicy Bypass -File .\install.ps1 -CapriPath "C:\path\to\Capri.exe"

param([string]$CapriPath = "")

$dir = Join-Path $env:LOCALAPPDATA "CapriTrigger"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot "capri-watch.ps1") -Destination $dir -Force
$script = Join-Path $dir "capri-watch.ps1"

$taskArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
if ($CapriPath) { $taskArgs += " -CapriPath `"$CapriPath`"" }

$action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Capri USB Trigger" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Starts Capri Desktop when a USB drive with capri.key is plugged in." -Force | Out-Null
Start-ScheduledTask -TaskName "Capri USB Trigger"

Write-Host "Capri USB trigger installed and running."
Write-Host "Copy capri.key (from the usb folder) to the top folder of your USB drive, then plug it in."
Write-Host "Tip: turn off Capri's own 'Start with Windows' switch if you only want the USB to start her."
