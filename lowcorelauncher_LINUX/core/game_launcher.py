import os
import sys
import uuid
import time
import hmac
import hashlib
import shutil
import subprocess
import threading
import minecraft_launcher_lib

NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _library_version_fallback() -> str:
    """Version string for minecraft_launcher_lib when its version.txt is not available."""
    try:
        from importlib.metadata import version
        return version("minecraft-launcher-lib")
    except Exception:
        return "unknown"


def _ensure_launcher_lib_data():
    """
    Packaged builds (PyInstaller etc.) can miss minecraft_launcher_lib's version.txt, which makes
    get_minecraft_command() fail with "[Errno 2] No such file or directory: ...\\version.txt".
    If the file is missing, try to recreate it, and if that is not possible make the library's
    version lookup return a fallback instead of crashing. Does nothing when the file exists.
    """
    try:
        pkg_dir = os.path.dirname(os.path.abspath(minecraft_launcher_lib.__file__))
        version_file = os.path.join(pkg_dir, "version.txt")
        if os.path.exists(version_file):
            return

        fallback = _library_version_fallback()
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(fallback)
            return
        except OSError:
            pass  # install folder is read-only: patch the lookup instead

        for name, module in list(sys.modules.items()):
            if (name == "minecraft_launcher_lib" or name.startswith("minecraft_launcher_lib.")) \
                    and module is not None and hasattr(module, "get_library_version"):
                setattr(module, "get_library_version", lambda: fallback)
    except Exception:
        pass  # never block a launch because of this safety net


# Mods shipped inside the launcher's bundled/ folder and copied into an instance's mods folder on every launch.
# Supports both GitHub Actions output names ("bundled/lowcore-mc<ver>-<modver>.jar") and legacy
# underscore naming ("bundled/LowCore-<ver_underscore>.jar").
BUNDLED_MC_VERSIONS = ("1.21.1", "1.21.4", "1.21.5", "1.21.8", "1.21.11", "26.1.2", "26.2", "26.3")
BUNDLED_MODS = [
    {
        "mc_version": ver,
        "loader": "fabric",
        "files": [
            f"bundled/lowcore-mc{ver}-2.0.0.jar",
            f"bundled/LowCore-{ver.replace('.', '_')}.jar",
        ],
    }
    for ver in BUNDLED_MC_VERSIONS
]


def _bundled_base_dirs():
    """Candidate root folders containing bundled/ in PyInstaller, Nuitka, or source runs."""
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        getattr(sys, "_MEIPASS", None),                 # PyInstaller
        os.path.dirname(os.path.abspath(sys.argv[0])),  # Nuitka standalone / next to the .exe
        os.path.dirname(here),                          # running from source (project root)
    ]


def _find_bundled(rel_path: str):
    """Locate a bundled file both when running from source and when packaged (PyInstaller / Nuitka)."""
    for base in _bundled_base_dirs():
        if base:
            path = os.path.join(base, rel_path)
            if os.path.isfile(path):
                return path
    return None


def _find_bundled_mod_jar(mod: dict):
    """Locate a matching bundled mod jar from explicit filenames or any lowcore-mc<ver>-*.jar in bundled/."""
    for rel_path in mod.get("files", ()):
        found = _find_bundled(rel_path)
        if found:
            return found

    mc_ver = mod["mc_version"]
    ver_token_a = f"mc{mc_ver}-"
    ver_token_b = f"-{mc_ver}."
    ver_token_c = f"-{mc_ver.replace('.', '_')}."
    for base in _bundled_base_dirs():
        if not base:
            continue
        for folder in (os.path.join(base, "bundled", mc_ver), os.path.join(base, "bundled")):
            if not os.path.isdir(folder):
                continue
            is_ver_subdir = os.path.basename(folder) == mc_ver
            for fname in sorted(os.listdir(folder)):
                low = fname.lower()
                if not low.endswith(".jar") or low.endswith("-sources.jar"):
                    continue
                if "lowcore" not in low:
                    continue
                if is_ver_subdir or (ver_token_a in low) or (ver_token_b in low) or (ver_token_c in low):
                    return os.path.join(folder, fname)
    return None


