from __future__ import annotations

import json
import ctypes
import os
import platform
import re
import shutil
import subprocess
import threading
import tempfile
import time
import urllib.error
import urllib.request
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


APP_NAME = "Maple Toolbox"
APP_VERSION = "v0.26"
VISIBLE_CONSOLE_COUNTDOWN_SECONDS = 8  # Successful visible console runs count down before closing.
FEEDBACK_EMAIL = "maple@arcadeheaven.com"
TAGLINE = "One Toolbox to run them all."
DEFAULT_ROOT = Path(r"C:\MapleOCR")
CAPTURE_REPO = "GuruChoc/EquipmentBagCaptureTool"
CAPTURE_RELEASE_API = f"https://api.github.com/repos/{CAPTURE_REPO}/releases/latest"
CAPTURE_RELEASE_WEB = f"https://github.com/{CAPTURE_REPO}/releases/latest"

MODULE_REPOS = {
    "toolbox": "GuruChoc/MapleToolbox",
    "capture": "GuruChoc/EquipmentBagCaptureTool",
    "mapleocr": "GuruChoc/MapleOCR",
    "mapleforge": "GuruChoc/MapleForge",
    "bismirpg": "GuruChoc/BISMIRPG",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# User-facing wording kept together so labels/order are easy to tweak later.
TEXT = {
    "select_operating_folder": "Select Operating Folder",
    "open_folder": "Open Folder",
    "operating_folder": "Operating Folder",
    "not_set": "Not set",
    "coming_soon": "COMING SOON",
}



def config_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home())))
    return base / "MapleToolbox" / "config.json"


def config_exists() -> bool:
    return config_path().exists()


def update_log_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home())))
    return base / "MapleToolbox" / "updates.log"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_update_log(text: str) -> None:
    p = update_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text}\n")


def count_images(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(
        1 for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def latest_importer(root: Path) -> Path | None:
    if not root.exists():
        return None

    found = []
    for p in root.glob("maple_batch_importer_easyocr_v*.py"):
        m = re.search(r"_v(\d+)", p.name, re.I)
        if m:
            found.append((int(m.group(1)), p.stat().st_mtime, p))

    if not found:
        return None

    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return found[0][2]


def importer_version(path: Path | None) -> str:
    if not path:
        return "Not detected"
    m = re.search(r"_v(\d+)", path.name, re.I)
    return f"v{m.group(1)}" if m else "Unknown"


def latest_output_zip(root: Path) -> Path | None:
    found = list(root.glob("Output_v*.zip"))
    output = root / "Output"

    if output.exists():
        found.extend(output.glob("Output_v*.zip"))
        found.extend(output.glob("*.zip"))

    if not found:
        return None

    return max(found, key=lambda p: p.stat().st_mtime)


def open_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    os.startfile(str(path))


def fetch_latest_release(repo_api_url: str, timeout: int = 8) -> dict:
    """
    Fetch latest release from GitHub API.
    If the API request fails, derive owner/repo and try the public releases/latest redirect.
    """
    req = urllib.request.Request(
        repo_api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MapleToolbox",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as api_exc:
        m = re.search(r"/repos/([^/]+/[^/]+)/releases/latest", repo_api_url)
        if not m:
            raise api_exc

        repo = m.group(1)
        public_url = f"https://github.com/{repo}/releases/latest"
        req2 = urllib.request.Request(
            public_url,
            headers={"User-Agent": "MapleToolbox"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req2, timeout=timeout) as response:
                final_url = response.geturl()
                tag = final_url.rstrip("/").split("/")[-1]
                if tag and tag.lower() != "latest":
                    return {
                        "tag_name": tag,
                        "name": tag,
                        "html_url": final_url,
                    }
        except Exception:
            pass

        raise api_exc


def version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", value or "")
    return tuple(int(x) for x in nums) if nums else (0,)



def github_repo_web(repo: str) -> str:
    return f"https://github.com/{repo}"


def github_release_web(repo: str) -> str:
    return f"https://github.com/{repo}/releases/latest"


def github_release_api(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases/latest"


def git_origin_repo(folder: Path | None) -> str | None:
    """Return owner/repo from .git/config origin when available."""
    if not folder:
        return None
    config = folder / ".git" / "config"
    if not config.exists():
        return None
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Handles https://github.com/owner/repo.git and git@github.com:owner/repo.git
    match = re.search(
        r'url\s*=\s*(?:https://github\.com/|git@github\.com:)([^/\s:]+/[^/\s]+?)(?:\.git)?\s*$',
        text,
        re.I | re.M,
    )
    if not match:
        return None
    repo = match.group(1).strip()
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    return repo


def local_version_from_folder(folder: Path | None) -> str | None:
    if not folder or not folder.exists():
        return None
    for name in ("VERSION", "version.txt", "VERSION.txt"):
        p = folder / name
        if p.exists():
            try:
                value = p.read_text(encoding="utf-8", errors="replace").strip()
                if value:
                    return value if value.lower().startswith("v") else f"v{value}"
            except Exception:
                pass
    return None



def internet_status(timeout: int = 4):
    """
    Return (online, detail).

    Do not equate one failed GitHub API request with "no internet".
    Try several independent HTTPS endpoints and report what actually failed.
    """
    endpoints = [
        ("GitHub", "https://github.com"),
        ("GitHub API", "https://api.github.com"),
        ("Microsoft", "https://www.microsoft.com"),
    ]

    errors = []
    successes = []

    for label, url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MapleToolbox"},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if 200 <= status < 500:
                    successes.append(label)
                    continue
                errors.append(f"{label}: HTTP {status}")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}")

    if successes:
        if "GitHub" in successes or "GitHub API" in successes:
            return True, "Online — GitHub reachable"
        return True, "Online — internet works, GitHub check may be blocked"

    return False, "Offline or Python HTTPS blocked — " + "; ".join(errors[:3])


def internet_available(timeout: int = 4) -> bool:
    return internet_status(timeout)[0]



def run_quiet(command, timeout=6):
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except Exception:
        return 1, "", ""


def file_version_windows(path: Path):
    if os.name != "nt" or not path.exists():
        return None
    escaped = str(path).replace("'", "''")
    script = "(Get-Item -LiteralPath '{}').VersionInfo.ProductVersion".format(escaped)
    rc, out, _ = run_quiet(
        ["powershell.exe", "-NoProfile", "-Command", script],
        timeout=5,
    )
    value = out.strip()
    return value if rc == 0 and value else None


def detect_autohotkey_v2():
    candidates = []

    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))

    candidates.extend([
        pf / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        pf / "AutoHotkey" / "v2" / "AutoHotkey32.exe",
        pf / "AutoHotkey" / "AutoHotkey.exe",
        pf86 / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        pf86 / "AutoHotkey" / "AutoHotkey.exe",
        local / "Programs" / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        local / "Programs" / "AutoHotkey" / "AutoHotkey.exe",
        local / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        local / "AutoHotkey" / "AutoHotkey.exe",
    ])

    path_hit = shutil.which("AutoHotkey.exe")
    if path_hit:
        candidates.insert(0, Path(path_hit))

    if os.name == "nt":
        rc, out, _ = run_quiet(["cmd.exe", "/c", "assoc .ahk"], timeout=4)
        if rc == 0 and "=" in out:
            progid = out.strip().split("=", 1)[1].strip()
            if progid:
                rc2, out2, _ = run_quiet(["cmd.exe", "/c", "ftype {}".format(progid)], timeout=4)
                if rc2 == 0 and "=" in out2:
                    cmdline = out2.strip().split("=", 1)[1].strip()
                    m = re.match(r'^"([^"]+)"|^(\S+)', cmdline)
                    if m:
                        exe = m.group(1) or m.group(2)
                        if exe:
                            candidates.insert(0, Path(exe))

    seen = set()
    for p in candidates:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        if not p.exists():
            continue

        version = file_version_windows(p)
        v2ish = False
        if version:
            first = version.strip().lstrip("vV").split(".", 1)[0]
            v2ish = first == "2"
        if "\\v2\\" in str(p).lower():
            v2ish = True

        if v2ish:
            if version:
                shown = version if version.lower().startswith("v") else "v" + version
            else:
                shown = "v2"
            return True, "{} — {}".format(shown, p)

    if shutil.which("winget.exe") or shutil.which("winget"):
        rc, out, _ = run_quiet(
            ["winget", "list", "--id", "AutoHotkey.AutoHotkey", "--exact"],
            timeout=8,
        )
        if rc == 0 and "AutoHotkey.AutoHotkey" in out:
            lines = [ln.strip() for ln in out.splitlines() if "AutoHotkey.AutoHotkey" in ln]
            return True, lines[-1] if lines else "Installed via winget"

    return False, "Missing or AutoHotkey v2 could not be verified"


def detect_sharex():
    candidates = []
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))

    path_hit = shutil.which("ShareX.exe")
    if path_hit:
        candidates.append(Path(path_hit))

    candidates.extend([
        pf / "ShareX" / "ShareX.exe",
        local / "Programs" / "ShareX" / "ShareX.exe",
        local / "ShareX" / "ShareX.exe",
    ])

    for p in candidates:
        if p.exists():
            version = file_version_windows(p)
            return True, "{} — {}".format(version or "Found", p)

    if shutil.which("winget.exe") or shutil.which("winget"):
        rc, out, _ = run_quiet(
            ["winget", "list", "--id", "ShareX.ShareX", "--exact"],
            timeout=8,
        )
        if rc == 0 and "ShareX.ShareX" in out:
            lines = [ln.strip() for ln in out.splitlines() if "ShareX.ShareX" in ln]
            return True, lines[-1] if lines else "Installed via winget"

    return False, "Missing"



def winget_package_visible(package_id: str) -> bool:
    if not (shutil.which("winget.exe") or shutil.which("winget")):
        return False

    rc, out, _ = run_quiet(
        ["winget", "search", "--id", package_id, "--exact"],
        timeout=10,
    )
    return rc == 0 and package_id.lower() in out.lower()



def toolbox_dir() -> Path:
    return Path(__file__).resolve().parent


def errors_dir() -> Path:
    return toolbox_dir() / "Errors"


