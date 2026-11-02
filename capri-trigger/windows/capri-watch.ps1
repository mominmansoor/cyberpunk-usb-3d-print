# Capri USB trigger for Windows.
# Checks your drives every 2 seconds. When a drive with capri.key in its top folder
# appears, it starts Capri Desktop (or brings her back if she's already open). Once per plug-in.
# install.ps1 sets this up to run hidden every time you log in.
# Log: %LOCALAPPDATA%\CapriTrigger\log.txt

param(
    # Full path to Capri's .exe. Leave empty to search the usual install places.
    [string]$CapriPath = "",
    [int]$IntervalSeconds = 2
)

$KeyFile = "capri.key"
$LogFile = Join-Path $env:LOCALAPPDATA "CapriTrigger\log.txt"

function Log([string]$msg) {
    try {
        $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
        Add-Content -Path $LogFile -Value $line
        if ((Get-Item $LogFile).Length -gt 200KB) {
            Get-Content $LogFile -Tail 200 | Set-Content $LogFile
        }
    } catch { }
}

function Find-Capri {
    if ($CapriPath -and (Test-Path $CapriPath)) { return $CapriPath }
    $candidates = @(
        "$env:LOCALAPPDATA\Capri\Capri.exe",
        "$env:LOCALAPPDATA\Programs\Capri\Capri.exe",
        "$env:LOCALAPPDATA\Programs\capri-desktop\Capri.exe",
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

function Test-KeyDrive([string]$root) {
    $key = Join-Path $root $KeyFile
    if (-not (Test-Path -LiteralPath $key)) { return $false }
    $first = Get-Content -LiteralPath $key -TotalCount 1 -ErrorAction SilentlyContinue
    return ($first -and $first.Trim() -eq "CAPRI-KEY")
}

function Start-Capri([string]$root) {
    $target = Find-Capri
    if (-not $target) { Log "Key found on $root but Capri.exe was not found. Re-run install.ps1 with -CapriPath."; return }
    # No "already running" check: Capri only ever runs one copy of herself, so starting her again
    # just brings her back. (Her hidden input-recovery helper is also named Capri.exe and can
    # outlive her, which fooled a process-name check.)
    try {
        # Launched through Explorer, like a double-click, so Capri isn't a child of this watcher
        Start-Process -FilePath "explorer.exe" -ArgumentList "`"$target`""
        Log "Key found on $root; started $target"
    } catch {
        Log "Key found on $root; failed to start ${target}: $($_.Exception.Message)"
    }
}

# Ignore Ctrl+C / Ctrl+Break sent to this hidden console, which used to stop the watcher
try {
    Add-Type -Namespace CapriTrigger -Name Console -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool SetConsoleCtrlHandler(System.IntPtr handler, bool add);'
    [void][CapriTrigger.Console]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
} catch { }

Log "Watcher started (checking every $IntervalSeconds s). Capri: $(Find-Capri)"

# Drives that already have the key when the watcher starts count as seen, so a restart of the
# watcher never opens Capri by itself. Only plugging the key in does.
$seen = @{}
try {
    foreach ($d in [IO.DriveInfo]::GetDrives()) {
        if ($d.IsReady -and $d.DriveType -ne [IO.DriveType]::Network -and (Test-KeyDrive $d.RootDirectory.FullName)) {
            $seen[$d.RootDirectory.FullName] = $true
        }
    }
} catch { }

while ($true) {
    $now = @{}
    try {
        foreach ($d in [IO.DriveInfo]::GetDrives()) {
            if (-not $d.IsReady) { continue }
            if ($d.DriveType -eq [IO.DriveType]::Network) { continue }
            $root = $d.RootDirectory.FullName
            if (Test-KeyDrive $root) {
                $now[$root] = $true
                if (-not $seen.ContainsKey($root)) { Start-Capri $root }
            }
        }
    } catch {
        Log "Drive check error: $($_.Exception.Message)"
    }
    $seen = $now
    Start-Sleep -Seconds $IntervalSeconds
}
