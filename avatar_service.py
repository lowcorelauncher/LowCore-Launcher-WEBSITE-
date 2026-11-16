import os
import re
import time
import threading
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtCore import Qt

_AVATAR_SESSION = None
_inflight = set()
_inflight_lock = threading.Lock()

# After a failed download (offline / all mirrors down) don't try again for a few minutes,
# otherwise every account-list refresh would block the UI for several seconds again.
_RETRY_AFTER_SECONDS = 300
_failed_until = {}


def _get_avatar_session():
    global _AVATAR_SESSION
    if _AVATAR_SESSION is None:
        import requests
        sess = requests.Session()
        sess.trust_env = False
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LowCoreClient/1.0"
        })
        _AVATAR_SESSION = sess
    return _AVATAR_SESSION


class AvatarService:
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".lowcorelauncher", "avatars")

    @classmethod
    def _cache_path(cls, acc_type: str, username: str, size: int) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", username) or "player"
        return os.path.join(cls.CACHE_DIR, f"{acc_type}_{safe}_{size}.png")

    @classmethod
    def get_avatar(cls, account: dict, size: int = 24, on_ready=None, blocking: bool = True) -> QPixmap:
        """
        Returns the account's head. Pass blocking=False to get Steve instantly and let the real head
        download in the background (on_ready is then called from the worker thread).
        """
        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        acc_type = account.get("type", "offline")
        username = account.get("name", "").strip()
        uuid = str(account.get("id") or account.get("uuid") or "").replace("-", "").strip()

        cache_path = cls._cache_path(acc_type, username, size)
        legacy_path = os.path.join(cls.CACHE_DIR, f"{username}_{size}.png")

        for path in (cache_path, legacy_path):
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    return cls._round_pixmap(pix, size)

        if acc_type == "ms" and username and time.time() >= _failed_until.get(cache_path, 0):
            if blocking:
                if cls._download_head(username, uuid, size, cache_path):
                    pix = QPixmap(cache_path)
                    if not pix.isNull():
                        return cls._round_pixmap(pix, size)
                _failed_until[cache_path] = time.time() + _RETRY_AFTER_SECONDS
            else:
                cls._fetch_in_background(username, uuid, size, cache_path, on_ready)

        return cls._create_default_steve(size)

    @staticmethod
    def _download_head(username: str, uuid: str, size: int, cache_path: str) -> bool:
        sess = _get_avatar_session()
        endpoints = [
            f"https://minotar.net/helm/{username}/{size}.png",
            f"https://crafatar.com/avatars/{uuid}?size={size}&overlay",
            f"https://mc-heads.net/avatar/{username}/{size}.png"
        ]
        for url in endpoints:
            try:
                resp = sess.get(url, timeout=(2, 3))
                if resp.status_code == 200 and len(resp.content) > 100:
                    tmp = cache_path + ".part"
                    with open(tmp, "wb") as f:
                        f.write(resp.content)
                    os.replace(tmp, cache_path)
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def _fetch_in_background(cls, username: str, uuid: str, size: int, cache_path: str, on_ready=None):
        with _inflight_lock:
            if cache_path in _inflight:
                return
            _inflight.add(cache_path)

        def worker():
            try:
                if cls._download_head(username, uuid, size, cache_path):
                    if on_ready:
                        try:
                            on_ready()
                        except Exception:
                            pass
                else:
                    _failed_until[cache_path] = time.time() + _RETRY_AFTER_SECONDS
            finally:
                with _inflight_lock:
                    _inflight.discard(cache_path)

        threading.Thread(target=worker, daemon=True).start()

    @classmethod
    def _create_default_steve(cls, size: int) -> QPixmap:
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        colors = {
            'H': 0xFF2A1C14,
            'S': 0xFFB98563,
            'E': 0xFFFFFFFF,
            'B': 0xFF2C397E,
            'N': 0xFFA56D4D,
            'M': 0xFF5D3924
        }
        matrix = [
            "HHHHHHHH",
            "HHHHHHHH",
            "HHSHHSHH",
            "SSSSSSSS",
            "SESBBSES",
            "SSSSSSSS",
            "SSMMMMSS",
            "SSSHHSSS"
        ]
        for y, row in enumerate(matrix):
            for x, char in enumerate(row):
                img.setPixelColor(x, y, colors.get(char, 0xFF000000))

        scaled = QPixmap.fromImage(img).scaled(
            size, size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        return cls._round_pixmap(scaled, size)

    @staticmethod
    def _round_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, 4, 4)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        painter.end()

        return rounded
