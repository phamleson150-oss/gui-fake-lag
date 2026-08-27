import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes
import winsound
import json
import random
import subprocess
import urllib.request
import urllib.parse
import webbrowser
from collections import deque
from dataclasses import dataclass

import pydivert
import keyboard
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPointF, QTimer
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QRadialGradient

# ================= ĐƯỜNG DẪN THƯ MỤC CÙNG FILE .EXE =================
def get_app_dir():
    if getattr(sys, 'frozen', False):
        # Khi chạy dưới dạng file .exe đóng gói
        return os.path.dirname(sys.executable)
    else:
        # Khi chạy file .py trực tiếp
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_app_dir()
LICENSE_FILE = os.path.join(BASE_DIR, "zerox_license.json")
HOTKEY_FILE = os.path.join(BASE_DIR, "zerox_hotkey.json")
LOG_FILE = os.path.join(BASE_DIR, "debug.log")

# ================= CẤU HÌNH XÁC THỰC VPS =================
VPS_VERIFY_URL = "http://103.78.3.222:53689/api/verify_key"
GET_KEY_URL = "http://103.78.3.222:53689/"

def get_current_hwid():
    try:
        cmd = "wmic csproduct get uuid"
        raw = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        if raw:
            return raw.replace("-", "")[:16].upper()
    except Exception:
        pass
    return "HWID-DEFAULT-001"

CURRENT_HWID = get_current_hwid()

def load_saved_key():
    try:
        if os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('saved_key', '')
    except Exception:
        pass
    return ''

def save_license_key(key_str):
    try:
        with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'saved_key': key_str}, f, indent=2)
    except Exception:
        pass

