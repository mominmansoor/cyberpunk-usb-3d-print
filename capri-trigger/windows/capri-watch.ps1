# Capri USB trigger for Windows.
# Waits for a drive to be plugged in. If the drive has capri.key in its top folder,
# it starts Capri Desktop (unless Capri is already running).
# install.ps1 sets this up to run hidden every time you log in.

param(
    # Full path to Capri's .exe. Leave empty to search the usual install places.
    [string]$CapriPath = ""
)

$KeyFile = "capri.key"

function Find-Capri {
    if ($CapriPath -and (Test-Path $CapriPath)) { return $CapriPath }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Capri\Capri.exe",
        "$env:LOCALAPPDATA\Programs\capri-desktop\Capri.exe",
        "$env:LOCALAPPDATA\Capri\Capri.exe",
        "$env:ProgramFiles\Capri\Capri.exe",
        "${env:ProgramFiles(x86)}\Capri\Capri.exe"
    )
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
    # Fall back to the Start menu shortcut the installer creates
    $menus = @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs",
               "$env:ProgramData\Microsoft\Windows\Start Menu\Programs")
    foreach ($m in $menus) {
        $lnk = Get-ChildItem -Path $m -Filter "Capri*.lnk" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($lnk) { return $lnk.FullName }
    }
    return $null
}

function Start-CapriIfKey([string]$Drive) {
    if (-not $Drive) { return }
    $key = Join-Path ($Drive.TrimEnd('\') + '\') $KeyFile
    if (-not (Test-Path $key)) { return }
    $first = Get-Content -Path $key -TotalCount 1 -ErrorAction SilentlyContinue
    if ($first -ne "CAPRI-KEY") { return }
    if (Get-Process -Name "Capri" -ErrorAction SilentlyContinue) { return }
    $target = Find-Capri
    if ($target) { Start-Process -FilePath $target }
}

# EventType 2 = a new drive arrived
Register-CimIndicationEvent -ClassName Win32_VolumeChangeEvent -SourceIdentifier "CapriUsbArrive" `
    -Filter "EventType = 2" | Out-Null

while ($true) {
    $e = Wait-Event -SourceIdentifier "CapriUsbArrive"
    $drive = $e.SourceEventArgs.NewEvent.DriveName
    Remove-Event -EventIdentifier $e.EventIdentifier
    Start-Sleep -Milliseconds 800   # give Windows a moment to finish mounting
    try { Start-CapriIfKey $drive } catch { }
}