def _sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _matches_version_id(vid: str, loader: str, mc_version: str) -> bool:
    """Match loader and exact Minecraft version token so 1.21.1 does not collide with 1.21.11."""
    return loader in vid and (vid.endswith(f"-{mc_version}") or vid == mc_version)


def _inject_bundled_mods(version_id: str, instance_dir: str, log=None):
    """Copy bundled mods that match this instance's loader + Minecraft version into <instance>/mods."""
    vid = version_id.lower()
    for mod in BUNDLED_MODS:
        try:
            if not _matches_version_id(vid, mod["loader"], mod["mc_version"]):
                continue
            src = _find_bundled_mod_jar(mod)
            if not src:
                if log:
                    log(f"[CLIENT] Bundled mod not found for MC {mod['mc_version']} in bundled/")
                continue

            mods_dir = os.path.join(instance_dir, "mods")
            os.makedirs(mods_dir, exist_ok=True)
            target_name = os.path.basename(src)

            # Remove any stale LowCore jar from another MC version if this instance switched versions
            for existing in os.listdir(mods_dir):
                el = existing.lower()
                if el.startswith("lowcore") and el.endswith(".jar") and existing != target_name:
                    try:
                        os.remove(os.path.join(mods_dir, existing))
                    except OSError:
                        pass

            dst = os.path.join(mods_dir, target_name)
            if not os.path.exists(dst) or _sha1(dst) != _sha1(src):
                shutil.copy2(src, dst)
                if log:
                    log(f"[CLIENT] Installed bundled mod: {target_name}")
        except Exception as e:
            if log:
                log(f"[CLIENT] Could not install bundled mod: {e}")  # never block a launch


_GUARD_A = b'\xd0\t\xc3\x1a\x81W\x80\xbf\xf5\xeai\xc3"\x15\\\xa1\x8b\xc7\'\x84\xfc\xc2\xd1\x19i\xe7\rj\xc0\x8d\x05\x11'
_GUARD_B = b'\xd5-nq\x0e>\x89\x16/\xa8v,\xfd\xec_\xe1YK \x87\xdd\xba\xd5\xa3\x92\x008\xba\xbb\x86JZ'