def verify_key_with_vps(key_str):
    if not key_str:
        return False, "Vui lòng nhập mã Key!", 0
    try:
        url = f"{VPS_VERIFY_URL}?key={urllib.parse.quote(key_str)}&hwid={CURRENT_HWID}"
        req = urllib.request.Request(url, headers={'User-Agent': 'ZeroXClient/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            valid = res_data.get("valid", False) or res_data.get("success", False)
            msg = res_data.get("msg", "Lỗi xác thực")
            expires_at = res_data.get("expires_at", -1)
            return valid, msg, expires_at
    except Exception:
        return False, "Không thể kết nối VPS 103.78.3.222:53689!", 0

# ================= WIN32 DYNAMIC EMULATOR DETECTOR =================
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

EMULATOR_PROCESSES = [
    "hd-player.exe", "bluestacks.exe", "dnplayer.exe", 
    "nox.exe", "memu.exe", "projecttitan.exe", "androidprocess.exe", "gameloop.exe"
]

def get_process_name_by_hwnd(hwnd):
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h_proc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    if not h_proc:
        return ""
    buff = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(1024)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h_proc, 0, buff, ctypes.byref(size))
    ctypes.windll.kernel32.CloseHandle(h_proc)
    return os.path.basename(buff.value).lower()

def get_window_title(hwnd):
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value

def find_emulator_window():
    detected = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_windows_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            rect = RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            if w > 350 and h > 250:
                pname = get_process_name_by_hwnd(hwnd)
                if any(proc in pname for proc in EMULATOR_PROCESSES):
                    title = get_window_title(hwnd) or pname
                    detected.append((hwnd, title))
        return True

    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
    return detected[0] if detected else (None, "None")

# ================= CONFIG & NETWORK ENGINE =================
MASTER_FILTER = "udp and ((udp.DstPort >= 7000 and udp.DstPort <= 18000) or (udp.SrcPort >= 7000 and udp.SrcPort <= 18000))"
MAX_QUEUE_SIZE = 220
FREEZE_AUTO_DISABLE_SEC = 1.5

def debug_log(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

class AntiBan:
    _titles = ["System Settings", "Windows Update Core", "Device Manager Service", "Runtime Broker Process"]
    @staticmethod
    def get_title():
        return random.choice(AntiBan._titles)

@dataclass
class HotkeyConfig:
    key: str = ''
    is_valid: bool = True

class AppConfig:
    def __init__(self):
        self.tele_hotkey = HotkeyConfig(key='f')
        self.freeze_hotkey = HotkeyConfig(key='e')
        self.ghost_hotkey = HotkeyConfig(key='v')
        self.hide_hotkey = HotkeyConfig(key='f7')
        self.stream_hotkey = HotkeyConfig(key='f8')
        self.beep_enabled = True
        self.stream_mode = False

app_config = AppConfig()

def load_config():
    try:
        if os.path.exists(HOTKEY_FILE):
            with open(HOTKEY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                app_config.tele_hotkey.key = data.get('tele_hotkey', 'f')
                app_config.freeze_hotkey.key = data.get('freeze_hotkey', 'e')
                app_config.ghost_hotkey.key = data.get('ghost_hotkey', 'v')
                app_config.hide_hotkey.key = data.get('hide_hotkey', 'f7')
                app_config.stream_hotkey.key = data.get('stream_hotkey', 'f8')
                app_config.beep_enabled = data.get('beep_enabled', True)
                app_config.stream_mode = data.get('stream_mode', False)
    except Exception as e:
        debug_log(f"Config load error: {e}")

def save_config():
    try:
        data = {
            'tele_hotkey': app_config.tele_hotkey.key,
            'freeze_hotkey': app_config.freeze_hotkey.key,
            'ghost_hotkey': app_config.ghost_hotkey.key,
            'hide_hotkey': app_config.hide_hotkey.key,
            'stream_hotkey': app_config.stream_hotkey.key,
            'beep_enabled': app_config.beep_enabled,
            'stream_mode': app_config.stream_mode
        }
        with open(HOTKEY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        debug_log(f"Save config error: {e}")

load_config()

# ================= AUDIO =================
class AudioManager:
    def beep(self, freq, dur):
        if not app_config.beep_enabled or app_config.stream_mode:
            return
        threading.Thread(target=lambda: winsound.Beep(freq, dur), daemon=True).start()

    def play_on(self): self.beep(950, 80)
    def play_off(self): self.beep(420, 100)

audio = AudioManager()

# ================= SIGNALS & NETWORK STATE =================
class AppSignals(QObject):
    notify = pyqtSignal(str, bool)
    stream_toggle = pyqtSignal(bool)
    toggle_visibility = pyqtSignal()
    start_tracking = pyqtSignal()

signals = AppSignals()

class NetState:
    def __init__(self):
        self.lock = threading.Lock()
        self.tele_mode = False
        self.freeze_mode = False
        self.ghost_mode = False
        self.running = True
        self.is_authenticated = False
        self.is_injected = False
        self.active_key = ""
        self.key_expires_at = -1
        self.total_passed = 0
        self.freeze_active_time = 0.0

net_state = NetState()

# ================= FAST PACKET DIVERTER ENGINE =================
def master_divert_worker():
    outbound_queue = deque(maxlen=MAX_QUEUE_SIZE)
    inbound_queue = deque(maxlen=MAX_QUEUE_SIZE)

    while net_state.running:
        if not net_state.is_authenticated or not net_state.is_injected:
            time.sleep(0.05)
            continue
        try:
            with pydivert.WinDivert(MASTER_FILTER, layer=pydivert.Layer.NETWORK) as handle:
                while net_state.running and net_state.is_authenticated and net_state.is_injected:
                    packet = handle.recv()
                    if packet is None:
                        continue

                    is_out = (packet.direction == pydivert.Direction.OUTBOUND)

                    with net_state.lock:
                        block_out = net_state.tele_mode or net_state.ghost_mode
                        block_in = net_state.freeze_mode or net_state.ghost_mode

                    if is_out:
                        if block_out:
                            outbound_queue.append(packet)
                        else:
                            while outbound_queue:
                                try:
                                    handle.send(outbound_queue.popleft())
                                except Exception:
                                    pass
                            handle.send(packet)
                            net_state.total_passed += 1
                    else:
                        if block_in:
                            inbound_queue.append(packet)
                        else:
                            while inbound_queue:
                                try:
                                    handle.send(inbound_queue.popleft())
                                except Exception:
                                    pass
                            handle.send(packet)
                            net_state.total_passed += 1
        except Exception as e:
            debug_log(f"Divert error: {e}")
            time.sleep(0.1)

# ================= HOTKEY TOGGLE CONTROLLER =================
def toggle_tele():
    if not net_state.is_injected: return
    with net_state.lock:
        if net_state.tele_mode:
            net_state.tele_mode = False
            active = False
        else:
            net_state.tele_mode = True
            net_state.freeze_mode = False
            net_state.ghost_mode = False
            active = True

    (audio.play_on if active else audio.play_off)()
    signals.notify.emit('Telekill', active)
    signals.notify.emit('Freeze', False)
    signals.notify.emit('Ghost', False)

def toggle_freeze():
    if not net_state.is_injected: return
    with net_state.lock:
        if net_state.freeze_mode:
            net_state.freeze_mode = False
            net_state.freeze_active_time = 0.0
            active = False
        else:
            net_state.freeze_mode = True
            net_state.tele_mode = False
            net_state.ghost_mode = False
            net_state.freeze_active_time = time.time()
            active = True

    (audio.play_on if active else audio.play_off)()
    signals.notify.emit('Freeze', active)
    signals.notify.emit('Telekill', False)
    signals.notify.emit('Ghost', False)

def toggle_ghost():
    if not net_state.is_injected: return
    with net_state.lock:
        if net_state.ghost_mode:
            net_state.ghost_mode = False
            active = False
        else:
            net_state.ghost_mode = True
            net_state.tele_mode = False
            net_state.freeze_mode = False
            active = True

    (audio.play_on if active else audio.play_off)()
    signals.notify.emit('Ghost', active)
    signals.notify.emit('Telekill', False)
    signals.notify.emit('Freeze', False)

def hotkey_loop():
    tp = gp = fp = hp = sp = False
    while net_state.running:
        try:
            if not net_state.is_authenticated or not net_state.is_injected:
                time.sleep(0.05)
                continue

            curr_t = time.time()
            with net_state.lock:
                is_freeze = net_state.freeze_mode
                f_time = net_state.freeze_active_time

            # CHỈ DUY NHẤT FREEZE TỰ TẮT
            if is_freeze and f_time > 0 and (curr_t - f_time >= FREEZE_AUTO_DISABLE_SEC):
                with net_state.lock:
                    net_state.freeze_mode = False
                    net_state.freeze_active_time = 0.0
                audio.play_off()
                signals.notify.emit('Freeze', False)

            cur_t = keyboard.is_pressed(app_config.tele_hotkey.key)
            if cur_t and not tp: toggle_tele()
            tp = cur_t

            cur_f = keyboard.is_pressed(app_config.freeze_hotkey.key)
            if cur_f and not fp: toggle_freeze()
            fp = cur_f

            cur_g = keyboard.is_pressed(app_config.ghost_hotkey.key)
            if cur_g and not gp: toggle_ghost()
            gp = cur_g

            cur_h = keyboard.is_pressed(app_config.hide_hotkey.key)
            if cur_h and not hp: signals.toggle_visibility.emit()
            hp = cur_h

            cur_s = keyboard.is_pressed(app_config.stream_hotkey.key)
            if cur_s and not sp:
                app_config.stream_mode = not app_config.stream_mode
                signals.stream_toggle.emit(app_config.stream_mode)
                save_config()
            sp = cur_s

            time.sleep(0.015)
        except Exception:
            time.sleep(0.1)

# ================= BOTTOM RAINBOW BANNER =================
class RainbowHeaderOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(220, 24)

        self.hue_offset = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_rainbow)
        self.timer.start(16)

        self.target_hwnd = None
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.sync_bottom_position)

        signals.stream_toggle.connect(lambda enabled: self.hide() if enabled else self.show())
        signals.start_tracking.connect(self.enable_tracking)

    def enable_tracking(self):
        hwnd, _ = find_emulator_window()
        self.target_hwnd = hwnd
        self.track_timer.start(25)
        self.show()

    def sync_bottom_position(self):
        if not self.target_hwnd or not ctypes.windll.user32.IsWindow(self.target_hwnd):
            hwnd, _ = find_emulator_window()
            self.target_hwnd = hwnd
            if not self.target_hwnd:
                return

        if ctypes.windll.user32.IsIconic(self.target_hwnd) or not ctypes.windll.user32.IsWindowVisible(self.target_hwnd):
            if self.isVisible(): self.hide()
            return

        rect = RECT()
        ctypes.windll.user32.GetClientRect(self.target_hwnd, ctypes.byref(rect))
        client_w = rect.right - rect.left
        client_h = rect.bottom - rect.top

        pt = POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt))

        if pt.x < -10000 or pt.y < -10000:
            if self.isVisible(): self.hide()
            return

        if not app_config.stream_mode and not self.isVisible():
            self.show()

        target_x = pt.x + (client_w - self.width()) // 2
        target_y = pt.y + client_h - 26
        self.move(target_x, target_y)

    def animate_rainbow(self):
        self.hue_offset = (self.hue_offset + 0.006) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Segoe UI", 11, QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(font)

        grad = QLinearGradient(0, 0, self.width(), 0)
        for i in range(8):
            stop_pos = i / 7.0
            hue = (self.hue_offset + stop_pos) % 1.0
            grad.setColorAt(stop_pos, QColor.fromHsvF(hue, 0.9, 1.0))

        rect = self.rect()
        text = "ZeroX Mods"

        p.setPen(QPen(QBrush(grad), 1))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.end()

