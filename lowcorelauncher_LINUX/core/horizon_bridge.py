"""
Bridge between LowCore and Horizon, the Rust re-implementation of Minecraft: Java Edition 26.3.

LowCore does NOT download or run Horizon builds on its own. Horizon's own launcher installs, verifies,
prepares and updates the game; LowCore drives that launcher through its command line
(`horizon-launcher install | prepare | play`) and then watches the game process, so the normal
Kill button, playtime tracking and Discord status keep working.

Horizon needs its own copy of Minecraft 26.3 ("versions/26.3", "libraries", "assets"). LowCore keeps
exactly that layout in its game folder, so the same files are handed to Horizon's `prepare` step.
"""
import os
import re
import sys
import glob
import time
import shutil
import threading
import subprocess
from typing import Callable, List, Optional, Tuple

import psutil

HORIZON_MC_VERSION = "26.3"
HORIZON_SITE = "https://playhorizon.dev"
LOADER_NAME = "Horizon"
INSTANCE_DISPLAY_NAME = "Horizon (Rust)"
CONFIG_PATH_KEY = "horizon_launcher_path"       # where the user's horizon-launcher lives
CONFIG_INSTANCE_KEY = "horizon_instance_name"   # optional: which Horizon-launcher instance to play

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-]{0,63}$")


class HorizonError(RuntimeError):
    """Something went wrong while talking to Horizon's launcher (message is meant for the user)."""


def is_horizon_instance(inst: dict) -> bool:
    return str((inst or {}).get("loader", "")).strip().lower() == LOADER_NAME.lower()


# ------------------------------------------------------------------ finding the launcher

def validate_launcher_path(path: Optional[str]) -> bool:
    """Only an existing file that is clearly Horizon's launcher is ever executed."""
    if not path or not os.path.isfile(path):
        return False
    base = os.path.basename(path).lower()
    return "horizon" in base and (base.endswith((".exe", ".appimage")) or "." not in base)