def _build_launch_handshake() -> tuple:
    """Create a short-lived HMAC launch token passed via both env vars and JVM properties."""
    env = os.environ.copy()
    key = bytes(a ^ b for a, b in zip(_GUARD_A, _GUARD_B))
    ts = str(int(time.time()))
    nonce = os.urandom(16).hex()
    sig = hmac.new(key, f"{ts}:{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()
    env["LOWCORE_LAUNCH_TS"] = ts
    env["LOWCORE_LAUNCH_NONCE"] = nonce
    env["LOWCORE_LAUNCH_SIG"] = sig
    jvm_props = [
        f"-Dlowcore.launch.ts={ts}",
        f"-Dlowcore.launch.nonce={nonce}",
        f"-Dlowcore.launch.sig={sig}",
    ]
    return env, jvm_props


def _build_launch_env() -> dict:
    """Backward-compatible wrapper returning only the signed process environment."""
    return _build_launch_handshake()[0]


class GameLauncher:
    def __init__(self, base_dir: str, log_callback=None):
        self.base_dir = base_dir
        self.log_callback = log_callback

    def sanitize_uuid(self, account: dict) -> str:
        raw_id = str(account.get("id", "")).strip().replace("-", "")
        uname = account.get("name", "Player")

        if len(raw_id) == 32:
            return f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"

        original_id = str(account.get("id", "")).strip()
        if len(original_id) == 36 and original_id.count("-") == 4:
            return original_id

        return str(uuid.UUID(bytes=hashlib.md5(f"OfflinePlayer:{uname}".encode("utf-8")).digest()[:16]))

    def launch(
        self,
        version_id: str,
        account: dict,
        jvm_args: list,
        instance_dir: str,
        java_bin: str = "java",
        custom_res: dict = None,
        multicore_enabled: bool = None,
        cpu_cores: int = 0,
    ):
        clean_uuid = self.sanitize_uuid(account)
        access_token = account.get("access_token")

        if account.get("type") == "offline" or not access_token:
            access_token = "0"

        launch_env, guard_jvm_props = _build_launch_handshake()
        cleaned_jvm_args = [
            a for a in (jvm_args or [])
            if not str(a).startswith("-Dlowcore.launch.")
        ]
        cleaned_jvm_args.extend(guard_jvm_props)

        # Infer multicore/cores from JVM flags if caller didn't pass explicit arguments
        if multicore_enabled is None:
            multicore_enabled = True
            for arg in cleaned_jvm_args:
                s = str(arg)
                if s == "-Dlowcore.multicore=false":
                    multicore_enabled = False
                    break
        if not cpu_cores:
            for arg in cleaned_jvm_args:
                s = str(arg)
                if s.startswith("-XX:ActiveProcessorCount="):
                    try:
                        cpu_cores = int(s.split("=", 1)[1])
                    except ValueError:
                        pass

        options = {
            "username": account.get("name", "Player"),
            "uuid": clean_uuid,
            "token": access_token,
            "gameDirectory": instance_dir,
            "jvmArguments": cleaned_jvm_args
        }

        # Window size from Settings (main_window passes {"width": .., "height": ..})
        if custom_res and custom_res.get("width") and custom_res.get("height"):
            options["customResolution"] = True
            options["resolutionWidth"] = str(int(custom_res["width"]))
            options["resolutionHeight"] = str(int(custom_res["height"]))

        _ensure_launcher_lib_data()
        _inject_bundled_mods(version_id, instance_dir, self.log_callback)

        cmd = minecraft_launcher_lib.command.get_minecraft_command(
            version=version_id,
            minecraft_directory=self.base_dir,
            options=options
        )

        if java_bin and java_bin != "java":
            cmd[0] = java_bin

        # "Start Fullscreen" checkbox in Settings
        if custom_res and custom_res.get("fullscreen"):
            cmd.append("--fullscreen")

        if self.log_callback:
            self.log_callback(f"[CLIENT] Launching version: {version_id}")
            self.log_callback(f"[CLIENT] Instance Isolated Dir: {instance_dir}")
            self.log_callback(f"[CLIENT] Shared Assets/Libs Dir: {self.base_dir}")
            self.log_callback(f"[CLIENT] Normalized Player UUID: {clean_uuid}")
            self.log_callback("[CLIENT] Attached LowCore launch verification token (env + JVM props)")
            self.log_callback(f"[CLIENT] Starting process with {len(cmd)} arguments...")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,   # a windowed .exe has no console stdin: without this Popen raises WinError 6
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=instance_dir,
            env=launch_env,
            creationflags=NO_WINDOW
        )

        try:
            from core.optimization import OptimizationEngine
            aff_cores = OptimizationEngine.apply_process_core_affinity(
                process.pid,
                multicore_enabled=bool(multicore_enabled),
                cpu_cores=int(cpu_cores or 0),
            )
            if self.log_callback and aff_cores:
                mode_lbl = "MULTICORE" if multicore_enabled else "SINGLE-CORE"
                self.log_callback(f"[OPT] OS CPU Core Affinity ({mode_lbl}): {aff_cores} core(s) active")
        except Exception:
            pass

        def stream_logs():
            for line in iter(process.stdout.readline, ''):
                if self.log_callback:
                    self.log_callback(line.rstrip())
            process.stdout.close()

        t = threading.Thread(target=stream_logs, daemon=True)
        t.start()

        return process