# ================= STATUS HUD =================
class OverlayHUD(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(160, 180)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.items = {}
        for key, text, color in [("Freeze", "FREEZE ACTIVE", "#00f0ff"),
                                 ("Telekill", "TELEPKILL ACTIVE", "#7000ff"),
                                 ("Ghost", "GHOST ACTIVE", "#00ff88")]:
            lbl = QLabel(f" {text}")
            lbl.setFixedHeight(22)
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: rgba(5, 7, 10, 0.85);
                    color: #ffffff;
                    font-size: 10px;
                    font-weight: 800;
                    font-family: 'Consolas', 'Segoe UI', Arial;
                    padding-left: 6px;
                    padding-right: 8px;
                    border-left: 3px solid {color};
                    border-radius: 3px;
                }}
            """)
            lbl.hide()
            self.layout.addWidget(lbl)
            self.items[key] = lbl

        self.target_hwnd = None
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.sync_position_with_game)

        signals.notify.connect(self.on_notify)
        signals.stream_toggle.connect(lambda enabled: self.hide() if enabled else self.show())
        signals.start_tracking.connect(self.enable_tracking)

    def enable_tracking(self):
        hwnd, _ = find_emulator_window()
        self.target_hwnd = hwnd
        self.track_timer.start(25)
        self.show()

    def sync_position_with_game(self):
        if not self.target_hwnd or not ctypes.windll.user32.IsWindow(self.target_hwnd):
            hwnd, _ = find_emulator_window()
            self.target_hwnd = hwnd
            if not self.target_hwnd:
                return

        if ctypes.windll.user32.IsIconic(self.target_hwnd) or not ctypes.windll.user32.IsWindowVisible(self.target_hwnd):
            if self.isVisible(): self.hide()
            return

        pt = POINT(0, 0)
        ctypes.windll.user32.ClientToScreen(self.target_hwnd, ctypes.byref(pt))

        if pt.x < -10000 or pt.y < -10000:
            if self.isVisible(): self.hide()
            return

        if not app_config.stream_mode and not self.isVisible():
            self.show()

        self.move(pt.x + 20, pt.y + 85)

    def on_notify(self, feature, enabled):
        if app_config.stream_mode: return
        if feature in self.items:
            self.items[feature].setVisible(enabled)
            self.adjustSize()

# ================= PARTICLE BACKGROUND =================
class Particle:
    def __init__(self, w, h):
        self.reset(w, h, random_y=True)

    def reset(self, w, h, random_y=False):
        self.x = random.uniform(2, max(w - 4, 10))
        self.y = random.uniform(2, h - 4) if random_y else random.uniform(-10, 0)
        self.speed = random.uniform(0.3, 0.9)
        self.size = random.uniform(1.0, 2.2)
        self.alpha = random.randint(120, 230)
        self.drift = random.uniform(-0.1, 0.1)

    def update(self, w, h):
        self.y += self.speed
        self.x += self.drift
        if self.y > h - 4 or self.x < 2 or self.x > w - 2:
            self.reset(w, h)

class CustomParticleFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = [Particle(340, 240) for _ in range(45)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_particles)
        self.timer.start(16)

    def animate_particles(self):
        w, h = self.width(), self.height()
        for p in self.particles:
            p.update(w, h)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#0b0d11")))
        p.setPen(QPen(QColor("#1f242d"), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

        p.setPen(Qt.PenStyle.NoPen)
        for pt in self.particles:
            p.setBrush(QBrush(QColor(255, 255, 255, pt.alpha)))
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size / 2.0, pt.size / 2.0)
        p.end()

# ================= CUSTOM PROGRESS BAR =================
class CustomProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(5)
        self._progress = 0.0
        self._color = QColor("#00ff66")

    def set_progress(self, val: float, color: QColor):
        self._progress = max(0.0, min(100.0, val))
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#161a22")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 2, 2)

        if self._progress > 0:
            fill_w = int(self.width() * (self._progress / 100.0))
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(0, 0, max(fill_w, 4), self.height(), 2, 2)
        p.end()

# ================= CHẤM TRÒN XANH PHÁT SÁNG =================
class GlowingCircleDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        cx, cy = self.width() / 2.0, self.height() / 2.0

        glow = QRadialGradient(cx, cy, 6.5)
        glow.setColorAt(0.0, QColor(0, 255, 102, 180))
        glow.setColorAt(0.5, QColor(0, 255, 102, 60))
        glow.setColorAt(1.0, QColor(0, 255, 102, 0))
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)

        p.setBrush(QBrush(QColor("#00ff66")))
        p.drawEllipse(QPointF(cx, cy), 2.8, 2.8)
        p.end()

# ================= TOP TITLE BAR =================
class TopBar(QWidget):
    def __init__(self, title_text, on_close=None, on_minimize=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        self.dot = GlowingCircleDot()
        layout.addWidget(self.dot)

        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet("color: #d1d5db; font-size: 10px; font-weight: 700; letter-spacing: 0.3px; font-family: 'Consolas', 'Segoe UI', Arial;")
        layout.addWidget(self.title_lbl)
        layout.addStretch()

        if on_minimize:
            self.min_btn = QPushButton("—")
            self.min_btn.setFixedSize(16, 16)
            self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.min_btn.setStyleSheet("QPushButton { background: transparent; color: #6b7280; border: none; font-size: 10px; font-weight: bold; } QPushButton:hover { color: #ffffff; }")
            self.min_btn.clicked.connect(on_minimize)
            layout.addWidget(self.min_btn)

        if on_close:
            self.close_btn = QPushButton("✕")
            self.close_btn.setFixedSize(16, 16)
            self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.close_btn.setStyleSheet("QPushButton { background: transparent; color: #6b7280; border: none; font-size: 11px; font-weight: bold; } QPushButton:hover { color: #ef4444; }")
            self.close_btn.clicked.connect(on_close)
            layout.addWidget(self.close_btn)

# ================= GIAO DIỆN LOGIN KEY =================
class LoginWidget(QWidget):
    def __init__(self, on_login_success, on_close_callback, on_minimize_callback, parent=None):
        super().__init__(parent)
        self.on_login_success = on_login_success

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(5)

        layout.addWidget(TopBar("ZeroX Cheat  /   Login", on_close_callback, on_minimize_callback))
        layout.addSpacing(6)

        lbl_key = QLabel("LICENSE KEY")
        lbl_key.setStyleSheet("color: #525866; font-size: 9px; font-weight: 800; font-family: 'Consolas', monospace; letter-spacing: 1px;")
        layout.addWidget(lbl_key)

        key_box = QHBoxLayout()
        key_box.setSpacing(6)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("zerox-xxx-xxx")
        self.key_input.setFixedHeight(34)
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: #12141a;
                border: 1px solid #1c202a;
                border-radius: 6px;
                color: #ffffff;
                font-size: 11.5px;
                font-weight: 700;
                font-family: 'Consolas', monospace;
                padding-left: 8px;
            }
            QLineEdit:focus { border: 1px solid #00ff66; }
        """)

        saved_key = load_saved_key()
        if saved_key:
            self.key_input.setText(saved_key)

        key_box.addWidget(self.key_input)

        self.paste_btn = QPushButton("❐")
        self.paste_btn.setFixedSize(34, 34)
        self.paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #12141a;
                border: 1px solid #1c202a;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1a1e28; color: #ffffff; border-color: #2e3547; }
        """)
        self.paste_btn.clicked.connect(self.paste_clipboard)
        key_box.addWidget(self.paste_btn)
        layout.addLayout(key_box)

        self.status_msg = QLabel("")
        self.status_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_msg.setFixedHeight(14)
        self.status_msg.setStyleSheet("color: #ef4444; font-size: 9px; font-weight: bold;")
        layout.addWidget(self.status_msg)

        self.login_btn = QPushButton("LOGIN")
        self.login_btn.setFixedHeight(34)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f7;
                color: #0b0d11;
                border: none;
                border-radius: 7px;
                font-size: 11.5px;
                font-weight: 900;
                letter-spacing: 2px;
                font-family: 'Consolas', sans-serif;
            }
            QPushButton:hover { background-color: #ffffff; }
        """)
        self.login_btn.clicked.connect(self.handle_login)
        layout.addWidget(self.login_btn)

        self.get_key_btn = QPushButton("Get key")
        self.get_key_btn.setFixedHeight(28)
        self.get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.get_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #101218;
                border: 1px solid #1f232e;
                border-radius: 6px;
                color: #d1d5db;
                font-size: 10.5px;
                font-weight: 700;
                font-family: 'Consolas', monospace;
            }
            QPushButton:hover { background-color: #161a24; border-color: #2e3547; color: #ffffff; }
        """)
        self.get_key_btn.clicked.connect(lambda: webbrowser.open(GET_KEY_URL))
        layout.addWidget(self.get_key_btn)

    def paste_clipboard(self):
        cb = QApplication.clipboard().text().strip()
        if cb: self.key_input.setText(cb)

    def handle_login(self):
        self.status_msg.setText("Đang kiểm tra...")
        self.status_msg.setStyleSheet("color: #3b82f6; font-size: 9px; font-weight: bold;")
        QApplication.processEvents()

        user_key = self.key_input.text().strip()
        ok, msg, exp_at = verify_key_with_vps(user_key)
        if ok:
            net_state.active_key = user_key
            net_state.key_expires_at = exp_at
            save_license_key(user_key)
            self.status_msg.setStyleSheet("color: #00ff66; font-size: 9px; font-weight: bold;")
            self.status_msg.setText(msg)
            QTimer.singleShot(350, self.on_login_success)
        else:
            self.status_msg.setStyleSheet("color: #ef4444; font-size: 9px; font-weight: bold;")
            self.status_msg.setText(msg)

# ================= STAGE 1: DOWNLOAD LOADER =================
class DownloadWidget(QWidget):
    def __init__(self, on_inject_callback, on_close_callback, parent=None):
        super().__init__(parent)
        self.on_inject = on_inject_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 14)
        layout.setSpacing(0)

        layout.addWidget(TopBar("NETCHEAT LOADER", on_close_callback))
        layout.addSpacing(22)

        self.status_lbl = QLabel("Downloading...")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI', Arial;")
        layout.addWidget(self.status_lbl)
        layout.addSpacing(18)

        self.pbar = CustomProgressBar()
        layout.addWidget(self.pbar)
        layout.addSpacing(6)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(2, 0, 2, 0)
        self.left_lbl = QLabel("--")
        self.left_lbl.setStyleSheet("color: #00ff66; font-size: 11px; font-weight: 600; font-family: 'Segoe UI', Arial;")
        self.right_lbl = QLabel("0% --")
        self.right_lbl.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 500; font-family: 'Segoe UI', Arial;")

        info_layout.addWidget(self.left_lbl)
        info_layout.addStretch()
        info_layout.addWidget(self.right_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()

        self.action_btn = QPushButton("CLOSE")
        self.action_btn.setFixedHeight(34)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #12161f;
                color: #9ca3af;
                border: 1px solid #1f2937;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }
            QPushButton:hover {
                background-color: #181d28;
                color: #d1d5db;
                border-color: #374151;
            }
        """)
        self.action_btn.clicked.connect(self.handle_btn_click)
        layout.addWidget(self.action_btn)

        self.current_progress = 0
        self.is_completed = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_download)

    def start_download(self):
        self.current_progress = 0
        self.is_completed = False
        self.pbar.set_progress(0, QColor("#00ff66"))
        self.status_lbl.setText("Downloading...")
        self.status_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI', Arial;")
        self.left_lbl.setText("--")
        self.right_lbl.setText("0% 0.0/14.8 MB")
        self.action_btn.setText("CLOSE")
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #12161f;
                color: #9ca3af;
                border: 1px solid #1f2937;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }
            QPushButton:hover {
                background-color: #181d28;
                color: #d1d5db;
                border-color: #374151;
            }
        """)
        self.timer.start(25)

    def tick_download(self):
        if self.current_progress < 100:
            self.current_progress += 1
            self.pbar.set_progress(self.current_progress, QColor("#00ff66"))
            mb_done = (self.current_progress / 100.0) * 14.8
            self.right_lbl.setText(f"{self.current_progress}% {mb_done:.1f}/14.8 MB")
            if self.current_progress > 10:
                self.left_lbl.setText("--")
        else:
            self.timer.stop()
            self.is_completed = True
            self.status_lbl.setText("Ready to Inject")
            self.status_lbl.setStyleSheet("color: #00ff66; font-size: 13px; font-weight: 800; font-family: 'Segoe UI', Arial;")
            self.left_lbl.setText("Verified")
            self.right_lbl.setText("100% 14.8/14.8 MB")
            
            # GIAO DIỆN INJECT XANH LÁ ĐẬM
            self.action_btn.setText("INJECT")
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00873a;
                    color: #ffffff;
                    border: 2px solid #00c853;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 900;
                    letter-spacing: 2.5px;
                    font-family: 'Consolas', 'Segoe UI', Arial;
                    padding-top: 1px;
                }
                QPushButton:hover {
                    background-color: #00a346;
                    border: 2px solid #33e877;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #00662c;
                    border: 2px solid #00873a;
                    padding-top: 3px;
                }
            """)

    def handle_btn_click(self):
        if self.is_completed:
            self.on_inject()
        else:
            cleanup_and_exit()

