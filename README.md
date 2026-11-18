# mouse-battery-tray

Windows tray icon that shows the battery level of an **Attack Shark X3** wireless mouse on its 2.4 GHz receiver, in the Windows system tray.

![The mouse icon at 100% in the Windows 11 tray, next to the laptop battery](docs/tray.png)

Tested only with an Attack Shark X3 on its 2.4 GHz receiver (`1d57:fa60`) on Windows 11. Other mice that use the same receiver and battery frames may work too; see [Other mice](#other-mice). This project is not affiliated with Attack Shark.

## The icon

![Icon states: 100%, 30%, 10%, charging, waiting](docs/icon-states.png)

The icon is a mouse silhouette coloured by level (red at 20% or below, amber up to 40%, green above) with the percent below the wheel, a bolt in it while the charging cable is plugged in, and a grey loading spinner until the first reading arrives (it stops turning after 20 seconds, since each frame change writes a temporary icon file). Hover for the time of the last reading. A notification fires once per discharge when the level reaches 20%.

## Run

### Installer

Download `MouseBatteryTraySetup-<version>.exe` from the [latest release](https://github.com/bodypas/mouse-battery-tray/releases/latest) and run it.

The setup installs for the current user only, without admin rights, into `%LOCALAPPDATA%\Programs\Mouse Battery Tray`, and offers "Start with Windows". You can pick another folder or drive. Setup then makes that folder private to your account (plus SYSTEM and Administrators) before copying anything, because a folder on a second drive usually lets every account change files, and the exe there starts at every logon. It refuses a folder that already holds other files or a whole drive, and stops with a message if it can't make the folder private (FAT32 and exFAT drives, like most USB sticks, have no permissions). Python is bundled. The app then shows up in Settings > Apps > Installed apps and in the Start menu, with a second Start menu entry for the [diagnose report](#other-mice). Installing a newer version over a running copy closes it first.

Uninstalling (Settings > Apps > Installed apps) closes the app and removes its files, its Start menu entries, its app id key, its data folder `%LOCALAPPDATA%\mouse-battery-tray`, and the "Start with Windows" entry if that entry starts the installed copy.

The setup and the app are not code-signed, so Windows SmartScreen may show "Windows protected your PC" (More info > Run anyway), and some antivirus tools flag PyInstaller apps.

To build the setup yourself (`dist\MouseBatteryTraySetup-<version>.exe`), you need [uv](https://docs.astral.sh/uv/) and [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`):

```powershell
uv sync
uv run python scripts\build.py
```

### From source

```powershell
uv sync
.venv\Scripts\pythonw.exe -m mouse_battery_tray   # no console window
uv run mouse-battery-tray                         # with console logging, for debugging
```

### Using it

Right-click the icon for "Start with Windows" (writes `MouseBatteryTray` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, pointing at the exe or, from source, at pythonw) and "Quit". Only one instance runs at a time, and an installed copy and a source copy count as the same app, so quit one before starting the other.

On every start the app writes `HKCU\Software\Classes\AppUserModelId\MouseBatteryTray` (display name and logo) and adopts that app id, so notifications come from "Mouse Battery" instead of "Python". The uninstaller removes it; for a source install, delete that key, the Run value and the `%LOCALAPPDATA%\mouse-battery-tray` folder yourself.

Windows 11 puts new tray icons in the `^` overflow. To keep it next to the clock, drag it onto the taskbar or turn it on under Settings > Personalization > Taskbar > Other system tray icons.

## Other mice

If the icon keeps showing the spinner, your mouse probably uses another receiver or another battery format. Open "Mouse Battery Tray diagnose" from the Start menu, or from source run `uv run mouse-battery-tray --diagnose`.

It lists the HID devices, then listens for 15 seconds to every `1d57` device (use the mouse, don't type) and saves the report to `%LOCALAPPDATA%\mouse-battery-tray\diagnose.txt`. The installed app opens it in Notepad (your default text editor) when it finishes; from source it is printed as well. It works while the tray app is running. If your receiver has another vendor id, find it in the device list and listen to it by passing its `VID:PID` in hex (change the path if you installed elsewhere):

```powershell
& "$env:LOCALAPPDATA\Programs\Mouse Battery Tray\MouseBatteryTray.exe" --diagnose 1d57:fa60   # your receiver's VID:PID
```

The report holds your Windows and Python versions, device ids, usage pages, names and raw frames, but no serial numbers or device paths. It never listens to mouse, keyboard or media-key collections. Device names can include a person's name, so read the report before posting it. [Open an issue](https://github.com/bodypas/mouse-battery-tray/issues) with the report and your mouse model.

## How it reads the battery

There is no standard HID battery report. The receiver's HID collection on usage page `0x000A` pushes a frame every couple of seconds: `03 xx 40 <state> <level>`, with state `01` on battery and `03` charging. Byte 1 is ignored (`10` on this mouse). Frames with another byte 2 (such as `03 E5 01 00 00`) are not battery data. The frame layout comes from [Attack-Shark-Battery-KDE](https://gitlab.com/gabriel17166/Attack-Shark-Battery-KDE).

On this mouse the level is 0-10, not 0-100: only 7-10 have ever been seen, about 23 minutes of charging moved it only from 9 to 10, it stayed at 10 for about 25 more minutes on the cable, it dropped from 10 to 9 the day after that charge, and the mouse has shown no low-battery signs. The app shows level × 10 as "about N%". This scale was inferred, not documented; further slow drops over days of use would confirm it. Models that send 0-100 (as the KDE project describes for its mouse) are not supported: levels above 10 are rejected. The charging state `03` has never been seen on this mouse.

Right after the cable is unplugged the mouse sends one frame at level 7 before its real level, so a reading is only shown once the same value arrives twice in a row.

While the charging cable is plugged in, the mouse shows up as `1d57:fa61` and stops sending frames, so the app shows "charging" without a percent. It only looks for `fa61` in the device list and never opens it.

## Logs

`%LOCALAPPDATA%\mouse-battery-tray\app.log` has status changes, errors and each raw frame from the receiver whenever it differs from the previous one. With the receiver unplugged the icon shows the spinner. `hang.log` next to it gets a stack dump of every thread if a HID call blocks for 30 seconds; this is there because one probe once froze for over 90 seconds right after unplugging the cable.

## License

MIT, see [LICENSE](LICENSE).

The installed app also bundles Python (PSF License), hidapi (BSD, one of the licenses it offers), Pillow (MIT-CMU), pystray (LGPL-3.0), six (MIT) and the PyInstaller bootloader (GPL-2.0 with an exception that allows distributing the built app under any license). pystray is bundled unmodified, and anyone can rebuild the app with their own copy using `scripts\build.py`.
