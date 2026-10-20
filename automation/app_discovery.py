"""
COMPASS Application Discovery Engine
Dynamic discovery of installed Windows applications and URI handlers.
Scans Registry App Paths, Start Menu shortcuts, system PATH, and built-in Windows applications.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.logging_config import logger

# Common built-in apps and URI protocols on Windows
BUILTIN_APPS: dict[str, dict[str, Any]] = {
    "notepad": {"exe": "notepad.exe", "display_name": "Notepad", "is_uri": True, "uri": r"shell:AppsFolder\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},
    "notepad.exe": {"exe": "notepad.exe", "display_name": "Notepad", "is_uri": True, "uri": r"shell:AppsFolder\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},
    "calculator": {"exe": "calc.exe", "display_name": "Calculator", "is_uri": True, "uri": "calculator:"},
    "calc": {"exe": "calc.exe", "display_name": "Calculator", "is_uri": True, "uri": "calculator:"},
    "calc.exe": {"exe": "calc.exe", "display_name": "Calculator", "is_uri": True, "uri": "calculator:"},
    "paint": {"exe": "mspaint.exe", "display_name": "Paint", "is_uri": False},
    "mspaint": {"exe": "mspaint.exe", "display_name": "Paint", "is_uri": False},
    "explorer": {"exe": "explorer.exe", "display_name": "File Explorer", "is_uri": False},
    "files": {"exe": "explorer.exe", "display_name": "File Explorer", "is_uri": False},
    "file explorer": {"exe": "explorer.exe", "display_name": "File Explorer", "is_uri": False},
    "cmd": {"exe": "cmd.exe", "display_name": "Command Prompt", "is_uri": False},
    "terminal": {"exe": "wt.exe", "display_name": "Windows Terminal", "is_uri": False},
    "powershell": {"exe": "powershell.exe", "display_name": "PowerShell", "is_uri": False},
    "taskmgr": {"exe": "taskmgr.exe", "display_name": "Task Manager", "is_uri": False},
    "task manager": {"exe": "taskmgr.exe", "display_name": "Task Manager", "is_uri": False},
    "control": {"exe": "control.exe", "display_name": "Control Panel", "is_uri": False},
    "control panel": {"exe": "control.exe", "display_name": "Control Panel", "is_uri": False},
    "settings": {"exe": "", "display_name": "Windows Settings", "is_uri": True, "uri": "ms-settings:"},
    "edge": {"exe": "msedge.exe", "display_name": "Microsoft Edge", "is_uri": False},
    "msedge": {"exe": "msedge.exe", "display_name": "Microsoft Edge", "is_uri": False},
    "chrome": {"exe": "chrome.exe", "display_name": "Google Chrome", "is_uri": False},
    "google chrome": {"exe": "chrome.exe", "display_name": "Google Chrome", "is_uri": False},
    "firefox": {"exe": "firefox.exe", "display_name": "Mozilla Firefox", "is_uri": False},
    "spotify": {"exe": "spotify.exe", "display_name": "Spotify", "is_uri": True, "uri": "spotify:"},
    "code": {"exe": "code.cmd", "display_name": "Visual Studio Code", "is_uri": False},
    "vscode": {"exe": "code.cmd", "display_name": "Visual Studio Code", "is_uri": False},
    "vs code": {"exe": "code.cmd", "display_name": "Visual Studio Code", "is_uri": False},
    "visual studio code": {"exe": "code.cmd", "display_name": "Visual Studio Code", "is_uri": False},
    "cursor": {"exe": "cursor.exe", "display_name": "Cursor", "is_uri": False},
    "slack": {"exe": "slack.exe", "display_name": "Slack", "is_uri": True, "uri": "slack:"},
    "teams": {"exe": "ms-teams.exe", "display_name": "Microsoft Teams", "is_uri": True, "uri": "msteams:"},
    "discord": {"exe": "discord.exe", "display_name": "Discord", "is_uri": True, "uri": "discord:"},
    "vlc": {"exe": "vlc.exe", "display_name": "VLC media player", "is_uri": False},
    "word": {"exe": "winword.exe", "display_name": "Microsoft Word", "is_uri": False},
    "excel": {"exe": "excel.exe", "display_name": "Microsoft Excel", "is_uri": False},
    "powerpoint": {"exe": "powerpnt.exe", "display_name": "Microsoft PowerPoint", "is_uri": False},
}


@dataclass
class AppInfo:
    """Discovered application metadata."""
    key: str
    display_name: str
    path: str
    is_uri: bool = False
    uri: str | None = None
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "path": self.path,
            "is_uri": self.is_uri,
            "uri": self.uri,
            "source": self.source,
        }


class AppDiscovery:
    """Thread-safe application discovery and resolution engine."""

    def __init__(self, cache_ttl_seconds: float = 300.0) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, AppInfo] = {}
        self._last_scan_time: float = 0.0
        self._lock = threading.Lock()

    def discover_app(self, query: str) -> AppInfo | None:
        """
        Resolve an application name or command to an AppInfo object.
        Checks:
          1. Exact URI schemes (e.g. 'ms-settings:', 'https://')
          2. Cache / Built-in app catalogue
          3. System PATH lookup
          4. Registry App Paths
          5. Start Menu shortcuts
        """
        if not query or not query.strip():
            return None

        clean_query = query.strip()
        lower_query = clean_query.lower()

        # Handle URI schemes directly
        if ":" in clean_query and not clean_query[1:2] == ":":  # Not a drive letter C:\
            scheme = clean_query.split(":")[0].lower()
            if scheme in ("http", "https", "file", "ms-settings", "calculator", "spotify", "slack", "discord", "mailto"):
                return AppInfo(
                    key=scheme,
                    display_name=clean_query,
                    path="",
                    is_uri=True,
                    uri=clean_query,
                    source="uri_direct",
                )

        # Check in memory cache
        with self._lock:
            if lower_query in self._cache:
                return self._cache[lower_query]

        # 1. Check built-in table
        norm_query = lower_query[:-4].strip() if lower_query.endswith(".exe") else lower_query
        target_key = lower_query if lower_query in BUILTIN_APPS else (norm_query if norm_query in BUILTIN_APPS else None)
        if target_key:
            entry = BUILTIN_APPS[target_key]
            exe_or_name = entry["exe"]
            full_path = shutil.which(exe_or_name) if exe_or_name else None
            app_info = AppInfo(
                key=lower_query,
                display_name=entry["display_name"],
                path=full_path or exe_or_name,
                is_uri=entry.get("is_uri", False),
                uri=entry.get("uri"),
                source="builtin",
            )
            with self._lock:
                self._cache[lower_query] = app_info
            return app_info

        # 2. Check PATH directly
        path_match = shutil.which(clean_query) or shutil.which(f"{clean_query}.exe")
        if path_match:
            app_info = AppInfo(
                key=lower_query,
                display_name=Path(path_match).stem.capitalize(),
                path=path_match,
                is_uri=False,
                source="path",
            )
            with self._lock:
                self._cache[lower_query] = app_info
            return app_info

        # 3. Check Windows Registry App Paths
        reg_info = self._find_in_registry_app_paths(clean_query)
        if reg_info:
            with self._lock:
                self._cache[lower_query] = reg_info
            return reg_info

        # 4. Check Start Menu shortcuts
        shortcut_info = self._find_in_start_menu(clean_query)
        if shortcut_info:
            with self._lock:
                self._cache[lower_query] = shortcut_info
            return shortcut_info

        # 5. Fuzzy match against populated cache / built-ins
        for k, entry in BUILTIN_APPS.items():
            if lower_query in k or k in lower_query:
                full_path = shutil.which(entry["exe"]) if entry["exe"] else None
                app_info = AppInfo(
                    key=k,
                    display_name=entry["display_name"],
                    path=full_path or entry["exe"],
                    is_uri=entry.get("is_uri", False),
                    uri=entry.get("uri"),
                    source="fuzzy_builtin",
                )
                with self._lock:
                    self._cache[lower_query] = app_info
                return app_info

        return None

    def _find_in_registry_app_paths(self, name: str) -> AppInfo | None:
        """Scan HKEY_LOCAL_MACHINE and HKEY_CURRENT_USER App Paths."""
        if sys.platform != "win32":
            return None

        try:
            import winreg

            subkeys = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
            ]
            roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
            target_names = [name, f"{name}.exe"]

            for root in roots:
                for subkey in subkeys:
                    try:
                        with winreg.OpenKey(root, subkey) as key:
                            for target in target_names:
                                try:
                                    with winreg.OpenKey(key, target) as app_key:
                                        val, _ = winreg.QueryValueEx(app_key, "")
                                        if val and os.path.exists(val.strip('"')):
                                            clean_val = val.strip('"')
                                            return AppInfo(
                                                key=name.lower(),
                                                display_name=Path(clean_val).stem,
                                                path=clean_val,
                                                is_uri=False,
                                                source="registry",
                                            )
                                except (OSError, FileNotFoundError):
                                    continue
                    except (OSError, FileNotFoundError):
                        continue
        except Exception as e:
            logger.debug(f"Registry App Paths lookup error: {e}")
        return None

    def _find_in_start_menu(self, name: str) -> AppInfo | None:
        """Scan Start Menu Programs folders for matching .lnk or .exe files."""
        if sys.platform != "win32":
            return None

        clean_lower = name.lower()
        search_dirs: list[str] = []

        appdata = os.environ.get("APPDATA")
        if appdata:
            search_dirs.append(os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"))

        programdata = os.environ.get("PROGRAMDATA")
        if programdata:
            search_dirs.append(os.path.join(programdata, r"Microsoft\Windows\Start Menu\Programs"))

        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            search_dirs.append(os.path.join(localappdata, r"Programs"))

        for sdir in search_dirs:
            if not os.path.exists(sdir):
                continue
            try:
                for root, _, files in os.walk(sdir):
                    for file in files:
                        lower_file = file.lower()
                        if clean_lower in lower_file:
                            full_path = os.path.join(root, file)
                            stem = Path(file).stem
                            return AppInfo(
                                key=stem.lower(),
                                display_name=stem,
                                path=full_path,
                                is_uri=False,
                                source="start_menu",
                            )
            except Exception as e:
                logger.debug(f"Start Menu scan error in {sdir}: {e}")

        return None

    def list_known_apps(self) -> list[str]:
        """Return list of common recognizable application names."""
        return sorted(list(BUILTIN_APPS.keys()))


# Global singleton
_app_discovery_instance: AppDiscovery | None = None
_instance_lock = threading.Lock()


def get_app_discovery() -> AppDiscovery:
    global _app_discovery_instance
    if _app_discovery_instance is None:
        with _instance_lock:
            if _app_discovery_instance is None:
                _app_discovery_instance = AppDiscovery()
    return _app_discovery_instance


def discover_app(name: str) -> AppInfo | None:
    """Convenience helper to discover an app."""
    return get_app_discovery().discover_app(name)