# ================= STAGE 2: INITIALIZING =================
class InitializingWidget(QWidget):
    def __init__(self, on_finish_callback, parent=None):
        super().__init__(parent)
        self.on_finish = on_finish_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 14)
        layout.setSpacing(0)

        layout.addWidget(TopBar("LOADING"))
        layout.addSpacing(32)

        self.status_lbl = QLabel("Initializing System...")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI', Arial;")
        layout.addWidget(self.status_lbl)
        layout.addSpacing(22)

        self.pbar = CustomProgressBar()
        layout.addWidget(self.pbar)
        layout.addSpacing(8)

        self.pct_lbl = QLabel("0%")
        self.pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pct_lbl.setStyleSheet("color: #00e676; font-size: 12px; font-weight: 700; font-family: 'Segoe UI', Arial;")
        layout.addWidget(self.pct_lbl)
        layout.addStretch()

        self.current_progress = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_init)

    def start(self):
        self.current_progress = 0
        self.timer.start(24)

    def tick_init(self):
        self.current_progress += 1
        if self.current_progress < 50:
            color = QColor("#00e676")
            css = "#00e676"
        elif self.current_progress < 80:
            color = QColor("#00a2ff")
            css = "#00a2ff"
        else:
            color = QColor("#9d4edd")
            css = "#9d4edd"

        self.pbar.set_progress(self.current_progress, color)
        self.pct_lbl.setText(f"{self.current_progress}%")
        self.pct_lbl.setStyleSheet(f"color: {css}; font-size: 12px; font-weight: 700; font-family: 'Segoe UI', Arial;")

        if self.current_progress >= 100:
            self.timer.stop()
            QTimer.singleShot(250, self.on_finish)

