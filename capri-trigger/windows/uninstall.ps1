# Removes the Capri USB trigger.
# Run:  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1

Stop-ScheduledTask -TaskName "Capri USB Trigger" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Capri USB Trigger" -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
    Where-Object { $_.CommandLine -like "*CapriTrigger\capri-watch.ps1*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "CapriTrigger") -ErrorAction SilentlyContinue
Write-Host "Capri USB trigger removed."
