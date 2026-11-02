# Capri trigger: plug in the USB, Capri starts

USB drives can't start programs on their own. Windows removed that ("AutoRun") in Windows 7, and macOS and Linux never allowed it. So the trigger has two halves:

1. **The key, on the USB:** [`usb/capri.key`](usb/capri.key). Copy it to the top folder of your USB drive.
2. **The watcher, on your computer:** a tiny background script that notices when a drive with `capri.key` is plugged in, and starts Capri Desktop if she isn't already running. It only reacts to drives that have the key, so other USB sticks do nothing.

Install the watcher once per computer:

| System | Install | Remove |
|---|---|---|
| **Windows 10/11** | `powershell -ExecutionPolicy Bypass -File windows\install.ps1` | `windows\uninstall.ps1` |
| **macOS** | `bash macos/install.sh` | `bash macos/uninstall.sh` |
| **Linux** | `bash linux/install.sh ~/Capri/Capri` | `bash linux/uninstall.sh` |

No admin rights are needed on any of them.

## How each one works

- **Windows:** a scheduled task starts `capri-watch.ps1` hidden when you log in. It listens for Windows' "new drive" event, checks the drive for `capri.key`, and opens Capri. It finds Capri in the usual install folders or from the Start menu shortcut. If yours is somewhere else, pass the path: `install.ps1 -CapriPath "C:\...\Capri.exe"`.
- **macOS:** a launchd agent with `StartOnMount` runs `capri-watch.sh` whenever any drive mounts, and it runs `open -a Capri` if a mounted drive has the key. The first time, macOS may ask to let `bash` read a removable volume. Click Allow.
- **Linux:** an autostart entry runs `capri-watch.sh` after you log in. Every 2 seconds it looks at mounted drives under `/media`, `/run/media` and `/mnt`, and starts Capri once each time the key drive appears. Pass the path to your unpacked `Capri/Capri` binary when installing.

## Tips

- Capri's own **Start with Windows** switch is on by default. Turn it off if you want the USB to be the only thing that wakes her up.
- The key file must start with the line `CAPRI-KEY`. You can rename the drive or add other files freely.
- Pulling the USB out doesn't close Capri. Close her from the tray as usual.
