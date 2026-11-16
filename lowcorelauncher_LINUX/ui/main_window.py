import os
import sys
import gc
import json
import time
import shutil
import webbrowser
import subprocess
import ctypes
import html
import math
import re
from collections import OrderedDict, deque
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QDialog, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QFileDialog, QGraphicsOpacityEffect, QStackedWidget,
    QSystemTrayIcon, QMenu, QCheckBox, QSizePolicy, QScrollArea, QGridLayout
)
from PyQt6.QtCore import (
    Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QSize,
    QPropertyAnimation, QEasingCurve, QRect, QPoint, QTimer, pyqtProperty, QEvent,
    QVariantAnimation, QRectF, QPointF, QByteArray, QBuffer, QIODevice
)
from PyQt6.QtGui import (
    QPixmap, QImage, QImageReader, QIcon, QKeyEvent, QAction, QTextCursor, QPainter,
    QColor, QPen, QPainterPath, QFont, QFontMetrics, QPolygonF, QPixmapCache
)
from PyQt6.QtNetwork import QNetworkProxy

from core.config import ConfigManager
from core.theme_manager import ThemeManager
from core.instance_manager import InstanceManager
from core.avatar_service import AvatarService
from core.license import LicenseManager
from core import horizon_bridge as hb
from core.version import APP_VERSION, UPDATE_MANIFEST_URL
from core.i18n import I18n, LANGUAGE_META


TOS_VERSION = "1.2"
WHATS_NEW_KEY = "whats_new_shown_v1_2"
SUPPORTED_MC_VERSIONS = ("1.21.1", "1.21.4", "1.21.5", "1.21.8", "1.21.11", "26.1.2", "26.2", "26.3")

LOWCORE_JAR_DISCLAIMER_TEXT = (
    "IMPORTANT DISCLAIMER FOR LOWCORE.JAR USERS\n"
    "• Exclusive Launcher Binding (LauncherGuard): Bundled lowcore.jar (lowcore-mc*.jar) builds contain "
    "runtime verification and will ONLY run when launched from official LowCore Client. Dropping lowcore.jar "
    "into Prism, Modrinth App, CurseForge, or the Official Minecraft Launcher will intentionally close Minecraft.\n"
    "• Available Minecraft Versions: 1.21.1, 1.21.4, 1.21.5, 1.21.8, 1.21.11, 26.1.2, 26.2, and 26.3 (Fabric).\n"
    "• Fair-Play & Server Rules: LowCore provides client-side FPS optimization, HUD elements, and cosmetic capes. "
    "You are responsible for following the rules of every multiplayer server you join.\n"
    "• World Safety: Modded clients are provided 'as-is' without warranty. Always back up important worlds."
)

LOWCORE_TOS_TEXT = (
    "LOWCORE CLIENT — TERMS OF SERVICE (Version 1.2)\n\n"
    "By installing, opening, or using LowCore Client and its bundled lowcore.jar mod builds, you agree to the following terms:\n\n"
    "1. Authorized Use & Integrity\n"
    "   LowCore Mod (.jar) packages are built specifically to run inside LowCore Client. You agree not to strip, forge, "
    "or bypass LauncherGuard verification tokens or redistribute modified/tampered LowCore binaries.\n\n"
    "2. Multiplayer Compliance\n"
    "   You are solely responsible for how you configure modules in multiplayer environments. LowCore is not liable for "
    "server kicks, bans, or third-party moderation actions resulting from your mod configuration.\n\n"
    "3. Accounts, Privacy & Local Data\n"
    "   Microsoft sign-in uses Microsoft's official OAuth device flow. Account tokens, instances, settings, and capes "
    "remain stored locally on your machine; LowCore Client never sells credentials or personal data.\n\n"
    "4. Third-Party Software & Mods\n"
    "   Content downloaded via Modrinth (such as Fabric API, Sodium, shaders, or resource packs) and optional external "
    "tools (such as Horizon) are subject to their respective authors' terms and licenses.\n\n"
    "5. Disclaimer of Warranty\n"
    "   LowCore Client and lowcore.jar are provided 'AS IS' without warranties of any kind. Maintain regular backups of "
    "your worlds and saves before updating Minecraft versions or installing new mods."
)

DISCORD_INVITE_URL = "https://discord.gg/VK8eZZY8T7"
PATREON_DONATE_URL = (
    "https://www.patreon.com/LowCoreLauncher/posts/support-my-work-174078024"
    "?utm_medium=clipboard_copy&utm_source=copyLink&utm_campaign=postshare_creator&utm_content=join_link"
)


def _find_launcher_asset(rel_path: str, base_dir: str = None):
    """Locate an asset file (e.g. assets/rshift.png) across source, PyInstaller, and Nuitka layouts."""
    candidates = []
    if base_dir:
        candidates.append(os.path.join(base_dir, "assets", rel_path))
        candidates.append(os.path.join(base_dir, rel_path))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "assets", rel_path))
        candidates.append(os.path.join(meipass, rel_path))
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidates.append(os.path.join(exe_dir, "assets", rel_path))
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", rel_path))
    candidates.append(os.path.join(os.getcwd(), "assets", rel_path))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


if sys.platform == "win32":
    try:
        myappid = "lowcore.launcher.client.beta"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass


_ICON_SESSION = None
ICON_CACHE = OrderedDict()
_ICON_CACHE_MAX = 24


def _get_icon_session():
    global _ICON_SESSION
    if _ICON_SESSION is None:
        import requests
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 LowCoreLauncher/1.2"
        })
        _ICON_SESSION = sess
    return _ICON_SESSION


_WIN_MEM_PROTOS = None


def _get_win_mem_api():
    global _WIN_MEM_PROTOS
    if _WIN_MEM_PROTOS is not None:
        return _WIN_MEM_PROTOS
    try:
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=False)
        kernel32.GetProcessHeap.argtypes = []
        kernel32.GetProcessHeap.restype = wintypes.HANDLE
        kernel32.HeapCompact.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.HeapCompact.restype = ctypes.c_size_t
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetProcessWorkingSetSizeEx.argtypes = [
            wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD
        ]
        kernel32.SetProcessWorkingSetSizeEx.restype = wintypes.BOOL
        k32_empty = getattr(kernel32, "K32EmptyWorkingSet", None)
        if k32_empty is not None:
            k32_empty.argtypes = [wintypes.HANDLE]
            k32_empty.restype = wintypes.BOOL
        psapi_empty = None
        try:
            psapi = ctypes.WinDLL("psapi", use_last_error=False)
            psapi_empty = getattr(psapi, "EmptyWorkingSet", None)
            if psapi_empty is not None:
                psapi_empty.argtypes = [wintypes.HANDLE]
                psapi_empty.restype = wintypes.BOOL
        except Exception:
            pass
        ucrt_heapmin = None
        try:
            ucrt = ctypes.CDLL("ucrtbase")
            ucrt_heapmin = getattr(ucrt, "_heapmin", None)
            if ucrt_heapmin is not None:
                ucrt_heapmin.argtypes = []
                ucrt_heapmin.restype = ctypes.c_int
        except Exception:
            pass
        _WIN_MEM_PROTOS = (kernel32, k32_empty, psapi_empty, ucrt_heapmin)
    except Exception:
        _WIN_MEM_PROTOS = ()
    return _WIN_MEM_PROTOS


def _trim_process_memory(clear_pixmap_cache: bool = True):
    """Releases dead Python objects, Qt pixmap caches, and cold OS working-set pages."""
    try:
        if clear_pixmap_cache:
            QPixmapCache.clear()
            try:
                _prune_large_block_cache()
            except Exception:
                pass
        gc.collect()
        if sys.platform == "win32":
            api = _get_win_mem_api()
            if api:
                kernel32, k32_empty, psapi_empty, ucrt_heapmin = api
                try:
                    heap = kernel32.GetProcessHeap()
                    if heap:
                        kernel32.HeapCompact(heap, 0)
                except Exception:
                    pass
                if ucrt_heapmin is not None:
                    try:
                        ucrt_heapmin()
                    except Exception:
                        pass
                try:
                    proc = kernel32.GetCurrentProcess()
                    kernel32.SetProcessWorkingSetSizeEx(proc, ctypes.c_size_t(-1), ctypes.c_size_t(-1), 0)
                    ok = False
                    if k32_empty is not None:
                        ok = bool(k32_empty(proc))
                    if not ok and psapi_empty is not None:
                        psapi_empty(proc)
                except Exception:
                    pass
        elif sys.platform.startswith("linux"):
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except Exception:
                pass
    except Exception:
        pass


def crop_transparent_padding(pixmap: QPixmap, source_path: str = None) -> QPixmap:
    """Trims transparent border pixels fast (via RGBA byte scan + disk cache) so the icon fills 100% of slots."""
    if pixmap.isNull():
        return pixmap

    cache_dir = os.path.join(os.path.expanduser("~"), ".lowcorelauncher")
    cache_img = os.path.join(cache_dir, "trimmed_logo.png")
    cache_meta = os.path.join(cache_dir, "trimmed_logo.meta")
    sig = None
    if source_path:
        try:
            st = os.stat(source_path)
            sig = f"{st.st_size}:{st.st_mtime_ns}"
            if os.path.exists(cache_img) and os.path.exists(cache_meta):
                with open(cache_meta, "r", encoding="utf-8") as mf:
                    if mf.read().strip() == sig:
                        cached = QPixmap(cache_img)
                        if not cached.isNull():
                            return cached
        except OSError:
            sig = None

    work_pix = pixmap
    if work_pix.width() > 256 or work_pix.height() > 256:
        work_pix = work_pix.scaled(
            256, 256,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    img = work_pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    raw = img.constBits().asstring(img.sizeInBytes())

    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row_start = y * bpl
        alphas = raw[row_start + 3:row_start + w * 4:4]
        if not alphas or max(alphas) <= 15:
            continue
        if y < min_y:
            min_y = y
        max_y = y
        first_x = next((x for x, a in enumerate(alphas) if a > 15), None)
        if first_x is not None:
            if first_x < min_x:
                min_x = first_x
            last_x = w - 1 - next(i for i, a in enumerate(reversed(alphas)) if a > 15)
            if last_x > max_x:
                max_x = last_x

    result = work_pix
    if max_x >= min_x and max_y >= min_y:
        bw = max_x - min_x + 1
        bh = max_y - min_y + 1
        side = max(bw, bh)
        cx = min_x + bw // 2
        cy = min_y + bh // 2
        x0 = max(0, cx - side // 2)
        y0 = max(0, cy - side // 2)
        side = min(side, w - x0, h - y0)
        result = work_pix.copy(x0, y0, side, side)

    if sig:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            if result.save(cache_img, "PNG"):
                with open(cache_meta, "w", encoding="utf-8") as mf:
                    mf.write(sig)
        except OSError:
            pass

    return result


# ======================================================================================
#  UI kit: animated buttons, animated switches (replace check boxes), rounded window pieces
# ======================================================================================
def fade_in_widget(widget, duration: int = 190):
    """Quick fade-in used when pages change. Leaves widgets that already have an effect alone."""
    if widget is None or sip.isdeleted(widget) or widget.graphicsEffect() is not None:
        return
    eff = QGraphicsOpacityEffect(widget)
    eff.setOpacity(0.0)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done(w=widget):
        if not sip.isdeleted(w):
            w.setGraphicsEffect(None)
    anim.finished.connect(done)
    anim.start()


class AnimatedButton(QPushButton):
    """Button with a smooth hover glow and press feedback on top of the theme's own styling."""
    light_theme = False
    _RADII = {"PlayButton": 10, "PillButton": 8}

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = 0.0
        self._press = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(120)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press)

    @staticmethod
    def _go(anim: QVariantAnimation, start: float, end: float):
        anim.stop()
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.start()

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def _on_press(self, v):
        self._press = float(v)
        self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._go(self._hover_anim, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._go(self._hover_anim, self._hover, 0.0)
        self._go(self._press_anim, self._press, 0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._go(self._press_anim, self._press, 1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._go(self._press_anim, self._press, 0.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isEnabled() or (self._hover < 0.01 and self._press < 0.01):
            return
        radius = self._RADII.get(self.objectName(), 8)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._hover >= 0.01:
            c = QColor(0, 0, 0) if AnimatedButton.light_theme else QColor(255, 255, 255)
            c.setAlpha(int(26 * self._hover))
            p.setBrush(c)
            p.drawRoundedRect(r, radius, radius)
        if self._press >= 0.01:
            p.setBrush(QColor(0, 0, 0, int(46 * self._press)))
            p.drawRoundedRect(r, radius, radius)
        p.end()


class SwitchCheckBox(QCheckBox):
    """A QCheckBox that looks and moves like a modern switch. Same API (isChecked, setChecked, toggled...)."""
    colors = {"accent": "#2D8CDB", "off": "#4A505C", "text": "#E6E8EC", "text_sub": "#9AA0AA", "knob": "#FFFFFF"}

    @classmethod
    def set_theme(cls, t: dict):
        cls.colors = {
            "accent": t["accent"],
            "off": _lerp_color(t["pill_hover"], t["text_sub"], 0.38).name(),
            "text": t["text"],
            "text_sub": t["text_sub"],
            "knob": "#FFFFFF",
        }

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._compact = False
        self._pos = 1.0 if self.isChecked() else 0.0
        self._hover = 0.0
        self._press = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_font()

        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(210)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(120)
        self._press_anim.valueChanged.connect(self._on_press)
        self.toggled.connect(self._animate_to)

    # ---- look
    def set_compact(self, value: bool = True):
        self._compact = value
        self._apply_font()
        self.updateGeometry()
        self.update()

    def _apply_font(self):
        f = self.font()
        f.setPixelSize(11 if self._compact else 13)
        f.setWeight(QFont.Weight.DemiBold)
        self.setFont(f)

    PAD = 4

    def _dims(self):
        return (32, 18) if self._compact else (40, 22)

    def sizeHint(self):
        tw, th = self._dims()
        fm = self.fontMetrics()
        text = self.text()
        w = tw + self.PAD * 2 + ((12 + fm.horizontalAdvance(text)) if text else 0)
        return QSize(w, max(th + 10, fm.height() + 8))

    def minimumSizeHint(self):
        return QSize(self._dims()[0] + self.PAD * 2, self.sizeHint().height())

    def hitButton(self, pos):
        return self.rect().contains(pos)      # the whole row is clickable, not just the tiny box

    # ---- animation
    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float):
        self._pos = v
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def _animate_to(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def _on_press(self, v):
        self._press = float(v)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._pos = 1.0 if self.isChecked() else 0.0

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        for anim, cur in ((self._hover_anim, self._hover), (self._press_anim, self._press)):
            anim.stop()
            anim.setStartValue(cur)
            anim.setEndValue(0.0)
            anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_anim.stop()
            self._press_anim.setStartValue(self._press)
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press)
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()
        super().mouseReleaseEvent(event)

    # ---- painting
    def paintEvent(self, event):
        c = SwitchCheckBox.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            p.setOpacity(0.5)

        tw, th = self._dims()
        y = (self.height() - th) / 2.0
        track = QRectF(self.PAD, y, tw, th)

        col = _lerp_color(c["off"], c["accent"], self._pos)
        col = _lerp_color(col, "#FFFFFF", self._hover * 0.12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(track, th / 2.0, th / 2.0)

        kd = th - 6
        kw = kd + 4 * self._press            # the knob stretches a little while pressed
        kx = track.x() + 3 + self._pos * (tw - 6 - kw)
        knob = QRectF(kx, y + 3, kw, kd)
        p.setBrush(QColor(0, 0, 0, 55))      # soft shadow under the knob
        p.drawRoundedRect(knob.translated(0, 1), kd / 2.0, kd / 2.0)
        p.setBrush(QColor(c["knob"]))
        p.drawRoundedRect(knob, kd / 2.0, kd / 2.0)

        if self.hasFocus() and self.focusPolicy() != Qt.FocusPolicy.NoFocus:
            p.setBrush(Qt.BrushStyle.NoBrush)
            ring = QColor(c["accent"])
            ring.setAlpha(150)
            p.setPen(QPen(ring, 1.5))
            p.drawRoundedRect(track.adjusted(-2, -2, 2, 2), th / 2.0 + 2, th / 2.0 + 2)

        text = self.text()
        if text:
            fm = self.fontMetrics()
            tx = track.right() + 12
            avail = max(10, int(self.width() - tx))
            elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, avail)
            if elided != text:
                self.setToolTip(text)
            p.setPen(QColor(c["text_sub"] if self._compact else c["text"]))
            p.setFont(self.font())
            p.drawText(QRectF(tx, 0, avail, self.height()),
                       int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided)
        p.end()


class WindowControlButton(QWidget):
    """Round minimize / close button for the custom (frameless) title area."""
    clicked = pyqtSignal()

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Minimize" if kind == "min" else "Close")
        self._hover = 0.0
        self._glyph = QColor("#9AA0AA")
        self._hover_bg = QColor("#2A2D34")
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_value)

    def set_theme(self, glyph: str, hover_bg: str):
        self._glyph = QColor(glyph)
        self._hover_bg = QColor(hover_bg)
        self.update()

    def _on_value(self, v):
        self._hover = float(v)
        self.update()

    def _go(self, end: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, event):
        self._go(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._go(0.0)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        is_close = self.kind == "close"
        bg = _lerp_color(QColor(0, 0, 0, 0), QColor("#E5484D") if is_close else self._hover_bg, self._hover)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        glyph = _lerp_color(self._glyph, QColor("#FFFFFF") if is_close else self._glyph, self._hover)
        pen = QPen(glyph, 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        if is_close:
            d = 4.2
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
        else:
            p.drawLine(QPointF(cx - 4.6, cy + 1), QPointF(cx + 4.6, cy + 1))
        p.end()


class RoundedRoot(QWidget):
    """Window background: rounded corners, thin border and a soft shadow. Also drags the window."""
    SHADOW = 14
    RADIUS = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg = QColor("#121316")
        self._border = QColor("#2A2D34")
        self.controls = []
        self._press_pos = None

    def set_colors(self, bg: str, border: str):
        self._bg = QColor(bg)
        self._border = QColor(border)
        self.update()

    def reposition_controls(self):
        x = self.width() - self.SHADOW - 16
        for btn in reversed(self.controls):
            x -= btn.width()
            btn.move(x, self.SHADOW + 10)
            x -= 6

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_controls()

    def paintEvent(self, event):
        S, R = self.SHADOW, self.RADIUS
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(S, S, -S, -S)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(S - 3, 0, -1):
            alpha = int(40 * (1 - i / float(S)) ** 2)
            p.setPen(QPen(QColor(0, 0, 0, alpha), 1.2))
            p.drawRoundedRect(rect.translated(0, 3).adjusted(-i, -i, i, i), R + i, R + i)
        p.setPen(QPen(self._border, 1))
        p.setBrush(self._bg)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), R, R)
        p.end()

    # drag the window from empty areas near the top
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._press_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton)
                and self._press_pos.y() < self.SHADOW + 125
                and (event.position().toPoint() - self._press_pos).manhattanLength() > 6):
            self._press_pos = None
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        super().mouseReleaseEvent(event)


class FramelessDialog(QDialog):
    """Frameless rounded dialog matching the main launcher window (no native white OS titlebar)."""

    def __init__(self, theme_name: str = "Dark Mode", title: str = "", parent=None, use_main_bg: bool = False):
        super().__init__(parent)
        self.theme_name = theme_name
        self._use_main_bg = use_main_bg
        self._closing = False
        self._intro_done = False

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.0)

        if parent and hasattr(parent, "app_icon") and not parent.app_icon.isNull():
            self.setWindowIcon(parent.app_icon)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.root_frame = RoundedRoot(self)
        outer.addWidget(self.root_frame)

        _s = RoundedRoot.SHADOW
        self._shell_layout = QVBoxLayout(self.root_frame)
        self._shell_layout.setContentsMargins(_s, _s, _s, _s)
        self._shell_layout.setSpacing(0)

        # Custom title bar inside the rounded card
        title_bar = QWidget(self.root_frame)
        title_bar.setObjectName("DialogTitleBar")
        title_bar.setFixedHeight(44)
        title_bar.setStyleSheet("QWidget#DialogTitleBar { background: transparent; border: none; }")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(18, 8, 14, 4)
        tb_layout.setSpacing(10)

        self._title_icon = QLabel()
        self._title_icon.setFixedSize(18, 18)
        self._title_icon.setStyleSheet("background: transparent; border: none;")
        pix = getattr(parent, "trimmed_logo_pix", None) if parent else None
        if pix is not None and not pix.isNull():
            self._title_icon.setPixmap(
                pix.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            tb_layout.addWidget(self._title_icon)
        else:
            self._title_icon.hide()

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("DialogTitle")
        tb_layout.addWidget(self._title_lbl, stretch=1)

        self._close_btn = WindowControlButton("close", title_bar)
        self._close_btn.clicked.connect(self.reject)
        tb_layout.addWidget(self._close_btn)

        self._shell_layout.addWidget(title_bar)

        self._divider = QFrame(self.root_frame)
        self._divider.setObjectName("DialogDivider")
        self._divider.setFixedHeight(1)
        self._shell_layout.addWidget(self._divider)

        self.body_widget = QWidget(self.root_frame)
        self.body_widget.setObjectName("DialogBody")
        self.body_widget.setStyleSheet("QWidget#DialogBody { background: transparent; border: none; }")
        self.body_layout = QVBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(24, 18, 24, 22)
        self.body_layout.setSpacing(12)
        self._shell_layout.addWidget(self.body_widget, stretch=1)

        self._apply_dialog_theme(theme_name)
        if title:
            super().setWindowTitle(title)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if hasattr(self, "_title_lbl"):
            self._title_lbl.setText(title)

    def set_dialog_fixed_size(self, width: int, height: int):
        _s = RoundedRoot.SHADOW
        self.setFixedSize(width + 2 * _s, height + 2 * _s)

    def set_dialog_size(self, width: int, height: int, min_w: int = None, min_h: int = None):
        _s = RoundedRoot.SHADOW
        if min_w is not None and min_h is not None:
            self.setMinimumSize(min_w + 2 * _s, min_h + 2 * _s)
        self.resize(width + 2 * _s, height + 2 * _s)

    def _apply_dialog_theme(self, theme_name: str, extra_qss: str = ""):
        t = ThemeManager.get_theme_data(theme_name)
        bg_hex = t["bg"] if self._use_main_bg else t["card_bg"]
        self.root_frame.set_colors(bg_hex, t["border"])
        self._close_btn.set_theme(t["text_sub"], t["pill_hover"])
        self.setStyleSheet(f"""
            {ThemeManager.get_style(theme_name)}
            QDialog {{ background-color: transparent; }}
            QLabel#DialogTitle {{
                font-size: 13px;
                font-weight: 800;
                color: {t['text']};
                background: transparent;
                border: none;
            }}
            QFrame#DialogDivider {{
                background-color: {t['border']};
                border: none;
            }}
            {extra_qss}
        """)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._intro_done:
            self._intro_done = True
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(190)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._open_anim = anim
            anim.start()

    def done(self, result):
        if self._closing or not self.isVisible():
            super().done(result)
            return
        self._closing = True
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(140)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(lambda: QDialog.done(self, result))
        self._close_anim = anim
        anim.start()


class StyledMessageDialog(FramelessDialog):
    """Custom frameless replacement for QMessageBox."""

    def __init__(
        self,
        title: str,
        text: str,
        kind: str = "info",
        buttons: list = None,
        informative_text: str = "",
        theme_name: str = "Dark Mode",
        parent=None,
    ):
        super().__init__(theme_name=theme_name, title=title, parent=parent)
        self.clicked_label = None
        t = ThemeManager.get_theme_data(theme_name)

        self.body_layout.setContentsMargins(24, 18, 24, 20)
        self.body_layout.setSpacing(14)

        row = QHBoxLayout()
        row.setSpacing(14)

        icon_map = {
            "error": ("!", "#E5484D"),
            "warning": ("!", "#F5A623"),
            "question": ("?", t["accent"]),
            "info": ("i", t["accent"]),
        }
        glyph, badge_col = icon_map.get(kind, ("i", t["accent"]))

        badge = QLabel(glyph)
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            background-color: {_hex_rgba(badge_col, 0.16)};
            color: {badge_col};
            border: 1px solid {_hex_rgba(badge_col, 0.45)};
            border-radius: 17px;
            font-size: 16px;
            font-weight: 900;
        """)
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        msg_col = QVBoxLayout()
        msg_col.setSpacing(6)
        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t['text']}; background: transparent; border: none;")
        msg_col.addWidget(msg_lbl)

        if informative_text:
            info_lbl = QLabel(informative_text)
            info_lbl.setWordWrap(True)
            info_lbl.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {t['text_sub']}; background: transparent; border: none;")
            msg_col.addWidget(info_lbl)

        row.addLayout(msg_col, stretch=1)
        self.body_layout.addLayout(row)

        btn_specs = buttons or [("OK", "primary", True)]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        for label, style_role, is_accept in btn_specs:
            btn = AnimatedButton(label)
            btn.setObjectName("PlayButton" if style_role == "primary" else "PillButton")
            btn.setFixedHeight(38)
            btn.setMinimumWidth(92)
            if style_role == "danger":
                btn.setStyleSheet("color: #FF5555; border: 1px solid rgba(255, 85, 85, 0.45);")
            btn.clicked.connect(lambda _=False, lbl=label, acc=is_accept: self._choose(lbl, acc))
            btn_row.addWidget(btn)

        self.body_layout.addLayout(btn_row)
        self.setMinimumWidth(400 + 2 * RoundedRoot.SHADOW)
        self.setMaximumWidth(500 + 2 * RoundedRoot.SHADOW)
        self.adjustSize()

    def _choose(self, label: str, is_accept: bool):
        self.clicked_label = label
        if is_accept:
            self.accept()
        else:
            self.reject()

    @classmethod
    def alert(cls, parent, title: str, text: str, is_error: bool = False, kind: str = None):
        theme = getattr(parent, "current_theme", "Dark Mode")
        dlg_kind = kind or ("error" if is_error else "info")
        dlg = cls(title, text, kind=dlg_kind, theme_name=theme, parent=parent)
        dlg.exec()

    @classmethod
    def confirm(cls, parent, title: str, text: str, kind: str = "question", yes_text: str = "Yes", no_text: str = "No", danger: bool = False) -> bool:
        theme = getattr(parent, "current_theme", "Dark Mode")
        yes_role = "danger" if danger else "primary"
        dlg = cls(
            title, text, kind=kind,
            buttons=[(no_text, "secondary", False), (yes_text, yes_role, True)],
            theme_name=theme, parent=parent
        )
        return dlg.exec() == QDialog.DialogCode.Accepted


class StyledInputDialog(FramelessDialog):
    """Custom frameless replacement for QInputDialog.getText."""

    def __init__(self, title: str, label: str, text: str = "", theme_name: str = "Dark Mode", parent=None):
        super().__init__(theme_name=theme_name, title=title, parent=parent)
        t = ThemeManager.get_theme_data(theme_name)
        self.set_dialog_fixed_size(420, 190)

        lbl = QLabel(label)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t['text']}; background: transparent; border: none;")
        self.body_layout.addWidget(lbl)

        self.input_edit = QLineEdit(text)
        self.input_edit.selectAll()
        self.input_edit.returnPressed.connect(self.accept)
        self.body_layout.addWidget(self.input_edit)

        self.body_layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = AnimatedButton("Cancel")
        cancel_btn.setObjectName("PillButton")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setMinimumWidth(92)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = AnimatedButton("Confirm")
        ok_btn.setObjectName("PlayButton")
        ok_btn.setFixedHeight(38)
        ok_btn.setMinimumWidth(104)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        self.body_layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(20, self.input_edit.setFocus)

    @classmethod
    def get_text(cls, parent, title: str, label: str, text: str = "") -> tuple:
        theme = getattr(parent, "current_theme", "Dark Mode")
        dlg = cls(title, label, text=text, theme_name=theme, parent=parent)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.input_edit.text(), ok




class ClickableTextLabel(QLabel):
    clicked = pyqtSignal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            txt = self.text()
            x = int(event.position().x())
            fm = QFontMetrics(self.font())
            for i, ch in enumerate(txt):
                if x <= fm.horizontalAdvance(txt[:i + 1]):
                    if ch.isalpha():
                        self.clicked.emit(ch.lower())
                    break
        super().mousePressEvent(event)


class ClickableLetterLabel(QLabel):
    clicked = pyqtSignal(str)

    def __init__(self, char: str, parent=None):
        super().__init__(char, parent)
        self.char = char
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.char.lower())
        super().mousePressEvent(event)


class ScalingLogoLabel(QLabel):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self._target_size = 140
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")

    @pyqtProperty(int)
    def target_size(self) -> int:
        return self._target_size

    @target_size.setter
    def target_size(self, size: int):
        self._target_size = size
        self.setFixedSize(size, size)
        scaled = self.original_pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)


def format_log_line_html(line: str, theme_name: str = "Dark Mode") -> str:
    escaped = html.escape(line)
    upper = line.upper()
    light = ThemeManager.is_light(theme_name)

    if any(k in upper for k in ["[ERROR]", "ERROR", "FATAL", "EXCEPTION", "CRASH", "FAILED", "OS::COMMIT_MEMORY"]):
        color = "#C62828" if light else "#FF5555"
    elif any(k in upper for k in ["[WARN]", "[WARNING]", "WARN"]):
        color = "#B26A00" if light else "#FFB86C"
    elif any(k in upper for k in ["[AUTH]", "[CLIENT]", "[LAUNCH]"]):
        color = "#1E8E3E" if light else "#50FA7B"
    elif any(k in upper for k in ["[DEBUG]", "FINE", "TRACE"]):
        color = "#8A909E"
    else:
        color = "#1A1B1E" if light else "#F8F8F2"

    return f'<span style="color: {color}; font-family: Consolas, monospace; font-size: 12px; line-height: 1.4;">{escaped}</span><br>'


def format_playtime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_min = minutes % 60
    return f"{hours}h {rem_min}m"


def format_last_played(timestamp) -> str:
    if not timestamp:
        return "Never"
    try:
        delta = time.time() - float(timestamp)
    except (TypeError, ValueError):
        return "Never"
    if delta < 60:
        return "Just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    days = int(delta // 86400)
    if days == 1:
        return "Yesterday"
    if days < 30:
        return f"{days}d ago"
    return time.strftime("%b %d, %Y", time.localtime(float(timestamp)))


class ModManagerDialog(FramelessDialog):
    def __init__(self, mods_dir: str, theme_name: str, parent=None):
        super().__init__(theme_name=theme_name, title="Manage Installed Mods", parent=parent)
        self.mods_dir = mods_dir
        self.set_dialog_size(560, 460, min_w=460, min_h=360)

        header = QLabel("Installed Mods (Check to enable, uncheck to disable)")
        header.setObjectName("SectionLabel")
        self.body_layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("ModsList")
        self.body_layout.addWidget(self.list_widget)

        self.load_mods()

        footer = QHBoxLayout()
        footer.addStretch()

        btn_close = AnimatedButton("Done")
        btn_close.setObjectName("PlayButton")
        btn_close.setFixedHeight(38)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        self.body_layout.addLayout(footer)

    def load_mods(self):
        self.list_widget.clear()
        if not os.path.exists(self.mods_dir):
            return

        files = sorted(os.listdir(self.mods_dir))
        for filename in files:
            if not (filename.endswith(".jar") or filename.endswith(".jar.disabled")):
                continue

            is_enabled = filename.endswith(".jar")
            display_name = filename.replace(".disabled", "")

            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(self.list_widget.width() - 20, 42))

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 4, 8, 4)

            chk = SwitchCheckBox(display_name)
            chk.setChecked(is_enabled)
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            chk.toggled.connect(lambda state, fn=filename: self.toggle_mod(fn, state))
            row_layout.addWidget(chk)
            row_layout.addStretch()

            self.list_widget.setItemWidget(item, row_widget)

    def toggle_mod(self, original_filename: str, enable: bool):
        cur_path = os.path.join(self.mods_dir, original_filename)
        if enable and original_filename.endswith(".disabled"):
            new_name = original_filename.replace(".disabled", "")
            new_path = os.path.join(self.mods_dir, new_name)
            if os.path.exists(cur_path):
                os.rename(cur_path, new_path)
        elif not enable and not original_filename.endswith(".disabled"):
            new_name = original_filename + ".disabled"
            new_path = os.path.join(self.mods_dir, new_name)
            if os.path.exists(cur_path):
                os.rename(cur_path, new_path)
        self.load_mods()


class LogViewerDialog(FramelessDialog):
    def __init__(self, log_lines: list, theme_name: str, app_icon: QIcon = None, parent=None):
        super().__init__(theme_name=theme_name, title="Minecraft Execution Log", parent=parent)
        self.raw_logs = list(log_lines)
        self.set_dialog_size(780, 520, min_w=620, min_h=400)
        if app_icon:
            self.setWindowIcon(app_icon)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_label = QLabel("Game Execution & Crash Log")
        title_label.setObjectName("SectionLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.btn_copy = AnimatedButton("Copy Log")
        self.btn_copy.setObjectName("PillButton")
        self.btn_copy.setMinimumWidth(110)
        self.btn_copy.setStyleSheet("padding: 5px 14px;")
        self.btn_copy.clicked.connect(self.copy_log)
        header_layout.addWidget(self.btn_copy)

        self.btn_save = AnimatedButton("Save to File")
        self.btn_save.setObjectName("PillButton")
        self.btn_save.setMinimumWidth(110)
        self.btn_save.setStyleSheet("padding: 5px 14px;")
        self.btn_save.clicked.connect(self.save_log)
        header_layout.addWidget(self.btn_save)

        self.body_layout.addLayout(header_layout)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Filter lines (e.g. error, sodium, memory)...")
        self.search_filter.textChanged.connect(self.refresh_display)
        filter_row.addWidget(self.search_filter, stretch=2)

        self.btn_filter_all = AnimatedButton("All")
        self.btn_filter_all.setObjectName("PillButton")
        self.btn_filter_all.setMinimumWidth(60)
        self.btn_filter_all.setStyleSheet("padding: 4px 10px;")
        self.btn_filter_all.clicked.connect(lambda: self.set_severity_filter("ALL"))
        filter_row.addWidget(self.btn_filter_all)

        self.btn_filter_err = AnimatedButton("Errors")
        self.btn_filter_err.setObjectName("PillButton")
        self.btn_filter_err.setMinimumWidth(75)
        self.btn_filter_err.setStyleSheet("color: #FF5555; border: 1px solid rgba(255, 85, 85, 0.4); padding: 4px 10px;")
        self.btn_filter_err.clicked.connect(lambda: self.set_severity_filter("ERRORS"))
        filter_row.addWidget(self.btn_filter_err)

        self.btn_filter_warn = AnimatedButton("Warnings")
        self.btn_filter_warn.setObjectName("PillButton")
        self.btn_filter_warn.setMinimumWidth(85)
        self.btn_filter_warn.setStyleSheet("color: #FFB86C; border: 1px solid rgba(255, 184, 108, 0.4); padding: 4px 10px;")
        self.btn_filter_warn.clicked.connect(lambda: self.set_severity_filter("WARNS"))
        filter_row.addWidget(self.btn_filter_warn)

        self.body_layout.addLayout(filter_row)

        self.current_severity = "ALL"
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("ConsoleLog")
        self.text_edit.setReadOnly(True)
        self.body_layout.addWidget(self.text_edit)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        btn_close = AnimatedButton("Close")
        btn_close.setObjectName("PlayButton")
        btn_close.setFixedHeight(38)
        btn_close.setFixedWidth(110)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        self.body_layout.addLayout(footer_layout)
        self.refresh_display()

    def set_severity_filter(self, mode: str):
        self.current_severity = mode
        self.refresh_display()

    def refresh_display(self):
        query = self.search_filter.text().strip().lower()
        self.text_edit.clear()
        html_chunks = []

        for line in self.raw_logs:
            lower_line = line.lower()
            if query and query not in lower_line:
                continue

            upper = line.upper()
            if self.current_severity == "ERRORS":
                if not any(k in upper for k in ["[ERROR]", "ERROR", "FATAL", "EXCEPTION", "CRASH", "FAILED", "OS::COMMIT_MEMORY"]):
                    continue
            elif self.current_severity == "WARNS":
                if not any(k in upper for k in ["[WARN]", "[WARNING]", "WARN"]):
                    continue

            html_chunks.append(format_log_line_html(line, self.theme_name))

        self.text_edit.appendHtml("".join(html_chunks))
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def copy_log(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(self.raw_logs))
        self.btn_copy.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy Log"))

    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Minecraft Log", os.path.expanduser("~/minecraft_log.txt"), "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.raw_logs))
            self.btn_save.setText("Saved!")
            QTimer.singleShot(1500, lambda: self.btn_save.setText("Save to File"))


def _format_download_count(downloads: int) -> str:
    if downloads >= 1_000_000_000:
        val = downloads / 1_000_000_000
        return f"{val:.2f}".rstrip("0").rstrip(".") + "B"
    if downloads >= 1_000_000:
        val = downloads / 1_000_000
        return f"{val:.1f}".rstrip("0").rstrip(".") + "M"
    if downloads >= 10_000:
        return f"{downloads // 1000}k"
    if downloads >= 1_000:
        val = downloads / 1000
        return f"{val:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{downloads:,}"


class ModItemCard(QFrame):
    def __init__(self, item_data: dict, theme_data: dict, is_installed: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("ModItemCard")
        self.item_data = item_data
        self.theme_data = theme_data
        self.is_selected = False
        self.is_installed = bool(is_installed)
        self.setFixedHeight(68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 14, 8)
        layout.setSpacing(14)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(44, 44)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 8px; border: none;")
        layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.title_label = QLabel(item_data.get("title", "Unknown Mod"))
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {self.theme_data['text']}; border: none; background: transparent;")
        top_row.addWidget(self.title_label)

        author = item_data.get("author", "")
        if author:
            self.author_label = QLabel(f"by {author}")
            self.author_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {self.theme_data['text_sub']}; border: none; background: transparent;")
            top_row.addWidget(self.author_label)

        self.installed_label = QLabel(I18n.t("already_installed_tag"), self)
        self.installed_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #22C55E; border: none; background: transparent;")
        self.installed_label.setVisible(self.is_installed)
        top_row.addWidget(self.installed_label)

        top_row.addStretch()

        downloads = item_data.get("downloads", 0)
        if downloads:
            d_str = _format_download_count(int(downloads))
            self.dl_label = QLabel(f"↓ {d_str}")
            self.dl_label.setToolTip(f"{int(downloads):,}")
            self.dl_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {self.theme_data['accent']}; border: none; background: transparent;")
            top_row.addWidget(self.dl_label)

        info_layout.addLayout(top_row)

        desc_text = item_data.get("description", "").strip()
        if len(desc_text) > 85:
            desc_text = desc_text[:85] + "..."
        self.desc_label = QLabel(desc_text)
        self.desc_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {self.theme_data['text_sub']}; border: none; background: transparent;")
        info_layout.addWidget(self.desc_label)

        layout.addLayout(info_layout, stretch=1)
        self.update_appearance()

    def set_installed(self, installed: bool):
        self.is_installed = bool(installed)
        if hasattr(self, "installed_label") and not sip.isdeleted(self.installed_label):
            self.installed_label.setText(I18n.t("already_installed_tag"))
            self.installed_label.setVisible(self.is_installed)

    def retranslate_ui(self):
        if hasattr(self, "installed_label") and not sip.isdeleted(self.installed_label):
            self.installed_label.setText(I18n.t("already_installed_tag"))

    def set_selected_state(self, selected: bool):
        self.is_selected = selected
        self.update_appearance()

    def update_appearance(self):
        t = self.theme_data
        if self.is_selected:
            self.setStyleSheet(f"""
                QFrame#ModItemCard {{
                    background-color: {t['item_hover']};
                    border: 1px solid {t['accent']};
                    border-left: 4px solid {t['accent']};
                    border-radius: 8px;
                }}
                QLabel {{ border: none; background: transparent; }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#ModItemCard {{
                    background-color: {t['pill_bg']};
                    border: 1px solid {t['border']};
                    border-left: 1px solid {t['border']};
                    border-radius: 8px;
                }}
                QFrame#ModItemCard:hover {{
                    background-color: {t['pill_hover']};
                    border-color: {t['text_sub']};
                }}
                QLabel {{ border: none; background: transparent; }}
            """)

    def set_thumbnail(self, pixmap: QPixmap):
        if sip.isdeleted(self) or sip.isdeleted(self.icon_label):
            return
        if not pixmap.isNull():
            scaled = pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_label.setPixmap(scaled)
            self.icon_label.setStyleSheet("border-radius: 8px; border: none; background: transparent;")


class IconDownloadSignals(QObject):
    loaded = pyqtSignal(bytes)


class ModIconLoader(QRunnable):
    def __init__(self, icon_url: str):
        super().__init__()
        self.icon_url = icon_url
        self.signals = IconDownloadSignals()

    def run(self):
        if not self.icon_url:
            return
        cached = ICON_CACHE.get(self.icon_url)
        if cached is not None:
            ICON_CACHE.move_to_end(self.icon_url)
            self.signals.loaded.emit(cached)
            return
        try:
            res = _get_icon_session().get(self.icon_url, timeout=5)
            if res.status_code == 200 and res.content:
                raw_bytes = res.content
                # Downscale oversized remote mod icons to 44x44 PNG before caching in RAM
                img = QImage()
                if img.loadFromData(raw_bytes) and (img.width() > 48 or img.height() > 48):
                    small = img.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    ba = QByteArray()
                    buf = QBuffer(ba)
                    buf.open(QIODevice.OpenModeFlag.WriteOnly)
                    if small.save(buf, "PNG"):
                        raw_bytes = bytes(ba)
                    buf.close()
                ICON_CACHE[self.icon_url] = raw_bytes
                ICON_CACHE.move_to_end(self.icon_url)
                while len(ICON_CACHE) > _ICON_CACHE_MAX:
                    ICON_CACHE.popitem(last=False)
                self.signals.loaded.emit(raw_bytes)
        except Exception:
            pass


class ContentTypeBar(QWidget):
    type_changed = pyqtSignal(str)

    def __init__(self, theme_data: dict, parent=None):
        super().__init__(parent)
        self.theme_data = theme_data
        self.setFixedHeight(34)
        self.types = [
            (I18n.t("type_mods"), "mod"),
            (I18n.t("type_resourcepacks"), "resourcepack"),
            (I18n.t("type_shaders"), "shader"),
        ]
        self._type_keys = ["type_mods", "type_resourcepacks", "type_shaders"]
        self.buttons = []
        self.current_idx = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for idx, (label, val) in enumerate(self.types):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self.select_index(i))
            layout.addWidget(btn)
            self.buttons.append(btn)

        self.apply_styles()

    def retranslate_ui(self):
        for i, key in enumerate(self._type_keys):
            if i < len(self.buttons):
                self.buttons[i].setText(I18n.t(key))

    def select_index(self, idx: int):
        self.current_idx = idx
        self.apply_styles()
        self.type_changed.emit(self.types[idx][1])

    def get_selected_type(self) -> str:
        return self.types[self.current_idx][1]

    def apply_styles(self):
        t = self.theme_data
        for i, btn in enumerate(self.buttons):
            if i == self.current_idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {t['accent']};
                        color: {t.get('accent_text', '#FFFFFF')};
                        font-size: 11px;
                        font-weight: 800;
                        padding: 6px 10px;
                        border: none;
                        border-radius: 6px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {t['pill_bg']};
                        color: {t['text_sub']};
                        font-size: 11px;
                        font-weight: 700;
                        padding: 6px 10px;
                        border: 1px solid {t['border']};
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{
                        color: {t['text']};
                        background-color: {t['pill_hover']};
                    }}
                """)


class DropdownItemWidget(QFrame):
    row_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)

    def __init__(self, index: int, text: str, icon: QPixmap = None, enable_delete: bool = False, theme_data: dict = None, parent=None):
        super().__init__(parent)
        self.index = index
        self.enable_delete = enable_delete
        self.setObjectName("DropdownRowWidget")
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        t_data = theme_data or ThemeManager.get_theme_data("Dark Mode")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 8, 2)
        layout.setSpacing(8)

        if icon:
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(22, 22)
            icon_lbl.setPixmap(icon.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            icon_lbl.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(icon_lbl)

        self.text_lbl = QLabel(text)
        self.text_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t_data['text']}; background: transparent; border: none;")
        layout.addWidget(self.text_lbl, stretch=1)

        if self.enable_delete:
            self.del_btn = QPushButton("")
            self.del_btn.setObjectName("DropdownDeleteBtn")
            self.del_btn.setFixedSize(28, 28)
            self.del_btn.setIcon(_make_menu_icon("trash", t_data["text_sub"]))
            self.del_btn.setIconSize(QSize(14, 14))
            self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.index))
            layout.addWidget(self.del_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.row_clicked.emit(self.index)
        super().mousePressEvent(event)


class DropdownPopup(QWidget):
    item_selected = pyqtSignal(int)
    item_deleted = pyqtSignal(int)
    closed = pyqtSignal()

    MAX_VISIBLE_ROWS = 7  # longer lists (e.g. the theme picker) scroll instead of running off screen

    def __init__(self, items: list, width: int, enable_delete: bool = False, theme_data: dict = None, parent=None, current_index: int = -1):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self._owner = parent
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        row_font = QFont()
        row_font.setPixelSize(13)
        row_font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(row_font)
        has_icon = any(isinstance(entry, (tuple, list)) and len(entry) > 2 and entry[2] is not None for entry in items)
        has_scroll = len(items) > self.MAX_VISIBLE_ROWS
        widest_text = max(
            (fm.horizontalAdvance(entry[0] if isinstance(entry, (tuple, list)) else str(entry)) for entry in items),
            default=0
        )
        needed_w = widest_text + 36 + (30 if has_icon else 0) + (38 if enable_delete else 0) + (14 if has_scroll else 0)
        popup_width = max(width, needed_w, 360 if enable_delete else 0)
        self.setFixedWidth(popup_width)

        t_data = theme_data or ThemeManager.get_theme_data("Dark Mode")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.container = QFrame()
        self.container.setObjectName("DropdownPopupFrame")
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(2)

        self._scroll = None
        self._row_widgets = []
        self._focus_idx = current_index
        if has_scroll:
            self._scroll = QScrollArea()
            self._scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll.setWidgetResizable(True)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.viewport().setAutoFillBackground(False)
            self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            rows_host = QWidget()
            rows_host.setObjectName("DropdownRows")
            rows_host.setStyleSheet("QWidget#DropdownRows { background: transparent; }")
            rows_layout = QVBoxLayout(rows_host)
            rows_layout.setContentsMargins(0, 0, 0, 0)
            rows_layout.setSpacing(2)
            self._scroll.setWidget(rows_host)
            # QScrollArea.setWidget() switches autoFillBackground back ON (grey box), so turn it off AFTER.
            rows_host.setAutoFillBackground(False)
            self._scroll.viewport().setAutoFillBackground(False)
            self._scroll.setFixedHeight(self.MAX_VISIBLE_ROWS * 38 + (self.MAX_VISIBLE_ROWS - 1) * 2)
            c_layout.addWidget(self._scroll)
            rows_parent = rows_host
        else:
            rows_layout = c_layout
            rows_parent = self.container

        for idx, entry in enumerate(items):
            text = entry[0] if isinstance(entry, (tuple, list)) else entry
            icon = entry[2] if isinstance(entry, (tuple, list)) and len(entry) > 2 else None

            row_widget = DropdownItemWidget(
                idx, text, icon=icon,
                enable_delete=enable_delete,
                theme_data=t_data,
                parent=rows_parent
            )
            row_widget.row_clicked.connect(self.on_item_chosen)
            row_widget.delete_clicked.connect(self.on_item_delete_req)
            rows_layout.addWidget(row_widget)
            self._row_widgets.append(row_widget)

        layout.addWidget(self.container)
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        QApplication.instance().installEventFilter(self)
        if self._scroll is not None and 0 <= self._focus_idx < len(self._row_widgets):
            QTimer.singleShot(0, self._reveal_current)

    def _reveal_current(self):
        try:
            self._scroll.ensureWidgetVisible(self._row_widgets[self._focus_idx], 0, 6)
        except RuntimeError:
            pass  # popup already closed

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)
        self.closed.emit()

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonPress:
            gp = event.globalPosition().toPoint()
            if not self.frameGeometry().contains(gp):
                owner = self._owner
                on_owner = owner is not None and owner.rect().contains(owner.mapFromGlobal(gp))
                self.close()
                if on_owner:
                    return True
        elif t == QEvent.Type.ApplicationDeactivate:
            self.close()
        elif t == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.close()
            return True
        return False

    def on_item_chosen(self, idx: int):
        self._dismiss_then(self.item_selected, idx)

    def on_item_delete_req(self, idx: int):
        self._dismiss_then(self.item_deleted, idx)

    def _dismiss_then(self, signal, idx: int):
        # Hide now, emit on the next tick, and only THEN close (WA_DeleteOnClose):
        # closing first could delete the popup before the deferred emit ran.
        self.hide()

        def fire():
            signal.emit(idx)
            self.close()

        QTimer.singleShot(0, fire)


class CustomDropdown(QPushButton):
    currentIndexChanged = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)

    def __init__(self, enable_delete: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("CustomCombo")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.items = []
        self.current_idx = -1
        self.is_placeholder_mode = False
        self.enable_delete = enable_delete
        self.popup = None
        self._hover = 0.0
        self._theme_data = ThemeManager.get_theme_data("Dark Mode")

        f = self.font()
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.Bold)
        self.setFont(f)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

        self.clicked.connect(self.show_dropdown)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def set_theme_colors(self, theme_data: dict):
        self._theme_data = theme_data
        self.update()

    def _resolve_theme(self) -> dict:
        win = self.window()
        cur = getattr(win, "current_theme", None) or getattr(win, "theme_name", None)
        if cur:
            return ThemeManager.get_theme_data(cur)
        return self._theme_data

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        widest = max((fm.horizontalAdvance(t) for t, _, _ in self.items), default=110)
        has_icon = any(icon is not None and not icon.isNull() for _, _, icon in self.items)
        extra = 14 + (28 if has_icon else 0) + 32
        return QSize(max(150, widest + extra), 40)

    def set_placeholder_mode(self, enabled: bool):
        self.is_placeholder_mode = enabled

    def clear(self):
        self.items.clear()
        self.current_idx = -1
        self.setText("")
        self.setIcon(QIcon())
        self.setToolTip("")
        self.update()

    def addItem(self, text: str, userData=None, icon: QPixmap = None):
        self.items.append((text, userData, icon))
        if self.current_idx == -1:
            self.setCurrentIndex(0)

    def addItems(self, texts: list):
        for t in texts:
            self.addItem(t, userData=t)

    def count(self) -> int:
        return len(self.items)

    def currentText(self) -> str:
        if 0 <= self.current_idx < len(self.items):
            return self.items[self.current_idx][0]
        return ""

    def currentData(self):
        if 0 <= self.current_idx < len(self.items):
            return self.items[self.current_idx][1]
        return None

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self.items):
            self.current_idx = index
            item_text = self.items[index][0]
            item_icon = self.items[index][2]

            self.setText(item_text)
            self.setToolTip(item_text)
            if item_icon:
                self.setIcon(QIcon(item_icon))
            else:
                self.setIcon(QIcon())
            self.update()
            self.currentIndexChanged.emit(index)

    def setCurrentText(self, text: str):
        for idx, (t, _, _) in enumerate(self.items):
            if t == text:
                self.setCurrentIndex(idx)
                break

    def itemData(self, index: int):
        if 0 <= index < len(self.items):
            return self.items[index][1]
        return None

    def paintEvent(self, event):
        t = self._resolve_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if not self.isEnabled():
            p.setOpacity(0.55)

        bg = _lerp_color(t["pill_bg"], t["pill_hover"], self._hover)
        p.setPen(QPen(QColor(t["border"]), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        x = 14
        item_icon = self.items[self.current_idx][2] if 0 <= self.current_idx < len(self.items) else None
        if item_icon is not None and not item_icon.isNull():
            iy = (self.height() - 20) // 2
            p.drawPixmap(
                x, iy, 20, 20,
                item_icon.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            x += 28

        chevron_w = 18
        right_pad = 12
        avail = max(10, self.width() - x - chevron_w - right_pad)

        text = self.currentText()
        p.setFont(self.font())
        p.setPen(QColor(t["text"]))
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, avail)
        p.drawText(QRectF(x, 0, avail, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided)

        p.setPen(QColor(t["text_sub"]))
        p.drawText(
            QRectF(self.width() - right_pad - chevron_w, 0, chevron_w, self.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            "▾",
        )
        p.end()

    def show_dropdown(self):
        if self.is_placeholder_mode:
            p = self.window()
            if hasattr(p, "prompt_new_instance"):
                p.prompt_new_instance()
            return

        if not self.items:
            return

        main_win = self.window()
        cur_theme = getattr(main_win, "current_theme", None) or getattr(main_win, "theme_name", "Dark Mode")
        theme_data = ThemeManager.get_theme_data(cur_theme)
        self._theme_data = theme_data

        self.popup = DropdownPopup(
            self.items,
            self.width(),
            enable_delete=self.enable_delete,
            theme_data=theme_data,
            parent=self,
            current_index=self.current_idx
        )
        self.popup.setStyleSheet(ThemeManager.get_style(cur_theme))
        self.popup.item_selected.connect(self.setCurrentIndex)
        self.popup.item_deleted.connect(lambda idx: self.deleteRequested.emit(idx))
        self.popup.closed.connect(lambda: setattr(self, "popup", None))

        pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            popup_h = self.popup.sizeHint().height()
            popup_w = self.popup.width()
            if pos.y() + popup_h > geo.bottom():
                pos = self.mapToGlobal(QPoint(0, -popup_h - 4))  # not enough room below: open upwards
            if pos.x() + popup_w > geo.right() - 8:
                pos.setX(max(geo.left() + 8, geo.right() - popup_w - 8))
        opens_up = pos.y() < self.mapToGlobal(QPoint(0, 0)).y()
        self.popup.setWindowOpacity(0.0)
        self.popup.move(pos)
        self.popup.show()
        self._animate_popup_in(pos, opens_up)

    def _animate_popup_in(self, end_pos, opens_up: bool):
        pop = self.popup
        if pop is None:
            return
        try:
            start = QPoint(end_pos.x(), end_pos.y() + (8 if opens_up else -8))
            pop.move(start)
            a_opacity = QPropertyAnimation(pop, b"windowOpacity", pop)
            a_opacity.setDuration(150)
            a_opacity.setStartValue(0.0)
            a_opacity.setEndValue(1.0)
            a_opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_pos = QPropertyAnimation(pop, b"pos", pop)
            a_pos.setDuration(190)
            a_pos.setStartValue(start)
            a_pos.setEndValue(end_pos)
            a_pos.setEasingCurve(QEasingCurve.Type.OutCubic)
            a_opacity.start()
            a_pos.start()
        except RuntimeError:
            pass


class HeaderIconButton(QPushButton):
    """38x38 vector icon button in the header for the 3-bar dashboard menu and top-right Settings gear."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._hover = 0.0
        self._press = 0.0
        self._active = False
        self._has_badge = False
        self._badge_ver = ""
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedSize(38, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate_ui()

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(110)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_anim.valueChanged.connect(self._on_press)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def _on_press(self, v):
        self._press = float(v)
        self.update()

    def retranslate_ui(self):
        if self.kind == "menu":
            self.setToolTip(I18n.t("nav_menu"))
        elif self.kind == "updates":
            if self._has_badge and self._badge_ver:
                self.setToolTip(I18n.t("update_nav_badge_tip", ver=self._badge_ver))
            else:
                self.setToolTip(I18n.t("tab_updates"))
        else:
            self.setToolTip(I18n.t("tab_settings"))

    def set_badge(self, has_badge: bool, ver: str = ""):
        has_badge = bool(has_badge)
        ver = str(ver or "")
        if self._has_badge != has_badge or self._badge_ver != ver:
            self._has_badge = has_badge
            self._badge_ver = ver
            self.retranslate_ui()
            self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def set_active(self, active: bool):
        active = bool(active)
        if self._active != active:
            self._active = active
            self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_anim.stop()
            self._press_anim.setStartValue(self._press)
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press)
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._active:
            base_bg = _lerp_color(t["pill_bg"], t["accent"], 0.16)
            bg = _lerp_color(base_bg, t["accent"], self._hover * 0.14)
            border_col = _lerp_color(t["border"], t["accent"], 0.65)
            glyph_col = QColor(t["accent"])
        else:
            bg = _lerp_color(t["pill_bg"], t["pill_hover"], self._hover)
            border_col = _lerp_color(t["border"], t["text_sub"], self._hover * 0.45)
            glyph_col = _lerp_color(t["text_sub"], t["text"], self._hover)

        if self._press > 0.01:
            bg = _lerp_color(bg, "#000000", 0.14 * self._press)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border_col, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 9.0, 9.0)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self.kind == "menu":
            pen = QPen(glyph_col, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            half_w = 7.5
            for dy in (-5.0, 0.0, 5.0):
                p.drawLine(QPointF(cx - half_w, cy + dy), QPointF(cx + half_w, cy + dy))
        elif self.kind == "updates":
            pen = QPen(glyph_col, 1.9)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - 6.2, cy - 6.2, 12.4, 12.4), 35 * 16, 265 * 16)
            p.drawLine(QPointF(cx + 3.6, cy - 6.2), QPointF(cx + 6.0, cy - 3.0))
            p.drawLine(QPointF(cx + 2.3, cy - 2.6), QPointF(cx + 6.0, cy - 3.0))
        else:
            # Crisp 8-tooth vector cogwheel
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glyph_col)
            outer_r = 8.4
            inner_r = 6.2
            path = QPainterPath()
            teeth = 8
            step = (2.0 * math.pi) / teeth
            pts = []
            for i in range(teeth):
                a0 = i * step
                # Tooth base -> tooth tip -> tooth tip -> tooth base
                angles = [
                    (a0 - step * 0.24, inner_r),
                    (a0 - step * 0.13, outer_r),
                    (a0 + step * 0.13, outer_r),
                    (a0 + step * 0.24, inner_r),
                ]
                for ang, rad in angles:
                    pts.append(QPointF(cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
            if pts:
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
            hole = QPainterPath()
            hole.addEllipse(QPointF(cx, cy), 3.1, 3.1)
            p.drawPath(path.subtracted(hole))

        if self._has_badge and self.kind == "updates":
            p.setPen(QPen(QColor(t["bg"]), 1.6))
            p.setBrush(QColor(t["accent"]))
            p.drawEllipse(QPointF(self.width() - 7.5, 7.5), 4.2, 4.2)

        p.end()


class SideNavItem(QPushButton):
    """Full-width dashboard navigation item with vector icon and animated selection state."""

    def __init__(self, icon_kind: str, label: str, parent=None, nav_key: str = "", height: int = 34):
        super().__init__(label, parent)
        self.icon_kind = icon_kind
        self.nav_key = nav_key
        self._hover = 0.0
        self._active = False
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        f = self.font()
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.Bold)
        self.setFont(f)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def set_active(self, active: bool):
        active = bool(active)
        if self._active != active:
            self._active = active
            self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def _draw_icon(self, p: QPainter, cx: float, cy: float, color: QColor):
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        if self.icon_kind == "play":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            tri = QPainterPath()
            tri.moveTo(cx - 3.8, cy - 5.2)
            tri.lineTo(cx + 5.6, cy)
            tri.lineTo(cx - 3.8, cy + 5.2)
            tri.closeSubpath()
            p.drawPath(tri)
        elif self.icon_kind == "mods":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for dx, dy in ((-4.8, -4.8), (1.0, -4.8), (-4.8, 1.0), (1.0, 1.0)):
                p.drawRoundedRect(QRectF(cx + dx, cy + dy, 4.0, 4.0), 1.0, 1.0)
        elif self.icon_kind == "instances":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            top = QPointF(cx, cy - 6.2)
            right = QPointF(cx + 5.6, cy - 3.1)
            left = QPointF(cx - 5.6, cy - 3.1)
            center = QPointF(cx, cy + 0.1)
            bot = QPointF(cx, cy + 6.3)
            bl = QPointF(cx - 5.6, cy + 3.2)
            br = QPointF(cx + 5.6, cy + 3.2)
            p.drawPolygon(QPolygonF([top, right, br, bot, bl, left]))
            p.drawLine(left, center)
            p.drawLine(right, center)
            p.drawLine(center, bot)
        elif self.icon_kind == "accounts":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy - 2.6), 2.8, 2.8)
            arc = QPainterPath()
            arc.moveTo(cx - 5.2, cy + 5.6)
            arc.quadTo(cx, cy + 0.6, cx + 5.2, cy + 5.6)
            p.drawPath(arc)
        elif self.icon_kind in ("experimental", "premium"):
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            crown = QPainterPath()
            crown.moveTo(cx - 5.6, cy + 4.4)
            crown.lineTo(cx - 6.0, cy - 3.0)
            crown.lineTo(cx - 2.6, cy + 0.5)
            crown.lineTo(cx, cy - 5.0)
            crown.lineTo(cx + 2.6, cy + 0.5)
            crown.lineTo(cx + 6.0, cy - 3.0)
            crown.lineTo(cx + 5.6, cy + 4.4)
            crown.closeSubpath()
            p.drawPath(crown)
        elif self.icon_kind in ("heart", "donate"):
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            hp = QPainterPath()
            hp.moveTo(cx, cy + 5.2)
            hp.cubicTo(cx - 7.5, cy + 0.6, cx - 6.2, cy - 5.8, cx, cy - 2.0)
            hp.cubicTo(cx + 6.2, cy - 5.8, cx + 7.5, cy + 0.6, cx, cy + 5.2)
            p.drawPath(hp)
        elif self.icon_kind == "discord":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            dp = QPainterPath()
            dp.moveTo(cx - 4.6, cy - 3.6)
            dp.quadTo(cx, cy - 5.4, cx + 4.6, cy - 3.6)
            dp.quadTo(cx + 6.4, cy + 0.4, cx + 5.2, cy + 4.2)
            dp.lineTo(cx + 2.4, cy + 2.8)
            dp.quadTo(cx, cy + 3.4, cx - 2.4, cy + 2.8)
            dp.lineTo(cx - 5.2, cy + 4.2)
            dp.quadTo(cx - 6.4, cy + 0.4, cx - 4.6, cy - 3.6)
            p.drawPath(dp)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx - 2.0, cy + 0.1), 1.15, 1.35)
            p.drawEllipse(QPointF(cx + 2.0, cy + 0.1), 1.15, 1.35)
        elif self.icon_kind == "console":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(cx - 6.2, cy - 5.0, 12.4, 10.0), 2.0, 2.0)
            p.drawLine(QPointF(cx - 3.5, cy - 1.8), QPointF(cx - 1.2, cy + 0.2))
            p.drawLine(QPointF(cx - 3.5, cy + 2.1), QPointF(cx - 1.2, cy + 0.2))
            p.drawLine(QPointF(cx + 0.5, cy + 2.1), QPointF(cx + 3.5, cy + 2.1))
        elif self.icon_kind == "plus":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(cx - 5.6, cy - 5.6, 11.2, 11.2), 2.8, 2.8)
            p.drawLine(QPointF(cx, cy - 2.8), QPointF(cx, cy + 2.8))
            p.drawLine(QPointF(cx - 2.8, cy), QPointF(cx + 2.8, cy))
        elif self.icon_kind == "import":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(cx, cy - 5.6), QPointF(cx, cy + 2.2))
            p.drawLine(QPointF(cx - 2.8, cy - 0.5), QPointF(cx, cy + 2.4))
            p.drawLine(QPointF(cx + 2.8, cy - 0.5), QPointF(cx, cy + 2.4))
            tray = QPainterPath()
            tray.moveTo(cx - 5.5, cy + 2.0)
            tray.lineTo(cx - 5.5, cy + 5.2)
            tray.lineTo(cx + 5.5, cy + 5.2)
            tray.lineTo(cx + 5.5, cy + 2.0)
            p.drawPath(tray)
        elif self.icon_kind == "puzzle":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(cx - 5.6, cy - 2.8), QPointF(cx + 5.6, cy - 2.8))
            p.drawLine(QPointF(cx - 5.6, cy + 2.8), QPointF(cx + 5.6, cy + 2.8))
            p.setBrush(QColor(self._theme.get("card_bg", "#1A1B20")))
            p.drawEllipse(QPointF(cx - 1.8, cy - 2.8), 2.0, 2.0)
            p.drawEllipse(QPointF(cx + 2.0, cy + 2.8), 2.0, 2.0)
        elif self.icon_kind == "folder":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            folder = QPainterPath()
            folder.moveTo(cx - 6.0, cy - 4.4)
            folder.lineTo(cx - 1.4, cy - 4.4)
            folder.lineTo(cx + 0.2, cy - 2.6)
            folder.lineTo(cx + 6.0, cy - 2.6)
            folder.lineTo(cx + 6.0, cy + 4.8)
            folder.lineTo(cx - 6.0, cy + 4.8)
            folder.closeSubpath()
            p.drawPath(folder)
        elif self.icon_kind == "updates":
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - 5.4, cy - 5.4, 10.8, 10.8), 35 * 16, 265 * 16)
            p.drawLine(QPointF(cx + 3.2, cy - 5.4), QPointF(cx + 5.2, cy - 2.6))
            p.drawLine(QPointF(cx + 2.0, cy - 2.2), QPointF(cx + 5.2, cy - 2.6))
        elif self.icon_kind == "settings":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            outer_r = 6.4
            inner_r = 4.6
            path = QPainterPath()
            teeth = 8
            step = (2.0 * math.pi) / teeth
            pts = []
            for i in range(teeth):
                a0 = i * step
                for ang, rad in (
                    (a0 - step * 0.24, inner_r),
                    (a0 - step * 0.13, outer_r),
                    (a0 + step * 0.13, outer_r),
                    (a0 + step * 0.24, inner_r),
                ):
                    pts.append(QPointF(cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
            if pts:
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
            hole = QPainterPath()
            hole.addEllipse(QPointF(cx, cy), 2.3, 2.3)
            p.drawPath(path.subtracted(hole))

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._active:
            base = _lerp_color(t["card_bg"], t["accent"], 0.16)
            bg = _lerp_color(base, t["accent"], self._hover * 0.08)
            p.setPen(QPen(QColor(_hex_rgba(t["accent"], 0.45)), 1.0))
            p.setBrush(bg)
            p.drawRoundedRect(rect, 9.0, 9.0)

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t["accent"]))
            p.drawRoundedRect(QRectF(2.0, 8.0, 3.0, self.height() - 16.0), 1.5, 1.5)
            icon_col = QColor(t["accent"])
            text_col = QColor(t["text"])
        else:
            bg = _lerp_color(QColor(0, 0, 0, 0), t["pill_hover"], self._hover)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 9.0, 9.0)
            icon_col = _lerp_color(t["text_sub"], t["text"], self._hover)
            text_col = _lerp_color(t["text_sub"], t["text"], self._hover)

        self._draw_icon(p, 21.0, self.height() / 2.0, icon_col)

        f = self.font()
        f.setWeight(QFont.Weight.Bold if self._active else QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(text_col)
        tx = 37.0
        avail = max(10.0, self.width() - tx - 10.0)
        elided = QFontMetrics(f).elidedText(self.text(), Qt.TextElideMode.ElideRight, int(avail))
        p.drawText(
            QRectF(tx, 0, avail, self.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided,
        )
        p.end()


class _DrawerScrim(QWidget):
    """Translucent backdrop behind the left dashboard drawer; clicking dismisses the drawer."""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 105))
        p.drawRoundedRect(QRectF(self.rect()), 14.0, 14.0)
        p.end()


class SideNavDrawer(QWidget):
    """Collapsible left dashboard drawer opened via the header 3-bar menu button."""
    tab_changed = pyqtSignal(int)
    settings_page_requested = pyqtSignal(int)
    action_triggered = pyqtSignal(str)
    PANEL_WIDTH = 228

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_index = 0
        self._active_key = "tab_0"
        self.is_open = False
        self._theme = ThemeManager.get_theme_data("Dark Mode")
        self._anim = None
        self.setFixedWidth(0)
        self.setVisible(False)

        self.inner = QFrame(self)
        self.inner.setObjectName("SideDrawerCard")
        self.inner.setFixedWidth(self.PANEL_WIDTH)

        layout = QVBoxLayout(self.inner)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.lbl_header = QLabel(I18n.t("drawer_dashboard"))
        self.lbl_header.setObjectName("SectionLabel")
        self.lbl_header.setStyleSheet("padding-left: 8px; padding-bottom: 1px; background: transparent; border: none;")
        layout.addWidget(self.lbl_header)

        # Indices match QStackedWidget: 0=Play, 1=Content Browser, 2=Settings, 3=Console Log, 4=Updates
        self.btn_play = SideNavItem("play", I18n.t("tab_play"), self.inner, nav_key="tab_0", height=27)
        self.btn_mods = SideNavItem("mods", I18n.t("tab_mods"), self.inner, nav_key="tab_1", height=27)
        self.btn_instances = SideNavItem("instances", I18n.t("nav_instances"), self.inner, nav_key="settings_1", height=27)
        self.btn_accounts = SideNavItem("accounts", I18n.t("nav_accounts"), self.inner, nav_key="settings_2", height=27)
        self.btn_experimental = SideNavItem("premium", I18n.t("nav_experimental"), self.inner, nav_key="settings_5", height=27)
        self.btn_donations = SideNavItem("heart", I18n.t("nav_donations"), self.inner, nav_key="settings_7", height=27)
        self.btn_console = SideNavItem("console", I18n.t("tab_console"), self.inner, nav_key="tab_3", height=27)

        self.btn_play.clicked.connect(lambda _: self.select_tab(0))
        self.btn_mods.clicked.connect(lambda _: self.select_tab(1))
        self.btn_instances.clicked.connect(lambda _: self.request_settings_page(1))
        self.btn_accounts.clicked.connect(lambda _: self.request_settings_page(2))
        self.btn_experimental.clicked.connect(lambda _: self.request_settings_page(5))
        self.btn_donations.clicked.connect(lambda _: self.request_settings_page(7))
        self.btn_console.clicked.connect(lambda _: self.select_tab(3))

        for btn in (
            self.btn_play,
            self.btn_mods,
            self.btn_instances,
            self.btn_accounts,
            self.btn_experimental,
            self.btn_donations,
            self.btn_console,
        ):
            layout.addWidget(btn)

        layout.addSpacing(3)
        self.mid_divider = QFrame(self.inner)
        self.mid_divider.setFixedHeight(1)
        layout.addWidget(self.mid_divider)
        layout.addSpacing(3)

        self.lbl_actions = QLabel(I18n.t("drawer_actions"))
        self.lbl_actions.setObjectName("SectionLabel")
        self.lbl_actions.setStyleSheet("padding-left: 8px; padding-bottom: 1px; background: transparent; border: none;")
        layout.addWidget(self.lbl_actions)

        self.btn_act_new = SideNavItem("plus", I18n.t("action_new_instance"), self.inner, height=26)
        self.btn_act_import = SideNavItem("import", I18n.t("action_import_instances"), self.inner, height=26)
        self.btn_act_mods = SideNavItem("puzzle", I18n.t("action_installed_mods"), self.inner, height=26)
        self.btn_act_folder = SideNavItem("folder", I18n.t("action_instance_folder"), self.inner, height=26)
        self.btn_act_discord = SideNavItem("discord", I18n.t("action_join_discord"), self.inner, height=26)

        self.btn_act_new.clicked.connect(lambda _: self.action_triggered.emit("new_instance"))
        self.btn_act_import.clicked.connect(lambda _: self.action_triggered.emit("import_instances"))
        self.btn_act_mods.clicked.connect(lambda _: self.action_triggered.emit("manage_mods"))
        self.btn_act_folder.clicked.connect(lambda _: self.action_triggered.emit("open_folder"))
        self.btn_act_discord.clicked.connect(lambda _: self.action_triggered.emit("join_discord"))

        for btn in (self.btn_act_new, self.btn_act_import, self.btn_act_mods, self.btn_act_folder, self.btn_act_discord):
            layout.addWidget(btn)

        layout.addStretch(1)

        self.divider = QFrame(self.inner)
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)
        layout.addSpacing(2)

        self.btn_updates = SideNavItem("updates", I18n.t("tab_updates"), self.inner, nav_key="tab_4", height=27)
        self.btn_updates.clicked.connect(lambda _: self.select_tab(4))
        layout.addWidget(self.btn_updates)

        self.btn_settings = SideNavItem("settings", I18n.t("tab_settings"), self.inner, nav_key="settings_0", height=27)
        self.btn_settings.clicked.connect(lambda _: self.select_tab(2))
        layout.addWidget(self.btn_settings)

        # Keep [0, 1, 2, 3, 4] order intact so retranslate_ui() maps cleanly
        self.buttons = [self.btn_play, self.btn_mods, self.btn_settings, self.btn_console, self.btn_updates]
        self._all_items = [
            self.btn_play,
            self.btn_mods,
            self.btn_instances,
            self.btn_accounts,
            self.btn_experimental,
            self.btn_donations,
            self.btn_console,
            self.btn_act_new,
            self.btn_act_import,
            self.btn_act_mods,
            self.btn_act_folder,
            self.btn_act_discord,
            self.btn_updates,
            self.btn_settings,
        ]

        self.lbl_footer = QLabel(f"{I18n.t('client_name')}  v{APP_VERSION}")
        self.lbl_footer.setObjectName("MutedLabel")
        self.lbl_footer.setStyleSheet("font-size: 11px; padding-left: 8px; padding-top: 2px; background: transparent; border: none;")
        layout.addWidget(self.lbl_footer)

        self.set_active_key("tab_0")
        self._apply_panel_style()

    def retranslate_ui(self):
        self.lbl_header.setText(I18n.t("drawer_dashboard"))
        self.btn_play.setText(I18n.t("tab_play"))
        self.btn_mods.setText(I18n.t("tab_mods"))
        self.btn_instances.setText(I18n.t("nav_instances"))
        self.btn_accounts.setText(I18n.t("nav_accounts"))
        self.btn_experimental.setText(I18n.t("nav_experimental"))
        self.btn_donations.setText(I18n.t("nav_donations"))
        self.btn_console.setText(I18n.t("tab_console"))
        self.lbl_actions.setText(I18n.t("drawer_actions"))
        self.btn_act_new.setText(I18n.t("action_new_instance"))
        self.btn_act_import.setText(I18n.t("action_import_instances"))
        self.btn_act_mods.setText(I18n.t("action_installed_mods"))
        self.btn_act_folder.setText(I18n.t("action_instance_folder"))
        self.btn_act_discord.setText(I18n.t("action_join_discord"))
        self.btn_updates.setText(I18n.t("tab_updates"))
        self.btn_settings.setText(I18n.t("tab_settings"))
        self.lbl_footer.setText(f"{I18n.t('client_name')}  v{APP_VERSION}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.inner.setGeometry(0, 0, self.PANEL_WIDTH, self.height())

    def _apply_panel_style(self):
        t = self._theme
        self.inner.setStyleSheet(f"""
            QFrame#SideDrawerCard {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border']};
                border-radius: 14px;
            }}
        """)
        self.mid_divider.setStyleSheet(f"background-color: {t['border']}; border: none;")
        self.divider.setStyleSheet(f"background-color: {t['border']}; border: none;")
        for btn in self._all_items:
            btn.set_theme_colors(t)

    def set_theme_colors(self, active_color: str = None, inactive_color: str = None, accent_color: str = None, theme_dict: dict = None):
        if theme_dict:
            self._theme = theme_dict
        else:
            t = dict(self._theme)
            if active_color:
                t["text"] = active_color
            if inactive_color:
                t["text_sub"] = inactive_color
            if accent_color:
                t["accent"] = accent_color
            self._theme = t
        self._apply_panel_style()

    def set_active_key(self, key: str):
        self._active_key = key
        for btn in self._all_items:
            btn.set_active(bool(btn.nav_key) and btn.nav_key == key)

    def set_active_index(self, index: int):
        if 0 <= index < len(self.buttons):
            self.current_index = index
            if index == 2:
                self.set_active_key("settings_0")
            else:
                self.set_active_key(f"tab_{index}")

    def request_settings_page(self, sub_row: int):
        self.current_index = 2
        if sub_row in (1, 2, 5, 6, 7):
            self.set_active_key(f"settings_{sub_row}")
        else:
            self.set_active_key("settings_0")
        self.settings_page_requested.emit(sub_row)

    def select_tab(self, index: int):
        if index < 0 or index >= len(self.buttons):
            return
        self.set_active_index(index)
        self.tab_changed.emit(index)

    def _set_drawer_width(self, w: int):
        w = max(0, int(w))
        self.setFixedWidth(w)
        self.resize(w, self.height())

    def set_open(self, open_drawer: bool):
        open_drawer = bool(open_drawer)
        if self.is_open == open_drawer and (
            (open_drawer and self.width() == self.PANEL_WIDTH) or (not open_drawer and self.width() == 0)
        ):
            return
        self.is_open = open_drawer
        if self._anim is not None:
            self._anim.stop()

        start_w = self.width()
        end_w = self.PANEL_WIDTH if open_drawer else 0
        if open_drawer:
            self.setVisible(True)
            self.raise_()

        anim = QVariantAnimation(self)
        anim.setDuration(190)
        anim.setStartValue(start_w)
        anim.setEndValue(end_w)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._set_drawer_width)

        def _done():
            if not self.is_open:
                self._set_drawer_width(0)
                self.setVisible(False)
            else:
                self._set_drawer_width(self.PANEL_WIDTH)

        anim.finished.connect(_done)
        self._anim = anim
        anim.start()


class WorkerSignals(QObject):
    progress = pyqtSignal(str, int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class ModSearchSignals(QObject):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)


class ModInstallSignals(QObject):
    status = pyqtSignal(str)
    completed = pyqtSignal(list)
    error = pyqtSignal(str)


class ModInstallWorker(QRunnable):
    def __init__(self, project_id: str, version: str, loader: str, target_dir: str):
        super().__init__()
        self.project_id = project_id
        self.version = version
        self.loader = loader
        self.target_dir = target_dir
        self.signals = ModInstallSignals()

    def run(self):
        try:
            from core.modrinth_service import ModrinthService
            installed = ModrinthService.download_with_dependencies(
                self.project_id,
                self.version,
                self.loader,
                self.target_dir,
                progress_cb=lambda msg: self.signals.status.emit(msg)
            )
            self.signals.completed.emit(installed)
        except Exception as e:
            self.signals.error.emit(str(e))


class ModSearchWorker(QRunnable):
    def __init__(self, query: str, version: str, loader: str, p_type: str):
        super().__init__()
        self.query = query
        self.version = version
        self.loader = loader
        self.p_type = p_type
        self.signals = ModSearchSignals()

    def run(self):
        try:
            from core.modrinth_service import ModrinthService
            hits = ModrinthService.search_content(self.query, version=self.version, loader=self.loader, project_type=self.p_type)
            self.signals.results_ready.emit(hits)
        except Exception as e:
            self.signals.error.emit(str(e))


class LaunchWorker(QRunnable):
    def __init__(self, inst_mgr: InstanceManager, root_dir: str, instance_dir: str, version_id: str, loader: str, account: dict, ram_mb: int, custom_res: dict = None, parent_win=None):
        super().__init__()
        self.inst_mgr = inst_mgr
        self.root_dir = root_dir
        self.instance_dir = instance_dir
        self.version_id = version_id.strip()
        self.loader = loader
        self.account = account
        self.ram_mb = ram_mb
        self.custom_res = custom_res or {}
        self.parent_win = parent_win
        self.signals = WorkerSignals()

    TOKEN_FRESH_SECONDS = 12 * 3600   # Minecraft tokens last ~24h: reuse them instead of 5 web requests per launch
    TOKEN_USABLE_SECONDS = 23 * 3600

    def run(self):
        t_start = time.time()
        timings = []

        def mark(label: str, since: float):
            timings.append(f"{label} {time.time() - since:.1f}s")

        try:
            if str(self.loader).strip().lower() == hb.LOADER_NAME.lower():
                self._run_horizon()
                return

            t_stage = time.time()
            if self.account.get("type") == "ms":
                token_age = time.time() - float(self.account.get("token_time", 0) or 0)
                has_token = bool(self.account.get("access_token")) and self.account.get("access_token") != "0"
                if has_token and token_age < self.TOKEN_FRESH_SECONDS:
                    self.signals.log.emit(f"[AUTH] Microsoft session still valid ({int(token_age // 60)} min old), refresh skipped")
                elif self.account.get("refresh_token"):
                    self.signals.progress.emit("Validating Microsoft session...", 0, 1)
                    try:
                        from core.auth_service import AuthService
                        fresh_account = AuthService.refresh_microsoft_token(self.account["refresh_token"])
                        fresh_account["token_time"] = time.time()
                        self.account.update(fresh_account)
                        if self.parent_win and hasattr(self.parent_win, "config"):
                            accs = self.parent_win.config.get("accounts", {})
                            accs[self.account["id"]] = self.account
                            self.parent_win.config.set("accounts", accs)
                        self.signals.log.emit(f"[AUTH] Successfully refreshed Microsoft session for {self.account['name']}")
                    except Exception as auth_err:
                        self.signals.log.emit(f"[AUTH ERROR] Token refresh failed: {auth_err}")
                        if has_token and token_age < self.TOKEN_USABLE_SECONDS:
                            self.signals.log.emit("[AUTH] Using the saved session instead (it is still valid, e.g. you are offline)")
                        else:
                            raise RuntimeError(f"Microsoft session expired. Please re-add your account in Settings: {auth_err}")
                else:
                    raise RuntimeError("No refresh token stored. Please re-authenticate your Microsoft account in Settings.")
            mark("auth", t_stage)

            from core.java_manager import JavaManager
            from core.version_downloader import VersionDownloader
            from core.optimization import OptimizationEngine
            from core.game_launcher import GameLauncher
            from core.discord_rpc import DiscordRPCManager

            target_version = self.version_id

            t_stage = time.time()
            java_bin = JavaManager.ensure_java_runtime(
                target_version,
                self.root_dir,
                status_cb=lambda desc, cur, tot: self.signals.progress.emit(desc, cur, tot)
            )
            mark("java", t_stage)

            t_stage = time.time()
            downloader = VersionDownloader(
                self.root_dir,
                progress_callback=lambda desc, cur, tot: self.signals.progress.emit(desc, cur, tot)
            )
            downloader.install_version(target_version)
            mark("game files", t_stage)

            t_stage = time.time()
            self.signals.progress.emit(f"Preparing {self.loader} profile...", 0, 100)
            launch_version = self.inst_mgr.prepare_instance_loader(
                self.instance_dir, target_version, self.loader,
                status_cb=lambda desc, cur, tot: self.signals.progress.emit(desc, cur, tot)
            )

            if launch_version != target_version:
                downloader.install_version(launch_version)
            mark("loader", t_stage)

            if str(self.loader).strip().lower() == "fabric":
                t_mods = time.time()
                self._prepare_sodium_for_version(target_version)
                mark("mods", t_mods)

            cfg = self.parent_win.config if (self.parent_win and hasattr(self.parent_win, "config")) else None
            multicore_on = bool(cfg.get("multicore_enabled", True)) if cfg else True
            try:
                multicore_threads = int(cfg.get("multicore_threads", 0) or 0) if cfg else 0
            except (TypeError, ValueError):
                multicore_threads = 0
            try:
                multicore_cores = int(cfg.get("multicore_cores", 0) or 0) if cfg else 0
            except (TypeError, ValueError):
                multicore_cores = 0

            try:
                jvm_flags = OptimizationEngine.build_high_tier_jvm_args(
                    self.ram_mb,
                    multicore_enabled=multicore_on,
                    cpu_threads=multicore_threads,
                    cpu_cores=multicore_cores,
                )
            except TypeError:
                try:
                    jvm_flags = OptimizationEngine.build_high_tier_jvm_args(
                        self.ram_mb,
                        multicore_enabled=multicore_on,
                        cpu_threads=multicore_threads,
                    )
                except TypeError:
                    jvm_flags = OptimizationEngine.build_high_tier_jvm_args(self.ram_mb)

            try:
                active_cores = OptimizationEngine.resolve_core_count(multicore_on, multicore_cores)
                resolved_threads = OptimizationEngine.resolve_thread_count(multicore_on, multicore_threads, multicore_cores)
                total_cores = OptimizationEngine.detect_cpu_count()
            except Exception:
                total_cores = os.cpu_count() or 4
                active_cores = max(2, total_cores - 1) if multicore_on else 1
                resolved_threads = max(2, active_cores) if multicore_on else 1

            self.signals.log.emit(
                f"[OPT] Multicore Engine: {'ENABLED' if multicore_on else 'SINGLE-CORE'} "
                f"({active_cores} active CPU cores, {resolved_threads} GC/JIT/worker threads, {total_cores} cores detected)"
            )

            # Timing of the game process itself (launcher-side messages start with "[CLIENT]")
            proc_clock = {"start": None, "first_seen": False}

            def on_game_line(line: str):
                if proc_clock["start"] and not proc_clock["first_seen"] and not line.startswith("[CLIENT]"):
                    proc_clock["first_seen"] = True
                    self.signals.log.emit(f"[LAUNCH] Java printed its first line {time.time() - proc_clock['start']:.1f}s after starting")
                self.signals.log.emit(line)

            launcher = GameLauncher(self.root_dir, log_callback=on_game_line)
            self.signals.progress.emit("Launching Minecraft Engine...", 1, 1)
            self.signals.log.emit(f"[LAUNCH] Preparation took {time.time() - t_start:.1f}s ({', '.join(timings)})")

            DiscordRPCManager.get_instance().set_game_presence(
                version=target_version,
                loader=self.loader,
                instance_name=os.path.basename(self.instance_dir)
            )

            start_timestamp = time.time()
            proc_clock["start"] = start_timestamp

            try:
                proc = launcher.launch(
                    version_id=launch_version,
                    account=self.account,
                    jvm_args=jvm_flags,
                    instance_dir=self.instance_dir,
                    java_bin=java_bin,
                    custom_res=self.custom_res,
                    multicore_enabled=multicore_on,
                    cpu_cores=multicore_cores,
                )
            except TypeError:
                proc = launcher.launch(
                    version_id=launch_version,
                    account=self.account,
                    jvm_args=jvm_flags,
                    instance_dir=self.instance_dir,
                    java_bin=java_bin,
                    custom_res=self.custom_res,
                )

            if self.parent_win and proc:
                self.parent_win.active_process = proc
                self.signals.finished.emit()

            ret = proc.wait()
            elapsed_seconds = int(time.time() - start_timestamp)
            self._record_playtime(elapsed_seconds)

            DiscordRPCManager.get_instance().set_menu_presence()

            if ret != 0:
                self.signals.error.emit(f"Minecraft exited with error code {ret}. Check Console Log.")
            else:
                self.signals.progress.emit("Minecraft closed cleanly.", 0, 0)
        except Exception as e:
            try:
                from core.discord_rpc import DiscordRPCManager
                DiscordRPCManager.get_instance().set_menu_presence()
            except Exception:
                pass
            self.signals.error.emit(str(e))

    def _prepare_sodium_for_version(self, mc_version: str):
        """
        Ensures version-matched Fabric API + Sodium are paired for Fabric launches.
        Caches downloaded jars in <root_dir>/cached_mods/<mc_version>/ and safely skips Sodium on
        brand-new versions (e.g. 26.3) when no upstream Sodium build has been published yet.
        Built-in LowCore mod bundling stays handled by core/game_launcher.py (bundled/).
        """
        cfg = self.parent_win.config if (self.parent_win and hasattr(self.parent_win, "config")) else None
        auto_sodium = bool(cfg.get("auto_pair_sodium", True)) if cfg else True
        if not auto_sodium:
            return

        mods_dir = os.path.join(self.instance_dir, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        meta_path = os.path.join(self.instance_dir, ".lowcore_paired_mods.json")
        prev_meta = {}
        try:
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    prev_meta = json.load(f) or {}
        except Exception:
            prev_meta = {}

        # If instance switched MC version, remove previous auto-paired jars so mismatched versions don't crash Fabric
        if prev_meta.get("version") and prev_meta.get("version") != mc_version:
            for old_key in ("fabric_api_file", "sodium_file"):
                old_name = prev_meta.get(old_key)
                if old_name:
                    old_path = os.path.join(mods_dir, old_name)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass

        new_meta = {"version": mc_version}

        # Version-matched Fabric API + Sodium via Modrinth v2 API + local cache
        cache_dir = os.path.join(self.root_dir, "cached_mods", mc_version)
        os.makedirs(cache_dir, exist_ok=True)
        for slug, display, meta_key in (
            ("fabric-api", "Fabric API", "fabric_api_file"),
            ("sodium", "Sodium", "sodium_file"),
        ):
            try:
                installed = self._ensure_modrinth_mod_for_version(
                    slug=slug,
                    display_name=display,
                    mc_version=mc_version,
                    mods_dir=mods_dir,
                    cache_dir=cache_dir,
                )
                if installed:
                    new_meta[meta_key] = installed
            except Exception as exc:
                self.signals.log.emit(f"[{display.upper()}] Auto-pair skipped ({exc}); continuing launch.")

        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(new_meta, f, indent=2)
        except Exception:
            pass

    def _ensure_modrinth_mod_for_version(self, slug: str, display_name: str, mc_version: str, mods_dir: str, cache_dir: str):
        prefix = f"{slug}-"
        for existing in os.listdir(mods_dir):
            if existing.lower().startswith(prefix) and existing.lower().endswith(".jar"):
                return existing

        # Check disk cache first for instant offline launches
        cached = [
            f for f in os.listdir(cache_dir)
            if f.lower().startswith(prefix) and f.lower().endswith(".jar")
        ]
        if cached:
            src = os.path.join(cache_dir, cached[0])
            shutil.copy2(src, os.path.join(mods_dir, cached[0]))
            self.signals.log.emit(f"[{display_name.upper()}] Paired from cache for MC {mc_version}: {cached[0]}")
            return cached[0]

        import requests
        self.signals.progress.emit(f"Checking {display_name} for {mc_version}...", 0, 100)
        headers = {"User-Agent": f"LowCoreClient/{APP_VERSION}"}
        res = requests.get(
            f"https://api.modrinth.com/v2/project/{slug}/version",
            params={
                "loaders": json.dumps(["fabric"]),
                "game_versions": json.dumps([mc_version]),
            },
            headers=headers,
            timeout=10,
        )
        if res.status_code == 404:
            self.signals.log.emit(f"[{display_name.upper()}] Project not found for MC {mc_version}.")
            return None
        res.raise_for_status()
        versions = res.json() or []
        if not versions:
            self.signals.log.emit(
                f"[{display_name.upper()}] No {display_name} build published yet for MC {mc_version} — continuing without it."
            )
            return None

        chosen = next((v for v in versions if v.get("version_type") == "release"), versions[0])
        files = chosen.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary or not primary.get("url"):
            return None

        orig_name = primary.get("filename") or f"{slug}-{mc_version}.jar"
        cache_name = orig_name if orig_name.lower().startswith(prefix) else f"{prefix}{orig_name}"
        cache_path = os.path.join(cache_dir, cache_name)

        self.signals.progress.emit(f"Downloading {display_name} ({mc_version})...", 0, 100)
        dl = requests.get(primary["url"], headers=headers, stream=True, timeout=30)
        dl.raise_for_status()
        tmp_path = cache_path + ".tmp"
        with open(tmp_path, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        os.replace(tmp_path, cache_path)
        shutil.copy2(cache_path, os.path.join(mods_dir, cache_name))
        self.signals.log.emit(f"[{display_name.upper()}] Paired {cache_name} for MC {mc_version}")
        return cache_name

    def _run_horizon(self):
        """Horizon (Rust client): drive Horizon's own launcher. No Java / Minecraft download / loader steps."""
        from core.discord_rpc import DiscordRPCManager
        cfg = self.parent_win.config if self.parent_win else None
        launcher = hb.find_launcher(cfg.get(hb.CONFIG_PATH_KEY) if cfg else None)
        if not launcher:
            raise RuntimeError("The Horizon launcher was not found. Open Settings > Premium > Horizon and choose it.")

        ready, why = hb.minecraft_files_ready(self.root_dir)
        if not ready:
            self.signals.log.emit(f"[HORIZON] Note: LowCore's Minecraft {hb.HORIZON_MC_VERSION} files are {why}. "
                                  f"That is fine if Horizon was prepared from another Minecraft install.")

        instance_name = ((cfg.get(hb.CONFIG_INSTANCE_KEY, "") if cfg else "") or "").strip() or None
        self.signals.progress.emit("Starting Horizon...", 0, 0)
        self.signals.log.emit(f"[HORIZON] Using {launcher}")

        DiscordRPCManager.get_instance().set_game_presence(
            version=hb.HORIZON_MC_VERSION,
            loader="Horizon (Rust)",
            instance_name=os.path.basename(self.instance_dir)
        )

        start_timestamp = time.time()
        session = hb.start_play(launcher, instance_name, log_cb=lambda line: self.signals.log.emit(f"[HORIZON] {line}"))

        if self.parent_win:
            self.parent_win.active_process = session
            self.signals.finished.emit()

        ret = session.wait()
        self._record_playtime(int(time.time() - start_timestamp))
        DiscordRPCManager.get_instance().set_menu_presence()

        if ret != 0:
            self.signals.error.emit(f"Horizon exited with error code {ret}. Check Console Log.")
        else:
            self.signals.progress.emit("Minecraft closed cleanly.", 0, 0)

    def _record_playtime(self, elapsed_sec: int):
        meta_file = os.path.join(self.instance_dir, "instance.json")
        data = {}
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        current_time = data.get("playtime_seconds", 0)
        data["playtime_seconds"] = current_time + elapsed_sec
        data["last_played"] = int(time.time())
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass


class HorizonSetupWorker(QRunnable):
    """Settings > Premium > Horizon > "Set up Horizon": Minecraft files -> install -> prepare -> instance."""

    def __init__(self, launcher: str, game_dir: str, inst_mgr: InstanceManager):
        super().__init__()
        self.launcher = launcher
        self.game_dir = game_dir
        self.inst_mgr = inst_mgr
        self.signals = WorkerSignals()

    def run(self):
        try:
            log = lambda text: self.signals.log.emit(f"[HORIZON] {text}")

            ready, why = hb.minecraft_files_ready(self.game_dir)
            if not ready:
                from core.version_downloader import VersionDownloader
                self.signals.progress.emit(f"Downloading Minecraft {hb.HORIZON_MC_VERSION} files...", 0, 0)
                log(f"Minecraft {hb.HORIZON_MC_VERSION} files {why}; downloading them into LowCore's game folder")
                downloader = VersionDownloader(
                    self.game_dir,
                    progress_callback=lambda desc, cur, tot: self.signals.progress.emit(desc, cur, tot)
                )
                downloader.install_version(hb.HORIZON_MC_VERSION)

            self.signals.progress.emit("Installing the latest Horizon (Horizon's launcher does this)...", 0, 0)
            code, tail = hb.install_latest(self.launcher, log)
            if code != 0:
                raise RuntimeError(f"Horizon's launcher could not install Horizon (exit code {code}).\n{tail}")

            self.signals.progress.emit("Preparing Horizon's resources from the Minecraft files...", 0, 0)
            code, tail = hb.prepare(self.launcher, self.game_dir, log)
            if code != 0:
                raise RuntimeError(f"Horizon's launcher could not prepare the resources (exit code {code}).\n{tail}")

            if not any(hb.is_horizon_instance(i) for i in self.inst_mgr.list_instances()):
                self.inst_mgr.create_instance(hb.INSTANCE_DISPLAY_NAME, hb.HORIZON_MC_VERSION, hb.LOADER_NAME)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


class DeviceAuthWorker(QRunnable):
    def __init__(self, device_code: str, interval: int, expires_in: int):
        super().__init__()
        self.device_code = device_code
        self.interval = interval
        self.expires_in = expires_in
        self.signals = WorkerSignals()
        self.account_data = None

    def run(self):
        try:
            from core.auth_service import AuthService
            self.account_data = AuthService.poll_for_login(
                self.device_code,
                self.interval,
                self.expires_in,
                status_cb=lambda msg: self.signals.progress.emit(msg, 0, 0)
            )
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


class UpdateSignals(QObject):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)


class UpdateCheckWorker(QRunnable):
    def __init__(self, url: str, current_version: str):
        super().__init__()
        self.url = url
        self.current_version = current_version
        self.signals = UpdateSignals()

    def run(self):
        try:
            from core import updater as app_updater
            self.signals.done.emit(app_updater.check_for_update(self.url, self.current_version))
        except Exception as e:
            self.signals.failed.emit(str(e))


class UpdateInstallSignals(QObject):
    progress = pyqtSignal(str, int, int)
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)


class UpdateInstallWorker(QRunnable):
    def __init__(self, info: dict, app_dir: str):
        super().__init__()
        self.info = info
        self.app_dir = app_dir
        self.signals = UpdateInstallSignals()

    def run(self):
        try:
            from core import updater as app_updater
            res = app_updater.apply_in_place_update(
                self.info,
                self.app_dir,
                progress_cb=lambda msg, cur, tot: self.signals.progress.emit(msg, cur, tot),
            )
            self.signals.done.emit(res)
        except Exception as e:
            self.signals.failed.emit(str(e))


class ImportSignals(QObject):
    scanned = pyqtSignal(list)
    progress = pyqtSignal(int, int, str)      # done_bytes, total_bytes, instance name
    item_done = pyqtSignal(str, str)          # instance name, "" or error text
    finished = pyqtSignal(list)               # names that were imported
    error = pyqtSignal(str)


class ImportScanWorker(QRunnable):
    def __init__(self, folder: str = None):
        super().__init__()
        self.folder = folder
        self.signals = ImportSignals()

    def run(self):
        try:
            from core import importer as inst_importer
            if self.folder:
                entries = inst_importer.scan_folder(self.folder, with_sizes=True)
            else:
                entries = inst_importer.scan_default(with_sizes=True)
            self.signals.scanned.emit(entries)
        except Exception as e:
            self.signals.error.emit(str(e))


class ImportCopyWorker(QRunnable):
    def __init__(self, entries: list, inst_mgr, include_worlds: bool):
        super().__init__()
        self.entries = entries
        self.inst_mgr = inst_mgr
        self.include_worlds = include_worlds
        self.signals = ImportSignals()

    def run(self):
        from core import importer as inst_importer
        done_names = []
        taken = {i.get("name", "").lower() for i in self.inst_mgr.list_instances()}
        for entry in self.entries:
            name = entry.get("name", "Instance")
            try:
                result = inst_importer.import_entry(
                    entry, self.inst_mgr, include_worlds=self.include_worlds,
                    progress_cb=lambda d, t, n=name: self.signals.progress.emit(d, t, n),
                    taken_names=taken
                )
                taken.add(result["name"].lower())
                done_names.append(os.path.basename(result["folder"]) if result.get("folder") else result["name"])
                msg = ""
                if result.get("failed_files"):
                    msg = f"{len(result['failed_files'])} file(s) could not be copied"
                self.signals.item_done.emit(result["name"], msg)
            except Exception as e:
                self.signals.item_done.emit(name, f"Failed: {e}")
        self.signals.finished.emit(done_names)


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _lerp_color(c1, c2, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    a, b = QColor(c1), QColor(c2)
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def _shade_color(hex_color: str, factor: float) -> QColor:
    c = QColor(hex_color)
    return QColor(
        max(0, min(255, int(c.red() * factor))),
        max(0, min(255, int(c.green() * factor))),
        max(0, min(255, int(c.blue() * factor))),
        c.alpha(),
    )


MINECRAFT_BLOCKS = [
    ("grass", "Grass Block"),
    ("iron", "Block of Iron"),
    ("gold", "Block of Gold"),
    ("diamond", "Block of Diamond"),
    ("emerald", "Block of Emerald"),
    ("redstone", "Block of Redstone"),
    ("lapis", "Lapis Lazuli Block"),
    ("netherite", "Block of Netherite"),
    ("obsidian", "Obsidian"),
    ("oak_log", "Oak Log"),
    ("crafting", "Crafting Table"),
    ("bookshelf", "Bookshelf"),
    ("tnt", "TNT"),
    ("command", "Command Block"),
]
_MINECRAFT_BLOCK_MAP = {bid: name for bid, name in MINECRAFT_BLOCKS}
_BLOCK_PIXMAP_CACHE = OrderedDict()
_BLOCK_CACHE_MAX = 20


def _prune_large_block_cache():
    for k in [k for k in list(_BLOCK_PIXMAP_CACHE.keys()) if k[1] > 48]:
        _BLOCK_PIXMAP_CACHE.pop(k, None)


def get_minecraft_block_name(block_id: str) -> str:
    key = (block_id or "grass").strip().lower()
    return _MINECRAFT_BLOCK_MAP.get(key, "Grass Block")


def get_minecraft_block_pixmap(block_id: str, size: int = 48) -> QPixmap:
    """Procedurally renders a crisp 3D isometric Minecraft block icon and caches it."""
    key = (block_id or "grass").strip().lower()
    if key not in _MINECRAFT_BLOCK_MAP:
        key = "grass"
    cache_key = (key, int(size))
    cached = _BLOCK_PIXMAP_CACHE.get(cache_key)
    if cached is not None and not cached.isNull():
        _BLOCK_PIXMAP_CACHE.move_to_end(cache_key)
        return cached

    hi = max(64, int(size) * 2)
    pix = QPixmap(hi, hi)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    cx = hi * 0.5
    cy = hi * 0.51
    dx = hi * 0.39
    dy = hi * 0.195

    T = QPointF(cx, cy - 2.0 * dy)
    TL = QPointF(cx - dx, cy - dy)
    TR = QPointF(cx + dx, cy - dy)
    C = QPointF(cx, cy)
    B = QPointF(cx, cy + 2.0 * dy)
    BL = QPointF(cx - dx, cy + dy)
    BR = QPointF(cx + dx, cy + dy)

    def pt_face(face: str, u: float, v: float) -> QPointF:
        if face == "top":
            return T + (TR - T) * u + (TL - T) * v
        if face == "left":
            return TL + (C - TL) * u + (BL - TL) * v
        return C + (TR - C) * u + (B - C) * v

    def fill_face(face: str, col: QColor):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([pt_face(face, 0, 0), pt_face(face, 1, 0), pt_face(face, 1, 1), pt_face(face, 0, 1)]))

    def cell(face: str, col_idx: int, row_idx: int, color: QColor, n: int = 8, cw: int = 1, ch: int = 1):
        eps = 0.008
        u0 = max(0.0, col_idx / float(n) - eps)
        v0 = max(0.0, row_idx / float(n) - eps)
        u1 = min(1.0, (col_idx + cw) / float(n) + eps)
        v1 = min(1.0, (row_idx + ch) / float(n) + eps)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPolygon(QPolygonF([
            pt_face(face, u0, v0),
            pt_face(face, u1, v0),
            pt_face(face, u1, v1),
            pt_face(face, u0, v1),
        ]))

    def draw_bevel_block(base_hex: str, hi_hex: str, rim_hex: str, glint_hex: str):
        shades = {"top": 1.0, "left": 0.86, "right": 0.68}
        for face, mult in shades.items():
            fill_face(face, _shade_color(base_hex, mult))
            c_hi = _shade_color(hi_hex, mult)
            c_rim = _shade_color(rim_hex, mult)
            c_gl = _shade_color(glint_hex, mult)
            cell(face, 0, 0, c_hi, cw=8, ch=1)
            cell(face, 0, 0, c_hi, cw=1, ch=8)
            cell(face, 7, 1, c_rim, cw=1, ch=7)
            cell(face, 1, 7, c_rim, cw=7, ch=1)
            # Inner engraved border
            cell(face, 2, 2, c_rim, cw=4, ch=1)
            cell(face, 2, 2, c_rim, cw=1, ch=4)
            cell(face, 3, 3, c_hi, cw=2, ch=2)
            cell(face, 1, 1, c_gl, cw=2, ch=1)
            cell(face, 5, 5, c_gl, cw=1, ch=1)

    if key == "grass":
        fill_face("top", QColor("#67B347"))
        for u, v, col in (
            (1, 1, "#7BD058"), (5, 2, "#7BD058"), (2, 5, "#7BD058"), (6, 6, "#7BD058"),
            (3, 1, "#539636"), (6, 3, "#539636"), (1, 4, "#539636"), (4, 6, "#539636"),
            (0, 6, "#7BD058"), (4, 3, "#7BD058"), (7, 1, "#539636"), (3, 7, "#539636"),
        ):
            cell("top", u, v, QColor(col))
        for face, mult in (("left", 0.88), ("right", 0.70)):
            fill_face(face, _shade_color("#865E3F", mult))
            for u, v in ((1, 3), (4, 4), (6, 5), (2, 6), (5, 7), (0, 5), (7, 3)):
                cell(face, u, v, _shade_color("#6C482E", mult))
            for u, v in ((2, 4), (6, 6), (3, 7), (0, 7)):
                cell(face, u, v, _shade_color("#9B7250", mult))
            # Overhanging green turf band
            cell(face, 0, 0, _shade_color("#63AD43", mult), cw=8, ch=2)
            for u in (0, 2, 5, 7):
                cell(face, u, 2, _shade_color("#539636", mult))
            for u in (1, 4, 6):
                cell(face, u, 0, _shade_color("#79CA56", mult))

    elif key == "iron":
        draw_bevel_block("#DCE3E8", "#F4F8FB", "#AEB8C0", "#FFFFFF")

    elif key == "gold":
        draw_bevel_block("#F5C324", "#FFF073", "#BE810B", "#FFF9B0")

    elif key == "diamond":
        draw_bevel_block("#3AD8D0", "#9CFDF7", "#1C9994", "#E6FFFE")

    elif key == "emerald":
        for face, mult in (("top", 1.0), ("left", 0.86), ("right", 0.68)):
            fill_face(face, _shade_color("#28CC5B", mult))
            c_dark = _shade_color("#127A34", mult)
            c_mid = _shade_color("#1BA647", mult)
            c_hi = _shade_color("#75FF9F", mult)
            c_bright = _shade_color("#C9FFDA", mult)
            cell(face, 0, 0, c_dark, cw=8, ch=1)
            cell(face, 0, 7, c_dark, cw=8, ch=1)
            cell(face, 0, 0, c_dark, cw=1, ch=8)
            cell(face, 7, 0, c_dark, cw=1, ch=8)
            cell(face, 1, 1, c_mid, cw=6, ch=6)
            cell(face, 2, 2, _shade_color("#2CD663", mult), cw=4, ch=4)
            cell(face, 3, 2, c_hi, cw=2, ch=1)
            cell(face, 2, 3, c_hi, cw=1, ch=2)
            cell(face, 3, 3, c_bright, cw=2, ch=2)

    elif key == "redstone":
        for face, mult in (("top", 1.0), ("left", 0.86), ("right", 0.68)):
            fill_face(face, _shade_color("#C92222", mult))
            for u, v in ((0, 0), (3, 1), (6, 2), (1, 4), (4, 5), (7, 6), (2, 7), (5, 0)):
                cell(face, u, v, _shade_color("#7A0D0D", mult))
            for u, v in ((2, 2), (3, 3), (4, 3), (3, 4), (5, 4), (1, 2), (6, 5)):
                cell(face, u, v, _shade_color("#FF5747", mult))
            cell(face, 3, 3, _shade_color("#FF9C8F", mult))

    elif key == "lapis":
        for face, mult in (("top", 1.0), ("left", 0.86), ("right", 0.68)):
            fill_face(face, _shade_color("#254BB5", mult))
            for u, v in ((1, 1), (4, 2), (2, 5), (6, 4), (5, 6), (0, 3)):
                cell(face, u, v, _shade_color("#4B76EB", mult), cw=2 if (u + v) % 2 == 0 else 1)
            for u, v in ((0, 0), (5, 0), (3, 4), (7, 2), (1, 6), (6, 7)):
                cell(face, u, v, _shade_color("#172F7D", mult))

    elif key == "netherite":
        draw_bevel_block("#494246", "#665D63", "#2A2528", "#80757C")

    elif key == "obsidian":
        for face, mult in (("top", 1.0), ("left", 0.86), ("right", 0.72)):
            fill_face(face, _shade_color("#1B1226", mult))
            for u, v in ((1, 1), (5, 2), (2, 4), (6, 6), (0, 6), (4, 0)):
                cell(face, u, v, _shade_color("#3C2559", mult))
            for u, v in ((2, 1), (5, 5), (1, 5)):
                cell(face, u, v, _shade_color("#53357A", mult))
            for u, v in ((3, 3), (6, 1), (4, 6), (0, 2)):
                cell(face, u, v, _shade_color("#0E0814", mult))

    elif key == "oak_log":
        # Concentric wood grain on top
        fill_face("top", QColor("#5D4122"))
        cell("top", 1, 1, QColor("#C69B63"), cw=6, ch=6)
        cell("top", 2, 2, QColor("#A67A47"), cw=4, ch=4)
        cell("top", 3, 3, QColor("#825B30"), cw=2, ch=2)
        for face, mult in (("left", 0.88), ("right", 0.70)):
            fill_face(face, _shade_color("#684A28", mult))
            for col_i in (1, 4, 6):
                cell(face, col_i, 0, _shade_color("#4D351A", mult), cw=1, ch=8)
            for col_i in (2, 5):
                cell(face, col_i, 1, _shade_color("#7E5B34", mult), cw=1, ch=6)

    elif key == "crafting":
        fill_face("top", QColor("#C7985A"))
        # Dark wooden rim & 3x3 crafting grid on top
        for idx in (2, 5):
            cell("top", idx, 1, QColor("#6E441E"), cw=1, ch=6)
            cell("top", 1, idx, QColor("#6E441E"), cw=6, ch=1)
        for u in (0, 7):
            cell("top", u, 0, QColor("#8C5D32"), cw=1, ch=8)
        for v in (0, 7):
            cell("top", 0, v, QColor("#8C5D32"), cw=8, ch=1)
        for face, mult in (("left", 0.88), ("right", 0.70)):
            fill_face(face, _shade_color("#B38249", mult))
            cell(face, 0, 0, _shade_color("#734B24", mult), cw=8, ch=1)
            cell(face, 0, 7, _shade_color("#734B24", mult), cw=8, ch=1)
            # Tool silhouettes (saw / hammer)
            cell(face, 1, 2, _shade_color("#505760", mult), cw=2, ch=3)
            cell(face, 2, 1, _shade_color("#7A4E28", mult), cw=1, ch=1)
            cell(face, 5, 2, _shade_color("#505760", mult), cw=2, ch=2)
            cell(face, 5, 4, _shade_color("#7A4E28", mult), cw=1, ch=2)

    elif key == "bookshelf":
        fill_face("top", QColor("#BD8E53"))
        for col_i in (2, 5):
            cell("top", col_i, 0, QColor("#9C703B"), cw=1, ch=8)
        book_palette = ("#CC3B3B", "#3972CC", "#44A852", "#E0B23A", "#46B5C9", "#A14DC9")
        for face, mult in (("left", 0.88), ("right", 0.70)):
            fill_face(face, _shade_color("#BD8E53", mult))
            cell(face, 0, 1, _shade_color("#2E1D12", mult), cw=8, ch=2)
            cell(face, 0, 5, _shade_color("#2E1D12", mult), cw=8, ch=2)
            for u in range(8):
                if u in (3, 7):
                    continue
                b1 = _shade_color(book_palette[(u + (0 if face == "left" else 2)) % len(book_palette)], mult)
                b2 = _shade_color(book_palette[(u + (3 if face == "left" else 5)) % len(book_palette)], mult)
                cell(face, u, 1, b1, cw=1, ch=2)
                cell(face, u, 5, b2, cw=1, ch=2)

    elif key == "tnt":
        fill_face("top", QColor("#D93829"))
        for u in (1, 3, 5, 7):
            cell("top", u, 0, QColor("#A62217"), cw=1, ch=8)
        cell("top", 3, 3, QColor("#5E5B57"), cw=2, ch=2)
        for face, mult in (("left", 0.90), ("right", 0.74)):
            fill_face(face, _shade_color("#D93829", mult))
            cell(face, 0, 2, _shade_color("#F2F1EC", mult), cw=8, ch=4)
            ink = _shade_color("#1C1D20", mult)
            # Stylized dark pixel lettering band inside the white label
            cell(face, 1, 3, ink, cw=2, ch=1)
            cell(face, 1, 4, ink, cw=1, ch=1)
            cell(face, 3, 3, ink, cw=1, ch=2)
            cell(face, 4, 4, ink, cw=1, ch=1)
            cell(face, 5, 3, ink, cw=2, ch=1)
            cell(face, 6, 4, ink, cw=1, ch=1)

    elif key == "command":
        for face, mult in (("top", 1.0), ("left", 0.88), ("right", 0.70)):
            fill_face(face, _shade_color("#D48150", mult))
            cell(face, 1, 1, _shade_color("#B06035", mult), cw=6, ch=6)
            cell(face, 2, 2, _shade_color("#2B4F4B", mult), cw=4, ch=4)
            cell(face, 2, 2, _shade_color("#5EE89A", mult))
            cell(face, 5, 2, _shade_color("#FF6B6B", mult))
            cell(face, 2, 5, _shade_color("#FFE066", mult))
            cell(face, 5, 5, _shade_color("#63B3FF", mult))

    # Crisp subtle highlights along cube ridges & subtle outline
    p.setBrush(Qt.BrushStyle.NoBrush)
    ridge_pen = QPen(QColor(255, 255, 255, 55), max(1.0, hi * 0.018))
    ridge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(ridge_pen)
    p.drawLine(TL, C)
    p.drawLine(C, TR)
    p.drawLine(C, B)

    outline_pen = QPen(QColor(0, 0, 0, 95), max(1.1, hi * 0.02))
    outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(outline_pen)
    p.drawPolygon(QPolygonF([T, TR, BR, B, BL, TL]))
    p.end()

    final = pix.scaled(
        int(size), int(size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    _BLOCK_PIXMAP_CACHE[cache_key] = final
    _BLOCK_PIXMAP_CACHE.move_to_end(cache_key)
    while len(_BLOCK_PIXMAP_CACHE) > _BLOCK_CACHE_MAX:
        _BLOCK_PIXMAP_CACHE.popitem(last=False)
    return final


_MENU_ICON_CACHE = {}


def _make_menu_icon(kind: str, color_hex: str = "#9AA0AA", size: int = 16) -> QIcon:
    """Renders crisp theme-matched monochrome vector icons (no cartoonish OS emojis)."""
    cache_key = (kind, color_hex, int(size))
    cached = _MENU_ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    hi = max(32, int(size) * 2)
    pix = QPixmap(hi, hi)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    col = QColor(color_hex)
    pen = QPen(col, 2.3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    s = float(hi)
    m = s * 0.5

    if kind == "clock":
        p.drawEllipse(QRectF(5, 5, s - 10, s - 10))
        p.drawLine(QPointF(m, m), QPointF(m, 9))
        p.drawLine(QPointF(m, m), QPointF(m + 5, m + 2))
    elif kind == "edit":
        p.drawLine(QPointF(7, s - 7), QPointF(s - 9, 9))
        p.drawLine(QPointF(s - 12, 6), QPointF(s - 6, 12))
        p.drawLine(QPointF(6, s - 6), QPointF(10, s - 7))
        p.drawLine(QPointF(6, s - 6), QPointF(7, s - 10))
    elif kind == "copy":
        p.drawRoundedRect(QRectF(10, 6, s - 16, s - 16), 2.5, 2.5)
        p.drawRoundedRect(QRectF(6, 11, s - 16, s - 16), 2.5, 2.5)
    elif kind == "mods":
        for x, y in ((6, 6), (17, 6), (6, 17), (17, 17)):
            p.drawRoundedRect(QRectF(x, y, 8.5, 8.5), 2.0, 2.0)
    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(5, 8)
        path.lineTo(13, 8)
        path.lineTo(16, 11)
        path.lineTo(s - 5, 11)
        path.lineTo(s - 5, s - 6)
        path.lineTo(5, s - 6)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "palette":
        p.drawEllipse(QRectF(5.5, 5.5, s - 11, s - 11))
        p.setBrush(col)
        p.setPen(Qt.PenStyle.NoPen)
        for cx, cy in ((12, 12), (20, 12), (12, 20)):
            p.drawEllipse(QPointF(cx, cy), 1.9, 1.9)
    elif kind == "shaders":
        star = QPainterPath()
        star.moveTo(m, 4.5)
        star.lineTo(m + 2.6, m - 2.6)
        star.lineTo(s - 4.5, m)
        star.lineTo(m + 2.6, m + 2.6)
        star.lineTo(m, s - 4.5)
        star.lineTo(m - 2.6, m + 2.6)
        star.lineTo(4.5, m)
        star.lineTo(m - 2.6, m - 2.6)
        star.closeSubpath()
        p.drawPath(star)
    elif kind == "worlds":
        p.drawEllipse(QRectF(5, 5, s - 10, s - 10))
        p.drawEllipse(QRectF(11, 5, s - 22, s - 10))
        p.drawLine(QPointF(5.5, m), QPointF(s - 5.5, m))
    elif kind == "camera":
        p.drawRoundedRect(QRectF(5, 9, s - 10, s - 15), 3.0, 3.0)
        p.drawLine(QPointF(12, 9), QPointF(14, 6))
        p.drawLine(QPointF(14, 6), QPointF(s - 14, 6))
        p.drawLine(QPointF(s - 14, 6), QPointF(s - 12, 9))
        p.drawEllipse(QPointF(m, m + 1), 3.6, 3.6)
    elif kind == "gear":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        outer_r = 10.6
        inner_r = 7.6
        gp = QPainterPath()
        teeth = 8
        step = (2.0 * math.pi) / teeth
        pts = []
        for i in range(teeth):
            a0 = i * step
            for ang, rad in (
                (a0 - step * 0.24, inner_r),
                (a0 - step * 0.13, outer_r),
                (a0 + step * 0.13, outer_r),
                (a0 + step * 0.24, inner_r),
            ):
                pts.append(QPointF(m + math.cos(ang) * rad, m + math.sin(ang) * rad))
        if pts:
            gp.moveTo(pts[0])
            for pt in pts[1:]:
                gp.lineTo(pt)
            gp.closeSubpath()
        hole = QPainterPath()
        hole.addEllipse(QPointF(m, m), 3.8, 3.8)
        p.drawPath(gp.subtracted(hole))
    elif kind == "trash":
        p.drawLine(QPointF(7, 9.5), QPointF(s - 7, 9.5))
        p.drawLine(QPointF(12.5, 6.5), QPointF(s - 12.5, 6.5))
        p.drawRoundedRect(QRectF(8.5, 9.5, s - 17, s - 15.5), 2.0, 2.0)
        p.drawLine(QPointF(13.5, 13.5), QPointF(13.5, s - 9))
        p.drawLine(QPointF(s - 13.5, 13.5), QPointF(s - 13.5, s - 9))
    elif kind == "check":
        p.drawLine(QPointF(6.5, m + 1.0), QPointF(m - 2.0, s - 8.5))
        p.drawLine(QPointF(m - 2.0, s - 8.5), QPointF(s - 6.0, 8.5))
    elif kind == "user":
        p.drawEllipse(QPointF(m, 10.5), 4.6, 4.6)
        arc = QPainterPath()
        arc.moveTo(6.5, s - 6.5)
        arc.quadTo(m, 15.5, s - 6.5, s - 6.5)
        p.drawPath(arc)
    elif kind == "cube":
        top = QPointF(m, 5.0)
        right = QPointF(s - 5.5, 10.2)
        left = QPointF(5.5, 10.2)
        center = QPointF(m, 15.6)
        bot = QPointF(m, s - 5.0)
        bl = QPointF(5.5, s - 10.2)
        br = QPointF(s - 5.5, s - 10.2)
        p.drawPolygon(QPolygonF([top, right, br, bot, bl, left]))
        p.drawLine(left, center)
        p.drawLine(right, center)
        p.drawLine(center, bot)
    elif kind == "flask":
        fp = QPainterPath()
        fp.moveTo(m - 4.0, 6.0)
        fp.lineTo(m + 4.0, 6.0)
        fp.moveTo(m - 2.8, 6.0)
        fp.lineTo(m - 2.8, 13.5)
        fp.lineTo(6.2, s - 6.5)
        fp.quadTo(5.6, s - 5.2, 7.6, s - 5.2)
        fp.lineTo(s - 7.6, s - 5.2)
        fp.quadTo(s - 5.6, s - 5.2, s - 6.2, s - 6.5)
        fp.lineTo(m + 2.8, 13.5)
        fp.lineTo(m + 2.8, 6.0)
        p.drawPath(fp)
    elif kind == "proxy":
        shield = QPainterPath()
        shield.moveTo(m, 5.0)
        shield.lineTo(s - 6.5, 8.5)
        shield.lineTo(s - 6.5, 15.8)
        shield.quadTo(s - 6.8, s - 7.0, m, s - 4.8)
        shield.quadTo(6.8, s - 7.0, 6.5, 15.8)
        shield.lineTo(6.5, 8.5)
        shield.closeSubpath()
        p.drawPath(shield)
    elif kind == "updates":
        p.drawArc(QRectF(6.0, 6.0, s - 12.0, s - 12.0), 35 * 16, 265 * 16)
        p.drawLine(QPointF(m + 5.5, 6.0), QPointF(s - 6.0, 11.0))
        p.drawLine(QPointF(m + 3.2, 11.8), QPointF(s - 6.0, 11.0))
    elif kind == "premium":
        crown = QPainterPath()
        crown.moveTo(6.0, s - 7.5)
        crown.lineTo(5.2, 10.5)
        crown.lineTo(11.4, 16.5)
        crown.lineTo(m, 6.5)
        crown.lineTo(s - 11.4, 16.5)
        crown.lineTo(s - 5.2, 10.5)
        crown.lineTo(s - 6.0, s - 7.5)
        crown.closeSubpath()
        p.drawPath(crown)
    elif kind in ("heart", "donate"):
        hp = QPainterPath()
        hp.moveTo(m, s - 6.0)
        hp.cubicTo(4.0, 16.5, 6.5, 5.5, m, 12.2)
        hp.cubicTo(s - 6.5, 5.5, s - 4.0, 16.5, m, s - 6.0)
        p.drawPath(hp)

    p.end()
    final = pix.scaled(int(size), int(size), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    icon = QIcon(final)
    _MENU_ICON_CACHE[cache_key] = icon
    return icon


class SettingsIconButton(QPushButton):
    """Crisp inline vector icon button for Settings instance/account cards."""

    def __init__(self, icon_kind: str, tooltip: str = "", danger: bool = False, block_id: str = "", parent=None):
        super().__init__(parent)
        self.icon_kind = icon_kind
        self.danger = danger
        self.block_id = block_id
        self._hover = 0.0
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(130)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_block(self, block_id: str):
        self.block_id = block_id or "grass"
        self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self.danger:
            bg = _lerp_color(t["pill_bg"], "#FF5555", self._hover * 0.22)
            border = _lerp_color(t["border"], "#FF5555", self._hover * 0.75)
            icon_col = _lerp_color(t["text_sub"], "#FF6B6B", self._hover)
        else:
            bg = _lerp_color(t["pill_bg"], t["pill_hover"], self._hover)
            border = _lerp_color(t["border"], t["accent"], self._hover * 0.65)
            icon_col = _lerp_color(t["text_sub"], t["text"], self._hover)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 8.0, 8.0)

        if self.block_id:
            pix = get_minecraft_block_pixmap(self.block_id, 18)
            p.drawPixmap((self.width() - pix.width()) // 2, (self.height() - pix.height()) // 2, pix)
        else:
            ic = _make_menu_icon(self.icon_kind, icon_col.name(), 15)
            pix = ic.pixmap(15, 15)
            p.drawPixmap((self.width() - pix.width()) // 2, (self.height() - pix.height()) // 2, pix)
        p.end()


class SettingsTabItem(QPushButton):
    """Horizontal segmented Settings tab button with crisp vector icon and bottom accent indicator."""

    def __init__(self, icon_kind: str, label: str, parent=None):
        super().__init__(label, parent)
        self.icon_kind = icon_kind
        self._hover = 0.0
        self._active = False
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        f = self.font()
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Bold)
        self.setFont(f)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + 40, 36)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def set_active(self, active: bool):
        active = bool(active)
        if self._active != active:
            self._active = active
            self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._active:
            bg = _lerp_color(t["card_bg"], t["accent"], 0.16)
            p.setPen(QPen(QColor(_hex_rgba(t["accent"], 0.48)), 1.0))
            p.setBrush(bg)
            p.drawRoundedRect(rect, 9.0, 9.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t["accent"]))
            bar_w = max(18.0, self.width() * 0.42)
            p.drawRoundedRect(QRectF((self.width() - bar_w) / 2.0, self.height() - 3.0, bar_w, 2.2), 1.1, 1.1)
            icon_col = QColor(t["accent"])
            text_col = QColor(t["text"])
        else:
            bg = _lerp_color(QColor(0, 0, 0, 0), t["pill_hover"], self._hover)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 9.0, 9.0)
            icon_col = _lerp_color(t["text_sub"], t["text"], self._hover)
            text_col = _lerp_color(t["text_sub"], t["text"], self._hover)

        ic = _make_menu_icon(self.icon_kind, icon_col.name(), 13)
        ic_pix = ic.pixmap(13, 13)

        f = self.font()
        f.setWeight(QFont.Weight.Bold if self._active else QFont.Weight.DemiBold)
        p.setFont(f)
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(self.text())
        gap = 5
        total_w = 13 + gap + tw
        start_x = max(5.0, (self.width() - total_w) / 2.0)

        p.drawPixmap(int(start_x), (self.height() - 13) // 2, ic_pix)
        p.setPen(text_col)
        tx = start_x + 13 + gap
        avail = max(10.0, self.width() - tx - 5.0)
        elided = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight, int(avail))
        p.drawText(
            QRectF(tx, 0, avail, self.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided,
        )
        p.end()


class SettingsTabBar(QFrame):
    """Horizontal Settings subpage strip giving subpages full card width."""
    currentRowChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedHeight(50)
        self._current_row = 0
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 7, 6, 7)
        layout.setSpacing(3)

        specs = [
            ("gear", "settings_general"),
            ("cube", "nav_instances"),
            ("user", "nav_accounts"),
            ("worlds", "language"),
            ("proxy", "settings_proxy"),
            ("premium", "nav_experimental"),
            ("updates", "tab_updates"),
            ("heart", "nav_donations"),
        ]
        self._tab_keys = [k for _, k in specs]
        self.tabs = []
        for idx, (icon_kind, key) in enumerate(specs):
            lbl = I18n.t(key)
            btn = SettingsTabItem(icon_kind, lbl, self)
            btn.clicked.connect(lambda _, i=idx: self.setCurrentRow(i))
            self.tabs.append(btn)
            layout.addWidget(btn, stretch=max(4, len(lbl)))

        self.tabs[0].set_active(True)

    def retranslate_ui(self):
        for btn, key in zip(self.tabs, self._tab_keys):
            btn.setText(I18n.t(key))
            btn.update()

    def count(self) -> int:
        return len(self.tabs)

    def currentRow(self) -> int:
        return self._current_row

    def setCurrentRow(self, row: int):
        if not (0 <= row < len(self.tabs)):
            return
        changed = row != self._current_row
        self._current_row = row
        for i, btn in enumerate(self.tabs):
            btn.set_active(i == row)
        if changed:
            self.currentRowChanged.emit(row)

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        for btn in self.tabs:
            btn.set_theme_colors(theme_dict)


class SettingsInstanceCard(QFrame):
    """Spacious full-width instance card in Settings → Instances with 3D block icon and quick actions."""
    editRequested = pyqtSignal(dict)
    blockRequested = pyqtSignal(dict)
    folderRequested = pyqtSignal(dict)
    deleteRequested = pyqtSignal(dict)

    def __init__(self, inst_data: dict, is_active: bool, theme_dict: dict, parent=None):
        super().__init__(parent)
        self.inst_data = inst_data
        self.is_active = is_active
        self._theme = theme_dict
        self._selected = False
        self.setFixedHeight(68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        block_id = inst_data.get("icon", "grass")
        self.pedestal = _BlockPedestalWidget(block_id, box_size=46, icon_size=34, parent=self)
        self.pedestal.set_theme_colors(theme_dict)
        layout.addWidget(self.pedestal, alignment=Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self.lbl_name = QLabel(inst_data.get("name", "Unknown Instance"), self)
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.lbl_name.setToolTip(inst_data.get("name", ""))
        title_row.addWidget(self.lbl_name)

        self.active_badge = QLabel(I18n.t("active_badge"), self)
        title_row.addWidget(self.active_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.active_badge.setVisible(bool(is_active))
        title_row.addStretch(1)
        info_col.addLayout(title_row)

        loader = inst_data.get("loader", "Fabric")
        version = inst_data.get("version", "")
        block_name = get_minecraft_block_name(block_id)
        total_played = format_playtime(inst_data.get("playtime_seconds", 0))
        self.lbl_meta = QLabel(f"{loader} {version}  ·  {block_name}  ·  {I18n.t('playtime_prefix')} {total_played}", self)
        self.lbl_meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        info_col.addWidget(self.lbl_meta)

        layout.addLayout(info_col, stretch=1)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        self.btn_edit = SettingsIconButton("edit", "Edit Instance (Name / Version / Loader)", parent=self)
        self.btn_block = SettingsIconButton("cube", "Change Block Icon", block_id=block_id, parent=self)
        self.btn_folder = SettingsIconButton("folder", "Open Instance Folder", parent=self)
        self.btn_delete = SettingsIconButton("trash", "Delete Instance", danger=True, parent=self)

        self.btn_edit.clicked.connect(lambda: self.editRequested.emit(self.inst_data))
        self.btn_block.clicked.connect(lambda: self.blockRequested.emit(self.inst_data))
        self.btn_folder.clicked.connect(lambda: self.folderRequested.emit(self.inst_data))
        self.btn_delete.clicked.connect(lambda: self.deleteRequested.emit(self.inst_data))

        self._action_btns = [self.btn_edit, self.btn_block, self.btn_folder, self.btn_delete]
        for b in self._action_btns:
            actions_row.addWidget(b)
        layout.addLayout(actions_row)

        self._apply_styles()

    def set_active(self, is_active: bool):
        is_active = bool(is_active)
        if self.is_active != is_active:
            self.is_active = is_active
            self.active_badge.setVisible(is_active)
            self._apply_styles()

    def set_selected(self, selected: bool):
        selected = bool(selected)
        if self._selected != selected:
            self._selected = selected
            self._apply_styles()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.pedestal.set_theme_colors(theme_dict)
        for b in self._action_btns:
            b.set_theme_colors(theme_dict)
        self._apply_styles()

    def _apply_styles(self):
        t = self._theme
        if self._selected:
            bg = _lerp_color(t["card_bg"], t["accent"], 0.09).name()
            border = t["accent"]
        else:
            bg = t["card_bg"]
            border = t["border"]
        self.setStyleSheet(f"""
            SettingsInstanceCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        self.lbl_name.setStyleSheet(
            f"font-size: 14px; font-weight: 800; color: {t['text']}; background: transparent; border: none;"
        )
        self.lbl_meta.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {t['text_sub']}; background: transparent; border: none;"
        )
        self.active_badge.setStyleSheet(
            f"background-color: {_hex_rgba(t['accent'], 0.16)}; color: {t['accent']}; "
            "border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 800; letter-spacing: 0.7px; border: none;"
        )


class SettingsAccountCard(QFrame):
    """Spacious account row card in Settings → Accounts showing Minecraft skin avatar & quick actions."""
    activateRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)

    def __init__(self, acc_id: str, acc_data: dict, avatar_pix: QPixmap, is_active: bool, theme_dict: dict, parent=None):
        super().__init__(parent)
        self.acc_id = acc_id
        self.acc_data = acc_data
        self.is_active = is_active
        self._theme = theme_dict
        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        self.avatar_lbl = QLabel(self)
        self.avatar_lbl.setFixedSize(40, 40)
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if avatar_pix and not avatar_pix.isNull():
            self.avatar_lbl.setPixmap(
                avatar_pix.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(self.avatar_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        acc_name = acc_data.get("name") or "Player"
        self.lbl_name = QLabel(acc_name, self)
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.lbl_name.setToolTip(acc_name)
        top_row.addWidget(self.lbl_name)

        self.active_badge = QLabel(I18n.t("active_badge"), self)
        top_row.addWidget(self.active_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.active_badge.setVisible(bool(is_active))
        top_row.addStretch(1)
        info_col.addLayout(top_row)

        acc_type_str = I18n.t("acc_offline_profile") if acc_data.get("type") == "offline" else I18n.t("acc_ms_account")
        self.lbl_meta = QLabel(f"{acc_type_str}  ·  {I18n.t('ready')}", self)
        self.lbl_meta.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        info_col.addWidget(self.lbl_meta)

        layout.addLayout(info_col, stretch=1)

        self.btn_use = AnimatedButton(I18n.t("use_account"), parent=self)
        self.btn_use.setObjectName("PillButton")
        self.btn_use.setFixedHeight(32)
        self.btn_use.setStyleSheet("padding: 0 12px; font-size: 12px;")
        self.btn_use.clicked.connect(lambda: self.activateRequested.emit(self.acc_id))
        layout.addWidget(self.btn_use)
        self.btn_use.setVisible(not is_active)

        self.btn_delete = SettingsIconButton("trash", I18n.t("remove"), danger=True, parent=self)
        self.btn_delete.clicked.connect(lambda: self.deleteRequested.emit(self.acc_id))
        layout.addWidget(self.btn_delete)

        self._apply_styles()

    def set_active(self, is_active: bool):
        is_active = bool(is_active)
        if self.is_active != is_active:
            self.is_active = is_active
            self.active_badge.setVisible(is_active)
            self.btn_use.setVisible(not is_active)
            self._apply_styles()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.btn_delete.set_theme_colors(theme_dict)
        self._apply_styles()

    def _apply_styles(self):
        t = self._theme
        border = t["accent"] if self.is_active else t["border"]
        bg = _lerp_color(t["card_bg"], t["accent"], 0.06).name() if self.is_active else t["card_bg"]
        self.setStyleSheet(f"""
            SettingsAccountCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        self.avatar_lbl.setStyleSheet(
            f"background-color: {t['pill_bg']}; border: 1px solid {t['border']}; border-radius: 9px;"
        )
        self.lbl_name.setStyleSheet(
            f"font-size: 14px; font-weight: 800; color: {t['text']}; background: transparent; border: none;"
        )
        self.lbl_meta.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {t['text_sub']}; background: transparent; border: none;"
        )
        self.active_badge.setStyleSheet(
            f"background-color: {_hex_rgba(t['accent'], 0.16)}; color: {t['accent']}; "
            "border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 800; letter-spacing: 0.7px; border: none;"
        )


class LanguageOptionCard(QPushButton):
    """Selectable full-width language card in Settings → Language."""

    def __init__(self, code: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.lang_code = code
        self.title = title
        self.subtitle = subtitle
        self._selected = False
        self._hover = 0.0
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(140)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_selected(self, selected: bool):
        selected = bool(selected)
        if self._selected != selected:
            self._selected = selected
            self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._selected:
            bg = _lerp_color(t["card_bg"], t["accent"], 0.10)
            border = QColor(t["accent"])
        else:
            bg = _lerp_color(t["card_bg"], t["pill_hover"], self._hover * 0.7)
            border = _lerp_color(t["border"], t["text_sub"], self._hover * 0.45)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border, 1.3 if self._selected else 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 11.0, 11.0)

        badge_rect = QRectF(14, 12, 36, 36)
        badge_bg = _lerp_color(t["pill_bg"], t["accent"], 0.18 if self._selected else 0.0)
        p.setPen(QPen(QColor(t["accent"] if self._selected else t["border"]), 1.0))
        p.setBrush(badge_bg)
        p.drawRoundedRect(badge_rect, 9.0, 9.0)

        f = self.font()
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor(t["accent"] if self._selected else t["text_sub"]))
        p.drawText(badge_rect, int(Qt.AlignmentFlag.AlignCenter), self.lang_code.upper())

        f_title = QFont(self.font())
        f_title.setPixelSize(14)
        f_title.setWeight(QFont.Weight.Bold)
        p.setFont(f_title)
        p.setPen(QColor(t["text"]))
        p.drawText(QRectF(62, 11, self.width() - 110, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.title)

        f_sub = QFont(self.font())
        f_sub.setPixelSize(11)
        f_sub.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_sub)
        p.setPen(QColor(t["text_sub"]))
        p.drawText(QRectF(62, 31, self.width() - 110, 18), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.subtitle)

        if self._selected:
            ic = _make_menu_icon("check", t["accent"], 16)
            pix = ic.pixmap(16, 16)
            p.drawPixmap(self.width() - 34, (self.height() - 16) // 2, pix)
        p.end()


class ProxyModeButton(QPushButton):
    """Segmented mode pill for Proxy Settings (None / HTTP / SOCKS5)."""

    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self._selected = False
        self._hover = 0.0
        self._theme = ThemeManager.get_theme_data("Dark Mode")
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        f = self.font()
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.Bold)
        self.setFont(f)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(130)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_selected(self, selected: bool):
        selected = bool(selected)
        if self._selected != selected:
            self._selected = selected
            self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._selected:
            bg = _lerp_color(t["pill_bg"], t["accent"], 0.18)
            border = QColor(t["accent"])
            text_col = QColor(t["text"])
        else:
            bg = _lerp_color(t["pill_bg"], t["pill_hover"], self._hover)
            border = _lerp_color(t["border"], t["text_sub"], self._hover * 0.45)
            text_col = _lerp_color(t["text_sub"], t["text"], self._hover)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border, 1.3 if self._selected else 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 9.0, 9.0)
        p.setFont(self.font())
        p.setPen(text_col)
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self.text())
        p.end()


class InstanceBlockBadge(QPushButton):
    """Clickable 3D Minecraft block icon badge displayed in Create/Edit instance dialogs."""

    def __init__(self, block_id: str = "grass", box_size: int = 44, icon_size: int = 34, parent=None):
        super().__init__(parent)
        self.block_id = (block_id or "grass").strip().lower()
        self._box_size = box_size
        self._icon_size = icon_size
        self._hover = 0.0
        self._theme = ThemeManager.get_theme_data("Dark Mode")

        self.setFixedSize(box_size, box_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{get_minecraft_block_name(self.block_id)} — Click to change block")

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_block(self, block_id: str):
        self.block_id = (block_id or "grass").strip().lower()
        self.setToolTip(f"{get_minecraft_block_name(self.block_id)} — Click to change block")
        self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        bg = _lerp_color(t["pill_bg"], t["accent"], self._hover * 0.12)
        border = _lerp_color(t["border"], t["accent"], self._hover * 0.85)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border, 1.2 if self._hover > 0.2 else 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 11.0, 11.0)

        pix = get_minecraft_block_pixmap(self.block_id, self._icon_size)
        ix = int((self.width() - pix.width()) / 2)
        iy = int((self.height() - pix.height()) / 2)
        p.drawPixmap(ix, iy, pix)
        p.end()


class _BlockPedestalWidget(QWidget):
    """Non-clickable rounded frame displaying the active instance's 3D Minecraft block icon."""

    def __init__(self, block_id: str = "grass", box_size: int = 56, icon_size: int = 44, parent=None):
        super().__init__(parent)
        self.block_id = (block_id or "grass").strip().lower()
        self._icon_size = icon_size
        self._theme = ThemeManager.get_theme_data("Dark Mode")
        self.setFixedSize(box_size, box_size)
        self.setToolTip(get_minecraft_block_name(self.block_id))

    def set_block(self, block_id: str):
        self.block_id = (block_id or "grass").strip().lower()
        self.setToolTip(get_minecraft_block_name(self.block_id))
        self.update()

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.update()

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        bg = _lerp_color(t["pill_bg"], t["accent"], 0.08)
        border = _lerp_color(t["border"], t["accent"], 0.25)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 11.0, 11.0)

        pix = get_minecraft_block_pixmap(self.block_id, self._icon_size)
        ix = int((self.width() - pix.width()) / 2)
        iy = int((self.height() - pix.height()) / 2)
        p.drawPixmap(ix, iy, pix)
        p.end()


class InstanceShowcaseCard(QFrame):
    """Active instance spotlight card below Play controls showing the 3D Minecraft block without extra buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedHeight(80)
        self._theme = ThemeManager.get_theme_data("Dark Mode")
        self._last_inst_meta = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 18, 12)
        layout.setSpacing(14)

        self.block_pedestal = _BlockPedestalWidget("grass", box_size=56, icon_size=44, parent=self)
        layout.addWidget(self.block_pedestal, alignment=Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_eyebrow = QLabel(I18n.t("showcase_active_instance"))
        self.lbl_eyebrow.setObjectName("SectionLabel")
        info_col.addWidget(self.lbl_eyebrow)

        self.lbl_name = QLabel(I18n.t("showcase_no_instance"))
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.lbl_name.setStyleSheet("font-size: 15px; font-weight: 800; background: transparent; border: none;")
        info_col.addWidget(self.lbl_name)

        self.lbl_sub = QLabel(I18n.t("showcase_get_started"))
        self.lbl_sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.lbl_sub.setObjectName("MutedLabel")
        info_col.addWidget(self.lbl_sub)

        layout.addLayout(info_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        right_col.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        self.lbl_block_caption = QLabel(I18n.t("showcase_block_icon"))
        self.lbl_block_caption.setObjectName("SectionLabel")
        self.lbl_block_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self.lbl_block_caption)

        self.lbl_block_name = QLabel("Grass")
        self.lbl_block_name.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_block_name.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent; border: none;")
        right_col.addWidget(self.lbl_block_name)

        layout.addLayout(right_col)

    def retranslate_ui(self):
        self.lbl_eyebrow.setText(I18n.t("showcase_active_instance"))
        self.lbl_block_caption.setText(I18n.t("showcase_block_icon"))
        self.set_instance(self._last_inst_meta)

    def set_theme_colors(self, theme_dict: dict):
        self._theme = theme_dict
        self.block_pedestal.set_theme_colors(theme_dict)
        self.lbl_name.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {theme_dict['text']}; background: transparent; border: none;"
        )
        self.lbl_block_name.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme_dict['text']}; background: transparent; border: none;"
        )

    def set_instance(self, inst_meta: dict | None):
        self._last_inst_meta = inst_meta
        if not inst_meta or not isinstance(inst_meta, dict):
            self.block_pedestal.set_block("grass")
            self.lbl_name.setText(I18n.t("showcase_no_instance"))
            self.lbl_sub.setText(I18n.t("showcase_get_started"))
            self.lbl_block_name.setText("Grass")
            return

        block_id = inst_meta.get("icon", "grass")
        block_label = get_minecraft_block_name(block_id)
        name = inst_meta.get("name", "Unknown Instance")
        loader = inst_meta.get("loader", "Fabric")
        version = inst_meta.get("version", "")

        self.block_pedestal.set_block(block_id)
        self.lbl_name.setText(name)
        self.lbl_sub.setText(f"{loader} {version}  ·  {I18n.t('isolated_instance')}")
        self.lbl_block_name.setText(block_label)


class BlockTileButton(QPushButton):
    """Selectable Minecraft block tile inside BlockPickerDialog."""
    doubleClicked = pyqtSignal(str)

    def __init__(self, block_id: str, title: str, theme_dict: dict, parent=None):
        super().__init__(parent)
        self.block_id = block_id
        self.title = title
        self._theme = theme_dict
        self._selected = False
        self._hover = 0.0

        self.setFixedSize(112, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(title)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(130)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def set_selected(self, selected: bool):
        selected = bool(selected)
        if self._selected != selected:
            self._selected = selected
            self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.block_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._selected:
            bg = _lerp_color(t["pill_bg"], t["accent"], 0.18)
            border = QColor(t["accent"])
            bw = 1.8
        else:
            bg = _lerp_color(t["pill_bg"], t["pill_hover"], self._hover)
            border = _lerp_color(t["border"], t["text_sub"], self._hover * 0.5)
            bw = 1.0

        rect = QRectF(self.rect()).adjusted(0.8, 0.8, -0.8, -0.8)
        p.setPen(QPen(border, bw))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 10.0, 10.0)

        pix = get_minecraft_block_pixmap(self.block_id, 42)
        ix = int((self.width() - pix.width()) / 2)
        p.drawPixmap(ix, 10, pix)

        f = self.font()
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.Bold if self._selected else QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor(t["text"]) if self._selected else _lerp_color(t["text_sub"], t["text"], self._hover))
        short_title = self.title.replace("Block of ", "").replace(" Block", "")
        elided = QFontMetrics(f).elidedText(short_title, Qt.TextElideMode.ElideRight, self.width() - 10)
        p.drawText(
            QRectF(5, 56, self.width() - 10, 22),
            int(Qt.AlignmentFlag.AlignCenter),
            elided,
        )
        p.end()


class BlockPickerDialog(FramelessDialog):
    """Themed frameless dialog allowing users to choose a Minecraft block icon for an instance."""

    def __init__(self, current_block: str = "grass", theme_name: str = "Dark Mode", parent=None):
        super().__init__(theme_name=theme_name, title="Choose Instance Block", parent=parent)
        self.selected_block = (current_block or "grass").strip().lower()
        if self.selected_block not in _MINECRAFT_BLOCK_MAP:
            self.selected_block = "grass"

        self.set_dialog_fixed_size(530, 496)
        t = ThemeManager.get_theme_data(theme_name)

        layout = self.body_layout
        layout.setContentsMargins(22, 16, 22, 20)
        layout.setSpacing(12)

        sub = QLabel("Pick a Minecraft block to represent this instance across the client:")
        sub.setObjectName("MutedLabel")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self._tiles = {}
        for idx, (bid, bname) in enumerate(MINECRAFT_BLOCKS):
            tile = BlockTileButton(bid, bname, t, self)
            tile.set_selected(bid == self.selected_block)
            tile.clicked.connect(lambda _, k=bid: self._select(k))
            tile.doubleClicked.connect(lambda k: (self._select(k), self.accept()))
            grid.addWidget(tile, idx // 4, idx % 4)
            self._tiles[bid] = tile
        layout.addLayout(grid)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_cancel = AnimatedButton("Cancel")
        self.btn_cancel.setObjectName("PillButton")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_apply = AnimatedButton("Use Selected Block")
        self.btn_apply.setObjectName("PlayButton")
        self.btn_apply.setFixedHeight(40)
        self.btn_apply.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

    def _select(self, block_id: str):
        self.selected_block = block_id
        for bid, tile in self._tiles.items():
            tile.set_selected(bid == block_id)

    def get_selected_block(self) -> str:
        return self.selected_block


# loader -> (colour on dark themes, colour on light themes)
_LOADER_COLORS = {
    "fabric": ("#DBB69B", "#9A6B42"),
    "quilt": ("#C69BDB", "#8442A8"),
    "forge": ("#7FA8E0", "#2F5FA3"),
    "neoforge": ("#F29A4B", "#B3601A"),
    "vanilla": ("#8FD18B", "#2E7D32"),
    "horizon": ("#FF9A5C", "#C25A12"),
}


class ToggleSwitch(QWidget):
    """Animated on/off switch (the knob slides and the track fades to the accent colour)."""
    toggled = pyqtSignal(bool)

    def __init__(self, t: dict, checked: bool = True, parent=None):
        super().__init__(parent)
        self.t = t
        self._on = checked
        self._pos = 1.0 if checked else 0.0
        self.setFixedSize(50, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float):
        self._pos = v
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def isChecked(self) -> bool:
        return self._on

    def setChecked(self, value: bool, animate: bool = True):
        if value == self._on:
            return
        self._on = value
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if value else 0.0)
            self._anim.start()
        else:
            self._set_knob(1.0 if value else 0.0)
        self.toggled.emit(value)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.rect().contains(event.position().toPoint()):
            self.setChecked(not self._on)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._on)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            p.setOpacity(0.5)
        track = _lerp_color(self.t["pill_hover"], self.t["accent"], self._pos)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(2, 2, 46, 26), 13, 13)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(self.t["text_sub"]), 1.5))
            p.drawRoundedRect(QRectF(0.75, 0.75, 48.5, 28.5), 14.25, 14.25)
            p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(5 + self._pos * 20, 5, 20, 20))
        p.end()


class _TickCircle(QWidget):
    """Round selector that fills with the accent colour and draws a check mark."""

    def __init__(self, t: dict, ok: bool, parent=None):
        super().__init__(parent)
        self.t = t
        self.ok = ok
        self.selv = 0.0      # 0..1 selection progress
        self.scale = 1.0     # pop animation
        self.hover = 0.0
        self.setFixedSize(30, 30)

    def paintEvent(self, event):
        t = self.t
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = 11.0 * self.scale
        cx = cy = 15.0
        accent = QColor(t["accent"])
        if self.ok:
            border = _lerp_color(_lerp_color(t["text_sub"], t["text"], self.hover * 0.6), accent, self.selv)
            pen = QPen(border, 2)
        else:
            pen = QPen(QColor(t["border"]), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        fill = QColor(accent)
        fill.setAlpha(int(255 * max(0.0, min(1.0, self.selv))))
        p.setBrush(fill)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        if self.selv > 0.02:
            col = QColor(t["accent_text"])
            col.setAlpha(int(255 * max(0.0, min(1.0, self.selv))))
            cp = QPen(col, 2.6)
            cp.setCapStyle(Qt.PenCapStyle.RoundCap)
            cp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(cp)
            p.setBrush(Qt.BrushStyle.NoBrush)
            s = self.scale
            p.drawLine(int(cx - 4.5 * s), int(cy + 0.5 * s), int(cx - 1.5 * s), int(cy + 3.5 * s))
            p.drawLine(int(cx - 1.5 * s), int(cy + 3.5 * s), int(cx + 4.5 * s), int(cy - 3.0 * s))
        p.end()


class ImportCard(QFrame):
    """One clickable row. Hover, selection and the check mark all animate."""
    toggled = pyqtSignal()

    def __init__(self, entry: dict, t: dict, parent=None):
        super().__init__(parent)
        from core import importer as inst_importer
        self.entry = entry
        self.t = t
        mc = entry.get("mc_version")
        self.importable = bool(mc) and inst_importer.looks_like_mc_version(mc)
        self._checked = False
        self._hover = 0.0
        self._selv = 0.0

        self.setObjectName("ImportCard")
        if self.importable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 13, 18, 13)
        lay.setSpacing(14)

        self.tick = _TickCircle(t, self.importable)
        lay.addWidget(self.tick, alignment=Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        col.setSpacing(7)

        name = QLabel(entry.get("name", "Instance"))
        name.setObjectName("ImportName")
        name.setToolTip(entry.get("game_dir", ""))
        col.addWidget(name)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.setContentsMargins(0, 0, 0, 0)

        loader = entry.get("loader") or "Vanilla"
        loader_key = loader.lower().replace("-", "")
        dark_c, light_c = _LOADER_COLORS.get(loader_key, ("#9EA4B0", "#636975"))
        loader_c = light_c if t.get("is_light") else dark_c

        if self.importable:
            chips.addWidget(self._chip(f"Minecraft {mc}", t["text_sub"]))
        else:
            chips.addWidget(self._chip("Version unknown", "#E5534B"))
        chips.addWidget(self._chip(loader, loader_c))
        if entry.get("loader_version"):
            chips.addWidget(self._chip(str(entry["loader_version"]), t["text_sub"]))
        if entry.get("guessed"):
            chips.addWidget(self._chip("Guessed from mods", "#E0A93B"))
        chips.addStretch(1)
        col.addLayout(chips)

        if not self.importable:
            warn = QLabel("Can't import: the Minecraft version couldn't be detected.")
            warn.setObjectName("ImportWarn")
            col.addWidget(warn)
        lay.addLayout(col, stretch=1)

        from core import importer as inst_importer
        size_txt = inst_importer.format_size(entry["size"]) if entry.get("size") else ""
        self.size_lbl = QLabel(size_txt)
        self.size_lbl.setObjectName("ImportSize")
        lay.addWidget(self.size_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        if entry.get("note"):
            self.setToolTip(entry["note"])

        self.search_text = " ".join([
            entry.get("name", ""), entry.get("source", ""), str(mc or ""), loader
        ]).lower()

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_value)

        self._sel_anim = QVariantAnimation(self)
        self._sel_anim.setDuration(240)
        self._sel_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sel_anim.valueChanged.connect(self._on_sel_value)

        self._pop_anim = QVariantAnimation(self)
        self._pop_anim.setDuration(320)
        self._pop_anim.setStartValue(0.55)
        self._pop_anim.setEndValue(1.0)
        self._pop_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._pop_anim.valueChanged.connect(self._on_pop_value)

    @staticmethod
    def _chip(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background: {_hex_rgba(color, 0.16)}; color: {color}; border-radius: 9px;"
            "padding: 2px 10px; font-size: 11px; font-weight: 700;"
        )
        return lbl

    # ---- animation plumbing
    def _on_hover_value(self, v):
        self._hover = float(v)
        self.tick.hover = self._hover
        self.tick.update()
        self.update()

    def _on_sel_value(self, v):
        self._selv = float(v)
        self.tick.selv = self._selv
        self.tick.update()
        self.update()

    def _on_pop_value(self, v):
        self.tick.scale = float(v)
        self.tick.update()

    @staticmethod
    def _animate(anim: QVariantAnimation, start: float, end: float):
        anim.stop()
        anim.setStartValue(float(start))
        anim.setEndValue(float(end))
        anim.start()

    def enterEvent(self, event):
        if self.importable and self.isEnabled():
            self._animate(self._hover_anim, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate(self._hover_anim, self._hover, 0.0)
        super().leaveEvent(event)

    # ---- state
    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool, animate: bool = True):
        if not self.importable:
            value = False
        if value == self._checked:
            return
        self._checked = value
        if animate:
            self._sel_anim.stop()
            self._sel_anim.setStartValue(self._selv)
            self._sel_anim.setEndValue(1.0 if value else 0.0)
            self._sel_anim.start()
            if value:
                self._pop_anim.stop()
                self._pop_anim.start()
            else:
                self.tick.scale = 1.0
        else:
            self._on_sel_value(1.0 if value else 0.0)

    def mousePressEvent(self, event):
        if self.importable and self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)
            self.toggled.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        t = self.t
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            p.setOpacity(0.6)
        base = t["card_bg"] if self.importable else t["input_bg"]
        sel_bg = _lerp_color(t["card_bg"], t["accent"], 0.13)
        bg = _lerp_color(_lerp_color(base, t["item_hover"], self._hover), sel_bg, self._selv)
        border = _lerp_color(_lerp_color(t["border"], t["text_sub"], self._hover * 0.7), t["accent"], self._selv)
        p.setPen(QPen(border, 1.2))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.6, 0.6, self.width() - 1.2, self.height() - 1.2), 12, 12)
        p.end()


class ImportInstancesDialog(FramelessDialog):
    """Finds instances from other launchers (Minecraft Launcher, SKLauncher, Prism, CurseForge,
    Modrinth App, ATLauncher, GDLauncher...) and copies them into LowCore. Originals are never touched."""

    def __init__(self, inst_mgr, theme_name: str = "Dark Mode", parent=None):
        super().__init__(theme_name=theme_name, title="Import Instances", parent=parent, use_main_bg=True)
        self.inst_mgr = inst_mgr
        self.entries = []
        self.cards = []
        self.groups = []          # (header_widget, [cards])
        self.imported_folders = []
        self._errors = []
        self._busy = False
        self._anims = {}
        self._intro_anims = []
        self.t = ThemeManager.get_theme_data(theme_name)
        t = self.t

        self.set_dialog_size(780, 680, min_w=700, min_h=560)

        self._apply_dialog_theme(theme_name, extra_qss=f"""
            QLabel#ImportTitle {{ font-size: 22px; font-weight: 800; color: {t['text']}; background: transparent; }}
            QLabel#ImportSubtitle {{ font-size: 13px; color: {t['text_sub']}; background: transparent; }}
            QScrollArea#ImportScroll {{ background: transparent; border: none; }}
            QWidget#ImportContent {{ background: transparent; }}
            QFrame#ImportCard {{ background: transparent; border: none; }}
            QFrame#ImportCard QLabel {{ background: transparent; }}
            QLabel#ImportName {{ font-size: 15px; font-weight: 700; color: {t['text']}; }}
            QLabel#ImportSize {{ font-size: 12px; font-weight: 600; color: {t['text_sub']}; }}
            QLabel#ImportWarn {{ font-size: 11px; color: #E5534B; }}
            QLabel#GroupName {{
                font-size: 12px; font-weight: 800; letter-spacing: 1px;
                color: {t['text_sub']}; background: transparent;
            }}
            QLabel#GroupCount {{
                background-color: {t['pill_bg']}; color: {t['text_sub']};
                border-radius: 9px; padding: 1px 9px; font-size: 11px; font-weight: 700;
            }}
            QPushButton#LinkBtn {{
                background: transparent; border: none; color: {t['accent']};
                font-size: 12px; font-weight: 700; padding: 4px 6px;
            }}
            QPushButton#LinkBtn:hover {{ color: {t['accent_hover']}; text-decoration: underline; }}
            QPushButton#LinkBtn:disabled {{ color: {t['text_sub']}; }}
            QLabel#ImportSummary {{ font-size: 13px; font-weight: 700; color: {t['text']}; background: transparent; }}
            QLabel#ImportStatus {{ font-size: 12px; color: {t['text_sub']}; background: transparent; }}
            QLabel#ImportEmpty {{
                font-size: 14px; color: {t['text_sub']}; background: transparent; padding: 40px 20px;
            }}
            QLabel#OptTitle {{ font-size: 13px; font-weight: 700; color: {t['text']}; background: transparent; }}
            QLabel#OptSub {{ font-size: 11px; color: {t['text_sub']}; background: transparent; }}
            QFrame#OptionsBar {{
                background-color: {t['card_bg']}; border: 1px solid {t['border']}; border-radius: 12px;
            }}
            QFrame#OptionsBar QLabel {{ background: transparent; }}
        """)

        root = self.body_layout
        root.setContentsMargins(24, 16, 24, 20)
        root.setSpacing(12)

        # ---- header
        title = QLabel("Import Instances")
        title.setObjectName("ImportTitle")
        root.addWidget(title)
        sub = QLabel("Bring your worlds, mods and settings over from another launcher. "
                     "Your originals are copied, never changed or deleted.")
        sub.setObjectName("ImportSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ---- toolbar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search instances...")
        self.search.setFixedHeight(38)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        bar.addWidget(self.search, stretch=1)

        self.btn_rescan = AnimatedButton("Rescan")
        self.btn_rescan.setObjectName("PillButton")
        self.btn_rescan.setFixedHeight(38)
        self.btn_rescan.setMinimumWidth(90)
        self.btn_rescan.clicked.connect(lambda: self.start_scan())
        bar.addWidget(self.btn_rescan)

        self.btn_browse = AnimatedButton("Browse Folder...")
        self.btn_browse.setObjectName("PillButton")
        self.btn_browse.setFixedHeight(38)
        self.btn_browse.setMinimumWidth(140)
        self.btn_browse.setToolTip("Pick a launcher folder, an instances folder, or a single instance folder")
        self.btn_browse.clicked.connect(self.browse_folder)
        bar.addWidget(self.btn_browse)
        root.addLayout(bar)

        # ---- scan indicator
        self.scan_bar = QProgressBar()
        self.scan_bar.setRange(0, 0)
        self.scan_bar.setTextVisible(False)
        self.scan_bar.setFixedHeight(4)
        self.scan_bar.setGraphicsEffect(QGraphicsOpacityEffect(self.scan_bar))
        root.addWidget(self.scan_bar)

        # ---- results
        self.scroll = QScrollArea()
        self.scroll.setObjectName("ImportScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("ImportContent")
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 0, 6, 0)
        self.content_lay.setSpacing(8)
        self.content_lay.addStretch(1)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, stretch=1)

        # ---- options bar (animated switch)
        opts_frame = QFrame()
        opts_frame.setObjectName("OptionsBar")
        opts = QHBoxLayout(opts_frame)
        opts.setContentsMargins(16, 10, 12, 10)
        opts.setSpacing(12)

        self.worlds_toggle = ToggleSwitch(t, True)
        self.worlds_check = self.worlds_toggle   # same isChecked()/setEnabled() API as before
        opts.addWidget(self.worlds_toggle, alignment=Qt.AlignmentFlag.AlignVCenter)

        txt = QVBoxLayout()
        txt.setSpacing(1)
        self.opt_title = QLabel("Include worlds (saves)")
        self.opt_title.setObjectName("OptTitle")
        self.opt_title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.opt_title.mousePressEvent = lambda e: self.worlds_toggle.setChecked(not self.worlds_toggle.isChecked()) if self.worlds_toggle.isEnabled() else None
        self.opt_sub = QLabel("Copies your saves folder too. Turn off for a faster import.")
        self.opt_sub.setObjectName("OptSub")
        txt.addWidget(self.opt_title)
        txt.addWidget(self.opt_sub)
        opts.addLayout(txt, stretch=1)

        self.link_all = QPushButton("Select all")
        self.link_all.setObjectName("LinkBtn")
        self.link_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_all.clicked.connect(lambda: self._set_all(True))
        opts.addWidget(self.link_all)
        self.link_none = QPushButton("Clear")
        self.link_none.setObjectName("LinkBtn")
        self.link_none.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_none.clicked.connect(lambda: self._set_all(False))
        opts.addWidget(self.link_none)
        root.addWidget(opts_frame)

        # ---- copy progress + status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setGraphicsEffect(QGraphicsOpacityEffect(self.progress))
        self.progress.hide()
        root.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("ImportStatus")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setGraphicsEffect(QGraphicsOpacityEffect(self.status_lbl))
        root.addWidget(self.status_lbl)

        # ---- footer
        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.summary = QLabel("Nothing selected")
        self.summary.setObjectName("ImportSummary")
        self.summary.setGraphicsEffect(QGraphicsOpacityEffect(self.summary))
        foot.addWidget(self.summary)
        foot.addStretch(1)
        self.btn_close = AnimatedButton("Close")
        self.btn_close.setObjectName("PillButton")
        self.btn_close.setFixedHeight(42)
        self.btn_close.setMinimumWidth(100)
        self.btn_close.clicked.connect(self.reject)
        foot.addWidget(self.btn_close)
        self.btn_import = AnimatedButton("Import")
        self.btn_import.setObjectName("PlayButton")
        self.btn_import.setFixedHeight(42)
        self.btn_import.setMinimumWidth(170)
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.start_import)
        foot.addWidget(self.btn_import)
        root.addLayout(foot)

        QTimer.singleShot(0, self.start_scan)

    # ---------------------------------------------------------------- animation helpers

    def _run(self, key, anim: QPropertyAnimation):
        old = self._anims.get(key)
        if old is not None:
            try:
                old.stop()
            except RuntimeError:
                pass
        self._anims[key] = anim
        anim.start()

    def _fade(self, widget: QWidget, start: float, end: float, ms: int = 220, hide_at_end: bool = False):
        eff = widget.graphicsEffect()
        if eff is None:
            eff = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff)
        if end > 0:
            widget.show()
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(ms)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if hide_at_end:
            anim.finished.connect(widget.hide)
        self._run(("fade", id(widget)), anim)

    def _fade_text(self, label: QLabel, text: str):
        if label.text() == text:
            return
        label.setText(text)
        self._fade(label, 0.15, 1.0, 240)

    def _play_intro(self):
        """Staggered fade-in of group headers and cards."""
        widgets = []
        for header, cards in self.groups:
            widgets.append(header)
            widgets.extend(cards)
        self._intro_anims = []
        for i, w in enumerate(widgets[:24]):
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", w)
            anim.setDuration(320)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def finish(widget=w):
                try:
                    widget.setGraphicsEffect(None)
                except RuntimeError:
                    pass
            anim.finished.connect(finish)
            self._intro_anims.append(anim)

            def start(a=anim):
                try:
                    a.start()
                except RuntimeError:
                    pass
            QTimer.singleShot(70 * i, start)

    # ---------------------------------------------------------------- helpers

    def _clear_results(self):
        while self.content_lay.count():
            item = self.content_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.cards = []
        self.groups = []

    def _set_busy(self, busy: bool):
        self._busy = busy
        for w in (self.btn_rescan, self.btn_browse, self.worlds_toggle, self.search,
                  self.link_all, self.link_none, self.btn_close):
            w.setEnabled(not busy)
        for c in self.cards:
            c.setEnabled(not busy)
        self._refresh_summary()

    # ---------------------------------------------------------------- scanning

    def start_scan(self, folder: str = None):
        if self._busy:
            return
        self._clear_results()
        self.content_lay.addStretch(1)
        self._fade_text(self.status_lbl, "Scanning for other launchers..." if not folder else f"Scanning {folder} ...")
        self._fade(self.scan_bar, 0.0, 1.0, 200)
        self._set_busy(True)
        worker = ImportScanWorker(folder)
        worker.signals.scanned.connect(self._on_scanned)
        worker.signals.error.connect(self._on_scan_error)
        QThreadPool.globalInstance().start(worker)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select a launcher or instance folder")
        if folder:
            self.start_scan(folder)

    def _on_scan_error(self, err: str):
        self._fade(self.scan_bar, 1.0, 0.0, 200, hide_at_end=True)
        self._set_busy(False)
        self._fade_text(self.status_lbl, f"Scan failed: {err}")

    def _on_scanned(self, entries: list):
        self._fade(self.scan_bar, 1.0, 0.0, 200, hide_at_end=True)
        self.entries = entries
        self._clear_results()

        if not entries:
            empty = QLabel("No instances found automatically.\n\n"
                           "Use \"Browse Folder...\" and pick the other launcher's folder.")
            empty.setObjectName("ImportEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self.content_lay.addStretch(1)
            self.content_lay.addWidget(empty)
            self.content_lay.addStretch(2)
            self._fade(empty, 0.0, 1.0, 400)
            self._fade_text(self.status_lbl, "")
            self._set_busy(False)
            return

        by_source = {}
        for e in entries:
            by_source.setdefault(e.get("source", "Other"), []).append(e)

        for source, items in by_source.items():
            header = QWidget()
            hl = QHBoxLayout(header)
            hl.setContentsMargins(2, 8, 0, 0)
            hl.setSpacing(8)
            gname = QLabel(source.upper())
            gname.setObjectName("GroupName")
            gcount = QLabel(str(len(items)))
            gcount.setObjectName("GroupCount")
            hl.addWidget(gname)
            hl.addWidget(gcount)
            hl.addStretch(1)
            group_cards = []
            gsel = QPushButton("Select group")
            gsel.setObjectName("LinkBtn")
            gsel.setCursor(Qt.CursorShape.PointingHandCursor)
            hl.addWidget(gsel)
            self.content_lay.addWidget(header)

            for e in items:
                card = ImportCard(e, self.t)
                card.toggled.connect(self._refresh_summary)
                self.content_lay.addWidget(card)
                group_cards.append(card)
                self.cards.append(card)
            gsel.clicked.connect(lambda _=False, cs=group_cards: self._select_cards(cs))
            self.groups.append((header, group_cards))

        self.content_lay.addStretch(1)
        self._fade_text(self.status_lbl, f"Found {len(entries)} instance(s). Click the ones you want to import.")
        self._apply_filter(self.search.text())
        self._set_busy(False)
        self._play_intro()

    # ---------------------------------------------------------------- selection

    def _checked_entries(self) -> list:
        return [c.entry for c in self.cards if c.is_checked()]

    def _select_cards(self, cards: list):
        for c in cards:
            if (not c.isHidden()) and c.importable:
                c.set_checked(True)
        self._refresh_summary()

    def _set_all(self, checked: bool):
        for c in self.cards:
            if checked and c.isHidden():
                continue
            c.set_checked(checked)
        self._refresh_summary()

    def _apply_filter(self, text: str = ""):
        q = (text or "").strip().lower()
        for header, cards in self.groups:
            any_visible = False
            for c in cards:
                show = (not q) or q in c.search_text
                c.setVisible(show)
                any_visible = any_visible or show
            header.setVisible(any_visible)

    def _refresh_summary(self, *_):
        chosen = self._checked_entries()
        n = len(chosen)
        if n:
            from core import importer as inst_importer
            total = sum(int(e.get("size") or 0) for e in chosen)
            size_txt = f" · {inst_importer.format_size(total)}" if total else ""
            self._fade_text(self.summary, f"{n} selected{size_txt}")
            self.btn_import.setText(f"Import {n} instance{'s' if n != 1 else ''}")
        else:
            self._fade_text(self.summary, "Nothing selected")
            self.btn_import.setText("Import")
        self.btn_import.setEnabled(n > 0 and not self._busy)

    # ---------------------------------------------------------------- importing

    def start_import(self):
        chosen = self._checked_entries()
        if not chosen or self._busy:
            return
        self._set_busy(True)
        self.btn_import.setEnabled(False)
        self.progress.setValue(0)
        self._fade(self.progress, 0.0, 1.0, 220)
        self._errors = []
        self._fade_text(self.status_lbl, f"Importing {len(chosen)} instance(s)...")

        worker = ImportCopyWorker(chosen, self.inst_mgr, self.worlds_toggle.isChecked())
        worker.signals.progress.connect(self._on_progress)
        worker.signals.item_done.connect(self._on_item_done)
        worker.signals.finished.connect(self._on_finished)
        QThreadPool.globalInstance().start(worker)

    def _on_progress(self, done: int, total: int, name: str):
        target = int(done * 100 / total) if total else 0
        anim = QPropertyAnimation(self.progress, b"value", self)
        anim.setDuration(180)
        anim.setStartValue(self.progress.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._run("progress", anim)
        from core import importer as inst_importer
        self.status_lbl.setText(
            f"Copying '{name}'...  {inst_importer.format_size(done)} / {inst_importer.format_size(total)}")

    def _on_item_done(self, name: str, problem: str):
        if problem:
            self._errors.append(f"{name}: {problem}")

    def _on_finished(self, folders: list):
        self.imported_folders = folders
        self.progress.setValue(100)
        self._fade(self.progress, 1.0, 0.0, 300, hide_at_end=True)
        self._set_busy(False)
        if folders and not self._errors:
            self._fade_text(self.status_lbl, f"Imported {len(folders)} instance(s).")
            QTimer.singleShot(350, self.accept)
            return
        if folders:
            self._fade_text(self.status_lbl, f"Imported {len(folders)} instance(s), with problems:\n"
                            + "\n".join(self._errors[:6]))
        else:
            self._fade_text(self.status_lbl, "Nothing was imported:\n" + "\n".join(self._errors[:6]))

    def reject(self):
        if self._busy:
            return
        super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
            return
        super().closeEvent(event)


def load_leclerc_images(assets_dir: str, max_px: int = 328) -> list:
    """Loads assets/leclerc1.png, leclerc2.png, ... scaled on decode to keep RAM minimal."""
    try:
        names = os.listdir(assets_dir)
    except OSError:
        return []
    pat = re.compile(r"^leclerc[\s_\-]*\d*\.(png|jpe?g|webp)$", re.I)

    def sort_key(n):
        m = re.search(r"(\d+)", n)
        return (int(m.group(1)) if m else 0, n.lower())

    out = []
    for n in sorted((n for n in names if pat.match(n)), key=sort_key)[:12]:
        full_path = os.path.join(assets_dir, n)
        reader = QImageReader(full_path)
        sz = reader.size()
        if sz.isValid() and (sz.width() > max_px or sz.height() > max_px):
            if sz.width() <= sz.height():
                target_w = max_px
                target_h = max(1, int(sz.height() * (max_px / sz.width())))
            else:
                target_h = max_px
                target_w = max(1, int(sz.width() * (max_px / sz.height())))
            reader.setScaledSize(QSize(target_w, target_h))
        img = reader.read()
        if not img.isNull():
            pix = QPixmap.fromImage(img)
            if not pix.isNull():
                out.append(pix)
    return out


class LeclercBadge(QWidget):
    """Round 'driver card': Leclerc photos crossfade every few seconds inside an accent ring with a #16 tag.
    Click to skip to the next photo. Falls back to a big 16 if no images are in assets/."""

    def __init__(self, images: list, size: int = 58, accent: str = "#E10600", parent=None):
        super().__init__(parent)
        self._size = size
        self._accent = accent
        self._raw = images or []
        self._pix = []
        self._cur = 0
        self._prev = -1
        self._fade = 1.0
        self._hover = 0.0
        self.setFixedSize(size + 10, size + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Charles Leclerc  ·  #16\nClick for the next photo")
        self._build_pixmaps()

        self._timer = QTimer(self)
        self._timer.setInterval(4500)
        self._timer.timeout.connect(self._next)

        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(750)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.valueChanged.connect(self._on_fade)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(160)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)

    def _build_pixmaps(self):
        dpr = 2
        px = self._size * dpr
        self._pix = []
        for raw in self._raw:
            w, h = raw.width(), raw.height()
            side = min(w, h)
            x = (w - side) // 2
            y = int((h - side) * 0.22)   # faces sit in the upper part of a photo
            sq = raw.copy(x, y, side, side).scaled(
                px, px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            sq.setDevicePixelRatio(dpr)
            self._pix.append(sq)
        self._raw = []

    def set_images(self, images: list):
        self._raw = images or []
        self._cur = 0
        self._prev = -1
        self._build_pixmaps()
        if self.isVisible() and len(self._pix) > 1:
            self._timer.start()
        self.update()

    def clear_pixmaps(self):
        self._timer.stop()
        self._raw = []
        self._pix = []
        self._cur = 0
        self._prev = -1
        self.update()

    def set_accent(self, color: str):
        self._accent = color
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if len(self._pix) > 1:
            self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _next(self):
        if len(self._pix) < 2:
            return
        self._prev = self._cur
        self._cur = (self._cur + 1) % len(self._pix)
        self._fade_anim.stop()
        self._fade_anim.start()

    def _on_fade(self, v):
        self._fade = float(v)
        self.update()

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._next()
            if self._timer.isActive():
                self._timer.start()   # restart so the photo isn't swapped again a moment later
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        s = float(self._size)
        circle = QRectF(5, 5, s, s)
        accent = QColor(self._accent)

        # soft glow that grows on hover
        glow = QColor(accent)
        glow.setAlpha(int(40 + 70 * self._hover))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(circle.adjusted(-3 - 2 * self._hover, -3 - 2 * self._hover, 3 + 2 * self._hover, 3 + 2 * self._hover))

        clip = QPainterPath()
        clip.addEllipse(circle)
        p.save()
        p.setClipPath(clip)
        if self._pix:
            if self._prev >= 0 and self._fade < 1.0:
                p.drawPixmap(circle, self._pix[self._prev], QRectF(self._pix[self._prev].rect()))
            p.setOpacity(self._fade if self._prev >= 0 else 1.0)
            cur = self._pix[self._cur]
            p.drawPixmap(circle, cur, QRectF(cur.rect()))
        else:
            p.fillRect(circle, QColor("#1A1214"))
            p.setPen(accent)
            f = p.font()
            f.setPixelSize(int(s * 0.46))
            f.setWeight(QFont.Weight.Black)
            f.setItalic(True)
            p.setFont(f)
            p.drawText(circle, Qt.AlignmentFlag.AlignCenter, "16")
        p.restore()

        ring = _lerp_color(self._accent, "#FF5A4F", self._hover)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, 2.6 + self._hover))
        p.drawEllipse(circle)

        # number tag
        tag = QRectF(self.width() - 25, self.height() - 18, 23, 15)
        p.setPen(QPen(QColor("#0B0B0D"), 2))
        p.setBrush(accent)
        p.drawRoundedRect(tag, 7, 7)
        p.setPen(QColor("#FFFFFF"))
        f = p.font()
        f.setPixelSize(10)
        f.setWeight(QFont.Weight.Black)
        f.setItalic(False)
        p.setFont(f)
        p.drawText(tag, Qt.AlignmentFlag.AlignCenter, "16")
        p.end()


class LeclercUnlockDialog(FramelessDialog):
    """Shown when 'leclerc' is typed in the brand area of the Play tab."""

    def __init__(self, images: list, first_time: bool, parent=None):
        super().__init__(
            theme_name="Leclerc",
            title="Secret unlocked" if first_time else "Leclerc theme",
            parent=parent,
            use_main_bg=True,
        )
        self.apply_requested = False
        self._intro = False
        self._anims = []
        t = ThemeManager.get_theme_data("Leclerc")

        self.set_dialog_fixed_size(460, 560)

        self._apply_dialog_theme("Leclerc", extra_qss=f"""
            QLabel {{ background: transparent; }}
            QLabel#LcTag {{ color: {t['accent']}; font-size: 11px; font-weight: 800; letter-spacing: 4px; }}
            QLabel#LcTitle {{ color: {t['text']}; font-size: 40px; font-weight: 900; font-style: italic; letter-spacing: 5px; }}
            QLabel#LcSub {{ color: {t['text_sub']}; font-size: 13px; }}
            QFrame#LcStripe {{ background-color: {t['accent']}; border: none; border-radius: 1px; }}
        """)

        lay = self.body_layout
        lay.setContentsMargins(32, 22, 32, 26)
        lay.setSpacing(10)

        self.badge = LeclercBadge(images, size=164, accent=t["accent"])
        lay.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(6)

        self.tag = QLabel("SECRET THEME UNLOCKED" if first_time else "WELCOME BACK")
        self.tag.setObjectName("LcTag")
        self.tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.tag)

        self.title = QLabel("LECLERC")
        self.title.setObjectName("LcTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.title)

        stripe_row = QHBoxLayout()
        stripe_row.addStretch(1)
        self.stripe = QFrame()
        self.stripe.setObjectName("LcStripe")
        self.stripe.setFixedSize(64, 3)
        stripe_row.addWidget(self.stripe)
        stripe_row.addStretch(1)
        lay.addLayout(stripe_row)

        self.sub = QLabel("Carbon black, Rosso red and a driver card that follows you around the client. "
                          "Lights out and away we go.")
        self.sub.setObjectName("LcSub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub.setWordWrap(True)
        lay.addWidget(self.sub)
        lay.addStretch(1)

        self.btn_apply = AnimatedButton("Apply Leclerc theme")
        self.btn_apply.setObjectName("PlayButton")
        self.btn_apply.setFixedHeight(46)
        self.btn_apply.clicked.connect(self._apply)
        lay.addWidget(self.btn_apply)

        self.btn_later = AnimatedButton("Maybe later")
        self.btn_later.setObjectName("PillButton")
        self.btn_later.setFixedHeight(40)
        self.btn_later.clicked.connect(self.reject)
        lay.addWidget(self.btn_later)

        self._staggered = [self.badge, self.tag, self.title, self.stripe, self.sub, self.btn_apply, self.btn_later]

    def _apply(self):
        self.apply_requested = True
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        if self._intro:
            return
        self._intro = True
        for i, w in enumerate(self._staggered):
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)
            an = QPropertyAnimation(eff, b"opacity", w)
            an.setDuration(420)
            an.setStartValue(0.0)
            an.setEndValue(1.0)
            an.setEasingCurve(QEasingCurve.Type.OutCubic)
            an.finished.connect(lambda widget=w: widget.setGraphicsEffect(None))
            self._anims.append(an)
            QTimer.singleShot(120 + 90 * i, an.start)


class TermsOfServiceDialog(FramelessDialog):
    """Startup / review Terms of Service + lowcore.jar disclaimer modal."""

    def __init__(self, theme_name: str = "Dark Mode", base_dir: str = None, already_accepted: bool = False, parent=None):
        super().__init__(
            theme_name=theme_name,
            title=I18n.t("tos_dialog_title"),
            parent=parent,
        )
        t = ThemeManager.get_theme_data(theme_name)
        self.set_dialog_fixed_size(580, 560)

        lay = self.body_layout
        lay.setContentsMargins(24, 18, 24, 20)
        lay.setSpacing(10)

        hdr = QLabel(I18n.t("tos_dialog_hdr"))
        hdr.setObjectName("SectionLabel")
        lay.addWidget(hdr)

        sub = QLabel(I18n.t("tos_dialog_sub"))
        sub.setObjectName("MutedLabel")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setObjectName("TosScrollBody")
        body.setStyleSheet("QWidget#TosScrollBody { background: transparent; }")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 6, 0)
        bl.setSpacing(10)

        disc_card = QFrame()
        disc_card.setStyleSheet(
            f"QFrame {{ background-color: {_hex_rgba(t['accent'], 0.12)}; "
            f"border: 1px solid {_hex_rgba(t['accent'], 0.55)}; border-radius: 10px; }}"
        )
        dl = QVBoxLayout(disc_card)
        dl.setContentsMargins(14, 12, 14, 12)
        dl.setSpacing(6)
        disc_lbl = QLabel(LOWCORE_JAR_DISCLAIMER_TEXT)
        disc_lbl.setWordWrap(True)
        disc_lbl.setStyleSheet(f"color: {t['text']}; font-size: 12px; line-height: 1.45; border: none; background: transparent;")
        dl.addWidget(disc_lbl)
        bl.addWidget(disc_card)

        tos_card = QFrame()
        tos_card.setObjectName("Card")
        tl = QVBoxLayout(tos_card)
        tl.setContentsMargins(14, 12, 14, 12)
        tl.setSpacing(6)
        tos_lbl = QLabel(LOWCORE_TOS_TEXT)
        tos_lbl.setWordWrap(True)
        tos_lbl.setStyleSheet(f"color: {t['text_sub']}; font-size: 12px; line-height: 1.45; border: none; background: transparent;")
        tl.addWidget(tos_lbl)
        bl.addWidget(tos_card)

        scroll.setWidget(body)
        body.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(scroll, stretch=1)

        self.chk_accept = SwitchCheckBox(I18n.t("tos_accept_chk"))
        self.chk_accept.setChecked(bool(already_accepted))
        self.chk_accept.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.chk_accept)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        self.btn_decline = AnimatedButton(I18n.t("tos_decline_exit") if not already_accepted else I18n.t("tos_close"))
        self.btn_decline.setObjectName("PillButton")
        self.btn_decline.setFixedHeight(40)
        self.btn_decline.setMinimumWidth(128)
        self.btn_decline.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_decline)

        self.btn_accept = AnimatedButton(I18n.t("tos_accept_btn"))
        self.btn_accept.setObjectName("PlayButton")
        self.btn_accept.setFixedHeight(40)
        self.btn_accept.setMinimumWidth(164)
        self.btn_accept.setEnabled(bool(already_accepted))
        self.btn_accept.clicked.connect(self.accept)
        self.chk_accept.toggled.connect(self.btn_accept.setEnabled)
        btn_row.addWidget(self.btn_accept)

        lay.addLayout(btn_row)


class WhatsNewDialog(FramelessDialog):
    """First-launch showcase dialog introducing new features, supported MC versions, and the R-Shift menu."""

    def __init__(self, theme_name: str = "Dark Mode", base_dir: str = None, parent=None):
        super().__init__(
            theme_name=theme_name,
            title=I18n.t("wn_title", ver=APP_VERSION),
            parent=parent,
        )
        t = ThemeManager.get_theme_data(theme_name)
        self.set_dialog_fixed_size(640, 620)

        lay = self.body_layout
        lay.setContentsMargins(24, 16, 24, 18)
        lay.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setObjectName("WhatsNewBody")
        body.setStyleSheet("QWidget#WhatsNewBody { background: transparent; }")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 6, 0)
        bl.setSpacing(12)

        hero = QFrame()
        hero.setStyleSheet(
            f"QFrame {{ background-color: {_hex_rgba(t['accent'], 0.13)}; "
            f"border: 1px solid {_hex_rgba(t['accent'], 0.50)}; border-radius: 12px; }}"
        )
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(6)
        hero_title = QLabel(I18n.t("wn_hero_title"))
        hero_title.setStyleSheet(f"color: {t['accent']}; font-size: 13px; font-weight: 900; letter-spacing: 1px; border: none; background: transparent;")
        hl.addWidget(hero_title)

        vers_str = ", ".join(SUPPORTED_MC_VERSIONS)
        vers_lbl = QLabel(I18n.t("wn_hero_sub", versions=vers_str))
        vers_lbl.setWordWrap(True)
        vers_lbl.setStyleSheet(f"color: {t['text']}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        hl.addWidget(vers_lbl)
        bl.addWidget(hero)

        # ---- R-Shift Menu Preview (assets/rshift.png) ----
        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pl = QVBoxLayout(preview_card)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(8)

        p_hdr = QLabel(I18n.t("wn_rshift_hdr"))
        p_hdr.setObjectName("SectionLabel")
        pl.addWidget(p_hdr)

        p_sub = QLabel(I18n.t("wn_rshift_sub"))
        p_sub.setObjectName("MutedLabel")
        p_sub.setWordWrap(True)
        pl.addWidget(p_sub)

        rshift_path = _find_launcher_asset("rshift.png", base_dir=base_dir)
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if rshift_path:
            pix = QPixmap(rshift_path)
            if not pix.isNull():
                scaled = pix.scaled(540, 290, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                rounded = QPixmap(scaled.size())
                rounded.fill(Qt.GlobalColor.transparent)
                pt = QPainter(rounded)
                pt.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                path = QPainterPath()
                path.addRoundedRect(QRectF(rounded.rect()), 10.0, 10.0)
                pt.setClipPath(path)
                pt.drawPixmap(0, 0, scaled)
                pt.setClipping(False)
                pt.setPen(QPen(QColor(t["border"]), 1.2))
                pt.drawRoundedRect(QRectF(rounded.rect()).adjusted(0.6, 0.6, -0.6, -0.6), 10.0, 10.0)
                pt.end()
                img_lbl.setPixmap(rounded)
                img_lbl.setStyleSheet("background: transparent; border: none;")
            else:
                img_lbl.setText("Preview unavailable (assets/rshift.png could not be decoded).")
                img_lbl.setObjectName("MutedLabel")
        else:
            img_lbl.setText(I18n.t("wn_rshift_missing"))
            img_lbl.setWordWrap(True)
            img_lbl.setStyleSheet(
                f"color: {t['text_sub']}; background-color: {t['input_bg']}; border: 1px dashed {t['border']}; "
                "border-radius: 10px; padding: 18px; font-size: 12px;"
            )
        pl.addWidget(img_lbl)
        bl.addWidget(preview_card)

        # ---- New Launcher Highlights ----
        notes_card = QFrame()
        notes_card.setObjectName("Card")
        nl = QVBoxLayout(notes_card)
        nl.setContentsMargins(14, 12, 14, 12)
        nl.setSpacing(6)
        n_hdr = QLabel(I18n.t("wn_highlights_hdr"))
        n_hdr.setObjectName("SectionLabel")
        nl.addWidget(n_hdr)

        highlights = [
            "Multicore Engine: Parallel GC, JIT compiler & ForkJoin thread tuning plus multicore launcher task pools (configurable in Settings > General).",
            "Dedicated Updates Tab: Open Updates anytime from the header or menu drawer to check for releases, view supported versions, and read patch info.",
            "R-Shift In-Game Menu & HD Capes: Search modules, tweak HUD layouts with Right Ctrl, apply 14 themes, and render sharp custom capes.",
            "Terms of Service & lowcore.jar Disclaimer: Bundled lowcore.jar mods verify LowCore Client at startup — always launch directly through LowCore Client.",
        ]
        for h in highlights:
            item = QLabel(f"•  {h}")
            item.setWordWrap(True)
            item.setStyleSheet(f"color: {t['text_sub']}; font-size: 12px; border: none; background: transparent;")
            nl.addWidget(item)
        bl.addWidget(notes_card)

        scroll.setWidget(body)
        body.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(scroll, stretch=1)

        btn_done = AnimatedButton(I18n.t("wn_got_it"))
        btn_done.setObjectName("PlayButton")
        btn_done.setFixedHeight(42)
        btn_done.clicked.connect(self.accept)
        lay.addWidget(btn_done)


class NewInstanceDialog(FramelessDialog):
    def __init__(self, all_versions: list, theme_name: str = "Dark Mode", parent=None):
        super().__init__(theme_name=theme_name, title="Create New Instance", parent=parent)
        self.theme_name = theme_name
        self.selected_icon = "grass"
        self.set_dialog_fixed_size(480, 504)
        self.all_versions = all_versions if all_versions else ["1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.18.2", "1.16.5", "1.12.2", "1.8.9"]

        layout = self.body_layout
        layout.setContentsMargins(24, 18, 24, 22)
        layout.setSpacing(10)

        inst_label = QLabel("INSTANCE NAME:")
        inst_label.setObjectName("SectionLabel")
        layout.addWidget(inst_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. My Survival World, 1.8 PvP...")
        layout.addWidget(self.name_edit)

        v_label = QLabel("MINECRAFT VERSION (SEARCH OR TYPE ANY VERSION):")
        v_label.setObjectName("SectionLabel")
        layout.addWidget(v_label)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter versions (e.g. 1.21.1, 1.20, 1.8.9)...")
        self.filter_edit.textChanged.connect(self.apply_version_filter)
        layout.addWidget(self.filter_edit)

        self.version_box = CustomDropdown(enable_delete=False, parent=self)
        self.version_box.addItem("Select a version...", userData=None)
        self.version_box.addItems(self.all_versions)
        layout.addWidget(self.version_box)

        l_label = QLabel("MOD LOADER:")
        l_label.setObjectName("SectionLabel")
        layout.addWidget(l_label)

        self.loader_box = CustomDropdown(enable_delete=False, parent=self)
        self.loader_box.addItem("Select a mod loader...", userData=None)
        self.loader_box.addItems(["Fabric", "Vanilla", "Forge", "NeoForge", "Quilt"])
        layout.addWidget(self.loader_box)

        b_label = QLabel("INSTANCE BLOCK ICON:")
        b_label.setObjectName("SectionLabel")
        layout.addWidget(b_label)

        block_row = QHBoxLayout()
        block_row.setSpacing(10)
        self.block_preview = InstanceBlockBadge(self.selected_icon, box_size=40, icon_size=32, parent=self)
        self.block_preview.set_theme_colors(ThemeManager.get_theme_data(theme_name))
        self.block_preview.clicked.connect(self._pick_block)
        block_row.addWidget(self.block_preview)

        self.lbl_block_name = QLabel(get_minecraft_block_name(self.selected_icon))
        self.lbl_block_name.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent; border: none;")
        block_row.addWidget(self.lbl_block_name, stretch=1)

        self.btn_choose_block = AnimatedButton("Choose Block...")
        self.btn_choose_block.setObjectName("PillButton")
        self.btn_choose_block.setFixedHeight(36)
        self.btn_choose_block.clicked.connect(self._pick_block)
        block_row.addWidget(self.btn_choose_block)
        layout.addLayout(block_row)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        self.cancel_btn = AnimatedButton("Cancel")
        self.cancel_btn.setObjectName("PillButton")
        self.cancel_btn.setFixedHeight(42)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.create_btn = AnimatedButton("Create Instance")
        self.create_btn.setObjectName("PlayButton")
        self.create_btn.setFixedHeight(42)
        self.create_btn.clicked.connect(self.validate_and_submit)
        btn_box.addWidget(self.create_btn)
        layout.addLayout(btn_box)

    def _pick_block(self):
        dlg = BlockPickerDialog(self.selected_icon, self.theme_name, self)
        if dlg.exec():
            self.selected_icon = dlg.get_selected_block()
            self.block_preview.set_block(self.selected_icon)
            self.lbl_block_name.setText(get_minecraft_block_name(self.selected_icon))

    def apply_version_filter(self, query: str):
        query = query.strip().lower()
        self.version_box.clear()
        if not query:
            self.version_box.addItem("Select a version...", userData=None)
            self.version_box.addItems(self.all_versions)
        else:
            filtered = [v for v in self.all_versions if query in v.lower()]
            if query not in [v.lower() for v in self.all_versions]:
                filtered.insert(0, self.filter_edit.text().strip())
            self.version_box.addItem("Select a version...", userData=None)
            self.version_box.addItems(filtered)

    def validate_and_submit(self):
        name = self.name_edit.text().strip()
        version = self.version_box.currentData()
        loader = self.loader_box.currentData()

        if not name:
            StyledMessageDialog.alert(self, "Missing Name", "Please add a name for your instance.", kind="warning")
            self.name_edit.setFocus()
            return

        if not version or version == "Select a version...":
            custom_v = self.filter_edit.text().strip()
            if custom_v:
                version = custom_v
            else:
                StyledMessageDialog.alert(self, "Missing Version", "Please select or type a Minecraft version.", kind="warning")
                return

        if not loader or loader == "Select a mod loader...":
            StyledMessageDialog.alert(self, "Missing Loader", "Please select a mod loader.", kind="warning")
            return

        self.chosen_version = version
        self.chosen_loader = loader
        self.chosen_name = name
        self.accept()

    def get_data(self):
        return {
            "name": getattr(self, "chosen_name", self.name_edit.text().strip()),
            "version": getattr(self, "chosen_version", self.version_box.currentText().strip().replace("   ▾", "")),
            "loader": getattr(self, "chosen_loader", self.loader_box.currentText().replace("   ▾", "")),
            "icon": self.selected_icon,
        }


class EditInstanceDialog(FramelessDialog):
    """Frameless dialog to edit an existing instance's name, Minecraft version, mod loader, and block icon."""

    def __init__(self, inst_data: dict, all_versions: list, theme_name: str = "Dark Mode", parent=None):
        super().__init__(theme_name=theme_name, title=f"Edit Instance — {inst_data.get('name', '')}", parent=parent)
        self.inst_data = inst_data
        self.theme_name = theme_name
        self.selected_icon = str(inst_data.get("icon", "grass")).strip().lower() or "grass"
        self.is_horizon = hb.is_horizon_instance(inst_data)
        base_versions = all_versions if all_versions else ["1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.18.2", "1.16.5", "1.12.2", "1.8.9"]
        cur_version = str(inst_data.get("version", "1.21.1")).strip()
        if cur_version and cur_version not in base_versions:
            self.all_versions = [cur_version] + list(base_versions)
        else:
            self.all_versions = list(base_versions)

        self.set_dialog_fixed_size(480, 514)

        layout = self.body_layout
        layout.setContentsMargins(24, 18, 24, 22)
        layout.setSpacing(10)

        inst_label = QLabel("INSTANCE NAME:")
        inst_label.setObjectName("SectionLabel")
        layout.addWidget(inst_label)

        self.name_edit = QLineEdit(str(inst_data.get("name", "")))
        self.name_edit.setPlaceholderText("e.g. My Survival World, 1.8 PvP...")
        layout.addWidget(self.name_edit)

        v_label = QLabel("MINECRAFT VERSION (SEARCH OR TYPE ANY VERSION):")
        v_label.setObjectName("SectionLabel")
        layout.addWidget(v_label)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter versions (e.g. 1.21.1, 1.20, 1.8.9)...")
        self.filter_edit.textChanged.connect(self.apply_version_filter)
        layout.addWidget(self.filter_edit)

        self.version_box = CustomDropdown(enable_delete=False, parent=self)
        self.version_box.addItems(self.all_versions)
        if cur_version:
            self.version_box.setCurrentText(cur_version)
        layout.addWidget(self.version_box)

        l_label = QLabel("MOD LOADER:")
        l_label.setObjectName("SectionLabel")
        layout.addWidget(l_label)

        self.loader_box = CustomDropdown(enable_delete=False, parent=self)
        if self.is_horizon:
            self.loader_box.addItems([hb.LOADER_NAME])
            self.loader_box.setEnabled(False)
            self.loader_box.setToolTip("Horizon instances use the Horizon Rust client loader.")
        else:
            loaders = ["Fabric", "Vanilla", "Forge", "NeoForge", "Quilt"]
            cur_loader = str(inst_data.get("loader", "Fabric")).strip()
            match_loader = next((ld for ld in loaders if ld.lower() == cur_loader.lower()), None)
            if not match_loader and cur_loader:
                loaders.insert(0, cur_loader)
                match_loader = cur_loader
            self.loader_box.addItems(loaders)
            if match_loader:
                self.loader_box.setCurrentText(match_loader)
        layout.addWidget(self.loader_box)

        b_label = QLabel("INSTANCE BLOCK ICON:")
        b_label.setObjectName("SectionLabel")
        layout.addWidget(b_label)

        block_row = QHBoxLayout()
        block_row.setSpacing(10)
        self.block_preview = InstanceBlockBadge(self.selected_icon, box_size=40, icon_size=32, parent=self)
        self.block_preview.set_theme_colors(ThemeManager.get_theme_data(theme_name))
        self.block_preview.clicked.connect(self._pick_block)
        block_row.addWidget(self.block_preview)

        self.lbl_block_name = QLabel(get_minecraft_block_name(self.selected_icon))
        self.lbl_block_name.setStyleSheet("font-size: 13px; font-weight: 700; background: transparent; border: none;")
        block_row.addWidget(self.lbl_block_name, stretch=1)

        self.btn_choose_block = AnimatedButton("Choose Block...")
        self.btn_choose_block.setObjectName("PillButton")
        self.btn_choose_block.setFixedHeight(36)
        self.btn_choose_block.clicked.connect(self._pick_block)
        block_row.addWidget(self.btn_choose_block)
        layout.addLayout(block_row)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        self.cancel_btn = AnimatedButton("Cancel")
        self.cancel_btn.setObjectName("PillButton")
        self.cancel_btn.setFixedHeight(42)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.save_btn = AnimatedButton("Save Changes")
        self.save_btn.setObjectName("PlayButton")
        self.save_btn.setFixedHeight(42)
        self.save_btn.clicked.connect(self.validate_and_submit)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

    def _pick_block(self):
        dlg = BlockPickerDialog(self.selected_icon, self.theme_name, self)
        if dlg.exec():
            self.selected_icon = dlg.get_selected_block()
            self.block_preview.set_block(self.selected_icon)
            self.lbl_block_name.setText(get_minecraft_block_name(self.selected_icon))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(20, lambda: (self.name_edit.setFocus(), self.name_edit.selectAll()))

    def apply_version_filter(self, query: str):
        query_s = query.strip()
        q_low = query_s.lower()
        self.version_box.clear()
        if not q_low:
            self.version_box.addItems(self.all_versions)
        else:
            filtered = [v for v in self.all_versions if q_low in v.lower()]
            if q_low not in [v.lower() for v in self.all_versions]:
                filtered.insert(0, query_s)
            self.version_box.addItems(filtered)

    def validate_and_submit(self):
        name = self.name_edit.text().strip()
        version = self.version_box.currentData()
        loader = self.loader_box.currentData()

        if not name:
            StyledMessageDialog.alert(self, "Missing Name", "Please enter an instance name.", kind="warning")
            self.name_edit.setFocus()
            return

        custom_v = self.filter_edit.text().strip()
        if not version:
            version = custom_v
        if not version:
            StyledMessageDialog.alert(self, "Missing Version", "Please select or type a Minecraft version.", kind="warning")
            return

        if not loader:
            StyledMessageDialog.alert(self, "Missing Loader", "Please select a mod loader.", kind="warning")
            return

        self.chosen_name = name
        self.chosen_version = str(version).strip()
        self.chosen_loader = str(loader).strip()
        self.accept()

    def get_data(self) -> dict:
        return {
            "name": getattr(self, "chosen_name", self.name_edit.text().strip()),
            "version": getattr(self, "chosen_version", self.version_box.currentText().strip()),
            "loader": getattr(self, "chosen_loader", self.loader_box.currentText().strip()),
            "icon": self.selected_icon,
        }


class MainWindow(QMainWindow):
    avatar_ready = pyqtSignal()
    versions_loaded = pyqtSignal(tuple)

    def __init__(self, config: ConfigManager):
        super().__init__()
        QPixmapCache.setCacheLimit(256)  # keep Qt pixmap cache tight
        self.config = config
        self.threadpool = QThreadPool()
        self.icon_pool = QThreadPool()
        self._apply_multicore_pools()
        QThreadPool.globalInstance().setExpiryTimeout(4000)

        self._avatar_refresh_timer = QTimer(self)
        self._avatar_refresh_timer.setSingleShot(True)
        self._avatar_refresh_timer.setInterval(80)
        self._avatar_refresh_timer.timeout.connect(self.refresh_accounts)
        self.avatar_ready.connect(self._avatar_refresh_timer.start)
        self.versions_loaded.connect(self._on_versions_loaded)

        self.active_process = None
        self.all_mojang_versions = self._load_cached_versions(max_age=7 * 86400) or ()
        self.card_widgets = []
        self._settings_inst_cards = []
        self._settings_acc_cards = []
        self._built_settings_pages = set()
        self._pending_update_ui = None
        self.log_history = deque(maxlen=1500)
        self.current_console_filter = "ALL"
        self.is_force_quitting = False
        self.has_shown_tray_notice = self.config.get("tray_notified", False)

        self.content_browser_user_overridden = False
        self._last_non_settings_tab = 0

        self.search_debounce_timer = QTimer(self)
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.setInterval(350)
        self.search_debounce_timer.timeout.connect(self.run_mod_search)

        self.setWindowTitle("LowCore Client Beta")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        _shadow = RoundedRoot.SHADOW
        self.setFixedSize(760 + 2 * _shadow, 728 + 2 * _shadow)

        self.easter_egg_buffer = ""

        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.leclerc_images = []
        self.logo_path = os.path.join(self.base_dir, "assets", "logo.png")
        self.app_icon = QIcon()
        self.trimmed_logo_pix = QPixmap()
        if os.path.exists(self.logo_path):
            raw_pix = QPixmap(self.logo_path)
            full_trim = crop_transparent_padding(raw_pix, source_path=self.logo_path)
            for s in [16, 24, 32, 64]:
                self.app_icon.addPixmap(
                    full_trim.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
            self.trimmed_logo_pix = full_trim.scaled(
                62, 62, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            del raw_pix, full_trim
            self.setWindowIcon(self.app_icon)

        self.inst_mgr = InstanceManager(self.config.get("game_dir"))
        self.license = LicenseManager(self.config)
        self._redeem_fails = 0
        self._redeem_locked_until = 0.0
        self._update_check_running = False
        self._update_silent = False
        self._update_info = None
        self.purge_residual_default_instances()

        self.current_theme = self.config.get("theme_name", "Dark Mode")
        if not ThemeManager.is_valid(self.current_theme):
            self.current_theme = ThemeManager.DEFAULT_THEME
        if ThemeManager.is_secret(self.current_theme) and self.current_theme not in self.unlocked_themes():
            self.current_theme = ThemeManager.DEFAULT_THEME
        if self.current_theme == "Leclerc":
            self.leclerc_images = load_leclerc_images(os.path.join(self.base_dir, "assets"), max_px=128)

        saved_lang = self.config.get("language", "en")
        I18n.set_language(saved_lang)

        self.progress_anim = None
        self.setWindowOpacity(0.0)   # faded in by showEvent

        self.init_ui()
        # Keep only an 18x18 copy for FramelessDialog titlebars once header_logo & app_icon are ready
        if not self.trimmed_logo_pix.isNull():
            self.trimmed_logo_pix = self.trimmed_logo_pix.scaled(
                18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        self.leclerc_images = []
        self.setup_tray_icon()
        self.apply_current_theme()
        self.refresh_instances()
        self.refresh_accounts()
        self.retranslate_ui()
        QTimer.singleShot(50, self.fetch_all_versions)
        QTimer.singleShot(260, self._run_startup_onboarding)
        QTimer.singleShot(800, self._init_discord_rpc)
        QTimer.singleShot(1200, lambda: _trim_process_memory(True))
        QTimer.singleShot(3500, self._startup_update_check)

        self._mem_trim_timer = QTimer(self)
        self._mem_trim_timer.setInterval(12000)
        self._mem_trim_timer.timeout.connect(self._periodic_memory_trim)
        self._mem_trim_timer.start()

    def _apply_multicore_pools(self):
        multicore = bool(self.config.get("multicore_enabled", True))
        cores = os.cpu_count() or 4
        try:
            req = int(self.config.get("multicore_threads", 0) or 0)
        except (TypeError, ValueError):
            req = 0
        if multicore:
            worker_threads = min(8, max(2, min(cores, req) if req > 0 else cores))
            icon_threads = min(4, max(2, worker_threads // 2))
        else:
            worker_threads = 1
            icon_threads = 1
        self.threadpool.setMaxThreadCount(worker_threads)
        self.threadpool.setExpiryTimeout(4000)
        self.icon_pool.setMaxThreadCount(icon_threads)
        self.icon_pool.setExpiryTimeout(3000)

    def _run_startup_onboarding(self):
        if getattr(self, "_onboarding_ran", False):
            return
        self._onboarding_ran = True

        tos_ok = bool(self.config.get("tos_accepted", False)) and (self.config.get("tos_version", "") == TOS_VERSION)
        if not tos_ok:
            accepted = self.open_tos_dialog(require_acceptance=True)
            if not accepted:
                self.quit_application()
                return

        if not bool(self.config.get(WHATS_NEW_KEY, False)):
            self.config.set(WHATS_NEW_KEY, True)
            self.open_whats_new_dialog()

    def open_tos_dialog(self, require_acceptance: bool = False) -> bool:
        already = bool(self.config.get("tos_accepted", False)) and (self.config.get("tos_version", "") == TOS_VERSION)
        dlg = TermsOfServiceDialog(
            theme_name=self.current_theme,
            base_dir=self.base_dir,
            already_accepted=already and not require_acceptance,
            parent=self,
        )
        res = dlg.exec() == QDialog.DialogCode.Accepted
        dlg.deleteLater()
        if res:
            self.config.set("tos_accepted", True)
            self.config.set("tos_version", TOS_VERSION)
            self.config.set("tos_accepted_at", int(time.time()))
            self._refresh_tos_status_labels()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))
        return res

    def open_whats_new_dialog(self):
        dlg = WhatsNewDialog(
            theme_name=self.current_theme,
            base_dir=self.base_dir,
            parent=self,
        )
        dlg.exec()
        dlg.deleteLater()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def _refresh_tos_status_labels(self):
        accepted = bool(self.config.get("tos_accepted", False)) and (self.config.get("tos_version", "") == TOS_VERSION)
        status_txt = I18n.t("tos_accepted", ver=TOS_VERSION) if accepted else I18n.t("tos_pending")
        for attr in ("lbl_tos_status", "lbl_tab_tos_status"):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.setText(status_txt)

    def _init_discord_rpc(self):
        try:
            from core.discord_rpc import DiscordRPCManager
            DiscordRPCManager.get_instance()
        except Exception:
            pass
        _trim_process_memory(clear_pixmap_cache=True)

    def _periodic_memory_trim(self):
        if QApplication.activeModalWidget() is None and QApplication.activePopupWidget() is None:
            _trim_process_memory(clear_pixmap_cache=self.isMinimized() or not self.isVisible())

    def setup_tray_icon(self):
        if getattr(self, "tray_icon", None) is not None:
            return
        self.tray_icon = QSystemTrayIcon(self)
        if not self.app_icon.isNull():
            self.tray_icon.setIcon(self.app_icon)
        else:
            self.tray_icon.setIcon(self.windowIcon())

        self.tray_icon.setToolTip("LowCore Client Beta")

        tray_menu = QMenu(self)
        theme_dict = ThemeManager.get_theme_data(self.current_theme)
        tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme_dict['card_bg']};
                border: 1px solid {theme_dict['border']};
                border-radius: 8px;
                padding: 6px;
                color: {theme_dict['text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {theme_dict['accent']};
                color: {theme_dict['accent_text']};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme_dict['border']};
                margin: 4px 6px;
            }}
        """)

        action_show = QAction("Open LowCore Client", self)
        action_show.triggered.connect(self.show_from_tray)
        tray_menu.addAction(action_show)

        tray_menu.addSeparator()

        action_exit = QAction("Exit Completely", self)
        action_exit.triggered.connect(self.quit_application)
        tray_menu.addAction(action_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.aboutToQuit.connect(self._cleanup_tray_icon)

    def _cleanup_tray_icon(self):
        tray = getattr(self, "tray_icon", None)
        if tray is not None:
            tray.hide()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_from_tray()

    def showEvent(self, event):
        super().showEvent(event)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._show_anim = anim
        anim.start()

    def show_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()
        self.raise_()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(100, lambda: _trim_process_memory(True))

    def closeEvent(self, event):
        if self.is_force_quitting:
            self._cleanup_tray_icon()
            event.accept()
        else:
            event.ignore()
            self.hide()
            if not self.has_shown_tray_notice:
                self.tray_icon.showMessage(
                    "LowCore Client",
                    "LowCore is running in the background for instant launch.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
                self.has_shown_tray_notice = True
                self.config.set("tray_notified", True)
            QTimer.singleShot(120, lambda: _trim_process_memory(True))

    def quit_application(self):
        self.is_force_quitting = True
        self._cleanup_tray_icon()
        if self.active_process:
            self.kill_active_instance()
        QApplication.quit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape and hasattr(self, "side_drawer") and self.side_drawer.is_open:
            self.close_side_drawer()
            event.accept()
            return
        key_char = event.text().lower()
        if len(key_char) == 1 and key_char.isalpha():
            self.register_easter_egg_char(key_char)
        super().keyPressEvent(event)

    def register_easter_egg_char(self, char: str):
        """Typing (or clicking the brand letters) on the Play tab: 'grug' and 'leclerc' are secrets."""
        if self.stack.currentIndex() != 0:
            self.easter_egg_buffer = ""
            return
        if not char or not char.isalpha():
            return

        self.easter_egg_buffer = (self.easter_egg_buffer + char.lower())[-16:]
        if self.easter_egg_buffer.endswith("grug"):
            self.easter_egg_buffer = ""
            self.trigger_grug_easter_egg()
        elif self.easter_egg_buffer.endswith("leclerc"):
            self.easter_egg_buffer = ""
            self.trigger_leclerc_easter_egg()

    def trigger_grug_easter_egg(self):
        StyledMessageDialog.alert(
            self,
            "CRITICAL SYSTEM ALERT",
            "grug has hacked ur pc now he is installing 999gb of [REDACTED] stuff",
            is_error=True,
        )

    # ---- secret themes
    def unlocked_themes(self) -> list:
        value = self.config.get("unlocked_themes", [])
        return list(value) if isinstance(value, list) else []

    def refresh_theme_dropdown(self):
        """Rebuilds the Settings theme list (secret themes only show once unlocked)."""
        if not hasattr(self, "theme_dropdown"):
            return
        dd = self.theme_dropdown
        dd.blockSignals(True)
        dd.clear()
        dd.addItems(ThemeManager.get_theme_names(self.unlocked_themes()))
        dd.setCurrentText(self.current_theme)
        dd.blockSignals(False)

    def trigger_leclerc_easter_egg(self):
        unlocked = self.unlocked_themes()
        first_time = "Leclerc" not in unlocked
        if first_time:
            unlocked.append("Leclerc")
            self.config.set("unlocked_themes", unlocked)
            self.refresh_theme_dropdown()

        imgs = load_leclerc_images(os.path.join(self.base_dir, "assets"), max_px=340)
        dlg = LeclercUnlockDialog(imgs, first_time, self)
        dlg.exec()
        apply_req = dlg.apply_requested
        dlg.deleteLater()
        del imgs, dlg
        if apply_req and self.current_theme != "Leclerc":
            if hasattr(self, "theme_dropdown"):
                self.theme_dropdown.blockSignals(True)
                self.theme_dropdown.setCurrentText("Leclerc")
                self.theme_dropdown.blockSignals(False)
            self.on_theme_changed("Leclerc")
        else:
            QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def purge_residual_default_instances(self):
        legacy_dir = os.path.join(self.inst_mgr.instances_dir, "Default-1211")
        if os.path.exists(legacy_dir):
            try:
                shutil.rmtree(legacy_dir)
            except Exception:
                pass

    def apply_current_theme(self):
        style = ThemeManager.get_style(self.current_theme)
        self.setStyleSheet(style)
        theme_dict = ThemeManager.get_theme_data(self.current_theme)

        if hasattr(self, "leclerc_badge"):
            is_leclerc = self.current_theme == "Leclerc"
            if is_leclerc and not self.leclerc_badge._pix:
                imgs = load_leclerc_images(os.path.join(self.base_dir, "assets"), max_px=128)
                self.leclerc_badge.set_images(imgs)
                del imgs
            elif not is_leclerc:
                self.leclerc_badge.clear_pixmaps()
            self.leclerc_badge.set_accent(theme_dict["accent"])
            self.leclerc_badge.setVisible(is_leclerc)

        if hasattr(self, "side_drawer"):
            self.side_drawer.set_theme_colors(
                active_color=theme_dict["text"],
                inactive_color=theme_dict["text_sub"],
                accent_color=theme_dict["accent"],
                theme_dict=theme_dict,
            )
        if hasattr(self, "menu_btn"):
            self.menu_btn.set_theme_colors(theme_dict)
        if hasattr(self, "updates_nav_btn"):
            self.updates_nav_btn.set_theme_colors(theme_dict)
        if hasattr(self, "settings_gear_btn"):
            self.settings_gear_btn.set_theme_colors(theme_dict)
        if hasattr(self, "instance_showcase"):
            self.instance_showcase.set_theme_colors(theme_dict)
        if hasattr(self, "settings_sidebar") and hasattr(self.settings_sidebar, "set_theme_colors"):
            self.settings_sidebar.set_theme_colors(theme_dict)
        for _card in getattr(self, "_settings_inst_cards", []):
            _card.set_theme_colors(theme_dict)
        for _card in getattr(self, "_settings_acc_cards", []):
            _card.set_theme_colors(theme_dict)
        for _card in getattr(self, "_language_cards", []):
            _card.set_theme_colors(theme_dict)
        for _btn in getattr(self, "_proxy_mode_btns", []):
            _btn.set_theme_colors(theme_dict)

        if hasattr(self, "lbl_proxy_notice"):
            self.lbl_proxy_notice.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {theme_dict['text_sub']}; border: none; background: transparent;")
        if hasattr(self, "update_banner"):
            acc_q = QColor(theme_dict["accent"])
            acc_tint = f"rgba({acc_q.red()}, {acc_q.green()}, {acc_q.blue()}, 0.14)"
            acc_border = f"rgba({acc_q.red()}, {acc_q.green()}, {acc_q.blue()}, 0.55)"
            self.update_banner.setStyleSheet(
                f"QFrame#UpdateBanner {{ background-color: {acc_tint}; border: 1px solid {acc_border}; border-radius: 12px; }}"
            )
            if hasattr(self, "lbl_update_banner"):
                self.lbl_update_banner.setStyleSheet(
                    f"font-size: 12px; font-weight: 700; color: {theme_dict['text']}; border: none; background: transparent;"
                )

        # rounded window, window buttons, animated switches and button glow follow the theme
        if hasattr(self, "root_frame"):
            self.root_frame.set_colors(theme_dict["bg"], theme_dict["border"])
        for _btn in getattr(self, "win_buttons", []):
            _btn.set_theme(theme_dict["text_sub"], theme_dict["pill_hover"])
        SwitchCheckBox.set_theme(theme_dict)
        AnimatedButton.light_theme = bool(theme_dict.get("is_light"))
        for _dd in self.findChildren(CustomDropdown):
            _dd.set_theme_colors(theme_dict)
        for _w in self.findChildren(SwitchCheckBox) + self.findChildren(AnimatedButton):
            _w.update()

    def init_ui(self):
        central = RoundedRoot(self)
        central.setObjectName("RoundedRoot")
        self.setCentralWidget(central)
        self.root_frame = central

        self.win_min_btn = WindowControlButton("min", central)
        self.win_close_btn = WindowControlButton("close", central)
        self.win_min_btn.clicked.connect(self.showMinimized)
        self.win_close_btn.clicked.connect(self.close)
        self.win_buttons = [self.win_min_btn, self.win_close_btn]
        central.controls = self.win_buttons

        main_layout = QVBoxLayout(central)
        _s = RoundedRoot.SHADOW
        main_layout.setContentsMargins(28 + _s, 42 + _s, 28 + _s, 20 + _s)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)

        self.menu_btn = HeaderIconButton("menu", central)
        self.menu_btn.clicked.connect(self.toggle_side_drawer)
        header.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        if os.path.exists(self.logo_path):
            self.header_logo = QLabel()
            self.header_logo.setFixedSize(62, 62)
            logo_src = self.trimmed_logo_pix if not self.trimmed_logo_pix.isNull() else QPixmap(self.logo_path)
            self.header_logo.setPixmap(
                logo_src.scaled(
                    62, 62,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            self.header_logo.setStyleSheet("background: transparent; border: none; padding: 0px;")
            header.addWidget(self.header_logo, alignment=Qt.AlignmentFlag.AlignVCenter)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(2)
        brand_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        self.brand_title_lbl = ClickableTextLabel("LOWCORE CLIENT")
        self.brand_title_lbl.setObjectName("BrandTitle")
        self.brand_title_lbl.setStyleSheet("border: none; background: transparent;")
        self.brand_title_lbl.clicked.connect(self.register_easter_egg_char)
        title_row.addWidget(self.brand_title_lbl)

        beta_badge = QLabel("BETA")
        beta_badge.setStyleSheet("""
            background-color: #E85A52;
            color: #FFFFFF;
            font-size: 9px;
            font-weight: 900;
            padding: 2px 6px;
            border-radius: 4px;
            border: none;
            letter-spacing: 1px;
        """)
        title_row.addWidget(beta_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()

        brand_box.addLayout(title_row)

        self.brand_slogan_lbl = ClickableTextLabel("EVERYTHING IN ONE")
        self.brand_slogan_lbl.setObjectName("BrandSlogan")
        self.brand_slogan_lbl.setStyleSheet("border: none; background: transparent;")
        self.brand_slogan_lbl.clicked.connect(self.register_easter_egg_char)
        brand_box.addWidget(self.brand_slogan_lbl)

        header.addLayout(brand_box)
        header.addStretch()

        # Secret "Leclerc" theme: rotating driver card, only visible while that theme is active
        self.leclerc_badge = LeclercBadge(self.leclerc_images, size=52,
                                          accent=ThemeManager.get_theme_data("Leclerc")["accent"], parent=central)
        header.addWidget(self.leclerc_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.leclerc_badge.setVisible(self.current_theme == "Leclerc")

        self.updates_nav_btn = HeaderIconButton("updates", central)
        self.updates_nav_btn.clicked.connect(self.toggle_updates_tab)
        header.addWidget(self.updates_nav_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.settings_gear_btn = HeaderIconButton("gear", central)
        self.settings_gear_btn.clicked.connect(self.toggle_settings_tab)
        header.addWidget(self.settings_gear_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.kill_btn = AnimatedButton("Kill Minecraft")
        self.kill_btn.setObjectName("PillButton")
        self.kill_btn.setFixedHeight(38)
        self.kill_btn.setStyleSheet("color: #FF5555; border: 1px solid rgba(255, 85, 85, 0.4); padding: 0 14px;")
        self.kill_btn.clicked.connect(self.kill_active_instance)
        header.addWidget(self.kill_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        main_layout.addLayout(header)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self._drawer_scrim = _DrawerScrim(central)
        self._drawer_scrim.clicked.connect(self.close_side_drawer)
        self.side_drawer = SideNavDrawer(central)
        self.side_drawer.tab_changed.connect(self.on_tab_switch)
        self.side_drawer.settings_page_requested.connect(self.open_settings_subpage)
        self.side_drawer.action_triggered.connect(self.on_drawer_action)
        # Keep alias so existing callbacks (e.g. retranslate_ui / on_finished) continue to work
        self.nav_bar = self.side_drawer

        # ================= VIEW 1: PLAY =================
        dash = QWidget()
        dash_layout = QVBoxLayout(dash)
        dash_layout.setSpacing(10)
        dash_layout.setContentsMargins(0, 8, 0, 0)

        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.setVisible(False)
        ub_layout = QHBoxLayout(self.update_banner)
        ub_layout.setContentsMargins(14, 9, 14, 9)
        ub_layout.setSpacing(10)

        self.lbl_update_banner = QLabel("")
        self.lbl_update_banner.setWordWrap(True)
        self.lbl_update_banner.setStyleSheet("font-size: 12px; font-weight: 700; border: none; background: transparent;")
        ub_layout.addWidget(self.lbl_update_banner, stretch=1)

        self.btn_banner_notes = AnimatedButton(I18n.t("tab_updates"))
        self.btn_banner_notes.setObjectName("PillButton")
        self.btn_banner_notes.setFixedHeight(32)
        self.btn_banner_notes.clicked.connect(lambda: self.on_tab_switch(4))
        ub_layout.addWidget(self.btn_banner_notes)

        self.btn_banner_update = AnimatedButton(I18n.t("download_update_btn"))
        self.btn_banner_update.setObjectName("PlayButton")
        self.btn_banner_update.setFixedHeight(32)
        self.btn_banner_update.clicked.connect(self.open_update_download)
        ub_layout.addWidget(self.btn_banner_update)
        dash_layout.addWidget(self.update_banner)

        self.play_card = QFrame()
        self.play_card.setObjectName("Card")
        card_layout = QVBoxLayout(self.play_card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        self.inst_label = QLabel("Active Isolated Instance")
        self.inst_label.setObjectName("SectionLabel")
        card_layout.addWidget(self.inst_label)

        inst_bar = QHBoxLayout()
        inst_bar.setSpacing(8)

        self.instance_box = CustomDropdown(enable_delete=True, parent=self)
        self.instance_box.currentIndexChanged.connect(self.on_instance_changed)
        self.instance_box.deleteRequested.connect(self.delete_instance_by_index)
        inst_bar.addWidget(self.instance_box, stretch=5)

        self.btn_open_folder = AnimatedButton("⋮")
        self.btn_open_folder.setToolTip(I18n.t("inst_options_tooltip"))
        self.btn_open_folder.setObjectName("PillButton")
        self.btn_open_folder.setFixedWidth(44)
        self.btn_open_folder.setFixedHeight(40)
        self.btn_open_folder.setStyleSheet("font-size: 22px; font-weight: 900; padding: 0px;")
        self.btn_open_folder.clicked.connect(self.show_instance_options_menu)
        inst_bar.addWidget(self.btn_open_folder)

        self.btn_new_inst = AnimatedButton(I18n.t("new_instance"))
        self.btn_new_inst.setObjectName("PillButton")
        self.btn_new_inst.setFixedHeight(40)
        self.btn_new_inst.setMinimumWidth(116)
        self.btn_new_inst.clicked.connect(self.prompt_new_instance)
        inst_bar.addWidget(self.btn_new_inst)

        self.btn_import_inst = AnimatedButton(I18n.t("import_instance"))
        self.btn_import_inst.setObjectName("PillButton")
        self.btn_import_inst.setFixedHeight(40)
        self.btn_import_inst.setMinimumWidth(86)
        self.btn_import_inst.setToolTip(I18n.t("import_tooltip"))
        self.btn_import_inst.clicked.connect(self.prompt_import_instances)
        inst_bar.addWidget(self.btn_import_inst)
        card_layout.addLayout(inst_bar)

        self.acc_title = QLabel(I18n.t("account"))
        self.acc_title.setObjectName("SectionLabel")
        card_layout.addWidget(self.acc_title)

        acc_bar = QHBoxLayout()
        acc_bar.setSpacing(8)

        self.account_box = CustomDropdown(enable_delete=True, parent=self)
        self.account_box.currentIndexChanged.connect(self.on_account_changed)
        self.account_box.deleteRequested.connect(self.delete_account_by_index)
        acc_bar.addWidget(self.account_box, stretch=3)

        self.btn_offline = AnimatedButton(I18n.t("add_offline"))
        self.btn_offline.setObjectName("PillButton")
        self.btn_offline.clicked.connect(self.add_offline_account)
        acc_bar.addWidget(self.btn_offline, stretch=1)

        self.btn_ms = AnimatedButton(I18n.t("add_ms"))
        self.btn_ms.setObjectName("PillButton")
        self.btn_ms.clicked.connect(self.add_microsoft_account)
        acc_bar.addWidget(self.btn_ms, stretch=1)
        card_layout.addLayout(acc_bar)

        self.ram_title = QLabel(I18n.t("ram_alloc"))
        self.ram_title.setObjectName("SectionLabel")
        card_layout.addWidget(self.ram_title)

        self.ram_dropdown = CustomDropdown(enable_delete=False, parent=self)
        self._populate_ram_dropdown(target_mb=self.config.get("allocated_ram_mb", 4096))
        self.ram_dropdown.currentIndexChanged.connect(self.on_ram_changed)
        card_layout.addWidget(self.ram_dropdown)

        dash_layout.addWidget(self.play_card)

        self.instance_showcase = InstanceShowcaseCard(self)
        dash_layout.addWidget(self.instance_showcase)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(0)
        self.progress_bar.setTextVisible(False)
        dash_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel(I18n.t("ready"))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setObjectName("StatusLabel")  # colour comes from the theme
        self.status_lbl.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.8px;
            padding: 4px;
        """)
        self.status_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        dash_layout.addWidget(self.status_lbl)

        self.launch_btn = AnimatedButton(I18n.t("play"))
        self.launch_btn.setObjectName("PlayButton")
        self.launch_btn.setFixedHeight(50)
        self.launch_btn.clicked.connect(self.handle_launch)
        dash_layout.addWidget(self.launch_btn)

        def make_stat_tile(caption: str):
            tile = QFrame()
            tile.setObjectName("StatTile")
            tile.setFixedHeight(58)
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(14, 8, 14, 8)
            tile_layout.setSpacing(2)
            cap_lbl = QLabel(caption)
            cap_lbl.setObjectName("SectionLabel")
            val_lbl = QLabel("—")
            val_lbl.setObjectName("StatValue")
            tile_layout.addWidget(cap_lbl)
            tile_layout.addWidget(val_lbl)
            return tile, cap_lbl, val_lbl

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        playtime_tile, self.stat_cap_playtime, self.stat_playtime_val = make_stat_tile(I18n.t("stat_playtime"))
        mods_tile, self.stat_cap_mods, self.stat_mods_val = make_stat_tile(I18n.t("stat_mods"))
        last_tile, self.stat_cap_last, self.stat_last_val = make_stat_tile(I18n.t("stat_last_played"))
        for tile in (playtime_tile, mods_tile, last_tile):
            stats_row.addWidget(tile, 1)
        dash_layout.addLayout(stats_row)

        dash_layout.addStretch(1)
        self.stack.addWidget(dash)

        # ================= VIEW 2: CONTENT BROWSER =================
        mod_tab = QWidget()
        m_layout = QVBoxLayout(mod_tab)
        m_layout.setSpacing(10)

        m_card = QFrame()
        m_card.setObjectName("Card")
        m_card_layout = QVBoxLayout(m_card)
        m_card_layout.setSpacing(12)

        target_row = QHBoxLayout()
        target_row.setSpacing(10)

        self.lbl_target_inst = QLabel(I18n.t("target_instance"))
        self.lbl_target_inst.setObjectName("SectionLabel")
        target_row.addWidget(self.lbl_target_inst)

        self.browser_target_inst = CustomDropdown(enable_delete=False, parent=self)
        self.browser_target_inst.setFixedWidth(280)
        self.browser_target_inst.currentIndexChanged.connect(self.on_browser_instance_changed)
        target_row.addWidget(self.browser_target_inst)

        target_row.addStretch()

        theme_dict = ThemeManager.get_theme_data(self.current_theme)
        self.content_type_bar = ContentTypeBar(theme_dict, self)
        self.content_type_bar.type_changed.connect(lambda _: self.run_mod_search())
        target_row.addWidget(self.content_type_bar)

        m_card_layout.addLayout(target_row)

        search_bar = QHBoxLayout()
        self.mod_search_input = QLineEdit()
        self.mod_search_input.setPlaceholderText(I18n.t("search_mods"))
        self.mod_search_input.returnPressed.connect(self.run_mod_search)
        self.mod_search_input.textChanged.connect(self.on_search_text_changed)
        search_bar.addWidget(self.mod_search_input)

        self.btn_search = AnimatedButton(I18n.t("search"))
        self.btn_search.setObjectName("PillButton")
        self.btn_search.clicked.connect(self.run_mod_search)
        search_bar.addWidget(self.btn_search)
        m_card_layout.addLayout(search_bar)

        self.mod_results_list = QListWidget()
        self.mod_results_list.setObjectName("ModsList")
        self.mod_results_list.currentRowChanged.connect(self.on_mod_selection_changed)
        m_card_layout.addWidget(self.mod_results_list)

        self.btn_install_mod = AnimatedButton(I18n.t("download_mod"))
        self.btn_install_mod.setObjectName("PlayButton")
        self.btn_install_mod.setFixedHeight(42)
        self.btn_install_mod.clicked.connect(self.install_selected_mod)
        m_card_layout.addWidget(self.btn_install_mod)

        m_layout.addWidget(m_card)
        self.stack.addWidget(mod_tab)

        # ================= VIEW 3: SETTINGS =================
        settings_widget = QWidget()
        s_layout = QVBoxLayout(settings_widget)
        s_layout.setContentsMargins(0, 8, 0, 0)
        s_layout.setSpacing(12)

        self.settings_sidebar = SettingsTabBar(self)
        self.settings_subpages = QStackedWidget()
        self._settings_builders = (
            self._build_general_settings_page,
            self._build_instance_settings_page,
            self._build_accounts_settings_page,
            self._build_language_settings_page,
            self._build_proxy_settings_page,
            self._build_experimental_settings_page,
            self._build_updates_settings_page,
            self._build_donations_settings_page,
        )
        for _ in range(len(self._settings_builders)):
            self.settings_subpages.addWidget(QWidget())

        self.settings_sidebar.currentRowChanged.connect(self._on_settings_row_changed)
        self.settings_sidebar.setCurrentRow(0)

        s_layout.addWidget(self.settings_sidebar)
        s_layout.addWidget(self.settings_subpages, stretch=1)
        self.stack.addWidget(settings_widget)

        # ================= VIEW 4: CONSOLE LOG =================
        console_widget = QWidget()
        c_layout = QVBoxLayout(console_widget)
        c_layout.setContentsMargins(0, 8, 0, 0)
        c_layout.setSpacing(8)

        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        self.console_search = QLineEdit()
        self.console_search.setPlaceholderText(I18n.t("console_filter_ph"))
        self.console_search.textChanged.connect(self.refresh_main_console_display)
        ctrl_bar.addWidget(self.console_search, stretch=3)

        self.btn_c_all = AnimatedButton(I18n.t("console_all"))
        self.btn_c_all.setObjectName("PillButton")
        self.btn_c_all.setMinimumWidth(60)
        self.btn_c_all.setStyleSheet("padding: 4px 12px;")
        self.btn_c_all.clicked.connect(lambda: self.set_main_console_filter("ALL"))
        ctrl_bar.addWidget(self.btn_c_all)

        self.btn_c_err = AnimatedButton(I18n.t("console_errors"))
        self.btn_c_err.setObjectName("PillButton")
        self.btn_c_err.setMinimumWidth(75)
        self.btn_c_err.setStyleSheet("color: #FF5555; border: 1px solid rgba(255, 85, 85, 0.4); padding: 4px 12px;")
        self.btn_c_err.clicked.connect(lambda: self.set_main_console_filter("ERRORS"))
        ctrl_bar.addWidget(self.btn_c_err)

        self.btn_c_warn = AnimatedButton(I18n.t("console_warns"))
        self.btn_c_warn.setObjectName("PillButton")
        self.btn_c_warn.setMinimumWidth(75)
        self.btn_c_warn.setStyleSheet("color: #FFB86C; border: 1px solid rgba(255, 184, 108, 0.4); padding: 4px 12px;")
        self.btn_c_warn.clicked.connect(lambda: self.set_main_console_filter("WARNS"))
        ctrl_bar.addWidget(self.btn_c_warn)

        self.btn_c_copy = AnimatedButton(I18n.t("console_copy"))
        self.btn_c_copy.setObjectName("PillButton")
        self.btn_c_copy.setMinimumWidth(82)
        self.btn_c_copy.setStyleSheet("padding: 4px 14px;")
        self.btn_c_copy.clicked.connect(self.copy_main_console)
        ctrl_bar.addWidget(self.btn_c_copy)

        self.btn_c_clear = AnimatedButton(I18n.t("console_clear"))
        self.btn_c_clear.setObjectName("PillButton")
        self.btn_c_clear.setMinimumWidth(82)
        self.btn_c_clear.setStyleSheet("padding: 4px 14px;")
        self.btn_c_clear.clicked.connect(self.clear_main_console)
        ctrl_bar.addWidget(self.btn_c_clear)

        self.chk_autoscroll = SwitchCheckBox(I18n.t("console_autoscroll"))
        self.chk_autoscroll.set_compact(True)
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setCursor(Qt.CursorShape.PointingHandCursor)
        ctrl_bar.addWidget(self.chk_autoscroll)

        c_layout.addLayout(ctrl_bar)

        self.console = QPlainTextEdit()
        self.console.setObjectName("ConsoleLog")
        self.console.setReadOnly(True)
        self.console.setUndoRedoEnabled(False)
        self.console.setMaximumBlockCount(1200)
        c_layout.addWidget(self.console)
        self.stack.addWidget(console_widget)

        # ================= VIEW 5: UPDATES TAB =================
        updates_page = self._build_updates_tab_page()
        self.stack.addWidget(updates_page)

        central.reposition_controls()
        self._position_drawer_widgets()
        self._drawer_scrim.raise_()
        self.side_drawer.raise_()
        for _btn in self.win_buttons:
            _btn.raise_()

    def show_instance_options_menu(self):
        inst_data = self.instance_box.currentData()
        if not inst_data or not inst_data.get("path"):
            return

        base_path = inst_data["path"]
        menu = QMenu(self)
        
        t = ThemeManager.get_theme_data(self.current_theme)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t['card_bg']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                padding: 6px;
                color: {t['text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 7px 22px 7px 12px;
                border-radius: 6px;
                background-color: transparent;
                color: {t['text']};
            }}
            QMenu::item:selected {{
                background-color: {t['pill_hover']};
                color: {t['accent']};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t['border']};
                margin: 4px 6px;
            }}
        """)

        icon_color = t.get("text_sub", "#9AA0AA")
        cur_block = inst_data.get("icon", "grass")

        total_sec = inst_data.get("playtime_seconds", 0)
        action_time = QAction(_make_menu_icon("clock", icon_color), f"Total Playtime: {format_playtime(total_sec)}", self)
        action_time.setEnabled(False)
        menu.addAction(action_time)

        menu.addSeparator()

        action_edit = QAction(_make_menu_icon("edit", icon_color), "Edit Instance (Name / Version / Loader)", self)
        action_edit.triggered.connect(lambda: self.edit_instance(inst_data))
        menu.addAction(action_edit)

        action_block = QAction(QIcon(get_minecraft_block_pixmap(cur_block, 16)), "Change Block Icon...", self)
        action_block.triggered.connect(self.change_active_instance_block)
        menu.addAction(action_block)

        action_clone = QAction(_make_menu_icon("copy", icon_color), "Clone Instance (Create Copy)", self)
        action_clone.triggered.connect(lambda: self.clone_instance(inst_data))
        menu.addAction(action_clone)

        action_manage_mods = QAction(_make_menu_icon("mods", icon_color), "Manage Installed Mods", self)
        action_manage_mods.triggered.connect(lambda: self.open_mods_manager(os.path.join(base_path, "mods")))
        menu.addAction(action_manage_mods)

        menu.addSeparator()

        action_root = QAction(_make_menu_icon("folder", icon_color), "Open Instance Root", self)
        action_root.triggered.connect(lambda: self._open_dir(base_path))
        menu.addAction(action_root)

        action_mods = QAction(_make_menu_icon("folder", icon_color), "Open Mods Folder", self)
        action_mods.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "mods")))
        menu.addAction(action_mods)

        action_rp = QAction(_make_menu_icon("palette", icon_color), "Open Resource Packs", self)
        action_rp.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "resourcepacks")))
        menu.addAction(action_rp)

        action_shaders = QAction(_make_menu_icon("shaders", icon_color), "Open Shader Packs", self)
        action_shaders.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "shaderpacks")))
        menu.addAction(action_shaders)

        action_saves = QAction(_make_menu_icon("worlds", icon_color), "Open Saves / Worlds", self)
        action_saves.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "saves")))
        menu.addAction(action_saves)

        action_screenshots = QAction(_make_menu_icon("camera", icon_color), "Open Screenshots", self)
        action_screenshots.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "screenshots")))
        menu.addAction(action_screenshots)

        action_cfg = QAction(_make_menu_icon("gear", icon_color), "Open Configs", self)
        action_cfg.triggered.connect(lambda: self._open_dir(os.path.join(base_path, "config")))
        menu.addAction(action_cfg)

        pos = self.btn_open_folder.mapToGlobal(QPoint(0, self.btn_open_folder.height() + 4))
        menu.exec(pos)

    def open_mods_manager(self, mods_dir: str):
        os.makedirs(mods_dir, exist_ok=True)
        dlg = ModManagerDialog(mods_dir, self.current_theme, self)
        dlg.exec()
        dlg.deleteLater()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def clone_instance(self, source_inst: dict):
        new_name, ok = StyledInputDialog.get_text(
            self, "Clone Instance", f"Clone '{source_inst['name']}' as:", text=f"{source_inst['name']} (Copy)"
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        safe_folder = "".join(c for c in new_name if c.isalnum() or c in ("-", "_")).rstrip()
        target_path = os.path.join(self.inst_mgr.instances_dir, safe_folder)

        if os.path.exists(target_path):
            self.show_alert("Folder Exists", "An instance with a similar folder name already exists.", is_error=True)
            return

        try:
            shutil.copytree(source_inst["path"], target_path)
            meta_path = os.path.join(target_path, "instance.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["name"] = new_name
                meta["created_at"] = time.time()
                meta["playtime_seconds"] = 0
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=4)

            self.refresh_instances()
            self.show_alert("Cloned", f"Instance cloned successfully as '{new_name}'.")
        except Exception as e:
            self.show_alert("Clone Failed", f"Could not duplicate instance:\n{e}", is_error=True)

    def _open_dir(self, path: str):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def set_main_console_filter(self, mode: str):
        self.current_console_filter = mode
        self.refresh_main_console_display()

    def refresh_main_console_display(self):
        query = self.console_search.text().strip().lower()
        self.console.clear()
        chunks = []

        for line in self.log_history:
            if query and query not in line.lower():
                continue
            upper = line.upper()
            if self.current_console_filter == "ERRORS":
                if not any(k in upper for k in ["[ERROR]", "ERROR", "FATAL", "EXCEPTION", "CRASH", "FAILED", "OS::COMMIT_MEMORY"]):
                    continue
            elif self.current_console_filter == "WARNS":
                if not any(k in upper for k in ["[WARN]", "[WARNING]", "WARN"]):
                    continue

            chunks.append(format_log_line_html(line, self.current_theme))

        self.console.appendHtml("".join(chunks))
        if self.chk_autoscroll.isChecked():
            self.console.moveCursor(QTextCursor.MoveOperation.End)

    def append_log_line(self, line: str):
        self.log_history.append(line)
        query = self.console_search.text().strip().lower()

        if query and query not in line.lower():
            return

        upper = line.upper()
        if self.current_console_filter == "ERRORS":
            if not any(k in upper for k in ["[ERROR]", "ERROR", "FATAL", "EXCEPTION", "CRASH", "FAILED", "OS::COMMIT_MEMORY"]):
                return
        elif self.current_console_filter == "WARNS":
            if not any(k in upper for k in ["[WARN]", "[WARNING]", "WARN"]):
                return

        self.console.appendHtml(format_log_line_html(line, self.current_theme))
        if self.chk_autoscroll.isChecked():
            self.console.moveCursor(QTextCursor.MoveOperation.End)

    def clear_main_console(self):
        self.log_history.clear()
        self.console.clear()

    def copy_main_console(self):
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(self.log_history))
        self.btn_c_copy.setText(I18n.t("console_copied"))
        QTimer.singleShot(1500, lambda: self.btn_c_copy.setText(I18n.t("console_copy")))

    def _populate_ram_dropdown(self, target_mb: int = None):
        if target_mb is None:
            target_mb = self.ram_dropdown.currentData() or self.config.get("allocated_ram_mb", 4096)
        self.ram_dropdown.blockSignals(True)
        self.ram_dropdown.clear()
        self.ram_options = [
            ("2048 MB (2 GB)", 2048),
            ("3072 MB (3 GB)", 3072),
            (f"4096 MB (4 GB - {I18n.t('ram_recommended')})", 4096),
            ("6144 MB (6 GB)", 6144),
            (f"8192 MB (8 GB - {I18n.t('ram_high_end')})", 8192),
            ("12288 MB (12 GB)", 12288),
            ("16384 MB (16 GB)", 16384),
        ]
        sel_idx = 2
        for idx, (lbl, val) in enumerate(self.ram_options):
            self.ram_dropdown.addItem(lbl, userData=val)
            if val == target_mb:
                sel_idx = idx
        self.ram_dropdown.setCurrentIndex(sel_idx)
        self.ram_dropdown.blockSignals(False)

    def _populate_multicore_cores_dropdown(self, target_cores: int = None):
        if not hasattr(self, "multicore_cores_dropdown"):
            return
        if target_cores is None:
            cur = self.multicore_cores_dropdown.currentData()
            target_cores = int(cur) if cur is not None else int(self.config.get("multicore_cores", 0) or 0)
        detected_cores = os.cpu_count() or 4
        core_choices = [(I18n.t("multicore_cores_auto"), 0)]
        seen_vals = {0}
        for c in (2, 4, 6, 8, 12, 16, 24, 32, detected_cores):
            if 2 <= c <= detected_cores and c not in seen_vals:
                seen_vals.add(c)
                core_choices.append((I18n.t("multicore_cores_n", n=c), c))
        core_choices[1:] = sorted(core_choices[1:], key=lambda pair: pair[1])
        self.multicore_cores_dropdown.blockSignals(True)
        self.multicore_cores_dropdown.clear()
        sel_idx = 0
        for idx, (lbl_c, val_c) in enumerate(core_choices):
            self.multicore_cores_dropdown.addItem(lbl_c, userData=val_c)
            if val_c == target_cores:
                sel_idx = idx
        self.multicore_cores_dropdown.setCurrentIndex(sel_idx)
        self.multicore_cores_dropdown.blockSignals(False)

    def _populate_multicore_dropdown(self, target_threads: int = None):
        if not hasattr(self, "multicore_dropdown"):
            return
        if target_threads is None:
            cur = self.multicore_dropdown.currentData()
            target_threads = int(cur) if cur is not None else int(self.config.get("multicore_threads", 0) or 0)
        detected_cores = os.cpu_count() or 4
        thread_choices = [(I18n.t("multicore_auto"), 0)]
        for c in (2, 4, 6, 8, 12, 16):
            if c <= detected_cores:
                thread_choices.append((I18n.t("multicore_threads_n", n=c), c))
        self.multicore_dropdown.blockSignals(True)
        self.multicore_dropdown.clear()
        sel_th = 0
        for idx, (lbl_t, val_t) in enumerate(thread_choices):
            self.multicore_dropdown.addItem(lbl_t, userData=val_t)
            if val_t == target_threads:
                sel_th = idx
        self.multicore_dropdown.setCurrentIndex(sel_th)
        self.multicore_dropdown.blockSignals(False)

    def _build_general_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 4)
        layout.setSpacing(12)

        # ---- Card 1: Appearance ----
        theme_card = QFrame()
        theme_card.setObjectName("Card")
        tc_l = QVBoxLayout(theme_card)
        tc_l.setContentsMargins(18, 16, 18, 16)
        tc_l.setSpacing(8)

        self.lbl_client_theme = QLabel(I18n.t("client_theme"))
        self.lbl_client_theme.setObjectName("SectionLabel")
        tc_l.addWidget(self.lbl_client_theme)

        self.lbl_theme_sub = QLabel(I18n.t("theme_sub"))
        self.lbl_theme_sub.setObjectName("MutedLabel")
        self.lbl_theme_sub.setWordWrap(True)
        tc_l.addWidget(self.lbl_theme_sub)

        self.theme_dropdown = CustomDropdown(enable_delete=False, parent=self)
        self.theme_dropdown.addItems(ThemeManager.get_theme_names(self.unlocked_themes()))
        self.theme_dropdown.setCurrentText(self.current_theme)
        self.theme_dropdown.currentIndexChanged.connect(
            lambda: self.on_theme_changed(self.theme_dropdown.currentText().replace("   ▾", ""))
        )
        tc_l.addWidget(self.theme_dropdown)
        layout.addWidget(theme_card)

        # ---- Card 2: Game Window ----
        win_card = QFrame()
        win_card.setObjectName("Card")
        wc_l = QVBoxLayout(win_card)
        wc_l.setContentsMargins(18, 16, 18, 16)
        wc_l.setSpacing(10)

        self.lbl_res = QLabel(I18n.t("win_res_header"))
        self.lbl_res.setObjectName("SectionLabel")
        wc_l.addWidget(self.lbl_res)

        res_box = QHBoxLayout()
        res_box.setSpacing(10)

        self.lbl_res_w = QLabel(I18n.t("width_label"))
        self.lbl_res_w.setObjectName("SettingsItemLabel")
        self.spin_res_w = QSpinBox()
        self.spin_res_w.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin_res_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_res_w.setRange(640, 7680)
        self.spin_res_w.setFixedSize(92, 36)
        self.spin_res_w.setValue(self.config.get("res_width", 1280))
        self.spin_res_w.valueChanged.connect(lambda val: self.config.set("res_width", val))

        self.lbl_res_h = QLabel(I18n.t("height_label"))
        self.lbl_res_h.setObjectName("SettingsItemLabel")
        self.spin_res_h = QSpinBox()
        self.spin_res_h.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin_res_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_res_h.setRange(480, 4320)
        self.spin_res_h.setFixedSize(92, 36)
        self.spin_res_h.setValue(self.config.get("res_height", 720))
        self.spin_res_h.valueChanged.connect(lambda val: self.config.set("res_height", val))

        self.chk_fullscreen = SwitchCheckBox(I18n.t("start_fullscreen"))
        self.chk_fullscreen.setChecked(self.config.get("fullscreen", False))
        self.chk_fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_fullscreen.toggled.connect(lambda val: self.config.set("fullscreen", val))

        res_box.addWidget(self.lbl_res_w)
        res_box.addWidget(self.spin_res_w)
        res_box.addSpacing(8)
        res_box.addWidget(self.lbl_res_h)
        res_box.addWidget(self.spin_res_h)
        res_box.addStretch(1)
        res_box.addWidget(self.chk_fullscreen)
        wc_l.addLayout(res_box)
        layout.addWidget(win_card)

        # ---- Card 3: Diagnostics ----
        log_card = QFrame()
        log_card.setObjectName("Card")
        lc_l = QVBoxLayout(log_card)
        lc_l.setContentsMargins(18, 16, 18, 16)
        lc_l.setSpacing(10)

        self.lbl_log_section = QLabel(I18n.t("logging_header"))
        self.lbl_log_section.setObjectName("SectionLabel")
        lc_l.addWidget(self.lbl_log_section)

        log_row = QHBoxLayout()
        log_row.setSpacing(12)

        self.chk_auto_log_window = SwitchCheckBox(I18n.t("auto_log_window"))
        self.chk_auto_log_window.setObjectName("SettingsCheckBox")
        self.chk_auto_log_window.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_auto_log_window.setChecked(self.config.get("show_log_on_exit", True))
        self.chk_auto_log_window.toggled.connect(lambda val: self.config.set("show_log_on_exit", val))
        log_row.addWidget(self.chk_auto_log_window, stretch=1)

        self.btn_open_log_window = AnimatedButton(I18n.t("view_log_window"))
        self.btn_open_log_window.setObjectName("PillButton")
        self.btn_open_log_window.setFixedHeight(36)
        self.btn_open_log_window.setMinimumWidth(148)
        self.btn_open_log_window.clicked.connect(self.open_standalone_log_dialog)
        log_row.addWidget(self.btn_open_log_window)
        lc_l.addLayout(log_row)
        layout.addWidget(log_card)

        # ---- Card 3b: Per-Version Sodium & Fabric API Auto-Pairing ----
        mod_pair_card = QFrame()
        mod_pair_card.setObjectName("Card")
        mp_l = QVBoxLayout(mod_pair_card)
        mp_l.setContentsMargins(18, 16, 18, 16)
        mp_l.setSpacing(10)

        self.lbl_mp = QLabel(I18n.t("auto_pair_header"))
        self.lbl_mp.setObjectName("SectionLabel")
        mp_l.addWidget(self.lbl_mp)

        self.lbl_mp_sub = QLabel(I18n.t("auto_pair_sub"))
        self.lbl_mp_sub.setObjectName("MutedLabel")
        self.lbl_mp_sub.setWordWrap(True)
        mp_l.addWidget(self.lbl_mp_sub)

        self.chk_auto_sodium = SwitchCheckBox(I18n.t("auto_pair_check"))
        self.chk_auto_sodium.setObjectName("SettingsCheckBox")
        self.chk_auto_sodium.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_auto_sodium.setChecked(bool(self.config.get("auto_pair_sodium", True)))
        self.chk_auto_sodium.toggled.connect(lambda val: self.config.set("auto_pair_sodium", bool(val)))
        mp_l.addWidget(self.chk_auto_sodium)

        layout.addWidget(mod_pair_card)

        # ---- Card 3c: Multicore CPU Engine ----
        mc_card = QFrame()
        mc_card.setObjectName("Card")
        mc_l = QVBoxLayout(mc_card)
        mc_l.setContentsMargins(18, 16, 18, 16)
        mc_l.setSpacing(10)

        self.lbl_mc = QLabel(I18n.t("multicore_header"))
        self.lbl_mc.setObjectName("SectionLabel")
        mc_l.addWidget(self.lbl_mc)

        detected_cores = os.cpu_count() or 4
        self.lbl_mc_sub = QLabel(I18n.t("multicore_sub", cores=detected_cores))
        self.lbl_mc_sub.setObjectName("MutedLabel")
        self.lbl_mc_sub.setWordWrap(True)
        mc_l.addWidget(self.lbl_mc_sub)

        self.chk_multicore = SwitchCheckBox(I18n.t("multicore_enable"))
        self.chk_multicore.setObjectName("SettingsCheckBox")
        self.chk_multicore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_multicore.setChecked(bool(self.config.get("multicore_enabled", True)))
        self.chk_multicore.toggled.connect(self._on_multicore_toggled)
        mc_l.addWidget(self.chk_multicore)

        cores_row = QHBoxLayout()
        cores_row.setSpacing(10)
        self.lbl_mc_cores = QLabel(I18n.t("multicore_cores_lbl"))
        self.lbl_mc_cores.setObjectName("SettingsItemLabel")
        cores_row.addWidget(self.lbl_mc_cores)

        self.multicore_cores_dropdown = CustomDropdown(enable_delete=False, parent=self)
        self._populate_multicore_cores_dropdown(int(self.config.get("multicore_cores", 0) or 0))
        self.multicore_cores_dropdown.setEnabled(bool(self.config.get("multicore_enabled", True)))
        self.multicore_cores_dropdown.currentIndexChanged.connect(self._on_multicore_cores_changed)
        cores_row.addWidget(self.multicore_cores_dropdown, stretch=1)
        mc_l.addLayout(cores_row)

        th_row = QHBoxLayout()
        th_row.setSpacing(10)
        self.lbl_mc_threads = QLabel(I18n.t("multicore_threads_lbl"))
        self.lbl_mc_threads.setObjectName("SettingsItemLabel")
        th_row.addWidget(self.lbl_mc_threads)

        self.multicore_dropdown = CustomDropdown(enable_delete=False, parent=self)
        self._populate_multicore_dropdown(int(self.config.get("multicore_threads", 0) or 0))
        self.multicore_dropdown.setEnabled(bool(self.config.get("multicore_enabled", True)))
        self.multicore_dropdown.currentIndexChanged.connect(self._on_multicore_threads_changed)
        th_row.addWidget(self.multicore_dropdown, stretch=1)
        mc_l.addLayout(th_row)

        self.lbl_mc_tip = QLabel(I18n.t("multicore_tip"))
        self.lbl_mc_tip.setObjectName("MutedLabel")
        self.lbl_mc_tip.setWordWrap(True)
        mc_l.addWidget(self.lbl_mc_tip)

        layout.addWidget(mc_card)

        # ---- Card 3d: Terms of Service & lowcore.jar Disclaimer ----
        tos_card = QFrame()
        tos_card.setObjectName("Card")
        tos_l = QVBoxLayout(tos_card)
        tos_l.setContentsMargins(18, 16, 18, 16)
        tos_l.setSpacing(10)

        self.lbl_tos_hdr = QLabel(I18n.t("tos_card_header"))
        self.lbl_tos_hdr.setObjectName("SectionLabel")
        tos_l.addWidget(self.lbl_tos_hdr)

        self.lbl_tos_status = QLabel("")
        self.lbl_tos_status.setObjectName("MutedLabel")
        self._refresh_tos_status_labels()
        tos_l.addWidget(self.lbl_tos_status)

        self.lbl_tos_note = QLabel(I18n.t("tos_card_note", versions=", ".join(SUPPORTED_MC_VERSIONS)))
        self.lbl_tos_note.setObjectName("MutedLabel")
        self.lbl_tos_note.setWordWrap(True)
        tos_l.addWidget(self.lbl_tos_note)

        tos_btns = QHBoxLayout()
        tos_btns.setSpacing(10)
        self.btn_review_tos = AnimatedButton(I18n.t("btn_review_tos"))
        self.btn_review_tos.setObjectName("PillButton")
        self.btn_review_tos.setFixedHeight(36)
        self.btn_review_tos.clicked.connect(lambda: self.open_tos_dialog(require_acceptance=False))
        tos_btns.addWidget(self.btn_review_tos)

        self.btn_whats_new = AnimatedButton(I18n.t("btn_view_whats_new"))
        self.btn_whats_new.setObjectName("PillButton")
        self.btn_whats_new.setFixedHeight(36)
        self.btn_whats_new.clicked.connect(self.open_whats_new_dialog)
        tos_btns.addWidget(self.btn_whats_new)
        tos_btns.addStretch(1)
        tos_l.addLayout(tos_btns)

        layout.addWidget(tos_card)

        # ---- Card 4: Folders ----
        dir_card = QFrame()
        dir_card.setObjectName("Card")
        dc_l = QVBoxLayout(dir_card)
        dc_l.setContentsMargins(18, 16, 18, 16)
        dc_l.setSpacing(10)

        self.lbl_folders = QLabel(I18n.t("folders"))
        self.lbl_folders.setObjectName("SectionLabel")
        dc_l.addWidget(self.lbl_folders)

        folders = [
            ("folder_instances", os.path.join(self.config.get("game_dir"), "instances")),
            ("folder_shared_libs", self.config.get("game_dir")),
            ("folder_auto_java", os.path.join(self.config.get("game_dir"), "java")),
            ("folder_downloads", os.path.expanduser("~/Downloads")),
        ]

        self.folder_row_labels = []
        self.folder_browse_buttons = []
        for lbl_key, default_dir in folders:
            row = QHBoxLayout()
            row.setSpacing(10)

            lbl = QLabel(I18n.t(lbl_key))
            lbl.setObjectName("SettingsItemLabel")
            lbl.setFixedWidth(104)
            self.folder_row_labels.append((lbl_key, lbl))

            inp = QLineEdit(default_dir)
            inp.setFixedHeight(36)

            btn = AnimatedButton(I18n.t("browse"))
            btn.setObjectName("PillButton")
            btn.setFixedSize(96, 36)
            btn.clicked.connect(lambda _, target=inp: self._browse_folder(target))
            self.folder_browse_buttons.append(btn)

            row.addWidget(lbl)
            row.addWidget(inp, stretch=1)
            row.addWidget(btn)
            dc_l.addLayout(row)
        layout.addWidget(dir_card)

        layout.addStretch()

        page.setObjectName("GeneralSettingsPage")
        page.setStyleSheet("QWidget#GeneralSettingsPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def _on_multicore_toggled(self, val: bool):
        self.config.set("multicore_enabled", bool(val))
        if hasattr(self, "multicore_cores_dropdown"):
            self.multicore_cores_dropdown.setEnabled(bool(val))
        if hasattr(self, "multicore_dropdown"):
            self.multicore_dropdown.setEnabled(bool(val))
        self._apply_multicore_pools()

    def _on_multicore_cores_changed(self):
        if hasattr(self, "multicore_cores_dropdown"):
            val = int(self.multicore_cores_dropdown.currentData() or 0)
            self.config.set("multicore_cores", val)
            self._apply_multicore_pools()

    def _on_multicore_threads_changed(self):
        if hasattr(self, "multicore_dropdown"):
            val = int(self.multicore_dropdown.currentData() or 0)
            self.config.set("multicore_threads", val)
            self._apply_multicore_pools()

    def open_standalone_log_dialog(self):
        dlg = LogViewerDialog(self.log_history, self.current_theme, app_icon=self.app_icon, parent=self)
        dlg.exec()
        dlg.deleteLater()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def _browse_folder(self, target_input):
        chosen = QFileDialog.getExistingDirectory(self, "Select Directory", target_input.text())
        if chosen:
            target_input.setText(chosen)

    def _build_instance_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        head_card = QFrame()
        head_card.setObjectName("Card")
        hc_l = QHBoxLayout(head_card)
        hc_l.setContentsMargins(18, 14, 18, 14)
        hc_l.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_inst_mgr_hdr = QLabel(I18n.t("inst_mgr_header"))
        self.lbl_inst_mgr_hdr.setObjectName("SectionLabel")
        title_col.addWidget(self.lbl_inst_mgr_hdr)

        self.lbl_inst_count = QLabel(I18n.t("inst_mgr_sub"))
        self.lbl_inst_count.setObjectName("MutedLabel")
        title_col.addWidget(self.lbl_inst_count)
        hc_l.addLayout(title_col, stretch=1)

        self.btn_inst_import = AnimatedButton(I18n.t("import_btn"))
        self.btn_inst_import.setObjectName("PillButton")
        self.btn_inst_import.setFixedHeight(36)
        self.btn_inst_import.setMinimumWidth(88)
        self.btn_inst_import.clicked.connect(self.prompt_import_instances)
        hc_l.addWidget(self.btn_inst_import)

        self.btn_inst_new = AnimatedButton(I18n.t("new_instance"))
        self.btn_inst_new.setObjectName("PlayButton")
        self.btn_inst_new.setFixedHeight(36)
        self.btn_inst_new.setMinimumWidth(140)
        self.btn_inst_new.clicked.connect(self.prompt_new_instance)
        hc_l.addWidget(self.btn_inst_new)

        layout.addWidget(head_card)

        self._settings_inst_cards = []
        self.settings_inst_list = QListWidget()
        self.settings_inst_list.setObjectName("ModsList")
        self.settings_inst_list.setStyleSheet("QListWidget#ModsList { background: transparent; border: none; padding: 0px; }")
        self.settings_inst_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_inst_list.currentRowChanged.connect(self._on_settings_inst_row_changed)
        self.settings_inst_list.itemDoubleClicked.connect(lambda _item: self.edit_selected_settings_instance())
        layout.addWidget(self.settings_inst_list, stretch=1)
        return page

    def _on_settings_inst_row_changed(self, row: int):
        for i, card in enumerate(getattr(self, "_settings_inst_cards", [])):
            if not sip.isdeleted(card):
                card.set_selected(i == row)

    def _build_accounts_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        head_card = QFrame()
        head_card.setObjectName("Card")
        hc_l = QHBoxLayout(head_card)
        hc_l.setContentsMargins(18, 14, 18, 14)
        hc_l.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_accounts_mgmt = QLabel(I18n.t("accounts_mgmt"))
        self.lbl_accounts_mgmt.setObjectName("SectionLabel")
        title_col.addWidget(self.lbl_accounts_mgmt)

        self.lbl_accounts_sub = QLabel(I18n.t("accounts_sub"))
        self.lbl_accounts_sub.setObjectName("MutedLabel")
        title_col.addWidget(self.lbl_accounts_sub)
        hc_l.addLayout(title_col, stretch=1)

        self.btn_s_off = AnimatedButton(I18n.t("add_offline"))
        self.btn_s_off.setObjectName("PillButton")
        self.btn_s_off.setFixedHeight(36)
        self.btn_s_off.setMinimumWidth(96)
        self.btn_s_off.clicked.connect(self.add_offline_account)
        hc_l.addWidget(self.btn_s_off)

        self.btn_s_ms = AnimatedButton(I18n.t("add_ms"))
        self.btn_s_ms.setObjectName("PlayButton")
        self.btn_s_ms.setFixedHeight(36)
        self.btn_s_ms.setMinimumWidth(114)
        self.btn_s_ms.clicked.connect(self.add_microsoft_account)
        hc_l.addWidget(self.btn_s_ms)

        layout.addWidget(head_card)

        self._settings_acc_cards = []
        self.settings_acc_list = QListWidget()
        self.settings_acc_list.setObjectName("ModsList")
        self.settings_acc_list.setStyleSheet("QListWidget#ModsList { background: transparent; border: none; padding: 0px; }")
        self.settings_acc_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.settings_acc_list, stretch=1)
        return page

    def _build_language_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 4)
        layout.setSpacing(10)

        head_card = QFrame()
        head_card.setObjectName("Card")
        hc_l = QVBoxLayout(head_card)
        hc_l.setContentsMargins(18, 16, 18, 16)
        hc_l.setSpacing(4)

        self.lbl_lang_header = QLabel(I18n.t("language"))
        self.lbl_lang_header.setObjectName("SectionLabel")
        hc_l.addWidget(self.lbl_lang_header)

        self.lbl_lang_sub = QLabel(I18n.t("language_sub"))
        self.lbl_lang_sub.setObjectName("MutedLabel")
        self.lbl_lang_sub.setWordWrap(True)
        hc_l.addWidget(self.lbl_lang_sub)
        layout.addWidget(head_card)

        current_code = I18n.get_language()
        self._language_cards = []
        for code, title, desc in LANGUAGE_META:
            card = LanguageOptionCard(code, title, desc, self)
            card.set_selected(code == current_code)
            card.clicked.connect(lambda _, c=code: self.on_language_code_selected(c))
            self._language_cards.append(card)
            layout.addWidget(card)

        layout.addStretch(1)

        page.setObjectName("LanguageSettingsPage")
        page.setStyleSheet("QWidget#LanguageSettingsPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def on_language_code_selected(self, lang_code: str):
        I18n.set_language(lang_code)
        self.config.set("language", lang_code)
        for card in getattr(self, "_language_cards", []):
            card.set_selected(card.lang_code == lang_code)
        self.retranslate_ui()

    def on_language_selected(self, row: int):
        codes = [code for code, _, _ in LANGUAGE_META]
        if 0 <= row < len(codes):
            self.on_language_code_selected(codes[row])

    def retranslate_ui(self):
        tab_titles = [
            I18n.t("tab_play"),
            I18n.t("tab_mods"),
            I18n.t("tab_settings"),
            I18n.t("tab_console"),
            I18n.t("tab_updates"),
        ]
        for i, btn in enumerate(self.nav_bar.buttons):
            if i < len(tab_titles):
                btn.setText(tab_titles[i])
        if hasattr(self.side_drawer, "retranslate_ui"):
            self.side_drawer.retranslate_ui()

        for btn_attr in ("menu_btn", "updates_nav_btn", "settings_gear_btn"):
            b = getattr(self, btn_attr, None)
            if b is not None and hasattr(b, "retranslate_ui"):
                b.retranslate_ui()

        self.kill_btn.setText(I18n.t("kill_mc"))
        self.launch_btn.setText(I18n.t("play"))
        if hasattr(self, "instance_box"):
            if self.instance_box.is_placeholder_mode:
                self.status_lbl.setText(I18n.t("no_active_inst"))
            else:
                self.status_lbl.setText(I18n.t("ready"))

        self.inst_label.setText(I18n.t("active_inst"))
        self.btn_open_folder.setToolTip(I18n.t("inst_options_tooltip"))
        self.acc_title.setText(I18n.t("account"))
        self.ram_title.setText(I18n.t("ram_alloc"))
        self.btn_new_inst.setText(I18n.t("new_instance"))
        self.btn_import_inst.setText(I18n.t("import_instance"))
        self.btn_import_inst.setToolTip(I18n.t("import_tooltip"))
        self.btn_offline.setText(I18n.t("add_offline"))
        self.btn_ms.setText(I18n.t("add_ms"))
        self._populate_ram_dropdown()
        if hasattr(self, "instance_showcase"):
            self.instance_showcase.retranslate_ui()

        if hasattr(self, "stat_cap_playtime"):
            self.stat_cap_playtime.setText(I18n.t("stat_playtime"))
        if hasattr(self, "stat_cap_mods"):
            self.stat_cap_mods.setText(I18n.t("stat_mods"))
        if hasattr(self, "stat_cap_last"):
            self.stat_cap_last.setText(I18n.t("stat_last_played"))

        if hasattr(self, "lbl_target_inst"):
            self.lbl_target_inst.setText(I18n.t("target_instance"))
        if hasattr(self, "content_type_bar"):
            self.content_type_bar.retranslate_ui()
        self.mod_search_input.setPlaceholderText(I18n.t("search_mods"))
        self.btn_search.setText(I18n.t("search"))
        self.btn_install_mod.setText(I18n.t("download_mod"))

        if hasattr(self, "console_search"):
            self.console_search.setPlaceholderText(I18n.t("console_filter_ph"))
        if hasattr(self, "btn_c_all"):
            self.btn_c_all.setText(I18n.t("console_all"))
        if hasattr(self, "btn_c_err"):
            self.btn_c_err.setText(I18n.t("console_errors"))
        if hasattr(self, "btn_c_warn"):
            self.btn_c_warn.setText(I18n.t("console_warns"))
        if hasattr(self, "btn_c_copy"):
            self.btn_c_copy.setText(I18n.t("console_copy"))
        if hasattr(self, "btn_c_clear"):
            self.btn_c_clear.setText(I18n.t("console_clear"))
        if hasattr(self, "chk_autoscroll"):
            self.chk_autoscroll.setText(I18n.t("console_autoscroll"))

        if hasattr(self, "settings_sidebar"):
            self.settings_sidebar.retranslate_ui()

        # General settings page
        if hasattr(self, "lbl_client_theme"):
            self.lbl_client_theme.setText(I18n.t("client_theme"))
        if hasattr(self, "lbl_theme_sub"):
            self.lbl_theme_sub.setText(I18n.t("theme_sub"))
        if hasattr(self, "lbl_res"):
            self.lbl_res.setText(I18n.t("win_res_header"))
        if hasattr(self, "lbl_res_w"):
            self.lbl_res_w.setText(I18n.t("width_label"))
        if hasattr(self, "lbl_res_h"):
            self.lbl_res_h.setText(I18n.t("height_label"))
        if hasattr(self, "chk_fullscreen"):
            self.chk_fullscreen.setText(I18n.t("start_fullscreen"))
        if hasattr(self, "lbl_log_section"):
            self.lbl_log_section.setText(I18n.t("logging_header"))
        if hasattr(self, "chk_auto_log_window"):
            self.chk_auto_log_window.setText(I18n.t("auto_log_window"))
        if hasattr(self, "btn_open_log_window"):
            self.btn_open_log_window.setText(I18n.t("view_log_window"))
        if hasattr(self, "lbl_mp"):
            self.lbl_mp.setText(I18n.t("auto_pair_header"))
        if hasattr(self, "lbl_mp_sub"):
            self.lbl_mp_sub.setText(I18n.t("auto_pair_sub"))
        if hasattr(self, "chk_auto_sodium"):
            self.chk_auto_sodium.setText(I18n.t("auto_pair_check"))
        if hasattr(self, "lbl_mc"):
            self.lbl_mc.setText(I18n.t("multicore_header"))
        if hasattr(self, "lbl_mc_sub"):
            self.lbl_mc_sub.setText(I18n.t("multicore_sub", cores=os.cpu_count() or 4))
        if hasattr(self, "chk_multicore"):
            self.chk_multicore.setText(I18n.t("multicore_enable"))
        if hasattr(self, "lbl_mc_cores"):
            self.lbl_mc_cores.setText(I18n.t("multicore_cores_lbl"))
        self._populate_multicore_cores_dropdown()
        if hasattr(self, "lbl_mc_threads"):
            self.lbl_mc_threads.setText(I18n.t("multicore_threads_lbl"))
        self._populate_multicore_dropdown()
        if hasattr(self, "lbl_mc_tip"):
            self.lbl_mc_tip.setText(I18n.t("multicore_tip"))
        for c in getattr(self, "card_widgets", []):
            if not sip.isdeleted(c) and hasattr(c, "retranslate_ui"):
                c.retranslate_ui()
        if hasattr(self, "lbl_tos_hdr"):
            self.lbl_tos_hdr.setText(I18n.t("tos_card_header"))
        if hasattr(self, "lbl_tos_note"):
            self.lbl_tos_note.setText(I18n.t("tos_card_note", versions=", ".join(SUPPORTED_MC_VERSIONS)))
        if hasattr(self, "btn_review_tos"):
            self.btn_review_tos.setText(I18n.t("btn_review_tos"))
        if hasattr(self, "btn_whats_new"):
            self.btn_whats_new.setText(I18n.t("btn_view_whats_new"))
        if hasattr(self, "lbl_folders"):
            self.lbl_folders.setText(I18n.t("folders"))
        if hasattr(self, "folder_row_labels"):
            for k, lbl_w in self.folder_row_labels:
                lbl_w.setText(I18n.t(k))
        if hasattr(self, "folder_browse_buttons"):
            for b in self.folder_browse_buttons:
                b.setText(I18n.t("browse"))

        # Instances & Accounts settings headers + dynamic cards
        if hasattr(self, "lbl_inst_mgr_hdr"):
            self.lbl_inst_mgr_hdr.setText(I18n.t("inst_mgr_header"))
        if hasattr(self, "btn_inst_import"):
            self.btn_inst_import.setText(I18n.t("import_btn"))
        if hasattr(self, "btn_inst_new"):
            self.btn_inst_new.setText(I18n.t("new_instance"))
        if hasattr(self, "lbl_accounts_mgmt"):
            self.lbl_accounts_mgmt.setText(I18n.t("accounts_mgmt"))
        if hasattr(self, "lbl_accounts_sub"):
            self.lbl_accounts_sub.setText(I18n.t("accounts_sub"))
        if hasattr(self, "btn_s_off"):
            self.btn_s_off.setText(I18n.t("add_offline"))
        if hasattr(self, "btn_s_ms"):
            self.btn_s_ms.setText(I18n.t("add_ms"))

        # Language page
        if hasattr(self, "lbl_lang_header"):
            self.lbl_lang_header.setText(I18n.t("language"))
        if hasattr(self, "lbl_lang_sub"):
            self.lbl_lang_sub.setText(I18n.t("language_sub"))

        # Proxy page
        if hasattr(self, "lbl_proxy_title"):
            self.lbl_proxy_title.setText(I18n.t("proxy_title"))
        if hasattr(self, "lbl_proxy_notice"):
            self.lbl_proxy_notice.setText(I18n.t("proxy_notice"))
        if hasattr(self, "btn_proxy_none"):
            self.btn_proxy_none.setText(I18n.t("proxy_none"))
        if hasattr(self, "lbl_proxy_host"):
            self.lbl_proxy_host.setText(I18n.t("proxy_host"))
        if hasattr(self, "lbl_proxy_port"):
            self.lbl_proxy_port.setText(I18n.t("proxy_port"))
        if hasattr(self, "btn_apply_proxy"):
            self.btn_apply_proxy.setText(I18n.t("apply_proxy"))

        # Experimental page
        if hasattr(self, "lbl_exp_hdr"):
            self.lbl_exp_hdr.setText(I18n.t("exp_header"))
        if hasattr(self, "lbl_exp_note"):
            self.lbl_exp_note.setText(I18n.t("exp_note"))
        if hasattr(self, "btn_redeem"):
            self.btn_redeem.setText(I18n.t("exp_redeem"))
        if hasattr(self, "chk_experimental"):
            self.chk_experimental.setText(I18n.t("exp_enable"))
        if hasattr(self, "lbl_horizon_title"):
            self.lbl_horizon_title.setText(I18n.t("horizon_title"))
        if hasattr(self, "lbl_horizon_desc"):
            self.lbl_horizon_desc.setText(I18n.t("horizon_desc"))
        if hasattr(self, "lbl_horizon_inst"):
            self.lbl_horizon_inst.setText(I18n.t("horizon_inst_lbl"))
        if hasattr(self, "horizon_instance_input"):
            self.horizon_instance_input.setPlaceholderText(I18n.t("horizon_inst_ph"))
        if hasattr(self, "btn_horizon_setup"):
            self.btn_horizon_setup.setText(I18n.t("horizon_setup"))
        if hasattr(self, "btn_horizon_locate"):
            self.btn_horizon_locate.setText(I18n.t("horizon_locate"))
        if hasattr(self, "btn_horizon_site"):
            self.btn_horizon_site.setText(I18n.t("horizon_site"))
        # Premium / Support steps cards (shown in both Premium & Donations tabs)
        for card in getattr(self, "_support_step_cards", []):
            card["hdr"].setText(I18n.t("donate_page_hdr"))
            card["sub"].setText(I18n.t("donate_page_sub"))
            card["opt1_hdr"].setText(I18n.t("donate_opt1_hdr"))
            card["steps"].setText(I18n.t("donate_steps_body"))
            card["btn_discord"].setText(I18n.t("donate_join_discord_btn"))
            card["opt2_hdr"].setText(I18n.t("donate_opt2_hdr"))
            card["opt2_desc"].setText(I18n.t("donate_opt2_desc"))
            card["btn_patreon"].setText(I18n.t("donate_open_patreon_btn"))

        if hasattr(self, "lbl_donate_discord_hdr"):
            self.lbl_donate_discord_hdr.setText(I18n.t("donate_discord_hdr"))
        if hasattr(self, "lbl_donate_discord_sub"):
            self.lbl_donate_discord_sub.setText(I18n.t("donate_discord_sub"))
        if hasattr(self, "btn_donate_join_discord"):
            self.btn_donate_join_discord.setText(I18n.t("action_join_discord"))
        if hasattr(self, "btn_donate_go_premium"):
            self.btn_donate_go_premium.setText(I18n.t("donate_go_redeem_btn"))

        if hasattr(self, "exp_status_chip"):
            self._refresh_experimental_ui()

        # Updates tab & Settings Updates page
        if hasattr(self, "lbl_upd_title"):
            self.lbl_upd_title.setText(I18n.t("updates_header"))
        if hasattr(self, "lbl_version"):
            self.lbl_version.setText(f"{I18n.t('client_name')}  v{APP_VERSION}")
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.setText(I18n.t("check_updates_btn"))
        if hasattr(self, "btn_download_update"):
            self.btn_download_update.setText(I18n.t("download_update_btn"))
        if hasattr(self, "chk_auto_update"):
            self.chk_auto_update.setText(I18n.t("auto_check_updates"))

        if hasattr(self, "lbl_tab_upd_hdr"):
            self.lbl_tab_upd_hdr.setText(I18n.t("updates_tab_header"))
        if hasattr(self, "lbl_tab_upd_ver"):
            self.lbl_tab_upd_ver.setText(I18n.t("installed_version", ver=APP_VERSION))
        if hasattr(self, "btn_tab_check_update"):
            self.btn_tab_check_update.setText(I18n.t("check_updates_btn"))
        if hasattr(self, "btn_tab_download_update"):
            self.btn_tab_download_update.setText(I18n.t("download_update_btn"))
        if hasattr(self, "chk_tab_auto_update"):
            self.chk_tab_auto_update.setText(I18n.t("auto_check_updates_client"))
        if hasattr(self, "lbl_tab_vers_hdr"):
            self.lbl_tab_vers_hdr.setText(I18n.t("supported_versions_hdr"))
        if hasattr(self, "lbl_tab_vers_sub"):
            self.lbl_tab_vers_sub.setText(I18n.t("supported_versions_sub", versions=", ".join(SUPPORTED_MC_VERSIONS)))
        if hasattr(self, "btn_tab_wn"):
            self.btn_tab_wn.setText(I18n.t("open_whats_new_btn"))
        if hasattr(self, "btn_tab_tos"):
            self.btn_tab_tos.setText(I18n.t("tos_disclaimer_btn"))

        if hasattr(self, "btn_banner_notes"):
            self.btn_banner_notes.setText(I18n.t("tab_updates"))
        if hasattr(self, "btn_banner_update"):
            self.btn_banner_update.setText(I18n.t("download_update_btn"))
        if hasattr(self, "lbl_update_banner") and getattr(self, "_update_info", None):
            if self._update_info.get("available") and self._update_info.get("latest"):
                self.lbl_update_banner.setText(I18n.t("update_banner_msg", ver=self._update_info["latest"]))

        if not getattr(self, "_pending_update_ui", None):
            if hasattr(self, "update_status"):
                self.update_status.setText(I18n.t("updates_idle"))
            if hasattr(self, "upd_tab_status"):
                self.upd_tab_status.setText(I18n.t("updates_idle"))

        self._refresh_tos_status_labels()
        if hasattr(self, "inst_mgr"):
            self.refresh_instances()
            self.refresh_accounts()

    def _create_support_steps_card(self) -> QFrame:
        """Reusable 1-2-3 Discord payment steps + Instant Patreon redirect card for Premium & Donations."""
        if not hasattr(self, "_support_step_cards"):
            self._support_step_cards = []

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)

        lbl_hdr = QLabel(I18n.t("donate_page_hdr"))
        lbl_hdr.setObjectName("SectionLabel")
        cl.addWidget(lbl_hdr)

        lbl_sub = QLabel(I18n.t("donate_page_sub"))
        lbl_sub.setObjectName("MutedLabel")
        lbl_sub.setWordWrap(True)
        cl.addWidget(lbl_sub)

        # Option 1: Discord -> #paid-donations -> Patreon
        lbl_opt1 = QLabel(I18n.t("donate_opt1_hdr"))
        lbl_opt1.setObjectName("SectionLabel")
        lbl_opt1.setStyleSheet("font-size: 11px; letter-spacing: 0.6px; padding-top: 4px; background: transparent; border: none;")
        cl.addWidget(lbl_opt1)

        lbl_steps = QLabel(I18n.t("donate_steps_body"))
        lbl_steps.setWordWrap(True)
        lbl_steps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_steps.setStyleSheet("font-size: 13px; line-height: 1.45; padding: 6px 10px; border-radius: 8px; background-color: rgba(255,255,255,0.04);")
        cl.addWidget(lbl_steps)

        discord_row = QHBoxLayout()
        discord_row.setSpacing(10)
        btn_discord = AnimatedButton(I18n.t("donate_join_discord_btn"))
        btn_discord.setObjectName("PillButton")
        btn_discord.setFixedHeight(36)
        btn_discord.clicked.connect(lambda: webbrowser.open(DISCORD_INVITE_URL))
        discord_row.addWidget(btn_discord)

        lbl_discord_url = QLabel(f'<a href="{DISCORD_INVITE_URL}" style="color: #FF8822; text-decoration: none;">{DISCORD_INVITE_URL}</a>')
        lbl_discord_url.setOpenExternalLinks(True)
        lbl_discord_url.setStyleSheet("font-size: 12px; background: transparent; border: none;")
        discord_row.addWidget(lbl_discord_url, stretch=1)
        cl.addLayout(discord_row)

        # Option 2: Instant Patreon (skip Discord)
        lbl_opt2 = QLabel(I18n.t("donate_opt2_hdr"))
        lbl_opt2.setObjectName("SectionLabel")
        lbl_opt2.setStyleSheet("font-size: 11px; letter-spacing: 0.6px; padding-top: 8px; background: transparent; border: none;")
        cl.addWidget(lbl_opt2)

        lbl_opt2_desc = QLabel(I18n.t("donate_opt2_desc"))
        lbl_opt2_desc.setObjectName("MutedLabel")
        lbl_opt2_desc.setWordWrap(True)
        cl.addWidget(lbl_opt2_desc)

        patreon_row = QHBoxLayout()
        patreon_row.setSpacing(10)
        btn_patreon = AnimatedButton(I18n.t("donate_open_patreon_btn"))
        btn_patreon.setObjectName("PlayButton")
        btn_patreon.setFixedHeight(38)
        btn_patreon.clicked.connect(lambda: webbrowser.open(PATREON_DONATE_URL))
        patreon_row.addWidget(btn_patreon)
        patreon_row.addStretch(1)
        cl.addLayout(patreon_row)

        self._support_step_cards.append({
            "hdr": lbl_hdr,
            "sub": lbl_sub,
            "opt1_hdr": lbl_opt1,
            "steps": lbl_steps,
            "btn_discord": btn_discord,
            "opt2_hdr": lbl_opt2,
            "opt2_desc": lbl_opt2_desc,
            "btn_patreon": btn_patreon,
        })
        return card

    # ================= PREMIUM FEATURES (access code) =================
    def _build_experimental_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 4)
        layout.setSpacing(12)

        access_card = QFrame()
        access_card.setObjectName("Card")
        ac_l = QVBoxLayout(access_card)
        ac_l.setContentsMargins(18, 16, 18, 16)
        ac_l.setSpacing(10)

        head = QHBoxLayout()
        self.lbl_exp_hdr = QLabel(I18n.t("exp_header"))
        self.lbl_exp_hdr.setObjectName("SectionLabel")
        head.addWidget(self.lbl_exp_hdr)
        head.addStretch(1)
        self.exp_status_chip = QLabel("")
        head.addWidget(self.exp_status_chip)
        ac_l.addLayout(head)

        self.lbl_exp_note = QLabel(I18n.t("exp_note"))
        self.lbl_exp_note.setObjectName("MutedLabel")
        self.lbl_exp_note.setWordWrap(True)
        ac_l.addWidget(self.lbl_exp_note)

        self.exp_code_row = QWidget()
        row = QHBoxLayout(self.exp_code_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.exp_code_input = QLineEdit()
        self.exp_code_input.setPlaceholderText("LCX-XXXXX-XXXXX-XXXXX")
        self.exp_code_input.setMaxLength(24)
        self.exp_code_input.setFixedHeight(40)
        self.exp_code_input.returnPressed.connect(self.redeem_experimental_code)
        row.addWidget(self.exp_code_input, stretch=1)
        self.btn_redeem = AnimatedButton(I18n.t("exp_redeem"))
        self.btn_redeem.setObjectName("PlayButton")
        self.btn_redeem.setFixedHeight(40)
        self.btn_redeem.setMinimumWidth(110)
        self.btn_redeem.clicked.connect(self.redeem_experimental_code)
        row.addWidget(self.btn_redeem)
        ac_l.addWidget(self.exp_code_row)

        self.exp_msg = QLabel("")
        self.exp_msg.setObjectName("MutedLabel")
        self.exp_msg.setWordWrap(True)
        ac_l.addWidget(self.exp_msg)
        layout.addWidget(access_card)

        # How to pay / obtain a Premium access code (1-2-3 steps + Instant Patreon)
        layout.addWidget(self._create_support_steps_card())

        # Everything below is only usable once a valid code is redeemed.
        self.exp_features_frame = QFrame()
        self.exp_features_frame.setObjectName("Card")
        fl = QVBoxLayout(self.exp_features_frame)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(10)
        self.chk_experimental = SwitchCheckBox(I18n.t("exp_enable"))
        self.chk_experimental.setChecked(bool(self.config.get("experimental_enabled", False)))
        self.chk_experimental.toggled.connect(lambda v: self.config.set("experimental_enabled", bool(v)))
        fl.addWidget(self.chk_experimental)
        # >>> Put the switches / buttons of your premium features here (inside fl). <<<
        # Anywhere else in the launcher, gate a feature with:  if self.experimental_active(): ...
        self._build_horizon_section(fl)
        layout.addWidget(self.exp_features_frame)

        layout.addStretch()
        self._refresh_experimental_ui()

        # The page got longer than the window: let it scroll (setWidget() re-enables the grey auto-fill, so turn it off after).
        page.setObjectName("ExperimentalPage")
        page.setStyleSheet("QWidget#ExperimentalPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def _build_donations_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 4)
        layout.setSpacing(12)

        layout.addWidget(self._create_support_steps_card())

        discord_card = QFrame()
        discord_card.setObjectName("Card")
        dc_l = QVBoxLayout(discord_card)
        dc_l.setContentsMargins(18, 16, 18, 16)
        dc_l.setSpacing(10)

        self.lbl_donate_discord_hdr = QLabel(I18n.t("donate_discord_hdr"))
        self.lbl_donate_discord_hdr.setObjectName("SectionLabel")
        dc_l.addWidget(self.lbl_donate_discord_hdr)

        self.lbl_donate_discord_sub = QLabel(I18n.t("donate_discord_sub"))
        self.lbl_donate_discord_sub.setObjectName("MutedLabel")
        self.lbl_donate_discord_sub.setWordWrap(True)
        dc_l.addWidget(self.lbl_donate_discord_sub)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_donate_join_discord = AnimatedButton(I18n.t("action_join_discord"))
        self.btn_donate_join_discord.setObjectName("PillButton")
        self.btn_donate_join_discord.setFixedHeight(38)
        self.btn_donate_join_discord.clicked.connect(lambda: webbrowser.open(DISCORD_INVITE_URL))
        btn_row.addWidget(self.btn_donate_join_discord)

        self.btn_donate_go_premium = AnimatedButton(I18n.t("donate_go_redeem_btn"))
        self.btn_donate_go_premium.setObjectName("PillButton")
        self.btn_donate_go_premium.setFixedHeight(38)
        self.btn_donate_go_premium.clicked.connect(lambda: self.open_settings_subpage(5))
        btn_row.addWidget(self.btn_donate_go_premium)
        btn_row.addStretch(1)
        dc_l.addLayout(btn_row)

        layout.addWidget(discord_card)
        layout.addStretch()

        page.setObjectName("DonationsPage")
        page.setStyleSheet("QWidget#DonationsPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    # ------------------------------------------------------------------ Horizon (Rust client)

    def _build_horizon_section(self, fl):
        fl.addSpacing(8)
        self.lbl_horizon_title = QLabel(I18n.t("horizon_title"))
        self.lbl_horizon_title.setObjectName("SectionLabel")
        fl.addWidget(self.lbl_horizon_title)

        self.lbl_horizon_desc = QLabel(I18n.t("horizon_desc"))
        self.lbl_horizon_desc.setObjectName("MutedLabel")
        self.lbl_horizon_desc.setWordWrap(True)
        fl.addWidget(self.lbl_horizon_desc)

        self.horizon_status_launcher = QLabel("")
        self.horizon_status_files = QLabel("")
        self.horizon_status_inst = QLabel("")
        for lbl in (self.horizon_status_launcher, self.horizon_status_files, self.horizon_status_inst):
            lbl.setObjectName("MutedLabel")
            lbl.setWordWrap(True)
            fl.addWidget(lbl)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.lbl_horizon_inst = QLabel(I18n.t("horizon_inst_lbl"))
        self.lbl_horizon_inst.setObjectName("MutedLabel")
        name_row.addWidget(self.lbl_horizon_inst)
        self.horizon_instance_input = QLineEdit(str(self.config.get(hb.CONFIG_INSTANCE_KEY, "")))
        self.horizon_instance_input.setPlaceholderText(I18n.t("horizon_inst_ph"))
        self.horizon_instance_input.setFixedHeight(34)
        self.horizon_instance_input.editingFinished.connect(self._save_horizon_instance_name)
        name_row.addWidget(self.horizon_instance_input, stretch=1)
        fl.addLayout(name_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_horizon_setup = AnimatedButton(I18n.t("horizon_setup"))
        self.btn_horizon_setup.setObjectName("PlayButton")
        self.btn_horizon_setup.setFixedHeight(38)
        self.btn_horizon_setup.clicked.connect(self.horizon_setup)
        btn_row.addWidget(self.btn_horizon_setup, stretch=1)
        self.btn_horizon_locate = AnimatedButton(I18n.t("horizon_locate"))
        self.btn_horizon_locate.setObjectName("PillButton")
        self.btn_horizon_locate.setFixedHeight(38)
        self.btn_horizon_locate.clicked.connect(self.horizon_locate_launcher)
        btn_row.addWidget(self.btn_horizon_locate)
        self.btn_horizon_site = AnimatedButton(I18n.t("horizon_site"))
        self.btn_horizon_site.setObjectName("PillButton")
        self.btn_horizon_site.setFixedHeight(38)
        self.btn_horizon_site.clicked.connect(lambda: webbrowser.open(hb.HORIZON_SITE))
        btn_row.addWidget(self.btn_horizon_site)
        fl.addLayout(btn_row)

        self.horizon_msg = QLabel("")
        self.horizon_msg.setObjectName("MutedLabel")
        self.horizon_msg.setWordWrap(True)
        fl.addWidget(self.horizon_msg)

        self._refresh_horizon_status()

    def _save_horizon_instance_name(self):
        self.config.set(hb.CONFIG_INSTANCE_KEY, self.horizon_instance_input.text().strip())

    def _refresh_horizon_status(self):
        if not hasattr(self, "horizon_status_launcher"):
            return
        launcher = hb.find_launcher(self.config.get(hb.CONFIG_PATH_KEY))
        files_ok, why = hb.minecraft_files_ready(self.config.get("game_dir"))
        has_instance = any(hb.is_horizon_instance(i) for i in self.inst_mgr.list_instances())

        def mark(ok):
            return "\u2714" if ok else "\u2716"

        self.horizon_status_launcher.setText(f"{mark(launcher)}  Horizon launcher: {launcher or 'not found'}")
        self.horizon_status_files.setText(
            f"{mark(files_ok)}  Minecraft {hb.HORIZON_MC_VERSION} files in LowCore: {'ready' if files_ok else why}")
        self.horizon_status_inst.setText(
            f"{mark(has_instance)}  \"{hb.INSTANCE_DISPLAY_NAME}\" instance: {'created' if has_instance else 'not created yet'}")

    def horizon_locate_launcher(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Horizon's launcher", os.path.expanduser("~"),
            "Horizon launcher (horizon-launcher*);;All files (*)")
        if not path:
            return
        if not hb.validate_launcher_path(path):
            self.show_alert("Not Horizon's launcher",
                            "Please choose Horizon's launcher program (for example horizon-launcher.exe).", is_error=True)
            return
        self.config.set(hb.CONFIG_PATH_KEY, path)
        self.horizon_msg.setText("Launcher saved. Press \"Set up Horizon\" to continue.")
        self._refresh_horizon_status()

    def horizon_setup(self):
        launcher = hb.find_launcher(self.config.get(hb.CONFIG_PATH_KEY))
        if not launcher:
            self.show_alert(
                "Horizon launcher needed",
                f"Download Horizon's launcher from {hb.HORIZON_SITE} (only from the official site) and install it.\n\n"
                "Then press \"Locate launcher...\" here if LowCore does not find it by itself.", is_error=True)
            return

        self.btn_horizon_setup.setEnabled(False)
        self.horizon_msg.setText("Setting up Horizon. This can take several minutes...")
        worker = HorizonSetupWorker(launcher, self.config.get("game_dir"), self.inst_mgr)
        worker.signals.progress.connect(lambda desc, cur, tot: self.horizon_msg.setText(desc))
        worker.signals.log.connect(self.append_log_line)
        worker.signals.finished.connect(self._horizon_setup_done)
        worker.signals.error.connect(self._horizon_setup_failed)
        self.threadpool.start(worker)

    def _horizon_setup_done(self):
        self.btn_horizon_setup.setEnabled(True)
        self.horizon_msg.setText(f"Done. Pick \"{hb.INSTANCE_DISPLAY_NAME}\" on the Play tab and press PLAY.")
        self._refresh_horizon_status()
        self.refresh_instances()

    def _horizon_setup_failed(self, err: str):
        self.btn_horizon_setup.setEnabled(True)
        self.horizon_msg.setText("Set-up stopped. See the Console Log for details.")
        self._refresh_horizon_status()
        self.show_alert("Horizon set-up failed", err, is_error=True)

    def experimental_active(self) -> bool:
        """True only with a valid access code AND the 'Enable experimental features' switch on."""
        return self.license.is_unlocked() and bool(self.config.get("experimental_enabled", False))

    def _set_exp_message(self, text: str, ok: bool = None):
        color = "#3FB950" if ok is True else ("#E5534B" if ok is False else None)
        base = "font-size: 12px; font-weight: 600; background: transparent; border: none;"
        self.exp_msg.setStyleSheet(f"{base} color: {color};" if color else "")
        self.exp_msg.setText(text)

    def _refresh_experimental_ui(self):
        if not hasattr(self, "exp_status_chip"):
            return
        self._refresh_horizon_status()
        unlocked = self.license.is_unlocked()
        if unlocked:
            self.exp_status_chip.setText(I18n.t("exp_unlocked"))
            self.exp_status_chip.setStyleSheet(
                "background-color: rgba(63,185,80,0.16); color: #3FB950; border-radius: 9px;"
                "padding: 2px 12px; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        else:
            self.exp_status_chip.setText(I18n.t("exp_locked"))
            self.exp_status_chip.setStyleSheet(
                "background-color: rgba(160,160,170,0.16); color: #A0A0AA; border-radius: 9px;"
                "padding: 2px 12px; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        self.exp_code_row.setVisible(not unlocked)
        self.exp_features_frame.setEnabled(unlocked)
        if unlocked:
            when = self.license.redeemed_at()
            stamp = time.strftime("%Y-%m-%d", time.localtime(when)) if when else ""
            if not self.exp_msg.text():
                self._set_exp_message(f"Access code redeemed{(' on ' + stamp) if stamp else ''}." )

    def redeem_experimental_code(self):
        now = time.time()
        if now < self._redeem_locked_until:
            self._set_exp_message(f"Too many tries. Wait {int(self._redeem_locked_until - now) + 1} seconds.", ok=False)
            return
        ok, msg = self.license.redeem(self.exp_code_input.text())
        if ok:
            self._redeem_fails = 0
            self.exp_code_input.clear()
            self._set_exp_message(msg, ok=True)
        else:
            self._redeem_fails += 1
            if self._redeem_fails >= 5:
                self._redeem_fails = 0
                self._redeem_locked_until = now + 60
                msg += " Too many tries, wait 60 seconds."
            self._set_exp_message(msg, ok=False)
        self._refresh_experimental_ui()

    # ================= UPDATES =================
    def _build_updates_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        upd_card = QFrame()
        upd_card.setObjectName("Card")
        uc_l = QVBoxLayout(upd_card)
        uc_l.setContentsMargins(18, 16, 18, 16)
        uc_l.setSpacing(10)

        self.lbl_upd_title = QLabel(I18n.t("updates_header"))
        self.lbl_upd_title.setObjectName("SectionLabel")
        uc_l.addWidget(self.lbl_upd_title)

        self.lbl_version = QLabel(f"{I18n.t('client_name')}  v{APP_VERSION}")
        self.lbl_version.setStyleSheet("font-size: 16px; font-weight: 800; background: transparent; border: none;")
        uc_l.addWidget(self.lbl_version)

        self.update_status = QLabel(I18n.t("updates_idle"))
        self.update_status.setObjectName("MutedLabel")
        self.update_status.setWordWrap(True)
        uc_l.addWidget(self.update_status)

        self.update_notes = QLabel("")
        self.update_notes.setObjectName("MutedLabel")
        self.update_notes.setWordWrap(True)
        self.update_notes.setVisible(False)
        uc_l.addWidget(self.update_notes)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_check_update = AnimatedButton(I18n.t("check_updates_btn"))
        self.btn_check_update.setObjectName("PillButton")
        self.btn_check_update.setFixedHeight(38)
        self.btn_check_update.setMinimumWidth(148)
        self.btn_check_update.clicked.connect(lambda: self.check_for_updates(silent=False))
        btn_row.addWidget(self.btn_check_update)
        self.btn_download_update = AnimatedButton(I18n.t("download_update_btn"))
        self.btn_download_update.setObjectName("PlayButton")
        self.btn_download_update.setFixedHeight(38)
        self.btn_download_update.setMinimumWidth(148)
        self.btn_download_update.setVisible(False)
        self.btn_download_update.clicked.connect(self.open_update_download)
        btn_row.addWidget(self.btn_download_update)
        btn_row.addStretch(1)
        uc_l.addLayout(btn_row)
        layout.addWidget(upd_card)

        auto_card = QFrame()
        auto_card.setObjectName("Card")
        ac_l = QVBoxLayout(auto_card)
        ac_l.setContentsMargins(18, 14, 18, 14)
        self.chk_auto_update = SwitchCheckBox(I18n.t("auto_check_updates"))
        self.chk_auto_update.setChecked(bool(self.config.get("check_updates", True)))
        self.chk_auto_update.toggled.connect(self._on_auto_update_toggled)
        ac_l.addWidget(self.chk_auto_update)
        layout.addWidget(auto_card)

        layout.addStretch()
        self._apply_pending_update_ui()
        return page

    def _build_updates_tab_page(self):
        """Dedicated top-level Updates Tab showing releases, supported versions, What's New & lowcore.jar Disclaimer."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 6, 4)
        layout.setSpacing(12)

        # ---- Card 1: Software Updates ----
        upd_card = QFrame()
        upd_card.setObjectName("Card")
        uc_l = QVBoxLayout(upd_card)
        uc_l.setContentsMargins(18, 16, 18, 16)
        uc_l.setSpacing(10)

        self.lbl_tab_upd_hdr = QLabel(I18n.t("updates_tab_header"))
        self.lbl_tab_upd_hdr.setObjectName("SectionLabel")
        uc_l.addWidget(self.lbl_tab_upd_hdr)

        self.lbl_tab_upd_ver = QLabel(I18n.t("installed_version", ver=APP_VERSION))
        self.lbl_tab_upd_ver.setStyleSheet("font-size: 16px; font-weight: 800; background: transparent; border: none;")
        uc_l.addWidget(self.lbl_tab_upd_ver)

        self.upd_tab_status = QLabel(I18n.t("updates_idle"))
        self.upd_tab_status.setObjectName("MutedLabel")
        self.upd_tab_status.setWordWrap(True)
        uc_l.addWidget(self.upd_tab_status)

        self.upd_tab_notes = QLabel("")
        self.upd_tab_notes.setObjectName("MutedLabel")
        self.upd_tab_notes.setWordWrap(True)
        self.upd_tab_notes.setVisible(False)
        uc_l.addWidget(self.upd_tab_notes)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_tab_check_update = AnimatedButton(I18n.t("check_updates_btn"))
        self.btn_tab_check_update.setObjectName("PlayButton")
        self.btn_tab_check_update.setFixedHeight(38)
        self.btn_tab_check_update.setMinimumWidth(160)
        self.btn_tab_check_update.clicked.connect(lambda: self.check_for_updates(silent=False))
        btn_row.addWidget(self.btn_tab_check_update)

        self.btn_tab_download_update = AnimatedButton(I18n.t("download_update_btn"))
        self.btn_tab_download_update.setObjectName("PillButton")
        self.btn_tab_download_update.setFixedHeight(38)
        self.btn_tab_download_update.setMinimumWidth(148)
        self.btn_tab_download_update.setVisible(False)
        self.btn_tab_download_update.clicked.connect(self.open_update_download)
        btn_row.addWidget(self.btn_tab_download_update)
        btn_row.addStretch(1)
        uc_l.addLayout(btn_row)

        self.chk_tab_auto_update = SwitchCheckBox(I18n.t("auto_check_updates_client"))
        self.chk_tab_auto_update.setChecked(bool(self.config.get("check_updates", True)))
        self.chk_tab_auto_update.toggled.connect(self._on_auto_update_toggled)
        uc_l.addWidget(self.chk_tab_auto_update)
        layout.addWidget(upd_card)

        # ---- Card 2: Available Versions & What's New ----
        vers_card = QFrame()
        vers_card.setObjectName("Card")
        vc_l = QVBoxLayout(vers_card)
        vc_l.setContentsMargins(18, 16, 18, 16)
        vc_l.setSpacing(10)

        self.lbl_tab_vers_hdr = QLabel(I18n.t("supported_versions_hdr"))
        self.lbl_tab_vers_hdr.setObjectName("SectionLabel")
        vc_l.addWidget(self.lbl_tab_vers_hdr)

        self.lbl_tab_vers_sub = QLabel(I18n.t("supported_versions_sub", versions=", ".join(SUPPORTED_MC_VERSIONS)))
        self.lbl_tab_vers_sub.setObjectName("MutedLabel")
        self.lbl_tab_vers_sub.setWordWrap(True)
        vc_l.addWidget(self.lbl_tab_vers_sub)

        hl_row = QHBoxLayout()
        hl_row.setSpacing(10)
        self.btn_tab_wn = AnimatedButton(I18n.t("open_whats_new_btn"))
        self.btn_tab_wn.setObjectName("PillButton")
        self.btn_tab_wn.setFixedHeight(36)
        self.btn_tab_wn.clicked.connect(self.open_whats_new_dialog)
        hl_row.addWidget(self.btn_tab_wn)

        self.btn_tab_tos = AnimatedButton(I18n.t("tos_disclaimer_btn"))
        self.btn_tab_tos.setObjectName("PillButton")
        self.btn_tab_tos.setFixedHeight(36)
        self.btn_tab_tos.clicked.connect(lambda: self.open_tos_dialog(require_acceptance=False))
        hl_row.addWidget(self.btn_tab_tos)
        hl_row.addStretch(1)
        vc_l.addLayout(hl_row)
        layout.addWidget(vers_card)

        # ---- Card 3: lowcore.jar Disclaimer ----
        disc_card = QFrame()
        disc_card.setObjectName("Card")
        dc_l = QVBoxLayout(disc_card)
        dc_l.setContentsMargins(18, 16, 18, 16)
        dc_l.setSpacing(8)

        disc_lbl = QLabel(LOWCORE_JAR_DISCLAIMER_TEXT)
        disc_lbl.setObjectName("MutedLabel")
        disc_lbl.setWordWrap(True)
        dc_l.addWidget(disc_lbl)

        self.lbl_tab_tos_status = QLabel("")
        self.lbl_tab_tos_status.setObjectName("SectionLabel")
        self._refresh_tos_status_labels()
        dc_l.addWidget(self.lbl_tab_tos_status)
        layout.addWidget(disc_card)

        layout.addStretch(1)

        page.setObjectName("UpdatesTabPage")
        page.setStyleSheet("QWidget#UpdatesTabPage { background: transparent; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def _on_auto_update_toggled(self, val: bool):
        val = bool(val)
        self.config.set("check_updates", val)
        for attr in ("chk_auto_update", "chk_tab_auto_update"):
            chk = getattr(self, attr, None)
            if chk is not None and chk.isChecked() != val:
                chk.blockSignals(True)
                chk.setChecked(val)
                chk.blockSignals(False)

    def _apply_pending_update_ui(self):
        state = getattr(self, "_pending_update_ui", None)
        if not state:
            return
        status_txt = state.get("status", "")
        notes = state.get("notes", "")
        dl_vis = bool(state.get("download_visible", False))
        avail = bool(state.get("available", False))
        latest = str(state.get("latest", "") or "")

        if hasattr(self, "updates_nav_btn"):
            self.updates_nav_btn.set_badge(avail, latest)

        if hasattr(self, "update_banner"):
            if avail and latest:
                self.lbl_update_banner.setText(I18n.t("update_banner_msg", ver=latest))
                self.btn_banner_update.setVisible(dl_vis)
                self.update_banner.setVisible(True)
            else:
                self.update_banner.setVisible(False)

        if hasattr(self, "update_status"):
            self.update_status.setText(status_txt)
            self.update_notes.setText(notes)
            self.update_notes.setVisible(bool(notes))
            self.btn_download_update.setVisible(dl_vis)

        if hasattr(self, "upd_tab_status"):
            self.upd_tab_status.setText(status_txt)
            self.upd_tab_notes.setText(notes)
            self.upd_tab_notes.setVisible(bool(notes))
            self.btn_tab_download_update.setVisible(dl_vis)

    def _startup_update_check(self):
        if self.config.get("check_updates", True):
            self.check_for_updates(silent=True)

    def check_for_updates(self, silent: bool = False):
        if not UPDATE_MANIFEST_URL:
            if not silent:
                self._pending_update_ui = {
                    "status": "Update checking isn't set up in this build yet.",
                    "notes": "",
                    "download_visible": False,
                    "available": False,
                    "latest": "",
                }
                self._apply_pending_update_ui()
            return
        if self._update_check_running:
            return
        self._update_check_running = True
        self._update_silent = silent
        if not silent:
            if hasattr(self, "update_status"):
                self.update_status.setText(I18n.t("updates_checking"))
            if hasattr(self, "upd_tab_status"):
                self.upd_tab_status.setText(I18n.t("updates_checking"))
            for btn_name in ("btn_check_update", "btn_tab_check_update"):
                b = getattr(self, btn_name, None)
                if b is not None:
                    b.setEnabled(False)
        worker = UpdateCheckWorker(UPDATE_MANIFEST_URL, APP_VERSION)
        worker.signals.done.connect(self._on_update_result)
        worker.signals.failed.connect(self._on_update_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_update_failed(self, err: str):
        self._update_check_running = False
        for btn_name in ("btn_check_update", "btn_tab_check_update"):
            b = getattr(self, btn_name, None)
            if b is not None:
                b.setEnabled(True)
        if not self._update_silent:
            msg = f"Couldn't check for updates: {err}"
            self._pending_update_ui = {
                "status": msg,
                "notes": "",
                "download_visible": False,
                "available": False,
                "latest": "",
            }
            self._apply_pending_update_ui()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def _on_update_result(self, info: dict):
        self._update_check_running = False
        for btn_name in ("btn_check_update", "btn_tab_check_update"):
            b = getattr(self, btn_name, None)
            if b is not None:
                b.setEnabled(True)
        self.config.set("last_update_check", time.time())

        if self.license.set_revoked(info.get("revoked", [])):
            self._refresh_experimental_ui()

        self._update_info = info
        prompt_needed = False
        if info.get("available"):
            latest = str(info.get("latest", "") or "")
            notes = info.get("notes") or []
            notes_txt = "\n".join(f"•  {n}" for n in notes[:8]) if notes else ""
            mode = info.get("mode", "browser")
            can_install = mode in ("delta_manifest", "patch_zip", "github_tree_delta", "exe_swap") or bool(info.get("url"))
            mode_hint = (
                "  (In-place delta patch — only changed files will be downloaded)"
                if mode in ("delta_manifest", "patch_zip", "github_tree_delta")
                else ("  (Direct in-place executable update)" if mode == "exe_swap" else "")
            )
            self._pending_update_ui = {
                "status": f"Version {latest} is available (you have {info['current']}).{mode_hint}",
                "notes": notes_txt,
                "download_visible": can_install,
                "available": True,
                "latest": latest,
            }
            snoozed_ver = self.config.get("update_snoozed_version", "")
            snoozed_until = float(self.config.get("update_snoozed_until", 0) or 0)
            if self._update_silent and not (snoozed_ver == latest and time.time() < snoozed_until):
                prompt_needed = True
        else:
            self._pending_update_ui = {
                "status": f"You're up to date (v{info['current']}).",
                "notes": "",
                "download_visible": False,
                "available": False,
                "latest": "",
            }
        self._apply_pending_update_ui()
        if prompt_needed:
            self._prompt_update(info)
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def _prompt_update(self, info: dict):
        notes = info.get("notes") or []
        info_text = "\n".join(f"•  {n}" for n in notes[:6]) if notes else ""
        mode = info.get("mode", "browser")
        can_install = mode in ("delta_manifest", "patch_zip", "github_tree_delta", "exe_swap") or bool(info.get("url"))
        if can_install:
            btns = [("Later", "secondary", False), ("Install Update", "primary", True)]
        else:
            btns = [("OK", "primary", True)]
        dlg = StyledMessageDialog(
            "Update available",
            f"LowCore Client {info['latest']} is available.",
            kind="info",
            buttons=btns,
            informative_text=info_text,
            theme_name=self.current_theme,
            parent=self,
        )
        dlg.exec()
        if can_install and dlg.clicked_label == "Install Update":
            self.open_update_download()
        else:
            # Snooze popup for 12 hours instead of permanently hiding; the Play banner & header dot remain visible
            self.config.set("update_snoozed_version", info["latest"])
            self.config.set("update_snoozed_until", time.time() + 12 * 3600)

    def _set_update_buttons_enabled(self, enabled: bool):
        for btn_name in ("btn_check_update", "btn_tab_check_update", "btn_download_update", "btn_tab_download_update", "btn_banner_update"):
            b = getattr(self, btn_name, None)
            if b is not None:
                b.setEnabled(enabled)

    def _set_update_status_text(self, text: str):
        if hasattr(self, "update_status"):
            self.update_status.setText(text)
        if hasattr(self, "upd_tab_status"):
            self.upd_tab_status.setText(text)

    def open_update_download(self):
        info = self._update_info or {}
        mode = info.get("mode", "browser")
        if mode in ("delta_manifest", "patch_zip", "github_tree_delta", "exe_swap"):
            if getattr(self, "_update_install_running", False):
                return
            self._update_install_running = True
            self._set_update_buttons_enabled(False)
            self._set_update_status_text("Preparing incremental update...")
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            worker = UpdateInstallWorker(info, app_dir)
            worker.signals.progress.connect(lambda msg, _c, _t: self._set_update_status_text(msg))
            worker.signals.done.connect(self._on_in_place_update_done)
            worker.signals.failed.connect(self._on_in_place_update_failed)
            QThreadPool.globalInstance().start(worker)
            return

        url = info.get("url", "")
        if url.lower().startswith("https://"):
            webbrowser.open(url)

    def _on_in_place_update_done(self, res: dict):
        self._update_install_running = False
        self._set_update_buttons_enabled(True)
        updated = res.get("updated_files") or []
        skipped = int(res.get("skipped_files", 0) or 0)
        kb = max(1, round(int(res.get("bytes_downloaded", 0) or 0) / 1024))
        relaunch_script = res.get("relaunch_script", "")

        if not updated:
            self._set_update_status_text("All local launcher files are already up to date.")
            self.show_alert("Up to Date", "Your launcher files already match the latest release.")
            return

        summary = f"Updated {len(updated)} file(s) ({kb:,} KB downloaded, {skipped} unchanged file(s) skipped)."
        self._set_update_status_text(summary)
        dlg = StyledMessageDialog(
            "Update Installed",
            f"LowCore Client v{(self._update_info or {}).get('latest', '')} is ready.",
            kind="info",
            buttons=[("Later", "secondary", False), ("Restart Now", "primary", True)],
            informative_text=summary + "\nRestart LowCore Client now to load the updated version.",
            theme_name=self.current_theme,
            parent=self,
        )
        dlg.exec()
        if dlg.clicked_label == "Restart Now":
            from core import updater as app_updater
            app_updater.spawn_relaunch(relaunch_script)
            self.quit_application()

    def _on_in_place_update_failed(self, err: str):
        self._update_install_running = False
        self._set_update_buttons_enabled(True)
        self._set_update_status_text(f"Incremental update failed: {err}")
        url = (self._update_info or {}).get("url", "")
        if url.lower().startswith("https://"):
            dlg = StyledMessageDialog(
                "Update Error",
                "Could not apply the incremental patch automatically.",
                kind="error",
                buttons=[("Close", "secondary", False), ("Open Browser Download", "primary", True)],
                informative_text=str(err),
                theme_name=self.current_theme,
                parent=self,
            )
            dlg.exec()
            if dlg.clicked_label == "Open Browser Download":
                webbrowser.open(url)
        else:
            self.show_alert("Update Error", f"Could not install update:\n{err}", is_error=True)

    def _build_proxy_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        proxy_card = QFrame()
        proxy_card.setObjectName("Card")
        pc_l = QVBoxLayout(proxy_card)
        pc_l.setContentsMargins(18, 16, 18, 16)
        pc_l.setSpacing(12)

        self.lbl_proxy_title = QLabel(I18n.t("proxy_title"))
        self.lbl_proxy_title.setObjectName("SectionLabel")
        pc_l.addWidget(self.lbl_proxy_title)

        self.lbl_proxy_notice = QLabel(I18n.t("proxy_notice"))
        self.lbl_proxy_notice.setObjectName("MutedLabel")
        self.lbl_proxy_notice.setWordWrap(True)
        pc_l.addWidget(self.lbl_proxy_notice)

        # Keep QRadioButton state synchronized behind crisp segmented mode pills
        self.rb_no_proxy = QRadioButton("None")
        self.rb_socks5 = QRadioButton("SOCKS5")
        self.rb_http = QRadioButton("HTTP")
        self.rb_no_proxy.setChecked(True)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_proxy_none = ProxyModeButton(I18n.t("proxy_none"), self)
        self.btn_proxy_http = ProxyModeButton("HTTP", self)
        self.btn_proxy_socks5 = ProxyModeButton("SOCKS5", self)
        self._proxy_mode_btns = [self.btn_proxy_none, self.btn_proxy_http, self.btn_proxy_socks5]

        self.btn_proxy_none.clicked.connect(lambda: self._select_proxy_mode("none"))
        self.btn_proxy_http.clicked.connect(lambda: self._select_proxy_mode("http"))
        self.btn_proxy_socks5.clicked.connect(lambda: self._select_proxy_mode("socks5"))
        for b in self._proxy_mode_btns:
            mode_row.addWidget(b, stretch=1)
        pc_l.addLayout(mode_row)

        host_row = QHBoxLayout()
        host_row.setSpacing(10)

        h_col = QVBoxLayout()
        h_col.setSpacing(4)
        self.lbl_proxy_host = QLabel(I18n.t("proxy_host"))
        self.lbl_proxy_host.setObjectName("SectionLabel")
        h_col.addWidget(self.lbl_proxy_host)
        self.proxy_host = QLineEdit("127.0.0.1")
        self.proxy_host.setFixedHeight(38)
        h_col.addWidget(self.proxy_host)
        host_row.addLayout(h_col, stretch=3)

        p_col = QVBoxLayout()
        p_col.setSpacing(4)
        self.lbl_proxy_port = QLabel(I18n.t("proxy_port"))
        self.lbl_proxy_port.setObjectName("SectionLabel")
        p_col.addWidget(self.lbl_proxy_port)
        self.proxy_port = QSpinBox()
        self.proxy_port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.proxy_port.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(8080)
        self.proxy_port.setFixedHeight(38)
        self.proxy_port.setMinimumWidth(110)
        p_col.addWidget(self.proxy_port)
        host_row.addLayout(p_col, stretch=1)

        pc_l.addLayout(host_row)

        self.btn_apply_proxy = AnimatedButton(I18n.t("apply_proxy"))
        self.btn_apply_proxy.setObjectName("PlayButton")
        self.btn_apply_proxy.setFixedHeight(40)
        self.btn_apply_proxy.clicked.connect(self.apply_proxy)
        pc_l.addWidget(self.btn_apply_proxy)

        self._select_proxy_mode("none")
        layout.addWidget(proxy_card)
        layout.addStretch()
        return page

    def _select_proxy_mode(self, mode: str):
        self.rb_no_proxy.setChecked(mode == "none")
        self.rb_http.setChecked(mode == "http")
        self.rb_socks5.setChecked(mode == "socks5")
        if hasattr(self, "btn_proxy_none"):
            self.btn_proxy_none.set_selected(mode == "none")
            self.btn_proxy_http.set_selected(mode == "http")
            self.btn_proxy_socks5.set_selected(mode == "socks5")
        enabled = mode in ("http", "socks5")
        if hasattr(self, "proxy_host"):
            self.proxy_host.setEnabled(enabled)
        if hasattr(self, "proxy_port"):
            self.proxy_port.setEnabled(enabled)

    def apply_proxy(self):
        if self.rb_no_proxy.isChecked():
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
            self.show_alert("Proxy", "Proxy disabled.")
        elif self.rb_http.isChecked():
            QNetworkProxy.setApplicationProxy(
                QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, self.proxy_host.text(), self.proxy_port.value())
            )
            self.show_alert("Proxy", f"HTTP Proxy set to {self.proxy_host.text()}:{self.proxy_port.value()}")
        elif self.rb_socks5.isChecked():
            QNetworkProxy.setApplicationProxy(
                QNetworkProxy(QNetworkProxy.ProxyType.Socks5Proxy, self.proxy_host.text(), self.proxy_port.value())
            )
            self.show_alert("Proxy", f"SOCKS5 Proxy set to {self.proxy_host.text()}:{self.proxy_port.value()}")

    def on_browser_instance_changed(self, index: int = -1):
        if self.sender() == self.browser_target_inst:
            self.content_browser_user_overridden = True

        if self.stack.currentIndex() == 1:
            self.run_mod_search()

    def open_current_instance_folder(self):
        inst_data = self.instance_box.currentData()
        if inst_data and inst_data.get("path"):
            path = inst_data["path"]
            if os.path.exists(path):
                self._open_dir(path)

    def open_selected_settings_instance_folder(self):
        if not hasattr(self, "settings_inst_list"):
            return
        item = self.settings_inst_list.currentItem()
        inst = item.data(Qt.ItemDataRole.UserRole) if item else None
        if inst and inst.get("path") and os.path.exists(inst["path"]):
            self._open_dir(inst["path"])

    def delete_instance_by_index(self, index: int):
        inst_data = self.instance_box.itemData(index)
        if not inst_data:
            return
        self._confirm_delete_instance(inst_data)

    def _confirm_delete_instance(self, inst_data: dict):
        if not inst_data:
            return
        name = inst_data.get("name", "Unknown")
        path = inst_data.get("path")

        if StyledMessageDialog.confirm(
            self,
            "Delete Instance",
            f"Are you sure you want to delete instance '{name}'?\n\nThis will permanently remove its mods, saves, and configs.",
            kind="warning",
            danger=True,
        ):
            if self.inst_mgr.delete_instance(path):
                self.content_browser_user_overridden = False
                self.refresh_instances()
                self.show_alert("Deleted", f"Instance '{name}' was deleted.")
            else:
                self.show_alert("Error", f"Failed to delete directory: {path}", is_error=True)

    def delete_account_by_index(self, index: int):
        acc_id = self.account_box.itemData(index)
        if not acc_id:
            return
        self.delete_account_by_id(acc_id)

    def delete_account_by_id(self, acc_id: str):
        if not acc_id:
            return
        accs = self.config.get("accounts", {})
        acc_data = accs.get(acc_id, {})
        uname = acc_data.get("name", "Account")

        if StyledMessageDialog.confirm(
            self,
            "Remove Account",
            f"Remove account '{uname}' from LowCore Client?",
            kind="question",
            danger=True,
        ):
            if acc_id in accs:
                del accs[acc_id]
                self.config.set("accounts", accs)
                if self.config.get("active_account") == acc_id:
                    self.config.set("active_account", list(accs.keys())[0] if accs else "")
                self.refresh_accounts()
                self.show_alert("Removed", f"Account '{uname}' removed.")

    def activate_account_by_id(self, acc_id: str):
        if not acc_id:
            return
        self.config.set("active_account", acc_id)
        if hasattr(self, "account_box"):
            self.account_box.blockSignals(True)
            for idx in range(self.account_box.count()):
                if self.account_box.itemData(idx) == acc_id:
                    self.account_box.setCurrentIndex(idx)
                    break
            self.account_box.blockSignals(False)
        for card in getattr(self, "_settings_acc_cards", []):
            if not sip.isdeleted(card):
                card.set_active(card.acc_id == acc_id)

    def delete_selected_settings_instance(self):
        if not hasattr(self, "settings_inst_list"):
            return
        item = self.settings_inst_list.currentItem()
        target_inst = item.data(Qt.ItemDataRole.UserRole) if item else None
        if target_inst:
            self._confirm_delete_instance(target_inst)

    def edit_selected_settings_instance(self):
        if not hasattr(self, "settings_inst_list"):
            return
        item = self.settings_inst_list.currentItem()
        target_inst = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not target_inst:
            self.show_alert("No Instance", "Select an instance from the list to edit.", is_error=True)
            return
        self.edit_instance(target_inst)

    def change_instance_block(self, inst_data: dict):
        if not inst_data or not inst_data.get("path"):
            return
        cur_icon = inst_data.get("icon", "grass")
        dlg = BlockPickerDialog(cur_icon, self.current_theme, self)
        ok = dlg.exec()
        chosen = dlg.get_selected_block() if ok else None
        dlg.deleteLater()
        _prune_large_block_cache()
        if not ok:
            QTimer.singleShot(80, lambda: _trim_process_memory(True))
            return
        try:
            self.inst_mgr.set_instance_icon(inst_data["path"], chosen)
        except Exception as e:
            self.show_alert("Error", f"Could not save instance block icon:\n{e}", is_error=True)
            return
        self.refresh_instances()
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def edit_instance(self, inst_data: dict):
        if not inst_data or not inst_data.get("path"):
            return
        try:
            running = self.active_process is not None and self.active_process.poll() is None
        except Exception:
            running = False
        if running:
            self.show_alert(
                "Game Running",
                "Please close or kill Minecraft before editing an instance.",
                is_error=True,
            )
            return

        dlg = EditInstanceDialog(inst_data, self.all_mojang_versions, self.current_theme, self)
        ok = dlg.exec()
        data = dlg.get_data() if ok else None
        dlg.deleteLater()
        if not ok:
            QTimer.singleShot(80, lambda: _trim_process_memory(True))
            return
        try:
            updated = self.inst_mgr.update_instance(
                inst_data["path"],
                new_name=data["name"],
                new_version=data["version"],
                new_loader=data["loader"],
                new_icon=data.get("icon"),
            )
        except FileExistsError as e:
            self.show_alert("Folder Exists", str(e), is_error=True)
            return
        except Exception as e:
            self.show_alert("Update Failed", f"Could not update instance:\n{e}", is_error=True)
            return

        saved_active = self.config.get("active_instance", "")
        if saved_active in (updated["old_folder"], inst_data.get("name", ""), ""):
            self.config.set("active_instance", updated["new_folder"])

        self.refresh_instances()
        self.status_lbl.setText(I18n.t("ready"))
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def change_active_instance_block(self):
        inst_data = self.instance_box.currentData()
        if inst_data:
            self.change_instance_block(inst_data)

    def delete_current_account(self):
        acc_id = self.account_box.currentData()
        if not acc_id:
            self.show_alert("No Account", "No account selected to delete.", is_error=True)
            return
        self.delete_account_by_id(acc_id)

    def _position_drawer_widgets(self):
        if not hasattr(self, "root_frame") or not hasattr(self, "side_drawer"):
            return
        _s = RoundedRoot.SHADOW
        inner = self.root_frame.rect().adjusted(_s + 1, _s + 1, -(_s + 1), -(_s + 1))
        top_y = _s + 112
        scrim_y = top_y - 4
        scrim_h = max(0, inner.bottom() - scrim_y)
        self._drawer_scrim.setGeometry(inner.x(), scrim_y, inner.width(), scrim_h)
        drawer_h = max(180, inner.bottom() - top_y - 16)
        self.side_drawer.setGeometry(_s + 28, top_y, self.side_drawer.width(), drawer_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_drawer_widgets()

    def open_side_drawer(self):
        if not hasattr(self, "side_drawer"):
            return
        self._position_drawer_widgets()
        self._drawer_scrim.setVisible(True)
        self._drawer_scrim.raise_()
        self.side_drawer.set_open(True)
        self.side_drawer.raise_()
        for _btn in getattr(self, "win_buttons", []):
            _btn.raise_()
        if hasattr(self, "menu_btn"):
            self.menu_btn.set_active(True)

    def close_side_drawer(self):
        if hasattr(self, "_drawer_scrim"):
            self._drawer_scrim.setVisible(False)
        if hasattr(self, "side_drawer"):
            self.side_drawer.set_open(False)
        if hasattr(self, "menu_btn"):
            self.menu_btn.set_active(False)

    def toggle_side_drawer(self):
        if hasattr(self, "side_drawer") and self.side_drawer.is_open:
            self.close_side_drawer()
        else:
            self.open_side_drawer()

    def toggle_settings_tab(self):
        self.close_side_drawer()
        if self.stack.currentIndex() == 2:
            target = getattr(self, "_last_non_settings_tab", 0)
            if target == 2:
                target = 0
        else:
            target = 2
        self.side_drawer.select_tab(target)

    def toggle_updates_tab(self):
        self.close_side_drawer()
        if self.stack.currentIndex() == 4:
            target = getattr(self, "_last_non_settings_tab", 0)
            if target in (2, 4):
                target = 0
        else:
            target = 4
        self.side_drawer.select_tab(target)

    def _sync_drawer_active_state(self):
        if not hasattr(self, "side_drawer"):
            return
        idx = self.stack.currentIndex()
        if idx == 2 and hasattr(self, "settings_sidebar"):
            sub = self.settings_sidebar.currentRow()
            if sub in (1, 2, 5, 6, 7):
                self.side_drawer.set_active_key(f"settings_{sub}")
            else:
                self.side_drawer.set_active_key("settings_0")
        else:
            self.side_drawer.set_active_key(f"tab_{idx}")

    def _ensure_settings_page(self, row: int):
        if not hasattr(self, "settings_subpages") or not hasattr(self, "_settings_builders"):
            return
        if row < 0 or row >= len(self._settings_builders):
            return
        if row in self._built_settings_pages:
            return
        self._built_settings_pages.add(row)
        builder = self._settings_builders[row]
        real_page = builder()
        old = self.settings_subpages.widget(row)
        self.settings_subpages.insertWidget(row, real_page)
        if old is not None:
            self.settings_subpages.removeWidget(old)
            old.deleteLater()
        self.settings_subpages.setCurrentIndex(row)

        theme_dict = ThemeManager.get_theme_data(self.current_theme)
        if hasattr(self, "lbl_proxy_notice"):
            self.lbl_proxy_notice.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {theme_dict['text_sub']}; border: none; background: transparent;"
            )
        for _card in getattr(self, "_language_cards", []):
            _card.set_theme_colors(theme_dict)
        for _btn in getattr(self, "_proxy_mode_btns", []):
            _btn.set_theme_colors(theme_dict)
        for _dd in real_page.findChildren(CustomDropdown):
            _dd.set_theme_colors(theme_dict)
        if row == 1:
            self.refresh_instances()
        elif row == 2:
            self.refresh_accounts()
        self.retranslate_ui()

    def _on_settings_row_changed(self, row: int):
        if row < 0:
            return
        if self.stack.currentIndex() == 2:
            self._ensure_settings_page(row)
        if hasattr(self, "settings_subpages"):
            self.settings_subpages.setCurrentIndex(row)
        self._sync_drawer_active_state()

    def open_settings_subpage(self, sub_row: int):
        if hasattr(self, "settings_sidebar") and 0 <= sub_row < self.settings_sidebar.count():
            self.settings_sidebar.setCurrentRow(sub_row)
            self._ensure_settings_page(sub_row)
        self.on_tab_switch(2)

    def open_active_instance_mods(self):
        inst_data = self.instance_box.currentData()
        if not inst_data or not inst_data.get("path"):
            self.show_alert("No Instance", "Create or select an instance first to manage its installed mods.", is_error=True)
            return
        self.open_mods_manager(os.path.join(inst_data["path"], "mods"))

    def on_drawer_action(self, action_id: str):
        self.close_side_drawer()
        if action_id == "new_instance":
            self.prompt_new_instance()
        elif action_id == "import_instances":
            self.prompt_import_instances()
        elif action_id == "manage_mods":
            self.open_active_instance_mods()
        elif action_id == "open_folder":
            inst_data = self.instance_box.currentData()
            if not inst_data or not inst_data.get("path"):
                self.show_alert("No Instance", "Create or select an instance first to open its folder.", is_error=True)
            else:
                self.open_current_instance_folder()
        elif action_id == "join_discord":
            webbrowser.open(DISCORD_INVITE_URL)

    def on_tab_switch(self, index: int):
        prev_idx = self.stack.currentIndex()
        if index == 2 and hasattr(self, "settings_sidebar"):
            row = max(0, self.settings_sidebar.currentRow())
            self._ensure_settings_page(row)
        self.stack.setCurrentIndex(index)
        self.easter_egg_buffer = ""
        if index not in (2, 4):
            self._last_non_settings_tab = index
        if hasattr(self, "settings_gear_btn"):
            self.settings_gear_btn.set_active(index == 2)
        if hasattr(self, "updates_nav_btn"):
            self.updates_nav_btn.set_active(index == 4)
        self._sync_drawer_active_state()
        self.close_side_drawer()
        if prev_idx == 1 and index != 1:
            # Release Modrinth search cards and icon caches when leaving Content Browser
            self.mod_results_list.clear()
            self.card_widgets.clear()
            ICON_CACHE.clear()
            QTimer.singleShot(80, lambda: _trim_process_memory(True))
        elif prev_idx == 2 and index != 2:
            QTimer.singleShot(80, lambda: _trim_process_memory(True))
        if index == 0:
            self.update_instance_info()
        elif index == 1:
            self.run_mod_search()
        elif index == 3:
            self.refresh_main_console_display()

    def animate_progress_bar(self, expand: bool):
        self.progress_anim = QPropertyAnimation(self.progress_bar, b"maximumHeight")
        self.progress_anim.setDuration(220)
        self.progress_anim.setStartValue(self.progress_bar.height())
        self.progress_anim.setEndValue(8 if expand else 0)
        self.progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.progress_anim.start()

    def show_alert(self, title: str, text: str, is_error: bool = False):
        StyledMessageDialog.alert(self, title, text, is_error=is_error)

    @staticmethod
    def _versions_cache_path() -> str:
        return os.path.join(os.path.expanduser("~"), ".lowcorelauncher", "versions_cache.json")

    @classmethod
    def _load_cached_versions(cls, max_age: int = 48 * 3600):
        try:
            path = cls._versions_cache_path()
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            releases = data.get("releases")
            updated = float(data.get("updated", 0) or 0)
            if releases and len(releases) > 5 and (time.time() - updated) < max_age:
                return tuple(str(v) for v in releases)
        except Exception:
            pass
        return None

    @classmethod
    def _save_cached_versions(cls, releases: tuple):
        try:
            path = cls._versions_cache_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"updated": time.time(), "releases": list(releases)}, f)
            os.replace(tmp, path)
        except Exception:
            pass

    def _on_versions_loaded(self, releases: tuple):
        if releases:
            self.all_mojang_versions = releases
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def fetch_all_versions(self):
        cached = self._load_cached_versions(max_age=48 * 3600)
        if cached:
            self.all_mojang_versions = cached
            return

        def fetch():
            try:
                from core.version_downloader import VersionDownloader
                downloader = VersionDownloader(self.config.get("game_dir"))
                manifest = downloader.fetch_manifest()
                releases = tuple(v["id"] for v in manifest["versions"] if v.get("type") == "release")
                del downloader, manifest
                if releases:
                    self._save_cached_versions(releases)
                    self.versions_loaded.emit(releases)
            except Exception:
                pass
        self.threadpool.start(fetch)

    def refresh_instances(self):
        self.instance_box.blockSignals(True)
        self.browser_target_inst.blockSignals(True)
        try:
            self.instance_box.clear()
            self.browser_target_inst.clear()
            if hasattr(self, "settings_inst_list"):
                self.settings_inst_list.clear()
            if hasattr(self, "_settings_inst_cards"):
                self._settings_inst_cards.clear()

            instances = [inst for inst in self.inst_mgr.list_instances() if inst.get("name") != "Default-1211"]
            saved_active = self.config.get("active_instance", "")
            target_idx = 0
            theme_data = ThemeManager.get_theme_data(self.current_theme)

            if hasattr(self, "lbl_inst_count"):
                cnt = len(instances)
                self.lbl_inst_count.setText(I18n.t("inst_count_line", count=cnt))

            if not instances:
                self.instance_box.addItem(I18n.t("no_inst_placeholder"), userData=None)
                self.instance_box.set_placeholder_mode(True)
                self.status_lbl.setText(I18n.t("no_active_inst"))
                if hasattr(self, "settings_inst_list"):
                    empty_item = QListWidgetItem(I18n.t("no_inst_empty"))
                    empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
                    self.settings_inst_list.addItem(empty_item)
            else:
                self.instance_box.set_placeholder_mode(False)
                for idx, inst in enumerate(instances):
                    inst_folder = os.path.basename(inst["path"])
                    if inst_folder == saved_active or inst["name"] == saved_active:
                        target_idx = idx

                for idx, inst in enumerate(instances):
                    total_played = format_playtime(inst.get("playtime_seconds", 0))
                    block_pix = get_minecraft_block_pixmap(inst.get("icon", "grass"), 22)

                    play_display = f"{inst['name']}  ·  {inst.get('loader', 'Fabric')} {inst['version']}  ({total_played})"
                    self.instance_box.addItem(play_display, userData=inst, icon=block_pix)

                    browser_display = f"{inst['name']}  ·  {inst.get('loader', 'Fabric')} {inst['version']}"
                    self.browser_target_inst.addItem(browser_display, userData=inst, icon=block_pix)

                    if hasattr(self, "settings_inst_list"):
                        list_item = QListWidgetItem()
                        list_item.setSizeHint(QSize(0, 74))
                        list_item.setData(Qt.ItemDataRole.UserRole, inst)
                        card = SettingsInstanceCard(inst, is_active=(idx == target_idx), theme_dict=theme_data, parent=self.settings_inst_list)
                        card.editRequested.connect(self.edit_instance)
                        card.blockRequested.connect(self.change_instance_block)
                        card.folderRequested.connect(lambda d: self._open_dir(d["path"]) if d.get("path") else None)
                        card.deleteRequested.connect(self._confirm_delete_instance)
                        self.settings_inst_list.addItem(list_item)
                        self.settings_inst_list.setItemWidget(list_item, card)
                        self._settings_inst_cards.append(card)

                self.instance_box.setCurrentIndex(target_idx)
                self.browser_target_inst.setCurrentIndex(target_idx)
                self.content_browser_user_overridden = False
                if hasattr(self, "settings_inst_list") and self.settings_inst_list.count() > target_idx:
                    self.settings_inst_list.setCurrentRow(target_idx)
        finally:
            self.instance_box.blockSignals(False)
            self.browser_target_inst.blockSignals(False)

        self.update_instance_info()

    def update_instance_info(self):
        if not hasattr(self, "stat_playtime_val"):
            return

        inst = self.instance_box.currentData()
        path = inst.get("path") if isinstance(inst, dict) else None
        if not path:
            if hasattr(self, "instance_showcase"):
                self.instance_showcase.set_instance(None)
            for lbl in (self.stat_playtime_val, self.stat_mods_val, self.stat_last_val):
                lbl.setText("—")
            return

        meta = inst
        try:
            with open(os.path.join(path, "instance.json"), "r", encoding="utf-8") as f:
                meta = json.load(f)
                meta["path"] = path
        except Exception:
            pass

        if hasattr(self, "instance_showcase"):
            self.instance_showcase.set_instance(meta)
        self.stat_playtime_val.setText(format_playtime(int(meta.get("playtime_seconds", 0))))
        self.stat_last_val.setText(format_last_played(meta.get("last_played")))

        if str(meta.get("loader", inst.get("loader", ""))).strip().lower() in ("vanilla", "horizon"):
            self.stat_mods_val.setText("—")
        else:
            try:
                count = sum(1 for f in os.listdir(os.path.join(path, "mods")) if f.lower().endswith(".jar"))
            except OSError:
                count = 0
            self.stat_mods_val.setText(str(count))

    def on_instance_changed(self, index: int):
        inst_data = self.instance_box.currentData()
        if inst_data and inst_data.get("path"):
            norm_path = os.path.normcase(os.path.abspath(inst_data["path"]))
            folder_name = os.path.basename(inst_data["path"])
            self.config.set("active_instance", folder_name)
            self.content_browser_user_overridden = False

            self.browser_target_inst.blockSignals(True)
            try:
                for b_idx in range(self.browser_target_inst.count()):
                    b_data = self.browser_target_inst.itemData(b_idx)
                    b_path = b_data.get("path", "") if isinstance(b_data, dict) else ""
                    if b_path and (
                        os.path.normcase(os.path.abspath(b_path)) == norm_path
                        or os.path.basename(b_path) == folder_name
                    ):
                        self.browser_target_inst.setCurrentIndex(b_idx)
                        break
            finally:
                self.browser_target_inst.blockSignals(False)

            for i, card in enumerate(getattr(self, "_settings_inst_cards", [])):
                if not sip.isdeleted(card):
                    c_folder = os.path.basename(card.inst_data.get("path", ""))
                    is_cur = c_folder == folder_name
                    card.set_active(is_cur)
                    if is_cur and hasattr(self, "settings_inst_list"):
                        self.settings_inst_list.setCurrentRow(i)

        self.update_instance_info()

    def prompt_new_instance(self):
        dlg = NewInstanceDialog(self.all_mojang_versions, self.current_theme, self)
        ok = dlg.exec()
        data = dlg.get_data() if ok else None
        dlg.deleteLater()
        if ok:
            new_inst = self.inst_mgr.create_instance(
                name=data["name"],
                version=data["version"],
                loader=data["loader"],
                icon=data.get("icon", "grass"),
            )
            self.content_browser_user_overridden = False
            self.config.set("active_instance", os.path.basename(new_inst["path"]))
            self.refresh_instances()
            self.status_lbl.setText(I18n.t("ready"))
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def prompt_import_instances(self):
        dlg = ImportInstancesDialog(self.inst_mgr, self.current_theme, self)
        dlg.exec()
        imported = list(dlg.imported_folders)
        dlg.deleteLater()
        if imported:
            self.content_browser_user_overridden = False
            self.config.set("active_instance", imported[-1])
            self.refresh_instances()
            self.status_lbl.setText(I18n.t("ready"))
            self.show_alert("Import complete", f"Imported {len(imported)} instance(s). The last one is now selected.")
        QTimer.singleShot(80, lambda: _trim_process_memory(True))

    def on_search_text_changed(self, text: str):
        self.search_debounce_timer.start()

    def run_mod_search(self):
        self.search_debounce_timer.stop()
        query = self.mod_search_input.text().strip()
        inst_data = self.browser_target_inst.currentData() or self.instance_box.currentData() or {}
        ver = inst_data.get("version", "1.21.1")

        if hb.is_horizon_instance(inst_data):
            self.mod_results_list.clear()
            self.card_widgets.clear()
            note = QListWidgetItem("Horizon instances don't use Fabric/Forge mods (Horizon has its own mod system).")
            note.setFlags(Qt.ItemFlag.NoItemFlags)
            self.mod_results_list.addItem(note)
            return

        p_type = self.content_type_bar.get_selected_type()
        loader = inst_data.get("loader", "fabric").lower() if p_type == "mod" else None

        self.mod_results_list.clear()
        self.card_widgets.clear()

        label_type = "Resource Pack" if p_type == "resourcepack" else p_type.capitalize()
        loading_item = QListWidgetItem(f"Searching {label_type}s on Modrinth...")
        loading_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.mod_results_list.addItem(loading_item)

        worker = ModSearchWorker(query, ver, loader, p_type)
        worker.signals.results_ready.connect(self.display_mod_results)
        worker.signals.error.connect(lambda err: self.display_mod_results([]))
        self.threadpool.start(worker)

    @staticmethod
    def _get_content_subfolder(p_type: str) -> str:
        if p_type == "shader":
            return "shaderpacks"
        if p_type == "resourcepack":
            return "resourcepacks"
        return "mods"

    @staticmethod
    def _norm_content_token(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (text or "").lower())

    @classmethod
    def _extract_filename_base(cls, filename: str) -> str:
        stem = os.path.splitext(filename)[0]
        if filename.lower().endswith(".jar.disabled"):
            stem = filename[:-len(".jar.disabled")]
        # Strip trailing version / loader markers like -fabric-0.6.5+mc1.21.1 or _v8.2.09 or _r5.2.2
        cleaned = re.sub(
            r"(?:[-_+ ]+(?:mc)?[vr]?\d+(?:\.\d+)*.*|[-_+]+(?:fabric|forge|neoforge|quilt|universal)(?:[-_+].*)?)$",
            "",
            stem,
            flags=re.IGNORECASE,
        )
        return cls._norm_content_token(cleaned or stem)

    @staticmethod
    def _load_content_manifest(instance_dir: str) -> dict:
        if not instance_dir:
            return {}
        m_path = os.path.join(instance_dir, ".lowcore_content_manifest.json")
        if os.path.isfile(m_path):
            try:
                with open(m_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    @staticmethod
    def _save_installed_manifest_entry(instance_dir: str, sub_folder: str, project_id: str, slug: str, title: str, files: list):
        if not instance_dir or not project_id:
            return
        m_path = os.path.join(instance_dir, ".lowcore_content_manifest.json")
        data = MainWindow._load_content_manifest(instance_dir)
        bucket = data.setdefault(sub_folder, {})
        basenames = [os.path.basename(f) for f in (files or []) if f]
        bucket[str(project_id)] = {
            "slug": slug or "",
            "title": title or "",
            "files": basenames,
        }
        try:
            with open(m_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def _build_installed_index(cls, instance_dir: str, p_type: str) -> dict:
        idx = {"project_ids": set(), "ids": set(), "bases": set()}
        if not instance_dir or not os.path.isdir(instance_dir):
            return idx

        sub_folder = cls._get_content_subfolder(p_type)
        content_dir = os.path.join(instance_dir, sub_folder)
        if not os.path.isdir(content_dir):
            return idx

        try:
            entries = os.listdir(content_dir)
        except Exception:
            return idx

        entries_lower = {e.lower() for e in entries}

        # 1. Check manifest entries whose files are still present on disk
        manifest = cls._load_content_manifest(instance_dir)
        bucket = manifest.get(sub_folder, {})
        if isinstance(bucket, dict):
            for pid, meta in bucket.items():
                if not isinstance(meta, dict):
                    continue
                rec_files = meta.get("files") or []
                if any(os.path.basename(rf).lower() in entries_lower for rf in rec_files):
                    idx["project_ids"].add(str(pid))
                    if meta.get("slug"):
                        idx["ids"].add(cls._norm_content_token(meta["slug"]))
                    if meta.get("title"):
                        idx["bases"].add(cls._norm_content_token(meta["title"]))

        # 2. Scan real files & archives in mods/ / resourcepacks/ / shaderpacks/
        import zipfile
        for name in entries:
            full_path = os.path.join(content_dir, name)
            low = name.lower()
            if p_type == "mod":
                if not (low.endswith(".jar") or low.endswith(".jar.disabled")) or not os.path.isfile(full_path):
                    continue
                base_tok = cls._extract_filename_base(name)
                if base_tok:
                    idx["bases"].add(base_tok)
                try:
                    with zipfile.ZipFile(full_path, "r") as zf:
                        if "fabric.mod.json" in zf.namelist():
                            raw = zf.read("fabric.mod.json").decode("utf-8", errors="ignore")
                            meta = json.loads(raw)
                            mod_id = meta.get("id", "")
                            mod_name = meta.get("name", "")
                            if mod_id:
                                idx["ids"].add(cls._norm_content_token(mod_id))
                            if mod_name:
                                idx["bases"].add(cls._norm_content_token(mod_name))
                        elif "quilt.mod.json" in zf.namelist():
                            raw = zf.read("quilt.mod.json").decode("utf-8", errors="ignore")
                            qmeta = json.loads(raw).get("quilt_loader", {})
                            if qmeta.get("id"):
                                idx["ids"].add(cls._norm_content_token(qmeta["id"]))
                            qname = (qmeta.get("metadata") or {}).get("name", "")
                            if qname:
                                idx["bases"].add(cls._norm_content_token(qname))
                except Exception:
                    pass
            else:
                if os.path.isdir(full_path) or low.endswith(".zip"):
                    base_tok = cls._extract_filename_base(name)
                    if base_tok:
                        idx["bases"].add(base_tok)
                    full_tok = cls._norm_content_token(os.path.splitext(name)[0])
                    if full_tok:
                        idx["ids"].add(full_tok)
        return idx

    @classmethod
    def _is_content_item_installed(cls, item: dict, installed_idx: dict, p_type: str) -> bool:
        if not item or not installed_idx:
            return False
        pid = str(item.get("project_id", "") or "")
        if pid and pid in installed_idx["project_ids"]:
            return True

        slug_tok = cls._norm_content_token(item.get("slug", ""))
        title_tok = cls._norm_content_token(item.get("title", ""))

        for tok in (slug_tok, title_tok):
            if tok and (tok in installed_idx["ids"] or tok in installed_idx["bases"]):
                return True

        if p_type in ("shader", "resourcepack"):
            for tok in (slug_tok, title_tok):
                if not tok:
                    continue
                stripped = re.sub(r"(?:shaders?|resourcepacks?|packs?)$", "", tok)
                if len(stripped) >= 3 and (stripped in installed_idx["bases"] or stripped in installed_idx["ids"]):
                    return True
        return False

    def _refresh_mod_cards_installed_state(self):
        target_inst = self.browser_target_inst.currentData() or self.instance_box.currentData() or {}
        target_dir = target_inst.get("path", "")
        p_type = self.content_type_bar.get_selected_type()
        installed_idx = self._build_installed_index(target_dir, p_type)
        for card in getattr(self, "card_widgets", []):
            if not sip.isdeleted(card):
                card.set_installed(self._is_content_item_installed(card.item_data, installed_idx, p_type))

    def display_mod_results(self, hits: list):
        self.mod_results_list.clear()
        self.card_widgets.clear()

        if not hits:
            empty_item = QListWidgetItem("No compatible assets found for this search.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.mod_results_list.addItem(empty_item)
            return

        theme_data = ThemeManager.get_theme_data(self.current_theme)
        target_inst = self.browser_target_inst.currentData() or self.instance_box.currentData() or {}
        target_dir = target_inst.get("path", "")
        p_type = self.content_type_bar.get_selected_type()
        installed_idx = self._build_installed_index(target_dir, p_type)

        for item in hits:
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(self.mod_results_list.width() - 32, 72))
            list_item.setData(Qt.ItemDataRole.UserRole, item)

            is_inst = self._is_content_item_installed(item, installed_idx, p_type)
            card = ModItemCard(item, theme_data, is_installed=is_inst, parent=self.mod_results_list)
            self.mod_results_list.addItem(list_item)
            self.mod_results_list.setItemWidget(list_item, card)
            self.card_widgets.append(card)

            icon_url = item.get("icon_url")
            if icon_url:
                loader = ModIconLoader(icon_url)
                loader.signals.loaded.connect(lambda data, c=card: self._apply_loaded_thumbnail(data, c))
                self.icon_pool.start(loader)

        if self.mod_results_list.count() > 0:
            self.mod_results_list.setCurrentRow(0)

    def _apply_loaded_thumbnail(self, data: bytes, card: ModItemCard):
        if sip.isdeleted(card):
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            card.set_thumbnail(pix)

    def on_mod_selection_changed(self, row: int):
        for idx, card in enumerate(self.card_widgets):
            if not sip.isdeleted(card):
                card.set_selected_state(idx == row)

    def install_selected_mod(self):
        item = self.mod_results_list.currentItem()
        payload = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not payload:
            self.show_alert("No Selection", "Please select a valid item from the list.", is_error=True)
            return

        if isinstance(payload, dict):
            project_id = payload.get("project_id", "")
            mod_title = payload.get("title", "Unknown")
            mod_slug = payload.get("slug", "")
            item_dict = payload
        else:
            project_id, mod_title = payload
            mod_slug = ""
            item_dict = {"project_id": project_id, "title": mod_title, "slug": ""}

        target_inst = self.browser_target_inst.currentData() or self.instance_box.currentData()
        if not target_inst:
            self.show_alert("No Instance", "Please create an instance before downloading content.", is_error=True)
            return

        target_dir = target_inst.get("path")
        chosen_version = target_inst.get("version", "1.21.1")
        chosen_loader = target_inst.get("loader", "Fabric").lower()
        p_type = self.content_type_bar.get_selected_type()
        sub_folder = self._get_content_subfolder(p_type)

        # Prevent duplicate installation if already present on disk
        installed_idx = self._build_installed_index(target_dir, p_type)
        if self._is_content_item_installed(item_dict, installed_idx, p_type):
            row = self.mod_results_list.currentRow()
            if 0 <= row < len(self.card_widgets) and not sip.isdeleted(self.card_widgets[row]):
                self.card_widgets[row].set_installed(True)
            self.show_alert(
                I18n.t("already_installed_err_title"),
                I18n.t("already_installed_err_msg", name=mod_title, folder=sub_folder),
                is_error=True,
            )
            return

        final_dest = os.path.join(target_dir, sub_folder)
        self.btn_install_mod.setEnabled(False)
        self.btn_install_mod.setText("Resolving dependencies & downloading...")

        worker = ModInstallWorker(project_id, chosen_version, chosen_loader, final_dest)

        def on_done(installed_files):
            self._save_installed_manifest_entry(target_dir, sub_folder, project_id, mod_slug, mod_title, installed_files)
            self._refresh_mod_cards_installed_state()
            self.btn_install_mod.setEnabled(True)
            self.btn_install_mod.setText(I18n.t("download_mod"))
            files_str = "\n• " + "\n• ".join(installed_files)
            self.show_alert(
                "Installed",
                f"Successfully installed into {target_inst['name']}/{sub_folder}:{files_str}"
            )

        def on_err(err_msg):
            self.btn_install_mod.setEnabled(True)
            self.btn_install_mod.setText(I18n.t("download_mod"))
            self.show_alert("Download Failed", f"Could not download asset:\n{err_msg}", is_error=True)

        worker.signals.status.connect(lambda txt: self.btn_install_mod.setText(txt))
        worker.signals.completed.connect(on_done)
        worker.signals.error.connect(on_err)
        self.threadpool.start(worker)

    def kill_active_instance(self):
        if self.active_process:
            try:
                import psutil
                from core.discord_rpc import DiscordRPCManager
                proc = psutil.Process(self.active_process.pid)
                for child in proc.children(recursive=True):
                    child.kill()
                proc.kill()
                self.status_lbl.setText("Game terminated.")
                self.launch_btn.setEnabled(True)
                self.animate_progress_bar(expand=False)
                DiscordRPCManager.get_instance().set_menu_presence()
                self.show_alert("Terminated", "Minecraft process was force-closed.")
            except Exception as e:
                self.show_alert("Error", f"Could not kill process: {e}", is_error=True)

    def on_theme_changed(self, theme_name: str):
        self.current_theme = theme_name
        self.config.set("theme_name", theme_name)
        self.apply_current_theme()
        if hasattr(self, "content_type_bar"):
            self.content_type_bar.theme_data = ThemeManager.get_theme_data(theme_name)
            self.content_type_bar.apply_styles()
        if self.stack.currentIndex() == 1:
            self.run_mod_search()
        elif self.stack.currentIndex() == 3:
            self.refresh_main_console_display()
        QTimer.singleShot(120, lambda: _trim_process_memory(True))

    def on_ram_changed(self, index: int):
        val = self.ram_dropdown.itemData(index)
        if val:
            self.config.set("allocated_ram_mb", val)

    def refresh_accounts(self):
        self.account_box.blockSignals(True)
        self.account_box.clear()
        if hasattr(self, "settings_acc_list"):
            self.settings_acc_list.clear()
        if hasattr(self, "_settings_acc_cards"):
            self._settings_acc_cards.clear()

        accounts = self.config.get("accounts", {})
        active = self.config.get("active_account", "")
        theme_data = ThemeManager.get_theme_data(self.current_theme)

        if not accounts and hasattr(self, "settings_acc_list"):
            empty_item = QListWidgetItem(I18n.t("no_acc_empty"))
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.settings_acc_list.addItem(empty_item)

        idx = 0
        target = 0
        for acc_id, acc in accounts.items():
            avatar = AvatarService.get_avatar(
                acc, size=24, blocking=False, on_ready=self.avatar_ready.emit
            )
            acc_type_str = I18n.t("acc_offline") if acc["type"] == "offline" else I18n.t("acc_microsoft")
            label = f"{acc['name']}  ·  {acc_type_str}"
            self.account_box.addItem(label, userData=acc_id, icon=avatar)

            if hasattr(self, "settings_acc_list"):
                list_item = QListWidgetItem()
                list_item.setSizeHint(QSize(0, 70))
                card_avatar = AvatarService.get_avatar(
                    acc, size=36, blocking=False, on_ready=self.avatar_ready.emit
                )
                card = SettingsAccountCard(
                    acc_id,
                    acc,
                    card_avatar,
                    is_active=(acc_id == active),
                    theme_dict=theme_data,
                    parent=self.settings_acc_list,
                )
                card.activateRequested.connect(self.activate_account_by_id)
                card.deleteRequested.connect(self.delete_account_by_id)
                self.settings_acc_list.addItem(list_item)
                self.settings_acc_list.setItemWidget(list_item, card)
                self._settings_acc_cards.append(card)

            if acc_id == active:
                target = idx
            idx += 1

        if self.account_box.count() > 0:
            self.account_box.setCurrentIndex(target)
        self.account_box.blockSignals(False)

    def on_account_changed(self, index: int):
        acc_id = self.account_box.itemData(index)
        if acc_id:
            self.config.set("active_account", acc_id)
            for card in getattr(self, "_settings_acc_cards", []):
                if not sip.isdeleted(card):
                    card.set_active(card.acc_id == acc_id)

    def add_offline_account(self):
        name, ok = StyledInputDialog.get_text(self, "New Offline Player", "Username (3–16 characters):")
        if not ok or not name.strip():
            return

        cleaned_name = name.strip()
        
        # Validate username length (Min 3, Max 16) and characters (letters, numbers, underscores)
        if not (3 <= len(cleaned_name) <= 16) or not all(c.isalnum() or c == '_' for c in cleaned_name):
            self.show_alert(
                "Invalid Username",
                "Minecraft offline usernames must be between **3 and 16 characters** long and can only contain letters, numbers, and underscores (_).",
                is_error=True
            )
            return

        from core.auth_service import AuthService
        acc = AuthService.create_offline_account(cleaned_name)
        accs = self.config.get("accounts", {})
        accs[acc["id"]] = acc
        self.config.set("accounts", accs)
        self.config.set("active_account", acc["id"])
        self.refresh_accounts()

    def add_microsoft_account(self):
        try:
            from core.auth_service import AuthService
            device_info = AuthService.start_device_code_flow()
            user_code = device_info["user_code"]
            verification_uri = device_info.get("verification_uri", "https://microsoft.com/link")
            device_code = device_info["device_code"]
            interval = device_info.get("interval", 5)
            expires_in = device_info.get("expires_in", 900)

            webbrowser.open(verification_uri)

            dialog = FramelessDialog(theme_name=self.current_theme, title="Microsoft Sign-In", parent=self)
            dialog.set_dialog_fixed_size(400, 236)
            theme_dict = ThemeManager.get_theme_data(self.current_theme)

            d_layout = dialog.body_layout
            d_layout.setContentsMargins(24, 16, 24, 18)
            d_layout.setSpacing(10)

            instruct = QLabel("Go to <b>microsoft.com/link</b> and enter this code:")
            instruct.setAlignment(Qt.AlignmentFlag.AlignCenter)
            instruct.setStyleSheet(f"font-size: 13px; color: {theme_dict['text_sub']}; border: none; background: transparent;")
            d_layout.addWidget(instruct)

            code_lbl = QLabel(user_code)
            code_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            code_lbl.setStyleSheet(f"""
                font-size: 26px;
                font-weight: 900;
                color: {theme_dict['accent']};
                letter-spacing: 3px;
                padding: 10px;
                background-color: {theme_dict['input_bg']};
                border: 1px dashed {theme_dict['accent']};
                border-radius: 8px;
            """)
            d_layout.addWidget(code_lbl)

            status = QLabel("Waiting for authorization in your browser...")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status.setStyleSheet(f"font-size: 11px; color: {theme_dict['text_sub']}; border: none; background: transparent;")
            d_layout.addWidget(status)

            cancel_btn = AnimatedButton("Cancel")
            cancel_btn.setObjectName("PillButton")
            cancel_btn.clicked.connect(dialog.reject)
            d_layout.addWidget(cancel_btn)

            worker = DeviceAuthWorker(device_code, interval, expires_in)

            def on_success():
                acc = worker.account_data
                accs = self.config.get("accounts", {})
                accs[acc["id"]] = acc
                self.config.set("accounts", accs)
                self.config.set("active_account", acc["id"])
                self.refresh_accounts()
                dialog.accept()
                self.show_alert("Welcome", f"Logged in successfully as {acc['name']}!")

            def on_failure(err_msg):
                dialog.reject()
                self.show_alert("Sign-In Failed", str(err_msg), is_error=True)

            worker.signals.progress.connect(lambda msg, cur, tot: status.setText(msg))
            worker.signals.finished.connect(on_success)
            worker.signals.error.connect(on_failure)

            self.threadpool.start(worker)
            dialog.exec()

        except Exception as e:
            self.show_alert("Error", f"Failed to start device sign-in: {e}", is_error=True)

    def handle_launch(self):
        inst_data = self.instance_box.currentData()
        if not inst_data:
            self.prompt_new_instance()
            return

        if hb.is_horizon_instance(inst_data):
            self._launch_horizon(inst_data)
            return

        active_id = self.config.get("active_account")
        account = self.config.get("accounts", {}).get(active_id)
        if not account:
            self.show_alert("No Account", "Create an Offline or Microsoft account first.", is_error=True)
            return

        if account.get("type") == "offline":
            if not StyledMessageDialog.confirm(
                self,
                "Account Offline Warning",
                "Warning: Your Minecraft account is logged in as offline, not online.\n\n"
                "You will not be able to join premium online-mode servers (HTTP 401).\n\n"
                "Are you sure you want to continue?",
                kind="warning",
                yes_text="Yes",
                no_text="No",
            ):
                return

        version = inst_data.get("version", "1.21.1")
        loader = inst_data.get("loader", "Fabric")
        instance_dir = inst_data.get("path")
        root_dir = self.config.get("game_dir")
        selected_ram = self.ram_dropdown.currentData() or 4096

        custom_res = {
            "width": self.config.get("res_width", 1280),
            "height": self.config.get("res_height", 720),
            "fullscreen": self.config.get("fullscreen", False)
        }

        self.clear_main_console()
        self.launch_btn.setEnabled(False)
        self.animate_progress_bar(expand=True)

        worker = LaunchWorker(
            inst_mgr=self.inst_mgr,
            root_dir=root_dir,
            instance_dir=instance_dir,
            version_id=version,
            loader=loader,
            account=account,
            ram_mb=selected_ram,
            custom_res=custom_res,
            parent_win=self
        )
        worker.signals.progress.connect(self.on_progress)
        worker.signals.log.connect(self.append_log_line)
        worker.signals.finished.connect(self.on_finished)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    def _launch_horizon(self, inst_data: dict):
        if not self.experimental_active():
            self.show_alert(
                "Premium feature",
                "Horizon is a Premium feature.\n\nUnlock it in Settings > Premium and switch "
                "\"Enable Premium features\" on.", is_error=True)
            return
        if not hb.find_launcher(self.config.get(hb.CONFIG_PATH_KEY)):
            self.show_alert(
                "Horizon launcher not found",
                "LowCore starts Horizon through Horizon's own launcher.\n\n"
                "Open Settings > Premium > Horizon and press \"Set up Horizon\" "
                "(or \"Locate launcher...\" if it is installed somewhere unusual).", is_error=True)
            return

        self.clear_main_console()
        self.launch_btn.setEnabled(False)
        self.animate_progress_bar(expand=True)

        worker = LaunchWorker(
            inst_mgr=self.inst_mgr,
            root_dir=self.config.get("game_dir"),
            instance_dir=inst_data.get("path"),
            version_id=inst_data.get("version", hb.HORIZON_MC_VERSION),
            loader=hb.LOADER_NAME,
            account={},
            ram_mb=0,
            custom_res={},
            parent_win=self
        )
        worker.signals.progress.connect(self.on_progress)
        worker.signals.log.connect(self.append_log_line)
        worker.signals.finished.connect(self.on_finished)
        worker.signals.error.connect(self.on_error)
        self.threadpool.start(worker)

    def on_progress(self, desc: str, cur: int, tot: int):
        self.status_lbl.setText(desc)
        if desc.startswith("Minecraft closed"):
            self.update_instance_info()
        if tot > 0:
            self.progress_bar.setMaximum(tot)
            self.progress_bar.setValue(cur)
        else:
            self.progress_bar.setMaximum(0)

    def on_finished(self):
        current = self.instance_box.currentData() or {}
        self.status_lbl.setText("Horizon is running" if hb.is_horizon_instance(current) else "Minecraft is running")
        self.animate_progress_bar(expand=False)
        self.launch_btn.setEnabled(True)
        self.refresh_instances()
        self.nav_bar.select_tab(3)
        QTimer.singleShot(250, lambda: _trim_process_memory(True))

    def on_error(self, err: str):
        self.append_log_line(f"[LAUNCH ERROR] {err}")  # previously the reason was lost when the log window opened
        self.status_lbl.setText("Launch failed / Game closed")
        self.animate_progress_bar(expand=False)
        self.launch_btn.setEnabled(True)
        self.refresh_instances()

        if self.config.get("show_log_on_exit", True):
            QTimer.singleShot(100, self.open_standalone_log_dialog)
        else:
            self.show_alert("Launch Notice", str(err), is_error=True)