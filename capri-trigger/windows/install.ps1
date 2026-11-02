# Installs the Capri USB trigger for the current Windows user. No admin rights needed.
# Run from this folder:   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Optional:               powershell -ExecutionPolicy Bypass -File .\install.ps1 -CapriPath "C:\path\to\Capri.exe"

param([string]$CapriPath = "")

# Stop any watcher that's already running, so the new version takes over
Stop-ScheduledTask -TaskName "Capri USB Trigger" -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*CapriTrigger\capri-watch.ps1*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$dir = Join-Path $env:LOCALAPPDATA "CapriTrigger"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot "capri-watch.ps1") -Destination $dir -Force
$script = Join-Path $dir "capri-watch.ps1"

$taskArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
if ($CapriPath) { $taskArgs += " -CapriPath `"$CapriPath`"" }

$action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs
# Starts at login, and checks every minute so the watcher comes back if anything ever stops it.
# MultipleInstances IgnoreNew means it never runs twice.
$atLogOn  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$everyMin = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
            -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "Capri USB Trigger" -Action $action -Trigger @($atLogOn, $everyMin) `
    -Settings $settings -Description "Starts Capri Desktop when a USB drive with capri.key is plugged in." -Force | Out-Null
Start-ScheduledTask -TaskName "Capri USB Trigger"
Start-Sleep -Seconds 3
$log = Join-Path $dir "log.txt"
if (Test-Path $log) { Write-Host "Watcher log:"; Get-Content $log -Tail 5 | ForEach-Object { Write-Host "  $_" } }

Write-Host "Capri USB trigger installed and running."
Write-Host "Unplug your Capri USB and plug it back in to start her."
Write-Host "Tip: turn off Capri's own 'Start with Windows' switch if you only want the USB to start her."