# ================= STAGE 3: KEYBINDS =================
class KeybindsWidget(QWidget):
    def __init__(self, on_close_callback, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 12)
        layout.setSpacing(6)

        self.top_bar = TopBar("KEYBINDS", on_close_callback)
        layout.addWidget(self.top_bar)
        layout.addSpacing(6)

        self.btn_tele = self.create_key_row(layout, "TELEKILL", app_config.tele_hotkey, 'tele_hotkey')
        self.btn_freeze = self.create_key_row(layout, "FREEZE", app_config.freeze_hotkey, 'freeze_hotkey')
        self.btn_ghost = self.create_key_row(layout, "GHOST", app_config.ghost_hotkey, 'ghost_hotkey')

        layout.addSpacing(4)

        hint_lbl = QLabel("Click button then press a key to bind")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setStyleSheet("color: #71717a; font-size: 10px; font-weight: 500; font-family: 'Segoe UI', Arial;")
        layout.addWidget(hint_lbl)

        layout.addSpacing(4)

        self.sound_btn = QPushButton("Sound: ON" if app_config.beep_enabled else "Sound: OFF")
        self.sound_btn.setFixedHeight(30)
        self.sound_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sound_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e1117;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #141821;
                border-color: #3f3f46;
                color: #ffffff;
            }
        """)
        self.sound_btn.clicked.connect(self.toggle_sound)
        layout.addWidget(self.sound_btn)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_key_expiry_display)
        self.countdown_timer.start(1000)
        self.update_key_expiry_display()

    def update_key_expiry_display(self):
        exp_at = net_state.key_expires_at
        curr_key = net_state.active_key or load_saved_key() or "KEY"

        key_badge = f'<span style="color:#60a5fa; font-weight:700; font-size:9.5px;">[{curr_key}]</span>'

        if exp_at == -1:
            time_badge = '<span style="color:#00ff66; font-size:9.5px;">[Vĩnh viễn]</span>'
        elif exp_at <= 0:
            time_badge = ''
        else:
            rem = exp_at - time.time()
            if rem <= 0:
                time_badge = '<span style="color:#ef4444; font-size:9.5px;">[Hết hạn]</span>'
            else:
                days = int(rem // 86400)
                hrs = int((rem % 86400) // 3600)
                mins = int((rem % 3600) // 60)
                secs = int(rem % 60)

                if days > 0:
                    time_str = f"{days}d {hrs:02d}h {mins:02d}m {secs:02d}s"
                else:
                    time_str = f"{hrs:02d}h {mins:02d}m {secs:02d}s"

                time_badge = f'<span style="color:#00ff66; font-weight:800; font-size:9.5px;">[{time_str}]</span>'

        self.top_bar.title_lbl.setText(f"KEYBINDS {key_badge} {time_badge}")

    def create_key_row(self, parent_layout, label_text, config_obj, config_key):
        row = QHBoxLayout()
        row.setContentsMargins(4, 2, 4, 2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #f4f4f5; font-size: 12px; font-weight: 700; font-family: 'Segoe UI', Arial; letter-spacing: 1px;")
        row.addWidget(lbl)
        row.addStretch()

        btn = QPushButton(config_obj.key.upper())
        btn.setFixedSize(62, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #12151c;
                color: #ffffff;
                border: 1px solid #222733;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover {
                background-color: #1a1f2c;
                border-color: #3b4252;
            }
        """)
        btn.clicked.connect(lambda: self.start_rebinding(btn, config_obj, config_key))
        row.addWidget(btn)

        parent_layout.addLayout(row)
        return btn

    def start_rebinding(self, btn, config_obj, config_key):
        btn.setText("...")
        def on_key(event):
            k = event.name.lower() if len(event.name) > 1 else event.name
            config_obj.key = k
            btn.setText(k.upper())
            keyboard.unhook(hook)
            save_config()
        hook = keyboard.on_release(on_key)

    def toggle_sound(self):
        app_config.beep_enabled = not app_config.beep_enabled
        self.sound_btn.setText("Sound: ON" if app_config.beep_enabled else "Sound: OFF")
        save_config()

