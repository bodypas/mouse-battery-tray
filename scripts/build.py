"""Build the app and its installer: uv run python scripts/build.py

Output: dist/MouseBatteryTray/ (PyInstaller folder build) and dist/MouseBatteryTraySetup-<version>.exe (Inno Setup 6).
"""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import PyInstaller.__main__

from mouse_battery_tray.icon import render_app_icon

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
INSTALLER_SCRIPT = ROOT / "installer" / "MouseBatteryTray.iss"


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    iscc = _find_iscc()  # before the slow PyInstaller step
    BUILD.mkdir(exist_ok=True)
    icon = BUILD / "app.ico"
    render_app_icon().save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)])
    PyInstaller.__main__.run(
        [
            str(ROOT / "src" / "mouse_battery_tray" / "__main__.py"),
            "--name=MouseBatteryTray",
            "--onedir",  # a one-file exe would unpack itself to a temp folder on every start
            "--windowed",
            f"--icon={icon}",
            f"--paths={ROOT / 'src'}",
            "--hidden-import=pystray._win32",  # pystray picks its backend with a dynamic import
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={BUILD / 'pyinstaller'}",
            f"--specpath={BUILD}",
            "--noconfirm",
            "--clean",
        ]
    )
    subprocess.run([str(iscc), f"/DAppVersion={version}", str(INSTALLER_SCRIPT)], check=True)


def _find_iscc() -> Path:
    on_path = shutil.which("ISCC")
    candidates = [Path(on_path)] if on_path else []
    candidates += [
        Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup")


if __name__ == "__main__":
    main()