def candidate_launcher_paths() -> List[str]:
    """Places the Horizon launcher is commonly installed (best effort: the user can always pick it by hand)."""
    home = os.path.expanduser("~")
    out: List[str] = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        roots = [local, os.path.join(local, "Programs"),
                 os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        for base in roots:
            for folder in ("Horizon launcher", "Horizon Launcher", "Horizon", "horizon-launcher", "horizon"):
                out.append(os.path.join(base, folder, "horizon-launcher.exe"))
        for d in ("Downloads", "Desktop"):
            out += glob.glob(os.path.join(home, d, "horizon*", "horizon-launcher.exe"))
            out += glob.glob(os.path.join(home, d, "horizon*", "*", "horizon-launcher.exe"))
    elif sys.platform == "darwin":
        out += ["/Applications/Horizon.app/Contents/MacOS/horizon-launcher",
                os.path.join(home, "Applications", "Horizon.app", "Contents", "MacOS", "horizon-launcher")]
    else:
        for d in (home, os.path.join(home, "Applications"), os.path.join(home, "Downloads"),
                  os.path.join(home, ".local", "bin"), os.path.join(home, ".local", "share", "horizon")):
            out += glob.glob(os.path.join(d, "Horizon*.AppImage")) + glob.glob(os.path.join(d, "horizon-launcher*"))
    return out


def find_launcher(saved_path: Optional[str] = None) -> Optional[str]:
    """The saved path first, then PATH, then the usual install folders."""
    if validate_launcher_path(saved_path):
        return saved_path
    for name in ("horizon-launcher", "horizon-launcher.exe"):
        hit = shutil.which(name)
        if hit and validate_launcher_path(hit):
            return hit
    for cand in candidate_launcher_paths():
        if validate_launcher_path(cand):
            return cand
    return None


# ------------------------------------------------------------------ Minecraft files

def minecraft_files_ready(game_dir: str, version: str = HORIZON_MC_VERSION) -> Tuple[bool, str]:
    """Does `game_dir` contain what Horizon reads: versions/<v>/, libraries/ and assets/ ?"""
    missing = []
    vdir = os.path.join(game_dir, "versions", version)
    for ext in (".json", ".jar"):
        p = os.path.join(vdir, version + ext)
        if not (os.path.isfile(p) and os.path.getsize(p) > 0):
            missing.append(f"versions/{version}/{version}{ext}")
    lib_dir = os.path.join(game_dir, "libraries")
    if not (os.path.isdir(lib_dir) and any(files for _, _, files in os.walk(lib_dir))):
        missing.append("libraries/")
    if not os.path.isdir(os.path.join(game_dir, "assets", "indexes")):
        missing.append("assets/indexes/")
    if not os.path.isdir(os.path.join(game_dir, "assets", "objects")):
        missing.append("assets/objects/")
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, "ready"


# ------------------------------------------------------------------ running the launcher's CLI

def _pump(proc: subprocess.Popen, lines: List[str], log_cb: Optional[Callable[[str], None]]) -> threading.Thread:
    def reader():
        try:
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip()
                lines.append(line)
                if log_cb:
                    log_cb(line)
        except Exception:
            pass
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    return t


def _spawn(launcher: str, args: List[str], env_extra: Optional[dict] = None) -> subprocess.Popen:
    if not validate_launcher_path(launcher):
        raise HorizonError("The Horizon launcher was not found. Pick it in Settings > Experimental > Horizon.")
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.Popen(
        [launcher] + [str(a) for a in args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1, env=env, creationflags=NO_WINDOW,
    )


def run_cli(launcher: str, args: List[str], log_cb: Optional[Callable[[str], None]] = None,
            timeout: int = 1800, env_extra: Optional[dict] = None) -> Tuple[int, str]:
    """Runs one launcher command to the end. Returns (exit code, last output lines)."""
    proc = _spawn(launcher, args, env_extra)
    lines: List[str] = []
    reader = _pump(proc, lines, log_cb)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        reader.join(2)
        raise HorizonError(f"The Horizon launcher took longer than {timeout // 60} minutes and was stopped.")
    reader.join(5)
    return proc.returncode, "\n".join(lines[-15:])


def install_latest(launcher: str, log_cb=None) -> Tuple[int, str]:
    return run_cli(launcher, ["install", "latest"], log_cb)


def prepare(launcher: str, minecraft_dir: str, log_cb=None) -> Tuple[int, str]:
    """Horizon builds its resources from Minecraft's own files, here LowCore's game folder."""
    return run_cli(launcher, ["prepare", "--minecraft", minecraft_dir], log_cb,
                   env_extra={"HORIZON_MINECRAFT_DIR": minecraft_dir})


def installed_versions(launcher: str) -> str:
    try:
        code, out = run_cli(launcher, ["versions", "--installed"], timeout=60)
        return out if code == 0 else ""
    except HorizonError:
        return ""


# ------------------------------------------------------------------ playing

def find_client_process(since: float) -> Optional[psutil.Process]:
    """A horizon-client process that started after `since` (never one the user started earlier)."""
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name.endswith(".exe"):
                name = name[:-4]
            if name.startswith("horizon-client") and (p.info.get("create_time") or 0) >= since - 1.0:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


class HorizonSession:
    """Looks like the subset of subprocess.Popen the launcher UI needs (pid / poll / wait)."""

    def __init__(self, client: Optional[psutil.Process], launcher_proc: Optional[subprocess.Popen] = None):
        self.client = client
        self.launcher_proc = launcher_proc

    @property
    def pid(self) -> int:
        return self.client.pid if self.client is not None else self.launcher_proc.pid

    def poll(self):
        try:
            if self.client is not None:
                return None if self.client.is_running() and self.client.status() != psutil.STATUS_ZOMBIE else 0
        except psutil.NoSuchProcess:
            return 0
        return self.launcher_proc.poll()

    def wait(self) -> int:
        if self.client is not None:
            try:
                code = self.client.wait()
            except psutil.NoSuchProcess:
                code = None
        else:
            code = self.launcher_proc.wait()
        return code if isinstance(code, int) else 0


def start_play(launcher: str, instance_name: Optional[str] = None, log_cb=None,
               find_timeout: float = 90.0, grace_after_exit: float = 15.0) -> HorizonSession:
    """
    Starts the game through `horizon-launcher play`. Whether that command stays running for as long as
    the game does or hands the game over and exits, the game process is found and followed.
    """
    args = ["play"]
    if instance_name:
        name = instance_name.strip()
        if not _SAFE_NAME.match(name):
            raise HorizonError("The Horizon instance name has unusual characters. Use letters, numbers, spaces, - . _")
        args += ["--instance", name]

    t0 = time.time()
    proc = _spawn(launcher, args)
    lines: List[str] = []
    _pump(proc, lines, log_cb)

    exited_at = None
    while time.time() - t0 < find_timeout:
        client = find_client_process(t0)
        if client is not None:
            return HorizonSession(client, proc)
        if proc.poll() is not None:
            exited_at = exited_at or time.time()
            if time.time() - exited_at > grace_after_exit:
                break
        time.sleep(0.4)

    if proc.poll() is None:
        # Still running but no "horizon-client" process seen: follow the launcher command itself.
        return HorizonSession(None, proc)

    tail = "\n".join(lines[-12:])
    if proc.returncode != 0:
        raise HorizonError(f"The Horizon launcher failed (exit code {proc.returncode}).\n{tail}")
    raise HorizonError("The Horizon launcher finished, but the game did not start.\n"
                       "Open the Horizon launcher once, press Play there, and check that it works.\n" + tail)