def prune_error_logs(max_logs: int = 20) -> None:
    folder = errors_dir()
    if not folder.exists():
        return
    logs = sorted(
        [p for p in folder.glob("*.log") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in logs[max_logs:]:
        try:
            old.unlink()
        except Exception:
            pass


def write_error_log(
    module: str,
    action: str,
    *,
    command=None,
    exit_code=None,
    exception_text=None,
    output=None,
) -> Path | None:
    try:
        folder = errors_dir()
        folder.mkdir(parents=True, exist_ok=True)

        safe_module = re.sub(r"[^A-Za-z0-9_-]+", "_", module.strip()) or "Module"
        safe_action = re.sub(r"[^A-Za-z0-9_-]+", "_", action.strip()) or "Error"
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = folder / f"{safe_module}_{safe_action}_{stamp}.log"

        lines = [
            f"Maple Toolbox {APP_VERSION}",
            f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
            f"Module: {module}",
            f"Action: {action}",
        ]
        if command is not None:
            if isinstance(command, (list, tuple)):
                command_text = " ".join(str(x) for x in command)
            else:
                command_text = str(command)
            lines.append(f"Command: {command_text}")
        if exit_code is not None:
            lines.append(f"Exit code: {exit_code}")
        if exception_text:
            lines.append(f"Exception: {exception_text}")

        lines.append("")
        lines.append("OUTPUT")
        lines.append("=" * 72)
        lines.append(output or "(no captured output)")
        path.write_text("\n".join(lines), encoding="utf-8", errors="replace")

        prune_error_logs(20)
        return path
    except Exception:
        return None



def detected_version_from_module_files(folder: Path | None) -> str | None:
    """
    Best-effort module version detection when a VERSION file is absent.

    Prefer semantic release versions such as v1.0.0 over old internal workflow
    markers such as v191 found inside source/comments/filenames.
    """
    if not folder or not folder.exists():
        return None

    semantic_versions = []
    legacy_versions = []

    candidates = [
        folder / "README.md",
        folder / "README.txt",
        folder / "RELEASE_NOTES.txt",
        folder / "bis_report_generator.py",
    ]

    try:
        candidates.extend(
            p for p in folder.iterdir()
            if p.is_file() and (
                p.name.lower().startswith("release_notes")
                or p.name.lower().startswith("readme")
            )
        )
    except Exception:
        pass

    seen = set()
    for p in candidates:
        if p in seen or not p.exists() or not p.is_file():
            continue
        seen.add(p)

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""

        # Full semantic versions are authoritative public-release identifiers.
        for m in re.finditer(r'(?i)\bv(\d+)\.(\d+)\.(\d+)\b', text):
            semantic_versions.append(tuple(int(x) for x in m.groups()))

        for m in re.finditer(r'(?i)\bv(\d{1,5})\b', text):
            try:
                legacy_versions.append(int(m.group(1)))
            except ValueError:
                pass

        # Filenames such as RELEASE_NOTES_v1.0.0.txt are also authoritative.
        for m in re.finditer(r'(?i)\bv(\d+)\.(\d+)\.(\d+)\b', p.name):
            semantic_versions.append(tuple(int(x) for x in m.groups()))

    if semantic_versions:
        major, minor, patch = max(semantic_versions)
        return f"v{major}.{minor}.{patch}"

    # Legacy fallback only when no semantic public-release version exists.
    try:
        for p in folder.iterdir():
            if not p.is_file():
                continue
            for m in re.finditer(r'(?i)\bv(\d{1,5})\b', p.name):
                try:
                    legacy_versions.append(int(m.group(1)))
                except ValueError:
                    pass
    except Exception:
        pass

    if legacy_versions:
        return f"v{max(legacy_versions)}"

    return None


def latest_error_log() -> Path | None:
    folder = errors_dir()
    if not folder.exists():
        return None
    logs = [p for p in folder.glob("*.log") if p.is_file()]
    if not logs:
        return None
    return max(logs, key=lambda p: p.stat().st_mtime)



class ToolTip:
    """Small hover tooltip for first-time guidance without cluttering the GUI."""
    def __init__(self, widget, text: str, delay: int = 450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after = None
        self.tipwindow = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self):
        self._after = None
        if self.tipwindow or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return

        tw = tk.Toplevel(self.widget)
        self.tipwindow = tw
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except Exception:
            pass
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=440,
            background="#fff7d6",
            foreground="#111111",
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self.tipwindow is not None:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
            self.tipwindow = None


def add_tooltip(widget, text: str):
    ToolTip(widget, text)
    return widget



def saved_window_geometry(key: str, default: str | None = None) -> str | None:
    cfg = load_config()
    windows = cfg.get("window_geometry", {})
    value = windows.get(key)
    return value if isinstance(value, str) and value else default


def save_window_geometry(key: str, geometry: str) -> None:
    if not geometry:
        return
    cfg = load_config()
    windows = cfg.setdefault("window_geometry", {})
    if windows.get(key) == geometry:
        return
    windows[key] = geometry
    save_config(cfg)


def _parse_tk_geometry(geometry: str):
    m = re.match(r"^\s*(\d+)x(\d+)([+-]\d+)([+-]\d+)\s*$", geometry or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def _windows_find_window_by_title(title_text: str):
    """Best effort: find a visible top-level Windows window whose title contains text."""
    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
        matches = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_text.lower() in buf.value.lower():
                matches.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return matches[0] if matches else None
    except Exception:
        return None


def _windows_get_rect(hwnd):
    if os.name != "nt" or not hwnd:
        return None
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]
        rect = RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return (
            rect.right - rect.left,
            rect.bottom - rect.top,
            rect.left,
            rect.top,
        )
    except Exception:
        return None


def _windows_move_window(hwnd, geometry: str):
    parsed = _parse_tk_geometry(geometry)
    if os.name != "nt" or not hwnd or not parsed:
        return False
    try:
        width, height, x, y = parsed
        return bool(ctypes.windll.user32.MoveWindow(hwnd, x, y, width, height, True))
    except Exception:
        return False


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.canvas = tk.Canvas(
            self,
            bg="#0c1117",
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.inner = ttk.Frame(self.canvas)

        self.window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._sync_width)

        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

    def _sync_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class ZipBrowser(tk.Toplevel):
    PREVIEW_LIMIT = 512_000

    def __init__(self, master, zip_path: Path):
        super().__init__(master)
        self.zip_path = zip_path
        self.title(f"ZIP Inspector — {zip_path.name}")
        self.geometry("980x650")
        self.minsize(800, 520)
        self.configure(bg="#0c1117")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text=str(zip_path), style="Subtle.TLabel"
        ).pack(anchor="w", pady=(0, 10))

        pane = ttk.Panedwindow(outer, orient="horizontal")
        pane.pack(fill="both", expand=True)

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=3)

        self.members = tk.Listbox(
            left,
            bg="#121922",
            fg="#e8eef7",
            selectbackground="#2e6d9c",
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.members.pack(side="left", fill="both", expand=True)

        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.members.yview)
        sb1.pack(side="right", fill="y")
        self.members.configure(yscrollcommand=sb1.set)
        self.members.bind("<<ListboxSelect>>", self._preview_selected)

        self.preview = tk.Text(
            right,
            wrap="none",
            bg="#0f141b",
            fg="#dce7f3",
            insertbackground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.preview.pack(side="left", fill="both", expand=True)

        sb2 = ttk.Scrollbar(right, orient="vertical", command=self.preview.yview)
        sb2.pack(side="right", fill="y")
        self.preview.configure(yscrollcommand=sb2.set)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                self.members.insert("end", name)

        if self.members.size():
            self.members.selection_set(0)
            self._preview_selected()

    def _preview_selected(self, _event=None):
        selected = self.members.curselection()
        if not selected:
            return

        name = self.members.get(selected[0])
        self.preview.delete("1.0", "end")

        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                info = zf.getinfo(name)

                if info.is_dir():
                    self.preview.insert("1.0", "[Folder]")
                    return

                suffix = Path(name).suffix.lower()
                raw = zf.read(name)[:self.PREVIEW_LIMIT]

                if suffix in {
                    ".txt", ".json", ".csv", ".log", ".md",
                    ".ini", ".ps1", ".bat", ".py", ".ahk"
                }:
                    self.preview.insert(
                        "1.0", raw.decode("utf-8", errors="replace")
                    )
                else:
                    self.preview.insert(
                        "1.0",
                        f"{name}\n\n"
                        "Read directly from the ZIP — no extraction performed.\n\n"
                        f"Uncompressed size: {info.file_size:,} bytes\n"
                        f"Compressed size: {info.compress_size:,} bytes"
                    )
        except Exception as exc:
            self.preview.insert("1.0", f"Could not preview ZIP member:\n{exc}")


class MapleToolbox(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1220x880")
        try:
            if os.name == "nt":
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GuruChoc.MapleToolbox")
        except Exception:
            pass
        try:
            icon_path = toolbox_dir() / "MapleToolbox.ico"
            if icon_path.exists():
                self.iconbitmap(default=str(icon_path))
        except Exception:
            pass
        self.minsize(1080, 720)
        self.configure(bg="#0c1117")

        cfg = load_config()

        self.root_var = tk.StringVar(
            value=cfg.get("mapleocr_dir", cfg.get("mapleocr_root", str(DEFAULT_ROOT)))
        )
        self.capture_dir_var = tk.StringVar(value=cfg.get("capture_dir", ""))
        self.mapleocr_dir_var = tk.StringVar(
            value=cfg.get("mapleocr_dir", cfg.get("mapleocr_root", str(DEFAULT_ROOT)))
        )
        self.mapleforge_dir_var = tk.StringVar(value=cfg.get("mapleforge_dir", ""))
        self.ocr_dir_var = tk.StringVar(value="")
        self.bismirpg_dir_var = tk.StringVar(value=cfg.get("bismirpg_dir", ""))

        self.status_var = tk.StringVar(value="Ready")
        self.importer_var = tk.StringVar(value="Not detected")
        self.bag_count_var = tk.StringVar(value="0")
        self.equipped_count_var = tk.StringVar(value="0")
        self.zip_var = tk.StringVar(value="None detected")

        self.capture_installed_var = tk.StringVar(value="Installed: Not detected")
        self.capture_github_var = tk.StringVar(value="GitHub: not checked")
        self.capture_update_var = tk.StringVar(value="")

        self.up_to_date_var = tk.StringVar(value="0")
        self.update_available_var = tk.StringVar(value="0")
        self.not_installed_var = tk.StringVar(value="0")
        self.last_checked_var = tk.StringVar(value="Last checked: Never")
        self.update_details_var = tk.StringVar(value="No update check completed yet.")
        self.mapleocr_release_var = tk.StringVar(value="Release: not checked")
        self.mapleforge_release_var = tk.StringVar(value="Release: not checked")
        self.bismirpg_release_var = tk.StringVar(value="Release: not checked")
        self.bis_report_var = tk.StringVar(value="No BIS reports found")
        self.bis_report_detail_var = tk.StringVar(value="Generate a report or refresh the report list.")
        self.bis_baseline_var = tk.StringVar(value="Approved BIS baseline: NONE")
        self._bis_report_paths = {}

        self.prereq_summary_var = tk.StringVar(value="Prerequisites not checked yet.")
        self.directory_health_var = tk.StringVar(value="Directory health not checked yet.")

        self._configure_styles()
        self._build_ui()
        self.refresh_status()
        self.after(150, self._apply_button_tooltips)

        if not config_exists():
            self.after(250, self.show_first_run_wizard)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background="#0c1117")
        style.configure("Card.TFrame", background="#151d27")
        style.configure("TLabel", background="#0c1117", foreground="#e8eef7")
        style.configure("Card.TLabel", background="#151d27", foreground="#e8eef7")
        style.configure("Title.TLabel", background="#0c1117", foreground="#ffffff",
                        font=("Segoe UI Semibold", 24))
        style.configure("Tagline.TLabel", background="#0c1117", foreground="#b7c7d9",
                        font=("Segoe UI", 11, "italic"))
        style.configure("Section.TLabel", background="#151d27", foreground="#ffffff",
                        font=("Segoe UI Semibold", 14))
        style.configure("Subtle.TLabel", background="#0c1117", foreground="#93a4b7")
        style.configure("CardSubtle.TLabel", background="#151d27", foreground="#93a4b7")
        style.configure("Good.TLabel", background="#151d27", foreground="#61d98a",
                        font=("Segoe UI Semibold", 11))
        style.configure("Warn.TLabel", background="#151d27", foreground="#e1ad3d",
                        font=("Segoe UI Semibold", 11))
        style.configure("Teaser.TLabel", background="#151d27", foreground="#f0b83f",
                        font=("Segoe UI Semibold", 10))
        style.configure("Metric.TLabel", background="#151d27", foreground="#61d98a",
                        font=("Segoe UI Semibold", 16))
        style.configure("TButton", padding=(12, 9), background="#233244",
                        foreground="#ffffff", borderwidth=0)
        style.map("TButton",
                  background=[("active", "#31475f"), ("disabled", "#1a222c")],
                  foreground=[("disabled", "#657384")])
        style.configure("Accent.TButton", background="#2e6d9c", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#3b82b5")])
        style.configure("Green.TButton", background="#26753c", foreground="#ffffff")
        style.map("Green.TButton", background=[("active", "#32944d")])
        style.configure("Danger.TButton", background="#713e46", foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#92505b")])
        style.configure("TEntry", fieldbackground="#0f141b", foreground="#e8eef7",
                        insertcolor="#ffffff")
        style.configure("Latest.TCombobox", fieldbackground="#dff6df", background="#dff6df",
                        foreground="#111111")
        style.map("Latest.TCombobox",
                  fieldbackground=[("readonly", "#dff6df")],
                  foreground=[("readonly", "#111111")])
        style.configure("History.TCombobox", fieldbackground="#ffffff", background="#ffffff",
                        foreground="#111111")
        style.map("History.TCombobox",
                  fieldbackground=[("readonly", "#ffffff")],
                  foreground=[("readonly", "#111111")])

        style.configure(
            "Cylon.Horizontal.TProgressbar",
            troughcolor="#0f141b",
            background="#d71920",
            lightcolor="#ff3038",
            darkcolor="#a90f15",
            bordercolor="#0f141b",
        )


    def _build_ui(self):
        header = ttk.Frame(self, padding=(22, 16, 22, 10))
        header.pack(fill="x")

        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="Maple Toolbox", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="One Toolbox to run them all.", style="Tagline.TLabel").pack(anchor="w")

        ttk.Button(header, text="About", command=self.show_about).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Settings", command=self.open_settings).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="GitHub", command=self.open_capture_github).pack(side="right", padx=(8, 0))

        scroller = ScrollFrame(self)
        scroller.pack(fill="both", expand=True)

        body = scroller.inner
        body.configure(padding=(22, 4, 22, 14))

        feedback_bar = ttk.Frame(body)
        feedback_bar.pack(fill="x", pady=(0, 10))
        ttk.Button(
            feedback_bar,
            text="Send Feedback / Report a Problem",
            command=self.send_feedback,
        ).pack(side="right")

        self._build_directory_health(body)
        self._build_prerequisites(body)
        self._build_update_manager(body)
        self._build_capture(body)
        self._build_mapleocr(body)
        self._build_bismirpg(body)
        self._build_zip(body)
        self._build_future_modules(body)

        footer = ttk.Frame(self, padding=(22, 10, 22, 14))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Subtle.TLabel").pack(side="left")
        ttk.Label(footer, text=f"Maple Toolbox {APP_VERSION}", style="Subtle.TLabel").pack(side="left", padx=(40, 0))
        ttk.Button(footer, text="Open Toolbox Folder", command=self.open_toolbox_folder).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Exit", style="Danger.TButton", command=self.destroy).pack(side="right")

    def card(self, parent, padding=18):
        frame = ttk.Frame(parent, style="Card.TFrame", padding=padding)
        frame.pack(fill="x", pady=(0, 12))
        return frame

    def _configure_four_columns(self, card):
        for i in range(4):
            card.columnconfigure(i, weight=1, uniform="modulecols")

    def _section_header(self, card, title, description=None, right_textvariable=None):
        ttk.Label(card, text=title, style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        if right_textvariable is not None:
            ttk.Label(card, textvariable=right_textvariable, style="CardSubtle.TLabel").grid(
                row=0, column=3, sticky="e"
            )
        if description:
            ttk.Label(card, text=description, style="CardSubtle.TLabel").grid(
                row=1, column=0, columnspan=4, sticky="w", pady=(5, 14)
            )
            return 2
        return 1

    def _operating_folder_row(self, card, start_row, variable, select_command, open_command):
        ttk.Label(card, text="Operating Folder", style="CardSubtle.TLabel").grid(
            row=start_row, column=0, columnspan=4, sticky="w", pady=(0, 6)
        )
        ttk.Entry(card, textvariable=variable).grid(
            row=start_row + 1, column=0, columnspan=2, sticky="ew", padx=(0, 8)
        )
        ttk.Button(card, text="Select Operating Folder", command=select_command).grid(
            row=start_row + 1, column=2, sticky="ew", padx=4
        )
        ttk.Button(card, text="Open Folder", command=open_command).grid(
            row=start_row + 1, column=3, sticky="ew", padx=(4, 0)
        )
        return start_row + 2

    def _build_update_manager(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)

        row = self._section_header(
            card,
            "3. GitHub Update Manager",
            "Checks Maple Toolbox and supported modules against public GitHub releases."
        )

        ttk.Button(
            card, text="Check for Updates", style="Accent.TButton",
            command=self.check_updates
        ).grid(row=row, column=0, sticky="ew", padx=(0, 6))

        ttk.Button(
            card, text="Refresh Status",
            command=self.refresh_update_status
        ).grid(row=row, column=1, sticky="ew", padx=6)

        ttk.Label(
            card, textvariable=self.last_checked_var, style="CardSubtle.TLabel"
        ).grid(row=row, column=2, sticky="w", padx=8)

        ttk.Button(
            card, text="Open Updates Log", command=self.open_updates_log
        ).grid(row=row, column=3, sticky="ew", padx=(6, 0))

        metrics = ttk.Frame(card, style="Card.TFrame")
        metrics.grid(row=row + 1, column=0, columnspan=4, sticky="ew", pady=(16, 6))
        for i in range(3):
            metrics.columnconfigure(i, weight=1, uniform="metrics")

        self._update_metric(metrics, 0, "Up to date", self.up_to_date_var)
        self._update_metric(metrics, 1, "Update available", self.update_available_var)
        self._update_metric(metrics, 2, "Not installed", self.not_installed_var)

        ttk.Label(
            card, text="Update status", style="CardSubtle.TLabel"
        ).grid(row=row + 2, column=0, columnspan=4, sticky="w", pady=(10, 5))

        self.update_actions_frame = ttk.Frame(card, style="Card.TFrame")
        self.update_actions_frame.grid(
            row=row + 3, column=0, columnspan=4, sticky="ew"
        )
        for i in range(4):
            self.update_actions_frame.columnconfigure(i, weight=1, uniform="updateactions")

        ttk.Label(
            self.update_actions_frame,
            textvariable=self.update_details_var,
            style="Card.TLabel",
            wraplength=1000,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=(0, 6))

    def _update_metric(self, parent, col, label, variable):
        box = ttk.Frame(parent, style="Card.TFrame", padding=(12, 6))
        box.grid(row=0, column=col, sticky="ew")
        ttk.Label(box, textvariable=variable, style="Metric.TLabel").pack(anchor="center")
        ttk.Label(box, text=label, style="CardSubtle.TLabel").pack(anchor="center")

    def _build_prerequisites(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)
        self.prereq_card = card

        row = self._section_header(
            card,
            "2. System Requirements",
            "Checks prerequisites visibly. Nothing is installed or changed without your approval."
        )

        self.prereq_actions = ttk.Frame(card, style="Card.TFrame")
        self.prereq_actions.grid(
            row=row, column=0, columnspan=4, sticky="ew"
        )
        self._configure_four_columns(self.prereq_actions)

        ttk.Button(
            self.prereq_actions,
            text="Check Requirements",
            style="Accent.TButton",
            command=self.check_prerequisites,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ttk.Button(
            self.prereq_actions,
            text="Install Missing Requirements",
            command=self.install_missing_requirements,
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Button(
            self.prereq_actions,
            text="Re-check",
            command=self.check_prerequisites,
        ).grid(row=0, column=2, sticky="ew", padx=6)

        ttk.Button(
            self.prereq_actions,
            text="Open Windows Terminal",
            command=self.open_visible_terminal,
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        self.prereq_summary_frame = ttk.Frame(card, style="Card.TFrame")
        self.prereq_summary_frame.grid(
            row=row, column=0, columnspan=4, sticky="ew"
        )
        self.prereq_summary_frame.columnconfigure(0, weight=1)
        ttk.Label(
            self.prereq_summary_frame,
            text="✓ System Requirements — All OK",
            style="Good.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.prereq_toggle_button = ttk.Button(
            self.prereq_summary_frame,
            text="Show Details",
            command=self.toggle_prerequisite_details,
        )
        self.prereq_toggle_button.grid(row=0, column=1, sticky="e")
        self.prereq_summary_frame.grid_remove()

        self.prereq_frame = ttk.Frame(card, style="Card.TFrame")
        self.prereq_frame.grid(
            row=row + 1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(14, 0),
        )

        ttk.Label(
            self.prereq_frame,
            textvariable=self.prereq_summary_var,
            style="Card.TLabel",
            justify="left",
            wraplength=1000,
        ).grid(row=0, column=0, sticky="w")

    def _build_directory_health(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)
        self.directory_health_card = card

        row = self._section_header(
            card,
            "1. Directory Health",
            "Checks configured folders and can create only safe missing folders."
        )

        self.directory_health_actions = ttk.Frame(card, style="Card.TFrame")
        self.directory_health_actions.grid(
            row=row, column=0, columnspan=4, sticky="ew"
        )
        self._configure_four_columns(self.directory_health_actions)

        ttk.Button(
            self.directory_health_actions,
            text="Check Directories",
            style="Accent.TButton",
            command=self.check_directory_health,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ttk.Button(
            self.directory_health_actions,
            text="Create Safe Missing Folders",
            command=self.create_safe_missing_folders,
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Button(
            self.directory_health_actions,
            text="Open Errors Folder",
            command=self.open_errors_folder,
        ).grid(row=0, column=2, sticky="ew", padx=6)

        ttk.Button(
            self.directory_health_actions,
            text="Re-check",
            command=self.check_directory_health,
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        self.directory_health_summary_frame = ttk.Frame(card, style="Card.TFrame")
        self.directory_health_summary_frame.grid(
            row=row, column=0, columnspan=4, sticky="ew"
        )
        self.directory_health_summary_frame.columnconfigure(0, weight=1)
        ttk.Label(
            self.directory_health_summary_frame,
            text="✓ Directory Health — All OK",
            style="Good.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.directory_health_toggle_button = ttk.Button(
            self.directory_health_summary_frame,
            text="Show Details",
            command=self.toggle_directory_health_details,
        )
        self.directory_health_toggle_button.grid(row=0, column=1, sticky="e")
        self.directory_health_summary_frame.grid_remove()

        self.directory_health_frame = ttk.Frame(card, style="Card.TFrame")
        self.directory_health_frame.grid(
            row=row + 1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(14, 0),
        )

        ttk.Label(
            self.directory_health_frame,
            textvariable=self.directory_health_var,
            style="Card.TLabel",
            justify="left",
            wraplength=1000,
        ).grid(row=0, column=0, sticky="w")

    def _build_capture(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)

        row = self._section_header(
            card,
            "4. Equipment Bag Screenshot Capture Tool",
            "Automated screenshot capture for the equipment bag.",
            self.capture_github_var
        )

        row = self._operating_folder_row(
            card, row, self.capture_dir_var,
            lambda: self.select_module_folder("capture"),
            lambda: self.open_module_folder("capture")
        )

        status = ttk.Frame(card, style="Card.TFrame")
        status.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(12, 12))
        status.columnconfigure(0, weight=1)
        status.columnconfigure(1, weight=1)
        ttk.Label(status, textvariable=self.capture_installed_var, style="Good.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(status, textvariable=self.capture_update_var, style="Warn.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        row += 1

        buttons = [
            ("Launch Capture", self.launch_capture, "Accent.TButton"),
            ("Calibrate", self.launch_capture_calibration, None),
            ("Bag Screenshots", lambda: self.open_folder("screenshots"), None),
            ("Equipped Screenshots", lambda: self.open_folder("screenshots/Equipped"), None),
            ("Refresh Status", self.refresh_status, None),
            ("GitHub Release", self.open_capture_github, None),
        ]

        for idx, (label, command, style_name) in enumerate(buttons):
            r = row + idx // 3
            c = idx % 3
            kwargs = {"style": style_name} if style_name else {}
            ttk.Button(card, text=label, command=command, **kwargs).grid(
                row=r, column=c, sticky="ew",
                padx=(0 if c == 0 else 6, 0 if c == 2 else 6),
                pady=(0 if r == row else 8, 0)
            )

    def _build_mapleocr(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)

        row = self._section_header(card, "5. MapleOCR")

        row = self._operating_folder_row(
            card, row, self.mapleocr_dir_var,
            lambda: self.select_module_folder("mapleocr"),
            lambda: self.open_module_folder("mapleocr")
        )

        status = ttk.Frame(card, style="Card.TFrame")
        status.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(12, 12))
        status.columnconfigure(0, weight=3)
        status.columnconfigure(1, weight=1)

        ttk.Label(
            status, textvariable=self.importer_var, style="CardSubtle.TLabel"
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            status, textvariable=self.mapleocr_release_var, style="Good.TLabel"
        ).grid(row=0, column=1, sticky="e")
        row += 1

        # Primary OCR actions
        ttk.Button(
            card, text="Dry Run", style="Accent.TButton",
            command=lambda: self.run_ocr(True)
        ).grid(row=row, column=0, sticky="ew", padx=(0, 6))

        ttk.Button(
            card, text="Real Run", style="Green.TButton",
            command=lambda: self.run_ocr(False)
        ).grid(row=row, column=1, sticky="ew", padx=6)

        ttk.Button(
            card, text="Open Output", command=self.open_output
        ).grid(row=row, column=2, sticky="ew", padx=6)

        ttk.Button(
            card, text="Open mapleupload", command=self.open_mapleupload
        ).grid(row=row, column=3, sticky="ew", padx=(6, 0))
        row += 1

        # Navigation/update actions
        ttk.Button(
            card, text="Open MapleOCR Folder",
            command=self.open_mapleocr_folder
        ).grid(row=row, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))

        ttk.Button(
            card, text="Open mapleexport",
            command=self.open_mapleexport
        ).grid(row=row, column=1, sticky="ew", padx=6, pady=(8, 0))

        ttk.Button(
            card, text="GitHub Repository",
            command=lambda: self.open_module_github("mapleocr")
        ).grid(row=row, column=2, sticky="ew", padx=6, pady=(8, 0))

        ttk.Button(
            card, text="Get Release / Update",
            command=lambda: self.open_module_release("mapleocr")
        ).grid(row=row, column=3, sticky="ew", padx=(6, 0), pady=(8, 0))
        row += 1

        metrics = ttk.Frame(card, style="Card.TFrame")
        metrics.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        for i in range(3):
            metrics.columnconfigure(i, weight=1, uniform="ocrmetrics")

        self._ocr_metric(metrics, 0, "Bag screenshots", self.bag_count_var)
        self._ocr_metric(metrics, 1, "Equipped screenshots", self.equipped_count_var)
        self._ocr_metric(metrics, 2, "Latest ZIP", self.zip_var)

    def _ocr_metric(self, parent, col, label, variable):
        box = ttk.Frame(parent, style="Card.TFrame", padding=(12, 6))
        box.grid(row=0, column=col, sticky="ew")
        ttk.Label(box, text=label, style="CardSubtle.TLabel").pack(anchor="w")
        ttk.Label(box, textvariable=variable, style="Good.TLabel").pack(anchor="w", pady=(3, 0))

    def _build_zip(self, parent):
        card = self.card(parent)
        for i in range(3):
            card.columnconfigure(i, weight=1, uniform="zipcols")

        row = self._section_header(
            card,
            "7. ZIP Inspector",
            "Reads files directly inside Output ZIPs. Nothing is extracted."
        )

        ttk.Button(card, text="Open Latest ZIP", style="Accent.TButton",
                   command=self.open_latest_zip).grid(
            row=row, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(card, text="Choose ZIP...", command=self.choose_zip).grid(
            row=row, column=1, sticky="ew", padx=6
        )
        ttk.Button(card, text="Open mapleexport", command=self.open_mapleexport).grid(
            row=row, column=2, sticky="ew", padx=(6, 0)
        )

    def _build_future_modules(self, parent):
        self._release_module_card(
            parent,
            "8. MapleForge",
            None,
            self.mapleforge_dir_var,
            "mapleforge",
            self.mapleforge_release_var,
            coming_soon=True,
        )

    def _build_bismirpg(self, parent):
        card = self.card(parent)
        self._configure_four_columns(card)

        row = self._section_header(
            card,
            "6. BISMIRPG",
            "BIS report / Lock-Unlock report module — fresh optimiser export required before BIS report.",
        )
        row = self._operating_folder_row(
            card,
            row,
            self.bismirpg_dir_var,
            lambda: self.select_module_folder("bismirpg"),
            lambda: self.open_module_folder("bismirpg"),
        )

        ttk.Label(
            card, textvariable=self.bismirpg_release_var, style="Good.TLabel"
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 10))
        ttk.Label(
            card, text="REPORT GENERATOR ACTIVE", style="Good.TLabel"
        ).grid(row=row, column=2, columnspan=2, sticky="e", pady=(12, 10))
        row += 1

        ttk.Button(
            card, text="Generate BIS Report", style="Accent.TButton",
            command=self.run_bismirpg_report,
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=(0, 6))
        ttk.Button(
            card, text="Open BIS Reports",
            command=self.open_bismirpg_reports,
        ).grid(row=row, column=2, columnspan=2, sticky="ew", padx=(6, 0))
        row += 1

        # Report picker: defaults to newest PDF and allows older generated reports.
        report_box = ttk.Frame(card, style="Card.TFrame")
        report_box.grid(
            row=row, column=0, columnspan=4, sticky="ew", pady=(12, 0)
        )
        report_box.columnconfigure(1, weight=1)

        ttk.Label(
            report_box,
            text="Generated BIS Report",
            style="CardSubtle.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.bis_report_combo = ttk.Combobox(
            report_box,
            textvariable=self.bis_report_var,
            state="readonly",
            style="History.TCombobox",
        )
        self.bis_report_combo.grid(row=0, column=1, sticky="ew")
        self.bis_report_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._update_selected_bis_report_detail(),
        )

        ttk.Button(
            report_box,
            text="Refresh Reports",
            command=self.refresh_bis_report_picker,
        ).grid(row=0, column=2, sticky="ew", padx=(10, 0))

        ttk.Label(
            report_box,
            textvariable=self.bis_report_detail_var,
            style="CardSubtle.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 0))
        ttk.Label(
            report_box,
            textvariable=self.bis_baseline_var,
            style="Good.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(7, 0))
        row += 1

        ttk.Button(
            card,
            text="Open Selected Report",
            command=self.open_selected_bis_report,
        ).grid(row=row, column=0, sticky="ew", padx=(0, 4), pady=(8, 0))
        ttk.Button(
            card,
            text="Open Lock-Unlock TXT",
            command=self.open_selected_bis_text,
        ).grid(row=row, column=1, sticky="ew", padx=4, pady=(8, 0))
        ttk.Button(
            card,
            text="Approve Current BIS",
            command=self.approve_current_bis,
        ).grid(row=row, column=2, columnspan=2, sticky="ew", padx=(4, 0), pady=(8, 0))
        row += 1

        ttk.Button(
            card, text="GitHub Repository",
            command=lambda: self.open_module_github("bismirpg"),
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=(0, 6), pady=(8, 0))
        ttk.Button(
            card, text="Get Release / Update",
            command=lambda: self.open_module_release("bismirpg"),
        ).grid(row=row, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=(8, 0))

    def _release_module_card(
        self,
        parent,
        title,
        description,
        variable,
        module_key,
        release_var,
        coming_soon=False,
    ):
        card = self.card(parent)
        self._configure_four_columns(card)

        row = self._section_header(card, title, description)

        row = self._operating_folder_row(
            card,
            row,
            variable,
            lambda key=module_key: self.select_module_folder(key),
            lambda key=module_key: self.open_module_folder(key),
        )

        ttk.Label(
            card,
            textvariable=release_var,
            style="Good.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 10))

        if coming_soon:
            ttk.Label(
                card,
                text="COMING SOON",
                style="Teaser.TLabel",
            ).grid(row=row, column=2, columnspan=2, sticky="e", pady=(12, 10))
        else:
            ttk.Label(
                card,
                text="RELEASE TRACKING ACTIVE",
                style="Good.TLabel",
            ).grid(row=row, column=2, columnspan=2, sticky="e", pady=(12, 10))

        row += 1

        ttk.Button(
            card,
            text="GitHub Repository",
            command=lambda key=module_key: self.open_module_github(key),
        ).grid(
            row=row, column=0, columnspan=2,
            sticky="ew", padx=(0, 6)
        )

        ttk.Button(
            card,
            text="Get Release / Update",
            command=lambda key=module_key: self.open_module_release(key),
        ).grid(
            row=row, column=2, columnspan=2,
            sticky="ew", padx=(6, 0)
        )

    def _bismirpg_reports_dir(self) -> Path:
        folder = self.module_folder("bismirpg")
        if not folder:
            raise FileNotFoundError("BISMIRPG Operating Folder is not set.")
        return folder / "Reports"

    def open_bismirpg_reports(self):
        try:
            reports = self._bismirpg_reports_dir()
            reports.mkdir(parents=True, exist_ok=True)
            open_path(reports)
        except Exception as exc:
            messagebox.showerror("Could not open BIS Reports", str(exc))

    def _discover_bis_reports(self):
        """Return generated BIS PDFs newest first, paired to their TXT where possible."""
        try:
            reports = self._bismirpg_reports_dir()
        except Exception:
            return []

        if not reports.exists():
            return []

        found = []
        for pdf in reports.glob("*.pdf"):
            try:
                modified = pdf.stat().st_mtime
            except OSError:
                continue

            # Current Toolbox generator gives PDF/TXT the exact same timestamp suffix.
            txt = None
            suffix_match = re.search(r"(\d{8}_\d{6})", pdf.stem)
            if suffix_match:
                stamp = suffix_match.group(1)
                candidates = sorted(
                    reports.glob(f"*Lock*Unlock*{stamp}*.txt")
                )
                if candidates:
                    txt = candidates[0]

            if txt is None:
                # v1.0.0 names reports by report date rather than second-level timestamp.
                date_match = re.search(r"(\d{8})", pdf.stem)
                if date_match:
                    date_token = date_match.group(1)
                    candidates = sorted(
                        reports.glob(f"*Lock*Unlock*{date_token}*.txt")
                    )
                    if candidates:
                        txt = candidates[0]

            if txt is None:
                # Fallback: nearest lock/unlock TXT by modification time.
                txt_candidates = list(reports.glob("*.txt"))
                if txt_candidates:
                    txt = min(
                        txt_candidates,
                        key=lambda p: abs(p.stat().st_mtime - modified),
                    )
                    try:
                        if abs(txt.stat().st_mtime - modified) > 120:
                            txt = None
                    except OSError:
                        txt = None

            found.append({
                "pdf": pdf,
                "txt": txt,
                "modified": modified,
            })

        found.sort(key=lambda item: item["modified"], reverse=True)
        return found

    def refresh_bis_report_picker(self):
        reports = self._discover_bis_reports()
        self._bis_report_paths = {}

        if not reports:
            self.bis_report_var.set("No BIS reports found")
            self.bis_report_detail_var.set(
                "No generated BIS PDFs found in the BISMIRPG Reports folder."
            )
            try:
                self.bis_report_combo["values"] = ()
            except (AttributeError, tk.TclError):
                pass
            return

        labels = []
        for idx, item in enumerate(reports):
            pdf = item["pdf"]
            when = datetime.fromtimestamp(item["modified"]).strftime("%Y-%m-%d %H:%M:%S")
            prefix = "LATEST — " if idx == 0 else ""
            label = f"{prefix}{when} — {pdf.name}"
            labels.append(label)
            self._bis_report_paths[label] = item

        try:
            self.bis_report_combo["values"] = labels
        except (AttributeError, tk.TclError):
            pass

        current = self.bis_report_var.get()
        if current not in self._bis_report_paths:
            self.bis_report_var.set(labels[0])

        self._update_selected_bis_report_detail()
        self.refresh_bis_baseline_status()

    def _selected_bis_report(self):
        return self._bis_report_paths.get(self.bis_report_var.get())

    def _update_selected_bis_report_detail(self):
        item = self._selected_bis_report()
        if not item:
            self.bis_report_detail_var.set("No BIS report selected.")
            try:
                self.bis_report_combo.configure(style="History.TCombobox")
            except (AttributeError, tk.TclError):
                pass
            return

        try:
            if self.bis_report_var.get().startswith("LATEST"):
                self.bis_report_combo.configure(style="Latest.TCombobox")
            else:
                self.bis_report_combo.configure(style="History.TCombobox")
        except (AttributeError, tk.TclError):
            pass

        pdf = item["pdf"]
        txt = item.get("txt")
        try:
            when = datetime.fromtimestamp(item["modified"]).strftime("%A %d %B %Y, %H:%M:%S")
        except Exception:
            when = "Unknown time"

        txt_status = txt.name if txt else "No matching Lock-Unlock TXT found"
        self.bis_report_detail_var.set(
            f"{when}  |  PDF: {pdf.name}  |  TXT: {txt_status}"
        )

    def open_selected_bis_report(self):
        item = self._selected_bis_report()
        if not item:
            messagebox.showinfo(
                "BIS Report",
                "No generated BIS report is selected.\n\n"
                "Generate a BIS report or click Refresh Reports."
            )
            return
        try:
            open_path(item["pdf"])
        except Exception as exc:
            messagebox.showerror("Could not open BIS Report", str(exc))

    def open_selected_bis_text(self):
        item = self._selected_bis_report()
        if not item:
            messagebox.showinfo(
                "Lock-Unlock Report",
                "No generated BIS report is selected."
            )
            return

        txt = item.get("txt")
        if not txt or not txt.exists():
            messagebox.showinfo(
                "Lock-Unlock Report",
                "No matching Lock-Unlock TXT was found for the selected PDF."
            )
            return

        try:
            open_path(txt)
        except Exception as exc:
            messagebox.showerror("Could not open Lock-Unlock TXT", str(exc))

    def _watch_for_new_bis_report(self, existing_pdfs: set[Path], attempts: int = 180):
        """Refresh the picker when a newly generated report appears."""
        if attempts <= 0:
            return
        try:
            reports = self._bismirpg_reports_dir()
            current = set(reports.glob("*.pdf")) if reports.exists() else set()
            if current - existing_pdfs:
                self.refresh_bis_report_picker()
                self.status_var.set("New BIS report detected — report list refreshed")
                return
        except Exception:
            return

        self.after(
            1000,
            self._watch_for_new_bis_report,
            existing_pdfs,
            attempts - 1,
        )

    def _approved_bis_baseline_path(self):
        bis_folder = self.module_folder("bismirpg")
        if not bis_folder:
            return None
        return bis_folder / "approved_bis_state.json"

    def refresh_bis_baseline_status(self):
        approved = self._approved_bis_baseline_path()
        if approved and approved.exists():
            try:
                when = datetime.fromtimestamp(approved.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                when = "unknown time"
            self.bis_baseline_var.set(f"✓ Approved BIS baseline: {approved.name} — {when}")
        else:
            self.bis_baseline_var.set(
                "⚠ Approved BIS baseline: NONE — changed-cell shading will not appear"
            )

    def approve_current_bis(self):
        reports = self._bismirpg_reports_dir()
        current = reports / "current_bis_state.json"
        approved = self._approved_bis_baseline_path()

        if not current.exists():
            messagebox.showwarning(
                "No BIS state to approve",
                "Generate a BIS report first.\n\n"
                "No current_bis_state.json was found in the Reports folder."
            )
            return
        if approved is None:
            return

        if not messagebox.askyesno(
            "Approve Current BIS",
            "Make the current generated BIS the approved comparison baseline?\n\n"
            "Future BIS reports will shade equipment cells that changed from this approved state.\n\n"
            "Generating a report does NOT approve it automatically."
        ):
            return

        try:
            shutil.copy2(current, approved)
            self.refresh_bis_baseline_status()
            self.status_var.set("Current BIS approved as the comparison baseline")
            messagebox.showinfo(
                "BIS Baseline Approved",
                f"Approved baseline saved to:\n{approved}\n\n"
                "Future reports will compare against this state."
            )
        except Exception as exc:
            messagebox.showerror("Could not approve BIS baseline", str(exc))

    def _current_bis_run_id_from_work(self, work: Path):
        """Best-effort current BIS run ID detection from extracted BIS_stats files."""
        patterns = [
            re.compile(r"(?i)RUN_ID\s*[:=]\s*(\d{8}_\d{6})"),
            re.compile(r"(?i)run[_ -]?id\s*[:=]\s*(\d{8}_\d{6})"),
            re.compile(r"(\d{8}_\d{6})"),
        ]

        candidates = []
        for p in work.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".txt", ".csv", ".json"}:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for pattern in patterns:
                m = pattern.search(text)
                if m:
                    candidates.append(m.group(1))
                    break

        # Prefer the most common run ID across the handoff files.
        if candidates:
            from collections import Counter
            return Counter(candidates).most_common(1)[0][0]
        return None

    def _approved_bis_run_id(self, baseline: Path | None):
        if not baseline or not baseline.exists():
            return None
        try:
            data = json.loads(baseline.read_text(encoding="utf-8"))
        except Exception:
            return None

        for key in ("run_id", "RUN_ID", "runId"):
            value = data.get(key)
            if value:
                return str(value)

        # Fallback: recursive string search for a timestamp-like run ID.
        try:
            raw = json.dumps(data)
            m = re.search(r"(\d{8}_\d{6})", raw)
            return m.group(1) if m else None
        except Exception:
            return None

    def run_bismirpg_report(self):
        bis_folder = self.module_folder("bismirpg")
        if not bis_folder or not bis_folder.exists():
            messagebox.showwarning(
                "BISMIRPG not installed",
                "Select or install the BISMIRPG Operating Folder first."
            )
            return

        generator = bis_folder / "bis_report_generator.py"
        if not generator.exists():
            messagebox.showwarning(
                "BISMIRPG generator not found",
                f"Could not find:\n{generator}\n\nUse Get Release / Update first."
            )
            return

        source_zip = self.root_path() / "BIS_stats.zip"
        if not source_zip.exists():
            chosen = filedialog.askopenfilename(
                title="Choose BIS_stats.zip",
                filetypes=[("BIS stats ZIP", "*.zip"), ("All files", "*.*")],
            )
            if not chosen:
                return
            source_zip = Path(chosen)

        reports = bis_folder / "Reports"
        reports.mkdir(parents=True, exist_ok=True)
        work = bis_folder / ".toolbox_bis_work"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(source_zip, "r") as zf:
                zf.extractall(work)
        except Exception as exc:
            messagebox.showerror("Could not read BIS_stats.zip", str(exc))
            return

        def find_one(name):
            hits = list(work.rglob(name))
            return hits[0] if hits else None

        export = find_one("mapleexport.txt")
        status = find_one("lock_status.txt")
        csv_hits = sorted(work.rglob("import_review_easyocr_v*.csv"))
        review_csv = csv_hits[-1] if csv_hits else None

        missing = []
        if not export: missing.append("mapleexport.txt")
        if not status: missing.append("lock_status.txt")
        if not review_csv: missing.append("import_review_easyocr_vXXX.csv")
        if missing:
            messagebox.showerror(
                "BIS_stats.zip is incomplete",
                "Missing required file(s):\n\n" + "\n".join(missing)
            )
            return

        # Validate that the optimiser export and OCR lock snapshot belong to the
        # same current equipment state before the BIS generator is allowed to run.
        # This catches stale mapleexport.txt files early, with a useful message,
        # instead of letting the report crash later on a missing equipment ID.
        try:
            export_data = json.loads(export.read_text(encoding="utf-8"))
            export_item_ids = set()

            for arr in export_data.get("comparisonItemsBySlot", {}).values():
                for item in arr or []:
                    if isinstance(item, dict) and item.get("id") is not None:
                        export_item_ids.add(int(item["id"]))

            for item in export_data.get("equippedItemsBySlot", {}).values():
                if isinstance(item, dict) and item.get("id") is not None:
                    export_item_ids.add(int(item["id"]))

            lock_ids = set()
            for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(("locked|", "unlocked|")):
                    parts = line.split("|", 6)
                    if len(parts) >= 3:
                        try:
                            lock_ids.add(int(parts[2]))
                        except ValueError:
                            pass

            # Preset IDs are the critical failure mode: the report must be able
            # to resolve every non-empty preset item against the current export.
            preset_ids = set()
            preset_refs = []
            preset_names = export_data.get("equipmentPresetNames", [])
            for idx, preset in enumerate(export_data.get("equipmentPresets", [])):
                if not isinstance(preset, dict):
                    continue
                pname = (
                    str(preset_names[idx])
                    if idx < len(preset_names)
                    else f"Preset {idx + 1}"
                )
                for slot, iid in preset.items():
                    if iid in (None, "", 0):
                        continue
                    try:
                        iid_int = int(iid)
                    except (TypeError, ValueError):
                        continue
                    preset_ids.add(iid_int)
                    preset_refs.append((iid_int, pname, str(slot)))

            # OCR Equipped rows are authoritative for Basic, so those IDs must
            # also exist in the fresh optimiser export. Otherwise the report will
            # replace Basic with an ID it cannot resolve and later crash.
            equipped_ids = set()
            equipped_refs = []
            for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.startswith(("locked|", "unlocked|")):
                    continue
                parts = line.split("|", 6)
                if len(parts) < 6:
                    continue
                try:
                    iid = int(parts[2])
                except ValueError:
                    continue
                slot = parts[1]
                source_name = parts[4].strip().lower()
                if source_name == "equipped":
                    equipped_ids.add(iid)
                    equipped_refs.append((iid, slot))

            unresolved_presets = sorted(preset_ids - export_item_ids)
            unresolved_equipped = sorted(equipped_ids - export_item_ids)

            if unresolved_presets or unresolved_equipped:
                details = []

                for iid in unresolved_equipped[:12]:
                    slots = [slot for ref_id, slot in equipped_refs if ref_id == iid]
                    slot_text = ", ".join(slots[:3]) if slots else "Basic / Equipped"
                    details.append(f"ID {iid}: OCR Equipped / {slot_text}")

                remaining = max(0, 12 - len(details))
                for iid in unresolved_presets[:remaining]:
                    refs = [
                        f"{pname} / {slot}"
                        for ref_id, pname, slot in preset_refs
                        if ref_id == iid
                    ]
                    ref_text = ", ".join(refs[:3]) if refs else "preset reference"
                    details.append(f"ID {iid}: {ref_text}")

                total_bad = len(set(unresolved_presets) | set(unresolved_equipped))
                extra = ""
                if total_bad > len(details):
                    extra = f"\n...and {total_bad - len(details)} more."

                raise RuntimeError(
                    "The optimiser export is not valid for this BIS run.\n\n"
                    "BISMIRPG found equipment IDs required by the current OCR/optimiser "
                    "state that are missing from mapleexport.txt:\n\n"
                    + "\n".join(details)
                    + extra
                    + "\n\nThis means the OCR scan and optimiser export are not from "
                    "the same equipment state.\n\n"
                    "Correct workflow:\n"
                    "1. Run the current OCR scan.\n"
                    "2. Import the new mapleupload.txt into the optimiser.\n"
                    "3. Export a fresh mapleexport.txt back to MapleOCR.\n"
                    "4. Rebuild/refresh BIS_stats.zip.\n"
                    "5. Run BISMIRPG again."
                )

        except Exception as exc:
            messagebox.showerror(
                "BIS handoff validation failed",
                str(exc)
            )
            return

        # BISMIRPG v1.0.0+ exposes a real command-line interface.
        # Do not patch/edit the generator source. Pass BIS_stats.zip directly.
        state_out = reports / "current_bis_state.json"
        approved_baseline = self._approved_bis_baseline_path()
        baseline_arg = approved_baseline if approved_baseline and approved_baseline.exists() else None
        self.refresh_bis_baseline_status()

        current_run_id = self._current_bis_run_id_from_work(work)
        approved_run_id = self._approved_bis_run_id(baseline_arg)
        allow_same_run = False

        if baseline_arg is not None and current_run_id and approved_run_id and current_run_id == approved_run_id:
            allow_same_run = messagebox.askyesno(
                "Same BIS Run as Approved Baseline",
                f"The current BIS run ({current_run_id}) is the same run as the approved baseline.\n\n"
                "Normally there is nothing useful to compare because no new OCR/optimiser run has occurred.\n\n"
                "For testing, Toolbox can deliberately generate a same-run 0-change report.\n\n"
                "Generate the same-run comparison?"
            )
            if not allow_same_run:
                self.status_var.set("BIS generation cancelled — current run matches approved baseline")
                return

        if baseline_arg is None:
            proceed = messagebox.askyesno(
                "No Approved BIS Baseline",
                "There is no approved BIS baseline yet.\n\n"
                "This report can still be generated, but changed equipment cells WILL NOT be shaded.\n\n"
                "After generating it, use Approve Current BIS to establish the baseline for future comparisons.\n\n"
                "Generate without a shading baseline?"
            )
            if not proceed:
                return

        python_exe = self.root_path() / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_hit = shutil.which("python.exe") or shutil.which("python")
            if not python_hit:
                messagebox.showerror(
                    "Python not found",
                    "BISMIRPG needs Python. Run System Requirements first."
                )
                return
            python_exe = Path(python_hit)

        # Keep execution loud/visible, consistent with the rest of Toolbox.
        # Use a real .cmd file instead of passing a long quoted command through
        # `cmd.exe /k`.  The latter can turn the quoted Python path into a
        # literal command string on some Windows setups.
        launch_cmd = work / "run_bismirpg_from_toolbox.cmd"

        def cmd_escape(value: Path) -> str:
            # Batch SET syntax safely preserves spaces and most punctuation.
            return str(value).replace("%", "%%")

        batch = f"""@echo off
title Maple Toolbox - BISMIRPG report generator
echo Maple Toolbox - BISMIRPG report generator
echo.

set "PY={cmd_escape(python_exe)}"
set "GENERATOR={cmd_escape(generator)}"
set "SOURCE={cmd_escape(source_zip)}"
set "REPORTS={cmd_escape(reports)}"
set "STATEOUT={cmd_escape(state_out)}"
set "BASELINE={cmd_escape(baseline_arg) if baseline_arg else ""}"
set "ALLOW_SAME_RUN={"1" if allow_same_run else "0"}"
set "SHELLLOG={cmd_escape(work / "last_bismirpg_shell_output.txt")}"

> "%SHELLLOG%" echo Maple Toolbox - BISMIRPG report generator
>>"%SHELLLOG%" echo.

echo Checking BISMIRPG requirements...
>>"%SHELLLOG%" echo Checking BISMIRPG requirements...
"%PY%" -c "import reportlab" >nul 2>&1
if errorlevel 1 (
    echo reportlab is missing.
    >>"%SHELLLOG%" echo reportlab is missing.
    echo Installing reportlab visibly...
    >>"%SHELLLOG%" echo Installing reportlab visibly...
    powershell.exe -NoProfile -Command "& '%PY%' -m pip install reportlab 2>&1 | Tee-Object -FilePath '%SHELLLOG%' -Append; exit $LASTEXITCODE"
    if errorlevel 1 goto :failed
)

echo.
echo Generating BIS report...
>>"%SHELLLOG%" echo.
>>"%SHELLLOG%" echo Generating BIS report...
if defined BASELINE (
    echo Comparing against approved BIS baseline...
    >>"%SHELLLOG%" echo Comparing against approved BIS baseline: %BASELINE%
    if "%ALLOW_SAME_RUN%"=="1" (
        echo Same-run baseline explicitly allowed by user for validation.
        >>"%SHELLLOG%" echo Same-run baseline explicitly allowed by user for validation.
        powershell.exe -NoProfile -Command "& '%PY%' '%GENERATOR%' '%SOURCE%' --out-dir '%REPORTS%' --baseline '%BASELINE%' --state-out '%STATEOUT%' --allow-same-run-baseline 2>&1 | Tee-Object -FilePath '%SHELLLOG%' -Append; exit $LASTEXITCODE"
    ) else (
        powershell.exe -NoProfile -Command "& '%PY%' '%GENERATOR%' '%SOURCE%' --out-dir '%REPORTS%' --baseline '%BASELINE%' --state-out '%STATEOUT%' 2>&1 | Tee-Object -FilePath '%SHELLLOG%' -Append; exit $LASTEXITCODE"
    )
) else (
    echo No approved BIS baseline found - generating without change shading baseline.
    >>"%SHELLLOG%" echo No approved BIS baseline found - generating without change shading baseline.
    powershell.exe -NoProfile -Command "& '%PY%' '%GENERATOR%' '%SOURCE%' --out-dir '%REPORTS%' --state-out '%STATEOUT%' 2>&1 | Tee-Object -FilePath '%SHELLLOG%' -Append; exit $LASTEXITCODE"
)
if errorlevel 1 goto :failed

echo.
echo BISMIRPG complete.
echo Reports folder: %REPORTS%
>>"%SHELLLOG%" echo.
>>"%SHELLLOG%" echo BISMIRPG complete.
>>"%SHELLLOG%" echo Reports folder: %REPORTS%
type "%SHELLLOG%" | clip
echo.
echo Output copied to clipboard.
echo.
echo Report picker will refresh in Maple Toolbox.
echo This window will close automatically.
for /l %%S in (8,-1,1) do (
    echo Closing in %%S...
    timeout /t 1 /nobreak >nul
)
echo Closing now.
exit /b 0

:failed
echo.
echo BISMIRPG FAILED. This window will stay open.
>>"%SHELLLOG%" echo.
>>"%SHELLLOG%" echo BISMIRPG FAILED.
type "%SHELLLOG%" | clip
echo Output copied to clipboard.
echo.
pause
"""
        try:
            existing_pdfs = set(reports.glob("*.pdf"))
            launch_cmd.write_text(batch, encoding="utf-8")
            subprocess.Popen(
                ["cmd.exe", "/c", str(launch_cmd)],
                cwd=str(bis_folder),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            self._restore_and_track_console_window(
                "Maple Toolbox - BISMIRPG report generator",
                "shell_window",
            )
            self.status_var.set("BISMIRPG report generator opened")
            self._watch_for_new_bis_report(existing_pdfs)
        except Exception as exc:
            messagebox.showerror("Could not start BISMIRPG", str(exc))

    def _restore_and_track_console_window(self, title_text: str, key: str):
        """Restore a Toolbox-owned shell window and remember where the user moves it."""
        if os.name != "nt":
            return

        def worker():
            hwnd = None
            # Console creation can take a moment.
            for _ in range(60):
                hwnd = _windows_find_window_by_title(title_text)
                if hwnd:
                    break
                time.sleep(0.1)

            if not hwnd:
                return

            saved = saved_window_geometry(key)
            if saved:
                _windows_move_window(hwnd, saved)

            last_geometry = None
            # Keep sampling while the shell exists. This records manual moves/resizes.
            while True:
                try:
                    if not ctypes.windll.user32.IsWindow(hwnd):
                        break
                except Exception:
                    break

                rect = _windows_get_rect(hwnd)
                if rect:
                    width, height, x, y = rect
                    geometry = f"{width}x{height}{x:+d}{y:+d}"
                    if geometry != last_geometry:
                        last_geometry = geometry
                time.sleep(0.5)

            if last_geometry:
                save_window_geometry(key, last_geometry)

        threading.Thread(target=worker, daemon=True).start()

    def prerequisite_status(self):
        checks = []

        online, internet_detail = internet_status()
        checks.append({
            "key": "internet",
            "label": "Internet connection",
            "ok": online,
            "detail": internet_detail,
            "installable": False,
        })

        def found_command(name):
            return shutil.which(name) is not None

        # Windows
        is_windows = os.name == "nt"
        checks.append({
            "key": "windows",
            "label": "Windows",
            "ok": is_windows,
            "detail": "Supported" if is_windows else "Unsupported platform",
            "installable": False,
        })

        # PowerShell
        powershell_ok = found_command("powershell.exe") or found_command("pwsh.exe")
        checks.append({
            "key": "powershell",
            "label": "PowerShell",
            "ok": powershell_ok,
            "detail": "Found" if powershell_ok else "Missing",
            "installable": False,
        })

        # winget
        winget_ok = found_command("winget.exe") or found_command("winget")
        checks.append({
            "key": "winget",
            "label": "Windows Package Manager (winget)",
            "ok": winget_ok,
            "detail": "Found" if winget_ok else "Missing",
            "installable": False,
        })

        # Git
        git_ok = found_command("git.exe") or found_command("git")
        checks.append({
            "key": "git",
            "label": "Git",
            "ok": git_ok,
            "detail": "Found" if git_ok else "Missing",
            "installable": winget_ok,
            "winget_id": "Git.Git",
        })

        # AutoHotkey v2 — common paths, AppData, PATH, file association and winget.
        ahk_ok, ahk_detail = detect_autohotkey_v2()
        checks.append({
            "key": "autohotkey",
            "label": "AutoHotkey v2",
            "ok": ahk_ok,
            "detail": ahk_detail,
            "installable": winget_ok,
            "winget_id": "AutoHotkey.AutoHotkey",
        })

        # ShareX — common paths, PATH and winget.
        sharex_ok, sharex_detail = detect_sharex()
        checks.append({
            "key": "sharex",
            "label": "ShareX",
            "ok": sharex_ok,
            "detail": sharex_detail,
            "installable": winget_ok,
            "winget_id": "ShareX.ShareX",
        })

        # MapleOCR environment
        root = self.root_path()
        importer = latest_importer(root)
        py = root / ".venv" / "Scripts" / "python.exe"
        dry_wrapper = None
        real_wrapper = None
        if importer:
            m = re.search(r"_v(\d+)", importer.name, re.I)
            if m:
                v = m.group(1)
                dry_wrapper = root / f"run_v{v}_full_inventory_dry_run.ps1"
                real_wrapper = root / f"run_v{v}_full_inventory.ps1"

        checks.append({
            "key": "mapleocr_python",
            "label": "MapleOCR Python environment",
            "ok": py.exists(),
            "detail": str(py) if py.exists() else "Missing .venv Python",
            "installable": False,
        })
        checks.append({
            "key": "mapleocr_importer",
            "label": "MapleOCR importer",
            "ok": importer is not None,
            "detail": importer.name if importer else "Missing",
            "installable": False,
        })
        checks.append({
            "key": "mapleocr_dry_wrapper",
            "label": "MapleOCR Dry Run wrapper",
            "ok": bool(dry_wrapper and dry_wrapper.exists()),
            "detail": dry_wrapper.name if dry_wrapper and dry_wrapper.exists() else "Missing",
            "installable": False,
        })
        checks.append({
            "key": "mapleocr_real_wrapper",
            "label": "MapleOCR Real Run wrapper",
            "ok": bool(real_wrapper and real_wrapper.exists()),
            "detail": real_wrapper.name if real_wrapper and real_wrapper.exists() else "Missing",
            "installable": False,
        })

        return checks

    def _set_prerequisite_collapsed(self, collapsed: bool):
        try:
            if collapsed:
                self.prereq_actions.grid_remove()
                self.prereq_frame.grid_remove()
                self.prereq_summary_frame.grid()
                self.prereq_toggle_button.configure(text="Show Details")
            else:
                self.prereq_summary_frame.grid_remove()
                self.prereq_actions.grid()
                self.prereq_frame.grid()
                self.prereq_toggle_button.configure(text="Hide Details")
        except (AttributeError, tk.TclError):
            pass

    def toggle_prerequisite_details(self):
        try:
            if self.prereq_summary_frame.winfo_ismapped():
                self._set_prerequisite_collapsed(False)
            else:
                self._set_prerequisite_collapsed(True)
        except tk.TclError:
            pass

    def _set_directory_health_collapsed(self, collapsed: bool):
        try:
            if collapsed:
                self.directory_health_actions.grid_remove()
                self.directory_health_frame.grid_remove()
                self.directory_health_summary_frame.grid()
                self.directory_health_toggle_button.configure(text="Show Details")
            else:
                self.directory_health_summary_frame.grid_remove()
                self.directory_health_actions.grid()
                self.directory_health_frame.grid()
                self.directory_health_toggle_button.configure(text="Hide Details")
        except (AttributeError, tk.TclError):
            pass

    def toggle_directory_health_details(self):
        try:
            if self.directory_health_summary_frame.winfo_ismapped():
                self._set_directory_health_collapsed(False)
            else:
                self._set_directory_health_collapsed(True)
        except tk.TclError:
            pass

    def _render_prerequisites(self, checks):
        for child in self.prereq_frame.winfo_children():
            child.destroy()

        for row, item in enumerate(checks):
            symbol = "✓" if item["ok"] else "✗"
            style = "Good.TLabel" if item["ok"] else "Warn.TLabel"
            ttk.Label(
                self.prereq_frame,
                text=f"{symbol} {item['label']}",
                style=style,
            ).grid(row=row, column=0, sticky="w", pady=2)

            ttk.Label(
                self.prereq_frame,
                text=item["detail"],
                style="CardSubtle.TLabel",
            ).grid(row=row, column=1, sticky="w", padx=(16, 0), pady=2)

        self.prereq_frame.columnconfigure(0, weight=1)
        self.prereq_frame.columnconfigure(1, weight=2)

        missing = [c for c in checks if not c["ok"]]
        if not missing:
            self.prereq_summary_var.set("All checked requirements are present.")
            self._set_prerequisite_collapsed(True)
        else:
            self.prereq_summary_var.set(
                f"{len(missing)} requirement(s) need attention."
            )
            self._set_prerequisite_collapsed(False)

    def check_prerequisites(self):
        checks = self.prerequisite_status()
        self._render_prerequisites(checks)
        self.status_var.set("System requirements check complete")

    def open_visible_terminal(self):
        try:
            subprocess.Popen(["cmd.exe"], cwd=str(Path.home()))
        except Exception as exc:
            messagebox.showerror("Could not open terminal", str(exc))

    def install_missing_requirements(self):
        checks = self.prerequisite_status()

        online = next(
            (c["ok"] for c in checks if c["key"] == "internet"),
            False,
        )
        if not online:
            messagebox.showwarning(
                "Internet connection required",
                "Installing missing requirements needs an internet connection.\n\n"
                "Connect to the internet, then click Install Missing Requirements again."
            )
            return

        winget_ok = next(
            (c["ok"] for c in checks if c["key"] == "winget"),
            False,
        )
        if not winget_ok:
            messagebox.showwarning(
                "winget required",
                "Windows Package Manager (winget) is not available.\n\n"
                "Toolbox will not attempt a hidden workaround. Install or repair winget, "
                "then run Check Requirements again."
            )
            return

        requested = [
            c for c in checks
            if not c["ok"] and c.get("installable") and c.get("winget_id")
        ]

        if not requested:
            missing_noninstallable = [c for c in checks if not c["ok"]]
            if missing_noninstallable:
                messagebox.showinfo(
                    "Requirements",
                    "There are missing requirements, but none can currently be installed "
                    "automatically with winget from Toolbox.\n\n"
                    "Use the requirement list to fix them manually, then click Re-check."
                )
            else:
                messagebox.showinfo(
                    "Requirements",
                    "All checked requirements are already installed."
                )
            return

        # Search first. If the local source index is stale, refresh visibly later.
        visible = []
        missing_from_source = []
        for item in requested:
            if winget_package_visible(item["winget_id"]):
                visible.append(item)
            else:
                missing_from_source.append(item)

        lines = "\n".join(
            f"- {c['label']} ({c['winget_id']})"
            for c in requested
        )

        if missing_from_source:
            unavailable = "\n".join(
                f"- {c['label']} ({c['winget_id']})"
                for c in missing_from_source
            )

            approved = messagebox.askyesno(
                "winget source refresh required",
                "winget cannot currently find:\n\n"
                f"{unavailable}\n\n"
                "Toolbox can open a visible Command Prompt, run:\n\n"
                "winget source update\n\n"
                "then search again and install any packages it finds.\n\n"
                "Nothing will be hidden. Continue?"
            )
            if not approved:
                return

            ids = " ".join(c["winget_id"] for c in requested)

            shell_log = str((Path(os.environ.get("TEMP", str(Path.home()))) / "MapleToolbox_last_shell_output.txt")).replace("%", "%%")
            cmd_lines = [
                'title Maple Toolbox - Prerequisite Installer',
                f'set "SHELLLOG={shell_log}"',
                '> "%SHELLLOG%" echo Maple Toolbox prerequisite installer',
                'echo Maple Toolbox prerequisite installer',
                'echo.',
                'echo Refreshing winget package sources...',
                'powershell.exe -NoProfile -Command "winget source update 2>&1 | Tee-Object -FilePath \'%SHELLLOG%\' -Append; exit $LASTEXITCODE"',
                'echo.',
            ]

            for c in requested:
                pkg = c["winget_id"]
                label = c["label"]
                cmd_lines.extend([
                    f'echo Checking {label}...',
                    f'powershell.exe -NoProfile -Command "winget search --id \'{pkg}\' --exact 2>&1 | Tee-Object -FilePath \'%SHELLLOG%\' -Append; exit $LASTEXITCODE"',
                    f'if errorlevel 1 (echo PACKAGE NOT FOUND: {pkg} & echo PACKAGE NOT FOUND: {pkg}>>"%SHELLLOG%") else (powershell.exe -NoProfile -Command "winget install --id \'{pkg}\' --exact 2>&1 | Tee-Object -FilePath \'%SHELLLOG%\' -Append; exit $LASTEXITCODE")',
                    'echo.',
                ])

            cmd_lines.extend([
                'echo Install process finished.',
                'echo Return to Maple Toolbox and click Re-check.',
                'echo Return to Maple Toolbox and click Re-check.>>"%SHELLLOG%"',
                'type "%SHELLLOG%" | clip',
                'echo.',
                'echo Output copied to clipboard.',
                'echo This window will close automatically.',
                'for /l %S in (8,-1,1) do @echo Closing in %S... & timeout /t 1 /nobreak >nul',
                'echo Closing now.',
                'exit'
            ])
            final = " & ".join(cmd_lines)

        else:
            approved = messagebox.askyesno(
                "Install Missing Requirements",
                "Toolbox found these packages in winget:\n\n"
                f"{lines}\n\n"
                "A visible Command Prompt will open and run the installs.\n"
                "You will see every command and result.\n\n"
                "Continue?"
            )
            if not approved:
                return

            shell_log = str((Path(os.environ.get("TEMP", str(Path.home()))) / "MapleToolbox_last_shell_output.txt")).replace("%", "%%")
            cmd_lines = [
                'title Maple Toolbox - Prerequisite Installer',
                f'set "SHELLLOG={shell_log}"',
                '> "%SHELLLOG%" echo Maple Toolbox prerequisite installer',
                'echo Maple Toolbox prerequisite installer',
                'echo.',
            ]
            for c in visible:
                pkg = c["winget_id"]
                label = c["label"]
                cmd_lines.extend([
                    f'echo Installing {label}...',
                    f'powershell.exe -NoProfile -Command "winget install --id \'{pkg}\' --exact 2>&1 | Tee-Object -FilePath \'%SHELLLOG%\' -Append; exit $LASTEXITCODE"',
                    'echo.',
                ])
            cmd_lines.extend([
                'echo Install process finished.',
                'echo Return to Maple Toolbox and click Re-check.',
                'echo Return to Maple Toolbox and click Re-check.>>"%SHELLLOG%"',
                'type "%SHELLLOG%" | clip',
                'echo.',
                'echo Output copied to clipboard.',
                'echo This window will close automatically.',
                'for /l %S in (8,-1,1) do @echo Closing in %S... & timeout /t 1 /nobreak >nul',
                'echo Closing now.',
                'exit'
            ])
            final = " & ".join(cmd_lines)

        try:
            subprocess.Popen(
                ["cmd.exe", "/k", final],
                cwd=str(Path.home()),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            self._restore_and_track_console_window(
                "Maple Toolbox - Prerequisite Installer",
                "shell_window",
            )
            self.status_var.set("Visible prerequisite installer opened")
        except Exception as exc:
            messagebox.showerror(
                "Could not start installer",
                str(exc)
            )


    def directory_health_status(self):
        root = self.root_path()
        checks = []

        def add(label, path, safe_create=False):
            checks.append({
                "label": label,
                "path": path,
                "ok": path.exists(),
                "safe_create": safe_create,
            })

        add("Toolbox folder", toolbox_dir(), False)
        add("MapleOCR Operating Folder", root, False)
        add("MapleOCR screenshots", root / "screenshots", True)
        add("MapleOCR Equipped screenshots", root / "screenshots" / "Equipped", True)
        add("MapleOCR Results", root / "Results", True)
        add("MapleOCR Output", root / "Output", True)
        add("MapleOCR .venv", root / ".venv", False)

        capture = self.module_folder("capture")
        if capture:
            add("Screenshot Capture Operating Folder", capture, False)

        mapleforge = self.module_folder("mapleforge")
        if mapleforge:
            add("MapleForge Operating Folder", mapleforge, False)

        bismirpg = self.module_folder("bismirpg")
        if bismirpg:
            add("BISMIRPG Operating Folder", bismirpg, False)

        return checks

    def _render_directory_health(self, checks):
        for child in self.directory_health_frame.winfo_children():
            child.destroy()

        for row, item in enumerate(checks):
            symbol = "✓" if item["ok"] else "✗"
            style = "Good.TLabel" if item["ok"] else "Warn.TLabel"
            ttk.Label(
                self.directory_health_frame,
                text=f"{symbol} {item['label']}",
                style=style,
            ).grid(row=row, column=0, sticky="w", pady=2)

            detail = str(item["path"])
            if not item["ok"] and item["safe_create"]:
                detail += "  [safe to create]"
            ttk.Label(
                self.directory_health_frame,
                text=detail,
                style="CardSubtle.TLabel",
            ).grid(row=row, column=1, sticky="w", padx=(16, 0), pady=2)

        self.directory_health_frame.columnconfigure(0, weight=1)
        self.directory_health_frame.columnconfigure(1, weight=2)

        missing = [c for c in checks if not c["ok"]]
        if missing:
            self.directory_health_var.set(f"{len(missing)} directory item(s) need attention.")
            self._set_directory_health_collapsed(False)
        else:
            self.directory_health_var.set("All checked directories are healthy.")
            self._set_directory_health_collapsed(True)

    def check_directory_health(self):
        checks = self.directory_health_status()
        self._render_directory_health(checks)
        self.status_var.set("Directory health check complete")

    def create_safe_missing_folders(self):
        checks = self.directory_health_status()
        safe_missing = [c for c in checks if not c["ok"] and c["safe_create"]]

        if not safe_missing:
            messagebox.showinfo(
                "Directory Health",
                "There are no safe missing folders to create."
            )
            return

        lines = "\n".join(f"- {c['label']}\n  {c['path']}" for c in safe_missing)
        approved = messagebox.askyesno(
            "Create Safe Missing Folders",
            "Toolbox can create these folders safely:\n\n"
            f"{lines}\n\n"
            "No existing files will be moved or overwritten.\n\n"
            "Continue?"
        )
        if not approved:
            return

        failed = []
        for item in safe_missing:
            try:
                item["path"].mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                failed.append((item, exc))

        if failed:
            text = "\n".join(f"{item['path']}: {exc}" for item, exc in failed)
            log_path = write_error_log(
                "Directory_Health",
                "Create_Folders",
                exception_text=text,
                output=text,
            )
            messagebox.showerror(
                "Directory creation failed",
                "One or more folders could not be created.\n\n"
                + (f"Error log: {log_path}" if log_path else text)
            )
        self.check_directory_health()

    def open_errors_folder(self):
        folder = errors_dir()
        if not folder.exists():
            messagebox.showinfo(
                "Errors Folder",
                "No errors have been logged yet, so the Errors folder does not exist."
            )
            return
        open_path(folder)

    def root_path(self) -> Path:
        value = self.mapleocr_dir_var.get().strip().strip('"')
        return Path(value) if value else DEFAULT_ROOT

    def _save(self):
        self.root_var.set(self.mapleocr_dir_var.get())
        save_config({
            "mapleocr_root": self.mapleocr_dir_var.get(),
            "mapleocr_dir": self.mapleocr_dir_var.get(),
            "capture_dir": self.capture_dir_var.get(),
            "mapleforge_dir": self.mapleforge_dir_var.get(),
            "bismirpg_dir": self.bismirpg_dir_var.get(),
        })

    def module_folder(self, module_key: str) -> Path | None:
        if module_key == "toolbox":
            return toolbox_dir()

        mapping = {
            "capture": self.capture_dir_var,
            "mapleocr": self.mapleocr_dir_var,
            "mapleforge": self.mapleforge_dir_var,
            "bismirpg": self.bismirpg_dir_var,
        }
        value = mapping[module_key].get().strip().strip('"')
        return Path(value) if value else None

    def select_module_folder(self, module_key: str):
        current = self.module_folder(module_key)
        initial = str(current) if current else str(Path.home())

        chosen = filedialog.askdirectory(
            title="Select Operating Folder",
            initialdir=initial,
        )
        if not chosen:
            return

        folder = Path(chosen)
        validators = {
            "capture": self.validate_capture_folder,
            "mapleocr": self.validate_mapleocr_folder,
        }
        validator = validators.get(module_key)

        if validator:
            ok, detail = validator(folder)
            if not ok:
                messagebox.showwarning("Operating Folder Check", detail)
                return

        mapping = {
            "capture": self.capture_dir_var,
            "mapleocr": self.mapleocr_dir_var,
            "mapleforge": self.mapleforge_dir_var,
            "bismirpg": self.bismirpg_dir_var,
        }
        mapping[module_key].set(str(folder))
        self._save()
        self.refresh_status()

    def open_module_folder(self, module_key: str):
        folder = self.module_folder(module_key)
        if not folder:
            messagebox.showwarning("Operating Folder", "No Operating Folder has been selected for this module.")
            return
        if not folder.exists():
            messagebox.showwarning("Operating Folder", f"The selected Operating Folder does not exist:\n\n{folder}")
            return
        open_path(folder)

    def validate_capture_folder(self, folder: Path):
        required = ["EquipmentBagCaptureTool.ahk", "EquipmentBagCaptureCalibration.ahk"]
        missing = [name for name in required if not (folder / name).exists()]
        if missing:
            return False, (
                "This does not look like the Equipment Bag Capture Tool folder.\n\n"
                "Missing:\n- " + "\n- ".join(missing)
            )
        return True, "OK"

    def validate_mapleocr_folder(self, folder: Path):
        importer = latest_importer(folder)
        python_exe = folder / ".venv" / "Scripts" / "python.exe"
        missing = []
        if not importer:
            missing.append("maple_batch_importer_easyocr_vXXX.py")
        if not python_exe.exists():
            missing.append(r".venv\Scripts\python.exe")
        if missing:
            return False, (
                "This does not look like a complete MapleOCR Operating Folder.\n\n"
                "Missing:\n- " + "\n- ".join(missing)
            )
        return True, "OK"

    def module_repo(self, module_key: str) -> str:
        # For known Toolbox modules, the public repository name is authoritative.
        # Do not let an old/misconfigured local git remote break release checks.
        if module_key in MODULE_REPOS:
            return MODULE_REPOS[module_key]

        folder = self.module_folder(module_key)
        detected = git_origin_repo(folder)
        if detected:
            return detected

        raise KeyError(module_key)

    def open_module_github(self, module_key: str):
        repo = self.module_repo(module_key)
        try:
            os.startfile(github_repo_web(repo))
        except Exception as exc:
            messagebox.showerror("Could not open GitHub", str(exc))

    def open_module_release(self, module_key: str):
        repo = self.module_repo(module_key)
        try:
            os.startfile(github_release_web(repo))
        except Exception as exc:
            messagebox.showerror("Could not open GitHub Release", str(exc))

    def module_local_version(self, module_key: str) -> str | None:
        if module_key == "toolbox":
            return APP_VERSION

        folder = self.module_folder(module_key)

        if module_key == "mapleocr":
            return importer_version(latest_importer(self.root_path()))

        if module_key == "capture":
            if folder and folder.exists():
                value = self.capture_version(folder)
                return value if value and value != "Unknown" else None
            return None

        if module_key == "bismirpg":
            # BISMIRPG releases may omit VERSION. Prefer public semantic versions
            # from README/release notes (v1.0.0) over internal OCR markers (v195).
            if folder and (folder / "bis_report_generator.py").exists():
                return (
                    local_version_from_folder(folder)
                    or detected_version_from_module_files(folder)
                )
            return None

        return local_version_from_folder(folder)

    def _set_release_var(self, module_key: str, text: str):
        mapping = {
            "mapleocr": self.mapleocr_release_var,
            "mapleforge": self.mapleforge_release_var,
            "bismirpg": self.bismirpg_release_var,
        }
        var = mapping.get(module_key)
        if var:
            self.after(0, var.set, text)

    def _render_update_actions(self, results: list[dict]):
        for child in self.update_actions_frame.winfo_children():
            child.destroy()

        if not results:
            ttk.Label(
                self.update_actions_frame,
                text="No public releases were found for the configured modules.",
                style="Card.TLabel",
            ).grid(row=0, column=0, columnspan=4, sticky="w")
            return

        row = 0
        for result in results:
            status = result["status"]
            module_key = result["key"]
            label = result["label"]
            local = result.get("local")
            remote = result.get("remote")

            if status == "update":
                text = f"{label}: {local or 'not installed'} → {remote}"
                style = "Warn.TLabel"
                button_text = "Get Update"
            elif status == "not_installed":
                text = f"{label}: not installed — latest release {remote}"
                style = "Warn.TLabel"
                button_text = "Get Release"
            elif status == "current":
                text = f"{label}: {local} — up to date"
                style = "Good.TLabel"
                button_text = "Latest Release"
            elif status == "development":
                text = f"{label}: {local} — development build (latest public {remote})"
                style = "Warn.TLabel"
                button_text = "Latest Public Release"
            else:
                text = f"{label}: no public downloadable release found"
                style = "CardSubtle.TLabel"
                button_text = "GitHub Repository"

            ttk.Label(
                self.update_actions_frame,
                text=text,
                style=style,
            ).grid(
                row=row, column=0, columnspan=3, sticky="w",
                pady=(0 if row == 0 else 6, 0),
            )

            if status in {"update", "not_installed", "current", "development"}:
                command = lambda key=module_key: self.open_module_release(key)
            else:
                command = lambda key=module_key: self.open_module_github(key)

            ttk.Button(
                self.update_actions_frame,
                text=button_text,
                command=command,
            ).grid(
                row=row, column=3, sticky="ew",
                padx=(8, 0),
                pady=(0 if row == 0 else 6, 0),
            )
            row += 1

    def refresh_status(self):
        root = self.root_path()
        self._save()

        importer = latest_importer(root)
        self.importer_var.set(
            f"Detected importer: {importer.name}" if importer else "No MapleOCR importer detected"
        )

        screenshots = root / "screenshots"
        equipped = screenshots / "Equipped"
        self.bag_count_var.set(str(count_images(screenshots)))
        self.equipped_count_var.set(str(count_images(equipped)))

        latest_zip = latest_output_zip(root)
        self.zip_var.set(latest_zip.name if latest_zip else "None detected")

        capture = self.detect_capture_folder()
        if capture:
            self.capture_installed_var.set(f"Installed: {self.capture_version(capture)}")
        else:
            self.capture_installed_var.set("Installed: Not detected")

        self.status_var.set(f"Ready — {root}" if root.exists() else f"MapleOCR root not found — {root}")
        self.refresh_bis_report_picker()

    def choose_capture_folder(self):
        self.select_module_folder("capture")

    def detect_capture_folder(self) -> Path | None:
        folder = self.module_folder("capture")
        if folder and (folder / "EquipmentBagCaptureTool.ahk").exists():
            return folder
        return None

    def capture_version(self, folder: Path) -> str:
        version_file = folder / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8", errors="replace").strip() or "Unknown"
            except Exception:
                pass
        return "Unknown"

    def launch_ahk(self, script: Path, label: str):
        if not script.exists():
            messagebox.showwarning(
                f"{label} not found",
                f"Could not find:\n{script}\n\nSelect the Operating Folder first."
            )
            return
        try:
            os.startfile(str(script))
            self.status_var.set(f"Launched {label}")
        except Exception as exc:
            messagebox.showerror(
                f"Could not launch {label}",
                f"{exc}\n\nMake sure AutoHotkey v2 is installed."
            )

    def launch_capture(self):
        folder = self.detect_capture_folder()
        if not folder:
            messagebox.showwarning(
                "Capture Tool not found",
                "Select the Equipment Bag Capture Tool Operating Folder first."
            )
            return
        self.launch_ahk(folder / "EquipmentBagCaptureTool.ahk", "Equipment Bag Capture")

    def launch_capture_calibration(self):
        folder = self.detect_capture_folder()
        if not folder:
            messagebox.showwarning(
                "Capture Tool not found",
                "Select the Equipment Bag Capture Tool Operating Folder first."
            )
            return
        self.launch_ahk(folder / "EquipmentBagCaptureCalibration.ahk", "Equipment Bag Capture Calibration")

    def open_capture_folder(self):
        self.open_module_folder("capture")

    def open_capture_github(self):
        self.open_module_release("capture")

    def refresh_update_status(self):
        """
        Re-scan local module folders first, then refresh public release status.
        Use this after installing/updating a module without restarting Toolbox.
        """
        self.refresh_status()
        self.check_directory_health()

        self.status_var.set("Refreshing installed modules and release status...")

        # The public release comparison is the second half of the refresh.
        self.check_updates()

    def check_updates(self):
        online, detail = internet_status()
        if not online:
            self.status_var.set("Internet/GitHub connectivity check failed")
            self.capture_update_var.set("")
            messagebox.showwarning(
                "Internet / GitHub check failed",
                "Maple Toolbox could not reach any of its internet test endpoints.\n\n"
                f"{detail}\n\n"
                "Your browser may still have internet even if Python HTTPS is blocked by "
                "a firewall, proxy, antivirus, or certificate problem."
            )
            return

        self.status_var.set("Checking public GitHub releases...")
        self.capture_update_var.set("Checking...")
        threading.Thread(target=self._check_updates_worker, daemon=True).start()

    def _check_updates_worker(self):
        module_specs = [
            ("toolbox", "Maple Toolbox"),
            ("capture", "Equipment Bag Screenshot Capture Tool"),
            ("mapleocr", "MapleOCR"),
            ("bismirpg", "BISMIRPG"),
            ("mapleforge", "MapleForge"),
        ]

        up_to_date = 0
        update_available = 0
        not_installed = 0
        results = []
        log_lines = []

        for module_key, label in module_specs:
            repo = self.module_repo(module_key)
            local = self.module_local_version(module_key)

            try:
                release = fetch_latest_release(github_release_api(repo))
                remote = release.get("tag_name") or release.get("name") or "Unknown"

                if module_key == "capture":
                    self.after(0, self.capture_github_var.set, f"GitHub: {remote}")

                self._set_release_var(module_key, f"Latest release: {remote}")

                if not local:
                    not_installed += 1
                    status = "not_installed"
                    log_lines.append(f"{label}: not installed — public release {remote} available.")
                elif (
                    module_key == "toolbox"
                    and "development" in str(local).lower()
                    and version_tuple(local) > version_tuple(remote)
                ):
                    status = "development"
                    log_lines.append(
                        f"{label}: local development build {local}; latest public release is {remote}."
                    )
                elif version_tuple(local) < version_tuple(remote):
                    update_available += 1
                    status = "update"
                    log_lines.append(f"{label}: {local} -> {remote} available.")
                else:
                    up_to_date += 1
                    status = "current"
                    log_lines.append(f"{label}: {local} is current ({remote}).")

                results.append({
                    "key": module_key,
                    "label": label,
                    "status": status,
                    "local": local,
                    "remote": remote,
                })

                if module_key == "capture":
                    if status == "update":
                        self.after(0, self.capture_update_var.set, f"Update available: {remote}")
                    elif status == "current":
                        self.after(0, self.capture_update_var.set, "Up to date")
                    else:
                        self.after(0, self.capture_update_var.set, f"Release available: {remote}")

            except Exception as exc:
                # A private repo or repo without releases is intentionally not treated as
                # a downloadable update. Only public releases count.
                log_lines.append(f"{label}: no public downloadable release found ({repo}).")
                results.append({
                    "key": module_key,
                    "label": label,
                    "status": "no_public_release",
                    "local": local,
                    "remote": None,
                })
                self._set_release_var(module_key, "No public release")

                if module_key == "capture":
                    self.after(0, self.capture_github_var.set, "GitHub: no public release")
                    self.after(0, self.capture_update_var.set, "")

        stamp = datetime.now().strftime("%H:%M:%S")
        for line in log_lines:
            append_update_log(line)

        actionable = [
            r for r in results
            if r["status"] in {"update", "not_installed"}
        ]

        if actionable:
            summary = "\n".join(
                (
                    f'{r["label"]}: '
                    f'{r.get("local") or "not installed"} → {r.get("remote")}'
                )
                for r in actionable
            )
        else:
            summary = "No downloadable updates are currently available."

        self.after(0, self.up_to_date_var.set, str(up_to_date))
        self.after(0, self.update_available_var.set, str(update_available))
        self.after(0, self.not_installed_var.set, str(not_installed))
        self.after(0, self.last_checked_var.set, f"Last checked: {stamp}")
        self.after(0, self.update_details_var.set, summary)
        self.after(0, self._render_update_actions, results)
        self.after(0, self.status_var.set, "GitHub release check complete")

    def open_updates_log(self):
        p = update_log_path()
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("Maple Toolbox update log.\nNo checks have been completed yet.\n", encoding="utf-8")
        open_path(p)

    def run_ocr(self, dry_run: bool):
        root = self.root_path()
        importer = latest_importer(root)

        if not root.exists():
            messagebox.showerror(
                "Cannot run MapleOCR",
                f"The MapleOCR Operating Folder does not exist:\n\n{root}"
            )
            return

        if not importer:
            messagebox.showerror(
                "Cannot run MapleOCR",
                "No maple_batch_importer_easyocr_vXXX.py was found in the selected Operating Folder."
            )
            return

        python_exe = root / ".venv" / "Scripts" / "python.exe"
        screenshots = root / "screenshots"
        mapleexport = root / "mapleexport.txt"
        results = root / "Results"

        missing = []
        if not python_exe.exists():
            missing.append(r".venv\Scripts\python.exe")
        if not screenshots.exists():
            missing.append("screenshots folder")
        if not mapleexport.exists():
            missing.append("mapleexport.txt")

        if missing:
            messagebox.showerror(
                "Cannot run MapleOCR",
                "The selected MapleOCR Operating Folder is missing:\n\n- "
                + "\n- ".join(missing)
            )
            return

        results.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(python_exe),
            "-u",
            str(importer),
            str(screenshots),
            str(mapleexport),
            "--full-inventory",
            "--output-dir",
            str(results),
        ]

        if dry_run:
            cmd.append("--dry-run")

        mode = "DRY RUN" if dry_run else "REAL RUN"

        self.status_var.set(f"{mode} started — {importer.name}")
        self._run_process(cmd, root, mode)

    def _create_live_log(self, title: str):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry(saved_window_geometry("ocr_run_window", "940x660"))
        win.minsize(780, 520)
        win.configure(bg="#0c1117")

        # Deliberately NOT transient to the main Toolbox window.
        # This keeps the OCR run visible when Toolbox itself is minimized.
        win.attributes("-topmost", True)
        win.lift()
        try:
            win.focus_force()
        except tk.TclError:
            pass

        geometry_state = {"after": None}

        def remember_geometry(_event=None):
            if geometry_state["after"] is not None:
                try:
                    win.after_cancel(geometry_state["after"])
                except tk.TclError:
                    pass

            def commit_geometry():
                geometry_state["after"] = None
                try:
                    if win.state() == "normal":
                        save_window_geometry("ocr_run_window", win.geometry())
                except tk.TclError:
                    pass

            geometry_state["after"] = win.after(500, commit_geometry)

        win.bind("<Configure>", remember_geometry, add="+")

        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))

        status = ttk.Label(
            header,
            text="Starting...",
            style="Subtle.TLabel",
        )
        status.pack(side="left")

        elapsed = ttk.Label(
            header,
            text="Elapsed: 00:00",
            style="Subtle.TLabel",
        )
        elapsed.pack(side="right")

        progress = ttk.Progressbar(
            outer,
            orient="horizontal",
            mode="indeterminate",
            style="Cylon.Horizontal.TProgressbar",
        )
        progress.pack(fill="x", pady=(0, 8))
        progress.start(12)

        box = tk.Text(
            outer,
            bg="#0f141b",
            fg="#dce7f3",
            insertbackground="#ffffff",
            font=("Consolas", 10),
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
        )
        box.pack(fill="both", expand=True)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))

        footer_text = ttk.Label(
            footer,
            text="",
            style="Subtle.TLabel",
            anchor="center",
        )
        footer_text.pack(fill="x")

        footer_buttons = ttk.Frame(footer)
        footer_buttons.pack(fill="x", pady=(6, 0))

        return win, status, elapsed, progress, box, footer_text, footer_buttons

    def _append_live_log(self, box, text):
        try:
            box.insert("end", text)
            box.see("end")
        except tk.TclError:
            pass

    def _run_process(self, cmd, cwd, mode):
        win, live_status, elapsed_label, progress, box, footer_text, footer_buttons = self._create_live_log(
            f"MapleOCR — {mode}"
        )

        start_time = time.time()
        self._append_live_log(
            box,
            f"{mode} started.\n"
            f"Operating folder: {cwd}\n"
            f"Command: {' '.join(str(x) for x in cmd)}\n\n"
        )

        state = {
            "running": True,
            "last_output": time.time(),
            "heartbeat_count": 0,
        }

        def update_elapsed():
            if not state["running"]:
                return

            elapsed_seconds = int(time.time() - start_time)
            minutes, seconds = divmod(elapsed_seconds, 60)
            hours, minutes = divmod(minutes, 60)

            if hours:
                text = f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                text = f"Elapsed: {minutes:02d}:{seconds:02d}"

            try:
                elapsed_label.configure(text=text)
            except tk.TclError:
                return

            # Heartbeat after 15 seconds of silence, then every 15 seconds.
            silent_for = time.time() - state["last_output"]
            if silent_for >= 15:
                state["heartbeat_count"] += 1
                state["last_output"] = time.time()
                self._append_live_log(
                    box,
                    f"[Toolbox] MapleOCR is still working... {text.replace('Elapsed: ', '')}\n"
                )

            self.after(1000, update_elapsed)

        self.after(1000, update_elapsed)

        def worker():
            try:
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"

                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )

                captured = []

                if proc.stdout is not None:
                    for line in proc.stdout:
                        captured.append(line)
                        state["last_output"] = time.time()
                        self.after(0, self._append_live_log, box, line)

                returncode = proc.wait()
                output = "".join(captured).strip()

                state["running"] = False

                self.after(
                    0,
                    self._process_finished_live,
                    returncode,
                    output,
                    mode,
                    live_status,
                    elapsed_label,
                    progress,
                    box,
                    footer_text,
                    footer_buttons,
                    start_time,
                )

            except Exception as exc:
                state["running"] = False
                log_path = write_error_log(
                    "MapleOCR",
                    mode.replace(" ", "_"),
                    command=cmd,
                    exception_text=str(exc),
                    output=str(exc),
                )
                self.after(0, self._append_live_log, box, f"\nERROR: {exc}\n")
                self.after(0, live_status.configure, {"text": f"{mode} failed"})
                self.after(0, progress.stop)
                self.after(0, self.status_var.set, f"{mode} failed")
                self.after(
                    0,
                    self._show_error_footer,
                    footer_text,
                    footer_buttons,
                    log_path,
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_error_footer(self, footer_text, footer_buttons, log_path):
        try:
            footer_text.configure(
                text=(
                    f"Run failed — error log saved: {log_path}"
                    if log_path
                    else "Run failed — error log could not be written."
                )
            )
            for child in footer_buttons.winfo_children():
                child.destroy()

            if log_path:
                ttk.Button(
                    footer_buttons,
                    text="Open Error Log",
                    command=lambda p=log_path: open_path(p),
                ).pack(side="left", expand=True, fill="x", padx=(0, 6))

            ttk.Button(
                footer_buttons,
                text="Open Errors Folder",
                command=self.open_errors_folder,
            ).pack(side="left", expand=True, fill="x", padx=(6, 0))
        except tk.TclError:
            pass

    def _process_finished_live(
        self,
        returncode,
        output,
        mode,
        live_status,
        elapsed_label,
        progress,
        box,
        footer_text,
        footer_buttons,
        start_time,
    ):
        self.refresh_status()

        try:
            progress.stop()
        except tk.TclError:
            pass

        total_seconds = int(time.time() - start_time)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            elapsed_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            elapsed_text = f"{minutes:02d}:{seconds:02d}"

        try:
            elapsed_label.configure(text=f"Elapsed: {elapsed_text}")
        except tk.TclError:
            pass

        try:
            win = box.winfo_toplevel()
            win.attributes("-topmost", False)
        except tk.TclError:
            win = None

        if returncode == 0:
            live_status.configure(text=f"{mode} complete")
            self.status_var.set(f"{mode} complete")
            self._append_live_log(
                box,
                f"\n[Toolbox] {mode} complete in {elapsed_text}.\n"
            )
            if not output:
                self._append_live_log(
                    box,
                    "MapleOCR finished successfully.\n"
                )

            for child in footer_buttons.winfo_children():
                child.destroy()

            def close_countdown(seconds=5):
                if win is None:
                    return
                try:
                    if seconds > 0:
                        message = f"{mode} COMPLETE — this window will close in {seconds} seconds"
                        footer_text.configure(text=message)
                        self._append_live_log(box, f"[Toolbox] Closing in {seconds}...\n")
                        self.after(1000, close_countdown, seconds - 1)
                    else:
                        footer_text.configure(text=f"{mode} COMPLETE — closing...")
                        self._append_live_log(box, "[Toolbox] Closing now.\n")
                        self.after(250, win.destroy)
                except tk.TclError:
                    pass

            close_countdown(5)

        else:
            live_status.configure(text=f"{mode} failed — exit code {returncode}")
            self.status_var.set(f"{mode} failed — exit code {returncode}")
            self._append_live_log(
                box,
                f"\n[Toolbox] Process exited with code {returncode} after {elapsed_text}.\n"
            )

            log_path = write_error_log(
                "MapleOCR",
                mode.replace(" ", "_"),
                command=None,
                exit_code=returncode,
                output=output,
            )
            self._show_error_footer(
                footer_text,
                footer_buttons,
                log_path,
            )

    def _show_log(self, title, text):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("900x600")
        box = tk.Text(
            win, bg="#0f141b", fg="#dce7f3", insertbackground="#ffffff",
            font=("Consolas", 10), wrap="word"
        )
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.see("end")

    def open_folder(self, relative: str):
        p = self.root_path() / Path(relative)
        p.mkdir(parents=True, exist_ok=True)
        open_path(p)

    def open_mapleocr_folder(self):
        self.open_module_folder("mapleocr")

    def open_output(self):
        root = self.root_path()
        p = root / "Output"

        if p.exists():
            open_path(p)
            self.status_var.set(f"Opened Output — {p}")
            return

        # Do not silently create a misleading Output folder.
        if root.exists():
            open_path(root)
            self.status_var.set("Output folder not found — opened MapleOCR Operating Folder instead.")
        else:
            messagebox.showwarning(
                "Output not found",
                f"Neither the Output folder nor MapleOCR Operating Folder exists:\n\n{root}"
            )

    def open_mapleupload(self):
        root = self.root_path()
        candidates = [
            root / "mapleupload.txt",
            root / "Output" / "mapleupload.txt",
        ]

        for p in candidates:
            if p.exists():
                self._open_file(p)
                self.status_var.set(f"Opened mapleupload — {p}")
                return

        messagebox.showwarning(
            "mapleupload.txt not found",
            "Could not find mapleupload.txt in either:\n\n"
            f"{root}\n"
            f"{root / 'Output'}"
        )

    def open_mapleexport(self):
        root = self.root_path()
        candidates = [
            root / "mapleexport.txt",
            root / "Output" / "mapleexport.txt",
        ]

        for p in candidates:
            if p.exists():
                self._open_file(p)
                self.status_var.set(f"Opened mapleexport — {p}")
                return

        messagebox.showwarning(
            "mapleexport.txt not found",
            "Could not find mapleexport.txt in either:\n\n"
            f"{root}\n"
            f"{root / 'Output'}"
        )

    def _open_file(self, p: Path):
        try:
            open_path(p)
        except FileNotFoundError:
            messagebox.showwarning("File not found", str(p))
        except Exception as exc:
            messagebox.showerror("Could not open file", str(exc))

    def open_latest_zip(self):
        z = latest_output_zip(self.root_path())
        if not z:
            messagebox.showwarning("No ZIP found", "No Output ZIP was detected.")
            return
        try:
            ZipBrowser(self, z)
        except zipfile.BadZipFile:
            messagebox.showerror("Bad ZIP", f"Could not read:\n{z}")

    def choose_zip(self):
        chosen = filedialog.askopenfilename(
            title="Choose Output ZIP",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")],
        )
        if chosen:
            try:
                ZipBrowser(self, Path(chosen))
            except zipfile.BadZipFile:
                messagebox.showerror("Bad ZIP", chosen)

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("Maple Toolbox Settings")
        win.geometry("860x410")
        win.configure(bg="#0c1117")

        outer = ttk.Frame(win, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Operating Folders", style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 14)
        )

        rows = [
            ("MapleOCR", self.mapleocr_dir_var, "mapleocr"),
            ("Equipment Bag Screenshot Capture Tool", self.capture_dir_var, "capture"),
            ("BISMIRPG", self.bismirpg_dir_var, "bismirpg"),
            ("MapleForge", self.mapleforge_dir_var, "mapleforge"),
        ]

        for idx, (label, variable, key) in enumerate(rows, start=1):
            ttk.Label(outer, text=label, style="Subtle.TLabel").grid(
                row=idx, column=0, sticky="w", pady=6
            )
            ttk.Entry(outer, textvariable=variable).grid(
                row=idx, column=1, sticky="ew", padx=8, pady=6
            )
            ttk.Button(
                outer, text="Select",
                command=lambda k=key: self.select_module_folder(k)
            ).grid(row=idx, column=2, sticky="ew", pady=6)

        ttk.Button(
            outer, text="Run First Setup", command=self.show_first_run_wizard
        ).grid(row=len(rows) + 1, column=1, sticky="ew", pady=(18, 0), padx=(0, 8))

        ttk.Button(
            outer, text="Save / Refresh", style="Accent.TButton",
            command=self.refresh_status
        ).grid(row=len(rows) + 1, column=2, sticky="ew", pady=(18, 0))

        outer.columnconfigure(1, weight=1)

    def show_first_run_wizard(self):
        win = tk.Toplevel(self)
        win.title("Maple Toolbox — First Run Setup")
        win.geometry("760x500")
        win.minsize(700, 460)
        win.configure(bg="#0c1117")
        win.transient(self)
        win.grab_set()

        outer = ttk.Frame(win, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="First Run Setup",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(
            outer,
            text=(
                "Choose a base folder. Maple Toolbox can create standard module folders "
                "and save them as the initial Operating Folders. An internet connection is "
                "required for GitHub checks and downloads."
            ),
            style="Subtle.TLabel",
            wraplength=680,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 18))

        default_base = Path(r"C:\MapleTools")
        current_root = self.mapleocr_dir_var.get().strip().strip('"')
        if current_root:
            try:
                current_path = Path(current_root)
                default_base = current_path.parent if current_path.name.lower() == "mapleocr" else current_path
            except Exception:
                pass

        base_var = tk.StringVar(value=str(default_base))

        ttk.Label(
            outer, text="Base Folder", style="Subtle.TLabel"
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Entry(
            outer, textvariable=base_var
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=(0, 8))

        def browse_base():
            chosen = filedialog.askdirectory(
                title="Choose Maple Toolbox base folder",
                initialdir=base_var.get() or str(Path.home()),
            )
            if chosen:
                base_var.set(chosen)

        ttk.Button(
            outer, text="Browse", command=browse_base
        ).grid(row=3, column=2, sticky="ew")

        ttk.Label(
            outer,
            text="Create module folders",
            style="Subtle.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(20, 8))

        folder_specs = [
            ("mapleocr", "MapleOCR", self.mapleocr_dir_var),
            ("capture", "EquipmentBagCaptureTool", self.capture_dir_var),
            ("bismirpg", "BISMIRPG", self.bismirpg_dir_var),
            ("mapleforge", "MapleForge", self.mapleforge_dir_var),
        ]

        checks = {}
        for idx, (key, folder_name, variable) in enumerate(folder_specs, start=5):
            var = tk.BooleanVar(value=True)
            checks[key] = var
            ttk.Checkbutton(
                outer,
                text=folder_name,
                variable=var,
            ).grid(row=idx, column=0, columnspan=3, sticky="w", pady=3)

        result_var = tk.StringVar(value="")
        ttk.Label(
            outer,
            textvariable=result_var,
            style="Good.TLabel",
            wraplength=680,
            justify="left",
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(16, 0))

        def create_and_continue():
            base_text = base_var.get().strip().strip('"')
            if not base_text:
                messagebox.showwarning(
                    "First Run Setup",
                    "Choose a base folder first."
                )
                return

            base = Path(base_text)

            try:
                base.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                messagebox.showerror(
                    "Could not create base folder",
                    str(exc)
                )
                return

            created = []

            mapping = {
                "mapleocr": self.mapleocr_dir_var,
                "capture": self.capture_dir_var,
                "mapleforge": self.mapleforge_dir_var,
                    "bismirpg": self.bismirpg_dir_var,
            }

            names = {
                "mapleocr": "MapleOCR",
                "capture": "EquipmentBagCaptureTool",
                "mapleforge": "MapleForge",
                "bismirpg": "BISMIRPG",
            }

            for key, checked in checks.items():
                if not checked.get():
                    continue
                target = base / names[key]
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    messagebox.showerror(
                        "Folder creation failed",
                        f"Could not create:\n{target}\n\n{exc}"
                    )
                    return

                mapping[key].set(str(target))
                created.append(str(target))

            self._save()
            self.refresh_status()

            if created:
                result_var.set(
                    "Created and configured:\n" + "\n".join(created)
                )
            else:
                result_var.set("No folders were created.")

            self.after(350, win.destroy)

        def skip_setup():
            # Save current values so the wizard does not auto-open every launch.
            self._save()
            win.destroy()

        button_row = 11

        ttk.Button(
            outer,
            text="Check Requirements",
            command=self.check_prerequisites,
        ).grid(row=button_row, column=0, sticky="ew", padx=(0, 8), pady=(22, 0))

        ttk.Button(
            outer,
            text="Skip Setup",
            command=skip_setup,
        ).grid(row=button_row, column=1, sticky="ew", padx=(0, 8), pady=(22, 0))

        ttk.Button(
            outer,
            text="Create Folders & Continue",
            style="Accent.TButton",
            command=create_and_continue,
        ).grid(row=button_row, column=2, sticky="ew", pady=(22, 0))

        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.columnconfigure(2, weight=1)

    def choose_root(self):
        self.select_module_folder("mapleocr")

    def send_feedback(self):
        log_path = latest_error_log()

        subject = f"Maple Toolbox {APP_VERSION} Feedback"
        body_lines = [
            "Hi,",
            "",
            "Feedback / problem report:",
            "",
            "",
            "----------------------------------------",
            f"Maple Toolbox: {APP_VERSION}",
            f"Windows: {platform.platform()}",
            f"Python: {platform.python_version()}",
        ]

        if log_path:
            body_lines.extend([
                "",
                "Latest Toolbox error log:",
                str(log_path),
                "",
                "If this report is about an error, please attach that .log file to this email.",
            ])
        else:
            body_lines.extend([
                "",
                "No Toolbox error log was found.",
            ])

        body_lines.extend([
            "",
            "Please do not include passwords, API keys, or other private credentials.",
        ])

        params = urllib.parse.urlencode({
            "subject": subject,
            "body": "\r\n".join(body_lines),
        })
        mailto = f"mailto:{FEEDBACK_EMAIL}?{params}"

        try:
            os.startfile(mailto)
            self.status_var.set("Opened feedback email")
        except Exception as exc:
            log_path_written = write_error_log(
                "Toolbox",
                "Feedback_Email",
                exception_text=str(exc),
                output=str(exc),
            )
            messagebox.showerror(
                "Could not open email client",
                "Maple Toolbox could not open your default email application.\n\n"
                f"Send feedback manually to:\n{FEEDBACK_EMAIL}\n\n"
                + (
                    f"Toolbox error log: {log_path_written}"
                    if log_path_written
                    else f"Error: {exc}"
                )
            )

    def _apply_button_tooltips(self):
        tips = {'Check Directories': 'Checks that the configured Toolbox, MapleOCR, screenshot, Results, Output and module folders exist. Run this first on a new PC.', 'Create Safe Missing Folders': 'Creates only safe missing folders such as screenshots, Results, Output and Errors. It does not move or delete your existing files.', 'Open Errors Folder': 'Opens the Toolbox Errors folder. Successful runs do not create logs here; only failures are kept.', 'Check Requirements': 'Checks Windows, PowerShell, winget, Git, AutoHotkey v2, ShareX and the MapleOCR Python environment.', 'Install Missing Requirements': 'Offers to install missing prerequisites visibly. Nothing is installed silently or without your approval.', 'Re-check': 'Runs the requirements check again after you install or fix something.', 'Check for Updates': 'Checks public GitHub releases for Maple Toolbox and supported modules. Internet access is required.', 'Refresh Status': 'Re-scans local module folders, then refreshes installed versions and GitHub release status.', 'Open Updates Log': 'Opens the update-check history so you can see what Toolbox found on earlier checks.', 'Launch Capture': 'Launches the Equipment Bag Screenshot Capture Tool from its selected Operating Folder.', 'Calibrate': 'Starts capture-tool calibration so screen positions can be matched to this PC and game window.', 'Bag Screenshots': 'Opens the normal equipment bag screenshot folder used by MapleOCR.', 'Equipped Screenshots': 'Opens the Equipped screenshot folder. These screenshots are treated as the gear currently worn in the Basic Preset.', 'GitHub Release': 'Opens the latest public GitHub release for this module.', 'Dry Run': 'Scans and validates the current screenshots without doing the final optimiser handoff. Use this first if you want to check OCR results safely.', 'Real Run': 'Processes the current screenshot batch and writes the OCR/import outputs. After this, import mapleupload.txt into the optimiser and export a fresh mapleexport.txt before building BIS_stats.zip.', 'Open Output': 'Opens MapleOCR Output so you can inspect the latest generated files and ZIPs.', 'Open mapleupload': 'Opens mapleupload.txt. Import this into the optimiser after the OCR run.', 'Open MapleOCR Folder': 'Opens the configured MapleOCR Operating Folder.', 'Open mapleexport': 'Opens the current mapleexport.txt. For BIS work this should be freshly exported from the optimiser after importing the latest mapleupload.txt.', 'Open Latest ZIP': 'Opens the newest MapleOCR output ZIP without extracting it.', 'Choose ZIP...': 'Lets you choose a specific MapleOCR ZIP to inspect.', 'Choose ZIP': 'Lets you choose a specific ZIP to inspect.', 'Generate BIS Report': 'BIS workflow: OCR scan → import mapleupload.txt into optimiser → export fresh mapleexport.txt → build/validate BIS_stats.zip → generate report. Do not use a stale mapleexport.txt.', 'Open BIS Reports': 'Opens the BISMIRPG Reports folder containing generated BIS PDF and Lock/Unlock outputs.', 'Open BISMIRPG Folder': 'Opens the configured BISMIRPG Operating Folder.', 'Select Operating Folder': 'Choose the folder where this module is installed or should operate. Folder names can be different on each PC.', 'GitHub Repository': "Opens this module's GitHub repository.", 'Send Feedback / Report a Problem': 'Opens an email to maple@arcadeheaven.com with Toolbox and Windows version details. If there is an error log, attach it.'}

        def walk(widget):
            try:
                children = widget.winfo_children()
            except Exception:
                return
            for child in children:
                try:
                    if isinstance(child, (ttk.Button, tk.Button)):
                        text = str(child.cget("text"))
                        tip = tips.get(text)
                        if tip:
                            add_tooltip(child, tip)
                except Exception:
                    pass
                walk(child)

        walk(self)

    def show_about(self):
        messagebox.showinfo(
            "About Maple Toolbox",
            f"Maple Toolbox {APP_VERSION}\n\n"
            "One Toolbox to run them all.\n\n"            f"Feedback: {FEEDBACK_EMAIL}\n\n"
            "A Windows control panel for the separate MapleStory Idle RPG tools."
        )

    def open_toolbox_folder(self):
        try:
            open_path(Path(__file__).resolve().parent)
        except Exception as exc:
            messagebox.showerror("Could not open Toolbox folder", str(exc))


if __name__ == "__main__":
    MapleToolbox().mainloop()