# ================= MAIN WINDOW =================
class MainContainerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(AntiBan.get_title())
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(340, 240)

        self.bg_frame = CustomParticleFrame(self)
        self.bg_frame.setGeometry(0, 0, 340, 240)

        layout = QVBoxLayout(self.bg_frame)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.login_view = LoginWidget(self.on_login_success, cleanup_and_exit, self.showMinimized)
        self.download_view = DownloadWidget(self.on_inject_clicked, cleanup_and_exit)
        self.init_view = InitializingWidget(self.on_init_finished)
        self.keybinds_view = KeybindsWidget(cleanup_and_exit)

        self.stack.addWidget(self.login_view)
        self.stack.addWidget(self.download_view)
        self.stack.addWidget(self.init_view)
        self.stack.addWidget(self.keybinds_view)

        signals.toggle_visibility.connect(self.toggle_visibility)
        self._drag = False
        self._pos = None

    def on_login_success(self):
        net_state.is_authenticated = True
        self.stack.setCurrentIndex(1)
        self.download_view.start_download()

    def on_inject_clicked(self):
        signals.start_tracking.emit()
        self.stack.setCurrentIndex(2)
        self.init_view.start()

    def on_init_finished(self):
        net_state.is_injected = True
        self.keybinds_view.update_key_expiry_display()
        self.stack.setCurrentIndex(3)

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag and self._pos:
            self.move(e.globalPosition().toPoint() - self._pos)

    def mouseReleaseEvent(self, e):
        self._drag = False

# ================= RUNTIME ENTRY =================
def cleanup_and_exit():
    net_state.running = False
    with net_state.lock:
        net_state.tele_mode = False
        net_state.freeze_mode = False
        net_state.ghost_mode = False
    try: keyboard.unhook_all()
    except Exception: pass
    QApplication.quit()
    os._exit(0)

if __name__ == '__main__':
    if not (ctypes.windll.shell32.IsUserAnAdmin() != 0):
        ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, ' '.join(f'"{a}"' for a in sys.argv), None, 1)
        sys.exit()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)

    main_win = MainContainerWindow()
    main_win.show()

    hud = OverlayHUD()
    rainbow = RainbowHeaderOverlay()

    threading.Thread(target=master_divert_worker, daemon=True).start()
    threading.Thread(target=hotkey_loop, daemon=True).start()

    keyboard.add_hotkey('f10', cleanup_and_exit)
    app.aboutToQuit.connect(cleanup_and_exit)
    sys.exit(app.exec())