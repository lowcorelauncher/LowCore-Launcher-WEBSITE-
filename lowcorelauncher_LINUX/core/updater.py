"""
In-place & delta updater for LowCore Client.

Updates the launcher without redownloading the whole installer by:
  1. Custom delta manifest ("files" map with sha256) -> downloads ONLY changed files.
  2. GitHub Release Git-Tree diff -> fetches blob SHAs once, computes local Git blob
     SHA-1s, and downloads ONLY the files changed since your installed version.
  3. Lightweight patch ZIP asset -> extracts ONLY changed files safely (Zip-Slip guarded).
  4. Frozen .exe self-swap -> replaces the standalone .exe in-place and relaunches.
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

USER_AGENT = "LowCoreClient-Updater/1.2"

# Folders/files managed inside the repo that shouldn't be pulled into end-user runtime
_SKIP_PREFIXES = (".git/", ".github/", ".vscode/", "tools/", "tests/", "lowcore_multiversion/", "lowcore_1_21_11/", "dist/", "build/", "__pycache__/")
_ALLOWED_EXTS = (".py", ".jar", ".png", ".ico", ".json", ".txt", ".ttf", ".otf")


def parse_version(text: str) -> tuple:
    """'v1.2.3-beta' -> (1, 2, 3). Missing parts count as 0."""
    core = re.split(r"[-+ ]", str(text).strip().lstrip("vV"), maxsplit=1)[0]
    nums = [int(x) for x in re.findall(r"\d+", core)][:4]
    return tuple(nums) if nums else (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def _notes_list(value) -> list:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        lines = [re.sub(r"^[\s\-*\u2022#]+", "", ln).strip() for ln in value.splitlines()]
        return [ln for ln in lines if ln]
    return []


def _extract_github_repo(manifest_url: str) -> str:
    m = re.match(r"^https://api\.github\.com/repos/([^/]+/[^/]+)/", manifest_url or "")
    if m:
        return m.group(1)
    m2 = re.match(r"^https://raw\.githubusercontent\.com/([^/]+/[^/]+)/", manifest_url or "")
    if m2:
        return m2.group(1)
    return ""


_WIN_ASSET_TAGS = ("win32", "win64", "windows", "-win", "_win")
_LINUX_ASSET_TAGS = ("linux", "ubuntu", "debian", "appimage", "x86_64-linux")
_MAC_ASSET_TAGS = ("macos", "darwin", "osx")
_NON_PATCH_ZIP_TAGS = ("sources", "source", "multiversion", "all-versions", "-jars", "_jars", "fabric-mod")


def _pick_github_assets(assets: list) -> Tuple[str, str]:
    """Return (patch_zip_url, exe_url) filtered for the current operating system."""
    is_win = sys.platform == "win32"
    is_linux = sys.platform.startswith("linux")
    is_mac = sys.platform == "darwin"

    patch_url = ""
    exe_url = ""
    fallback_zip = ""
    for a in assets or []:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name", "")).lower()
        dl = str(a.get("browser_download_url", ""))
        if not dl.lower().startswith("https://"):
            continue

        if name.endswith(".zip"):
            if any(bad in name for bad in _NON_PATCH_ZIP_TAGS):
                continue
            has_win = any(t in name for t in _WIN_ASSET_TAGS)
            has_linux = any(t in name for t in _LINUX_ASSET_TAGS)
            has_mac = any(t in name for t in _MAC_ASSET_TAGS)

            if is_win and (has_linux or has_mac):
                continue
            if is_linux and (has_win or has_mac):
                continue
            if is_mac and (has_win or has_linux):
                continue

            if any(k in name for k in ("patch", "delta", "update", "fixed")):
                patch_url = dl
            elif is_linux and has_linux and not fallback_zip:
                fallback_zip = dl
            elif is_win and "launcher" in name and not has_linux and not has_mac and not patch_url:
                patch_url = dl
            elif not fallback_zip and "client" not in name and not has_linux and not has_mac:
                fallback_zip = dl
        elif is_win and name.endswith(".exe") and "setup" not in name and "installer" not in name:
            exe_url = dl
    return (patch_url or fallback_zip), exe_url


def check_for_update(manifest_url: str, current_version: str, timeout: int = 8) -> dict:
    """Inspect release metadata and select the most lightweight in-place update mode."""
    if not manifest_url.lower().startswith("https://"):
        raise ValueError("The update address must start with https://")

    res = requests.get(manifest_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=timeout)
    if res.status_code == 404 and "api.github.com" in manifest_url:
        raise ValueError("No release has been published on GitHub yet.")
    if res.status_code == 403 and "api.github.com" in manifest_url:
        raise ValueError("GitHub is limiting requests right now. Try again in a while.")
    res.raise_for_status()
    data = res.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected update data.")

    repo = _extract_github_repo(manifest_url)
    tag = ""
    patch_url = ""
    exe_url = ""
    files_map = {}

    if "tag_name" in data:  # GitHub release API
        tag = str(data.get("tag_name", ""))
        latest = tag
        url = str(data.get("html_url", ""))
        notes = _notes_list(data.get("body", ""))
        revoked = []
        patch_url, exe_url = _pick_github_assets(data.get("assets", []))
    else:
        latest = str(data.get("version", ""))
        tag = str(data.get("tag", latest))
        url = str(data.get("url", ""))
        notes = _notes_list(data.get("notes", []))
        revoked = data.get("revoked", []) if isinstance(data.get("revoked", []), list) else []
        patch_url = str(data.get("patch_url", "") or data.get("delta_url", "") or "")
        exe_url = str(data.get("exe_url", "") or "")
        if isinstance(data.get("files"), dict):
            files_map = data["files"]
        if isinstance(data.get("repo"), str) and data["repo"]:
            repo = data["repo"]

    if not latest:
        raise ValueError("The update data has no version.")
    for u_name, u_val in (("url", url), ("patch_url", patch_url), ("exe_url", exe_url)):
        if u_val and not u_val.lower().startswith("https://"):
            if u_name == "url":
                url = ""
            elif u_name == "patch_url":
                patch_url = ""
            else:
                exe_url = ""

    is_frozen = bool(getattr(sys, "frozen", False))
    if is_frozen:
        if exe_url:
            mode = "exe_swap"
        elif patch_url:
            mode = "patch_zip"
        else:
            mode = "browser"
    else:
        if files_map:
            mode = "delta_manifest"
        elif patch_url:
            mode = "patch_zip"
        elif repo and tag:
            mode = "github_tree_delta"
        else:
            mode = "browser"

    return {
        "available": is_newer(latest, current_version),
        "latest": latest.lstrip("vV"),
        "current": current_version,
        "url": url,
        "notes": notes,
        "revoked": revoked,
        "mode": mode,
        "patch_url": patch_url,
        "exe_url": exe_url,
        "files": files_map,
        "repo": repo,
        "tag": tag,
    }


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("utf-8")
    return hashlib.sha1(header + raw).hexdigest()


def _safe_target_path(app_dir: str, rel_path: str) -> Optional[str]:
    clean = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not clean or clean.startswith("..") or "/../" in f"/{clean}":
        return None
    base_abs = os.path.abspath(app_dir)
    target_abs = os.path.abspath(os.path.join(base_abs, clean))
    try:
        if os.path.commonpath([base_abs, target_abs]) != base_abs:
            return None
    except ValueError:
        return None
    return target_abs


def _should_sync_repo_path(rel_path: str) -> bool:
    low = rel_path.replace("\\", "/").lower().lstrip("/")
    if not low or any(low.startswith(p) for p in _SKIP_PREFIXES):
        return False
    if low == "assets/rshift.png":
        return False
    return low.endswith(_ALLOWED_EXTS)


def _atomic_write_bytes(dest_path: str, data: bytes):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(dest_path), prefix=".lc_upd_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, dest_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _download_bytes(url: str, timeout: int = 20) -> bytes:
    if not url.lower().startswith("https://"):
        raise ValueError(f"Blocked non-HTTPS update URL: {url}")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return r.content


def _apply_delta_manifest(info: dict, app_dir: str, progress_cb=None) -> dict:
    files_map: Dict[str, dict] = info.get("files") or {}
    to_fetch: List[Tuple[str, str, str, str]] = []
    skipped = 0

    for rel, meta in files_map.items():
        if not isinstance(meta, dict):
            continue
        target = _safe_target_path(app_dir, rel)
        dl_url = str(meta.get("url", ""))
        expected_sha = str(meta.get("sha256", "")).lower()
        if not target or not dl_url.lower().startswith("https://"):
            continue
        if os.path.isfile(target) and expected_sha:
            try:
                with open(target, "rb") as f:
                    if _sha256_bytes(f.read()) == expected_sha:
                        skipped += 1
                        continue
            except OSError:
                pass
        to_fetch.append((rel, target, dl_url, expected_sha))

    updated = []
    total_bytes = 0
    total = max(1, len(to_fetch))
    for i, (rel, target, dl_url, expected_sha) in enumerate(to_fetch, start=1):
        if progress_cb:
            progress_cb(f"Downloading changed file {i}/{len(to_fetch)}: {rel}", i - 1, total)
        raw = _download_bytes(dl_url)
        if expected_sha and _sha256_bytes(raw) != expected_sha:
            raise ValueError(f"Checksum mismatch on {rel}")
        _atomic_write_bytes(target, raw)
        updated.append(rel)
        total_bytes += len(raw)

    return {
        "mode": "delta_manifest",
        "updated_files": updated,
        "skipped_files": skipped,
        "bytes_downloaded": total_bytes,
        "needs_restart": bool(updated),
        "relaunch_script": "",
    }


def _apply_github_tree_delta(info: dict, app_dir: str, progress_cb=None) -> dict:
    repo = info.get("repo", "")
    tag = info.get("tag", "")
    if not repo or not tag:
        raise ValueError("Missing GitHub repository or release tag for delta update.")

    if progress_cb:
        progress_cb("Comparing local files with release manifest...", 0, 100)

    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{quote(tag)}?recursive=1"
    res = requests.get(tree_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=15)
    res.raise_for_status()
    tree_entries = (res.json() or {}).get("tree", [])

    candidates: List[Tuple[str, str, str]] = []
    skipped = 0

    for entry in tree_entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        rel = str(entry.get("path", ""))
        remote_sha = str(entry.get("sha", "")).lower()
        if not _should_sync_repo_path(rel):
            continue
        target = _safe_target_path(app_dir, rel)
        if not target:
            continue
        if os.path.isfile(target) and remote_sha:
            try:
                with open(target, "rb") as f:
                    if _git_blob_sha1(f.read()) == remote_sha:
                        skipped += 1
                        continue
            except OSError:
                pass
        candidates.append((rel, target, remote_sha))

    updated = []
    total_bytes = 0
    total = max(1, len(candidates))
    for i, (rel, target, remote_sha) in enumerate(candidates, start=1):
        if progress_cb:
            progress_cb(f"Updating {i}/{len(candidates)}: {rel}", i - 1, total)
        raw_url = f"https://raw.githubusercontent.com/{repo}/{quote(tag)}/{quote(rel)}"
        raw = _download_bytes(raw_url)
        if remote_sha and _git_blob_sha1(raw) != remote_sha:
            raise ValueError(f"Git blob SHA mismatch while updating {rel}")
        _atomic_write_bytes(target, raw)
        updated.append(rel)
        total_bytes += len(raw)

    return {
        "mode": "github_tree_delta",
        "updated_files": updated,
        "skipped_files": skipped,
        "bytes_downloaded": total_bytes,
        "needs_restart": bool(updated),
        "relaunch_script": "",
    }


def _apply_patch_zip(info: dict, app_dir: str, progress_cb=None) -> dict:
    patch_url = info.get("patch_url", "")
    if not patch_url:
        raise ValueError("No patch archive URL available.")

    if progress_cb:
        progress_cb("Downloading incremental update patch...", 10, 100)
    raw_zip = _download_bytes(patch_url, timeout=45)

    updated = []
    skipped = 0
    with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        # Detect single top-level wrapper directory inside zip (e.g. LowCore-Launcher/)
        top_dirs = {m.filename.split("/", 1)[0] for m in members if "/" in m.filename}
        strip_prefix = ""
        if len(top_dirs) == 1 and all("/" in m.filename for m in members):
            only_dir = next(iter(top_dirs))
            if only_dir not in ("core", "ui", "assets", "bundled"):
                strip_prefix = only_dir + "/"

        total = max(1, len(members))
        for i, m in enumerate(members, start=1):
            rel = m.filename[len(strip_prefix):] if strip_prefix and m.filename.startswith(strip_prefix) else m.filename
            if not rel:
                continue
            target = _safe_target_path(app_dir, rel)
            if not target:
                continue
            data = zf.read(m.filename)
            if os.path.isfile(target):
                try:
                    with open(target, "rb") as f:
                        if _sha256_bytes(f.read()) == _sha256_bytes(data):
                            skipped += 1
                            continue
                except OSError:
                    pass
            if progress_cb:
                progress_cb(f"Applying {i}/{len(members)}: {rel}", i, total)
            _atomic_write_bytes(target, data)
            if sys.platform != "win32" and (rel.endswith(".sh") or data.startswith((b"\x7fELF", b"#!"))):
                try:
                    os.chmod(target, 0o755)
                except OSError:
                    pass
            updated.append(rel)

    return {
        "mode": "patch_zip",
        "updated_files": updated,
        "skipped_files": skipped,
        "bytes_downloaded": len(raw_zip),
        "needs_restart": bool(updated),
        "relaunch_script": "",
    }


def _apply_exe_swap(info: dict, progress_cb=None) -> dict:
    exe_url = info.get("exe_url", "")
    if not exe_url:
        raise ValueError("No standalone executable URL available.")
    current_exe = os.path.abspath(sys.executable)
    new_exe = current_exe + ".update.tmp"

    if progress_cb:
        progress_cb("Downloading updated LowCore executable...", 15, 100)
    raw = _download_bytes(exe_url, timeout=60)
    if sys.platform == "win32" and not raw.startswith(b"MZ"):
        raise ValueError("Downloaded binary is not a valid Windows executable.")
    _atomic_write_bytes(new_exe, raw)

    pid = os.getpid()
    if sys.platform == "win32":
        script_path = os.path.join(tempfile.gettempdir(), f"lowcore_swap_{pid}.bat")
        bat = (
            "@echo off\r\n"
            f":waitloop\r\n"
            f"tasklist /FI \"PID eq {pid}\" 2>nul | find \"{pid}\" >nul\r\n"
            f"if not errorlevel 1 (\r\n"
            f"  ping -n 2 127.0.0.1 >nul\r\n"
            f"  goto waitloop\r\n"
            f")\r\n"
            f"move /Y \"{new_exe}\" \"{current_exe}\" >nul\r\n"
            f"start \"\" \"{current_exe}\"\r\n"
            f"del \"%~f0\"\r\n"
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(bat)
    else:
        script_path = os.path.join(tempfile.gettempdir(), f"lowcore_swap_{pid}.sh")
        os.chmod(new_exe, 0o755)
        sh = (
            "#!/bin/sh\n"
            f"while kill -0 {pid} 2>/dev/null; do sleep 0.3; done\n"
            f"mv -f \"{new_exe}\" \"{current_exe}\"\n"
            f"chmod +x \"{current_exe}\"\n"
            f"\"{current_exe}\" &\n"
            f"rm -f \"$0\"\n"
        )
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(sh)
        os.chmod(script_path, 0o755)

    return {
        "mode": "exe_swap",
        "updated_files": [os.path.basename(current_exe)],
        "skipped_files": 0,
        "bytes_downloaded": len(raw),
        "needs_restart": True,
        "relaunch_script": script_path,
    }


def apply_in_place_update(info: dict, app_dir: str, progress_cb: Optional[Callable[[str, int, int], None]] = None) -> dict:
    """Download and apply ONLY what changed based on the update mode in `info`."""
    mode = (info or {}).get("mode", "browser")
    if mode == "delta_manifest":
        return _apply_delta_manifest(info, app_dir, progress_cb)
    if mode == "patch_zip":
        return _apply_patch_zip(info, app_dir, progress_cb)
    if mode == "github_tree_delta":
        return _apply_github_tree_delta(info, app_dir, progress_cb)
    if mode == "exe_swap":
        return _apply_exe_swap(info, progress_cb)
    raise ValueError("This release does not have an in-place patch or direct download URL.")


def spawn_relaunch(relaunch_script: str = ""):
    """Launch a delayed restart helper so single-instance QLocalServer closes before relaunch."""
    if relaunch_script and os.path.isfile(relaunch_script):
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/c", relaunch_script],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
                close_fds=True,
            )
        else:
            subprocess.Popen(["/bin/sh", relaunch_script], start_new_session=True, close_fds=True)
        return

    args = [sys.executable] + sys.argv
    helper = (
        "import subprocess, sys, time; "
        "time.sleep(0.9); "
        f"subprocess.Popen({args!r}, close_fds=True)"
    )
    kwargs = {"close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-c", helper], **kwargs)
