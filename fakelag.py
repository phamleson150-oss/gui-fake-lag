import os
import sys
import threading
import time
import math
import ctypes
from ctypes import wintypes
import winsound
import json
import random
import subprocess
import urllib.parse
import webbrowser
from collections import deque
from dataclasses import dataclass
from datetime import datetime

try:
    import pydivert
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pydivert"])
    import pydivert

try:
    import keyboard
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard"])
    import keyboard

try:
    import pynput
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pynput"])
    import pynput
from pynput import mouse as pynput_mouse

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QFrame, QStackedWidget, QLineEdit, QGridLayout,
        QTextEdit
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPoint, QPointF, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QBuffer, QIODevice
    from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QRadialGradient, QPolygonF, QPainterPath, QGuiApplication
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QPushButton, QFrame, QStackedWidget, QLineEdit, QGridLayout,
        QTextEdit
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPoint, QPointF, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QBuffer, QIODevice
    from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QRadialGradient, QPolygonF, QPainterPath, QGuiApplication

# ================= CẤU HÌNH HỆ THỐNG =================
VPS_BASE_URL = "http://103.78.3.222:53689"
VPS_VERIFY_URL = f"{VPS_BASE_URL}/api/verify_key"
VPS_CHAT_URL = f"{VPS_BASE_URL}/api/chat"
GET_KEY_URL = f"{VPS_BASE_URL}/"
LICENSE_FILE = "zerox_license.json"
HOTKEY_FILE = "zerox_hotkey.json"

DISCORD_FEEDBACK_WEBHOOK = "https://discord.com/api/webhooks/1543470614025863308/SD9lOHs2pxJZFrdFFuYQMBOkKAF_6xgY8xetSagvXEU8fUc4O5e_jriDdIIbO1vylQrL"
DISCORD_CHAT_WEBHOOK = "https://discord.com/api/webhooks/1543478594439880857/fNw9bdIjZP5-1dRfflPKlVLVPRJN4Qz67DZ-E31Y4ArDQGlVOS_M3XTDREOv7_VueEwn"

APP_VERSION = "1.3.6"
BUILD_DATE = "30/08/2026"
BUILD_TIME = "11:50:00"

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
DEFAULT_USERNAME = os.environ.get('USERNAME', os.environ.get('USER', 'User'))

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
        response = requests.get(url, timeout=4)
        res_data = response.json()
        valid = res_data.get("valid", False) or res_data.get("success", False)
        msg = res_data.get("msg", "Lỗi xác thực")
        
        if "remaining_seconds" in res_data:
            rem = float(res_data["remaining_seconds"])
            expires_at = -1.0 if rem == -1 else (time.time() + rem)
        else:
            expires_at = float(res_data.get("expires_at", -1))
            
        return valid, msg, expires_at
    except Exception:
        return False, "Lỗi kết nối VPS!", 0

# ================= WIN32 EMULATOR DETECTOR =================
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
    "nox.exe", "memu.exe", "projecttitan.exe", "androidprocess.exe", "gameloop.exe", "bstk.exe"
]

def get_process_name_by_hwnd(hwnd):
    if not hwnd: return ""
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

def is_emulator_in_foreground():
    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not fg_hwnd:
        return False
    pname = get_process_name_by_hwnd(fg_hwnd)
    return any(proc in pname for proc in EMULATOR_PROCESSES)

# ================= NETWORK FILTERS =================
FILTER_FREEZE_FIX = "udp and ((udp.SrcPort >= 7000 and udp.SrcPort <= 18000) or (udp.DstPort >= 7000 and udp.DstPort <= 18000))"
FILTER_I          = "(udp.SrcPort >= 10011 and udp.SrcPort <= 10019) and ip and ip.Protocol == 17 and ip.Length >= 50 and ip.Length <= 1491"
FILTER_F          = "(udp.PayloadLength >= 53 and udp.PayloadLength <= 170) and (udp.DstPort >= 10011 and udp.DstPort <= 10020)"
FILTER_O          = "udp.DstPort >= 10010 and udp.DstPort <= 10020 and udp.PayloadLength >= 35"
FILTER_AIMLAG     = "(udp.SrcPort >= 10011 and udp.SrcPort <= 10019) and ip and ip.Protocol == 17 and ip.Length >= 50 and ip.Length <= 1491"

MAX_PACKETS = 80
MAX_AIMLAG_PACKETS = 30
FREEZE_AUTO_DISABLE_SEC = 1.5

def debug_log(msg):
    try:
        with open('debug.log', 'a', encoding='utf-8') as f:
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
        self.aimlag_hotkey = HotkeyConfig(key='c')
        self.hide_hotkey = HotkeyConfig(key='f7')
        self.stream_hotkey = HotkeyConfig(key='f8')
        
        self.beep_tele = True
        self.beep_freeze = True
        self.beep_ghost = True
        self.beep_aimlag = True
        
        self.stream_mode = False
        self.fix_dame_enabled = True
        self.custom_nickname = DEFAULT_USERNAME
        self.is_name_locked = False

app_config = AppConfig()

def load_config():
    try:
        if os.path.exists(HOTKEY_FILE):
            with open(HOTKEY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                app_config.tele_hotkey.key = data.get('tele_hotkey', 'f')
                app_config.freeze_hotkey.key = data.get('freeze_hotkey', 'e')
                app_config.ghost_hotkey.key = data.get('ghost_hotkey', 'v')
                app_config.aimlag_hotkey.key = data.get('aimlag_hotkey', 'c')
                app_config.hide_hotkey.key = data.get('hide_hotkey', 'f7')
                app_config.stream_hotkey.key = data.get('stream_hotkey', 'f8')
                
                app_config.beep_tele = data.get('beep_tele', True)
                app_config.beep_freeze = data.get('beep_freeze', True)
                app_config.beep_ghost = data.get('beep_ghost', True)
                app_config.beep_aimlag = data.get('beep_aimlag', True)
                
                app_config.stream_mode = data.get('stream_mode', False)
                app_config.fix_dame_enabled = data.get('fix_dame_enabled', True)
                app_config.custom_nickname = data.get('custom_nickname', DEFAULT_USERNAME)
                app_config.is_name_locked = data.get('is_name_locked', False)
    except Exception as e:
        debug_log(f"Config load error: {e}")

def save_config():
    try:
        data = {
            'tele_hotkey': app_config.tele_hotkey.key,
            'freeze_hotkey': app_config.freeze_hotkey.key,
            'ghost_hotkey': app_config.ghost_hotkey.key,
            'aimlag_hotkey': app_config.aimlag_hotkey.key,
            'hide_hotkey': app_config.hide_hotkey.key,
            'stream_hotkey': app_config.stream_hotkey.key,
            'beep_tele': app_config.beep_tele,
            'beep_freeze': app_config.beep_freeze,
            'beep_ghost': app_config.beep_ghost,
            'beep_aimlag': app_config.beep_aimlag,
            'stream_mode': app_config.stream_mode,
            'fix_dame_enabled': app_config.fix_dame_enabled,
            'custom_nickname': app_config.custom_nickname,
            'is_name_locked': app_config.is_name_locked
        }
        with open(HOTKEY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        debug_log(f"Save config error: {e}")

load_config()

# ================= AUDIO =================
class AudioManager:
    def beep(self, freq, dur):
        if app_config.stream_mode:
            return
        threading.Thread(target=lambda: winsound.Beep(freq, dur), daemon=True).start()

    def play_tele(self, active):
        if app_config.beep_tele: self.beep(950 if active else 420, 75)

    def play_freeze(self, active):
        if app_config.beep_freeze: self.beep(900 if active else 400, 75)

    def play_ghost(self, active):
        if app_config.beep_ghost: self.beep(1000 if active else 450, 75)

    def play_aimlag(self, active):
        if app_config.beep_aimlag: self.beep(850 if active else 380, 75)

audio = AudioManager()

# ================= SIGNALS & NETWORK STATE =================
class AppSignals(QObject):
    notify = pyqtSignal(str, bool)
    stream_toggle = pyqtSignal(bool)
    toggle_visibility = pyqtSignal()
    start_tracking = pyqtSignal()
    key_expired = pyqtSignal()
    open_tab_requested = pyqtSignal(int)
    show_honeycomb = pyqtSignal()

signals = AppSignals()

class NetState:
    def __init__(self):
        self.lock = threading.Lock()
        self.tele_mode = False
        self.freeze_mode = False
        self.ghost_mode = False
        
        self.aimlag_armed = False
        self.mouse_held = False
        self.is_fake_lag_tab_open = False

        self.running = True
        self.is_authenticated = False
        self.is_injected = False
        self.active_key = ""
        self.key_expires_at = -1
        self.cached_ip = "127.0.0.1"
        
        self.freeze_active_time = 0.0

net_state = NetState()

def fetch_ip_background():
    try:
        r = requests.get('https://api.ipify.org?format=json', timeout=3)
        net_state.cached_ip = r.json().get('ip', '127.0.0.1')
    except Exception:
        net_state.cached_ip = "127.0.0.1"

# ================= BỘ ĐIỀU PHỐI MẠNG =================
class DivertSession:
    def __init__(self, filter_str, max_packets=MAX_PACKETS):
        self.filter_str = filter_str
        self.max_packets = max_packets
        self.handle = None
        self.is_active = False
        self.packets = []
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.is_active:
                return
            self.is_active = True
            self.packets.clear()
            try:
                self.handle = pydivert.WinDivert(self.filter_str, layer=pydivert.Layer.NETWORK)
                self.handle.open()
            except Exception as e:
                debug_log(f"Session open error on {self.filter_str}: {e}")
                self.is_active = False
                self.handle = None
                return
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        h = self.handle
        if not h: return
        try:
            for pkt in h:
                if not self.is_active or not net_state.running:
                    break
                with self.lock:
                    if len(self.packets) >= self.max_packets:
                        self.packets.pop(0)
                    self.packets.append(pydivert.Packet(pkt.raw, pkt.interface, pkt.direction))
        except Exception:
            pass
        finally:
            try:
                if h: h.close()
            except Exception:
                pass

    def stop_and_flush(self):
        with self.lock:
            if not self.is_active and not self.packets:
                return
            self.is_active = False
            if self.handle:
                try:
                    self.handle.close()
                except Exception:
                    pass
                self.handle = None
            
            pkts_to_send = list(self.packets)
            self.packets.clear()

        if pkts_to_send:
            threading.Thread(target=self._flush_worker, args=(pkts_to_send, self.filter_str), daemon=True).start()

    @staticmethod
    def _flush_worker(packets, filter_str):
        if not packets: return
        try:
            with pydivert.WinDivert(filter_str, layer=pydivert.Layer.NETWORK) as sender:
                for pkt in packets:
                    try:
                        sender.send(pydivert.Packet(pkt.raw, pkt.interface, pkt.direction))
                    except Exception:
                        pass
        except Exception as e:
            debug_log(f"Flush error: {e}")

aimlag_session = DivertSession(FILTER_AIMLAG, max_packets=MAX_AIMLAG_PACKETS)
tele_session = DivertSession(FILTER_O, max_packets=MAX_PACKETS)
ghost_session = DivertSession(FILTER_F, max_packets=MAX_PACKETS)
freeze_shinmod_session = DivertSession(FILTER_I, max_packets=MAX_PACKETS)

def divert_freeze_fix_dame_worker():
    inbound_queue = deque(maxlen=MAX_PACKETS)

    while net_state.running:
        if not net_state.is_authenticated or not net_state.is_injected or not app_config.fix_dame_enabled:
            time.sleep(0.05)
            continue
        try:
            with pydivert.WinDivert(FILTER_FREEZE_FIX, layer=pydivert.Layer.NETWORK) as handle:
                while net_state.running and net_state.is_authenticated and net_state.is_injected and app_config.fix_dame_enabled:
                    packet = handle.recv()
                    if packet is None:
                        continue

                    is_out = (packet.direction == pydivert.Direction.OUTBOUND)

                    with net_state.lock:
                        block_freeze_fix = net_state.freeze_mode

                    if is_out:
                        handle.send(packet)
                    else:
                        if block_freeze_fix:
                            inbound_queue.append(packet)
                        else:
                            while inbound_queue:
                                try:
                                    handle.send(inbound_queue.popleft())
                                except Exception:
                                    pass
                            handle.send(packet)
        except Exception as e:
            debug_log(f"Freeze fix divert error: {e}")
            time.sleep(0.05)

# ================= TOGGLE CÁC CHỨC NĂNG =================
def toggle_freeze():
    if not net_state.is_injected or not net_state.is_fake_lag_tab_open: return
    with net_state.lock:
        if net_state.freeze_mode:
            net_state.freeze_mode = False
            net_state.freeze_active_time = 0.0
            if not app_config.fix_dame_enabled:
                freeze_shinmod_session.stop_and_flush()
            active = False
        else:
            net_state.freeze_mode = True
            net_state.freeze_active_time = time.time()
            if not app_config.fix_dame_enabled:
                freeze_shinmod_session.start()
            active = True

    audio.play_freeze(active)
    signals.notify.emit('Freeze', active)

def toggle_ghost():
    if not net_state.is_injected or not net_state.is_fake_lag_tab_open: return
    with net_state.lock:
        if net_state.ghost_mode:
            net_state.ghost_mode = False
            ghost_session.stop_and_flush()
            active = False
        else:
            net_state.ghost_mode = True
            ghost_session.start()
            active = True

    audio.play_ghost(active)
    signals.notify.emit('Ghost', active)

def toggle_tele():
    if not net_state.is_injected or not net_state.is_fake_lag_tab_open: return
    with net_state.lock:
        if net_state.tele_mode:
            net_state.tele_mode = False
            tele_session.stop_and_flush()
            active = False
        else:
            net_state.tele_mode = True
            tele_session.start()
            active = True

    audio.play_tele(active)
    signals.notify.emit('Telekill', active)

def toggle_aimlag_arm():
    if not net_state.is_injected or not net_state.is_fake_lag_tab_open: return
    with net_state.lock:
        net_state.aimlag_armed = not net_state.aimlag_armed
        active = net_state.aimlag_armed
        if not active:
            net_state.mouse_held = False
            aimlag_session.stop_and_flush()

    audio.play_aimlag(active)
    signals.notify.emit('AimLag', active)

def on_mouse_click(x, y, button, pressed):
    if not net_state.is_authenticated or not net_state.is_injected or not net_state.is_fake_lag_tab_open:
        return

    if button == pynput_mouse.Button.left:
        with net_state.lock:
            if not net_state.aimlag_armed:
                return

            if pressed:
                if is_emulator_in_foreground() and not net_state.mouse_held:
                    net_state.mouse_held = True
                    aimlag_session.start()
            else:
                if net_state.mouse_held:
                    net_state.mouse_held = False
                    aimlag_session.stop_and_flush()

def stop_all_features():
    with net_state.lock:
        net_state.tele_mode = False
        net_state.freeze_mode = False
        net_state.ghost_mode = False
        net_state.aimlag_armed = False
        net_state.mouse_held = False

    aimlag_session.stop_and_flush()
    tele_session.stop_and_flush()
    ghost_session.stop_and_flush()
    freeze_shinmod_session.stop_and_flush()

    signals.notify.emit('Freeze', False)
    signals.notify.emit('Telekill', False)
    signals.notify.emit('Ghost', False)
    signals.notify.emit('AimLag', False)

def hotkey_loop():
    tp = gp = fp = ap = hp = sp = False
    while net_state.running:
        try:
            if not net_state.is_authenticated or not net_state.is_injected:
                time.sleep(0.05)
                continue

            curr_t = time.time()
            with net_state.lock:
                is_freeze = net_state.freeze_mode
                f_time = net_state.freeze_active_time

            if app_config.fix_dame_enabled:
                if is_freeze and f_time > 0 and (curr_t - f_time >= FREEZE_AUTO_DISABLE_SEC):
                    toggle_freeze()

            if net_state.is_fake_lag_tab_open:
                cur_t = keyboard.is_pressed(app_config.tele_hotkey.key)
                if cur_t and not tp: toggle_tele()
                tp = cur_t

                cur_f = keyboard.is_pressed(app_config.freeze_hotkey.key)
                if cur_f and not fp: toggle_freeze()
                fp = cur_f

                cur_g = keyboard.is_pressed(app_config.ghost_hotkey.key)
                if cur_g and not gp: toggle_ghost()
                gp = cur_g

                cur_a = keyboard.is_pressed(app_config.aimlag_hotkey.key)
                if cur_a and not ap: toggle_aimlag_arm()
                ap = cur_a

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

# ================= VECTOR HEXAGON BUTTON (TỰ VẼ BẰNG QPAINTER) =================
class VectorHexagonButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_type, tooltip_text, is_maintenance=False, is_active=False, radius=22, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.tooltip_text = tooltip_text
        self.is_maintenance = is_maintenance
        self.is_active = is_active
        self.radius = radius
        self.setFixedSize(int(radius * 2), int(radius * 2))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip_text)
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        r = self.radius - 2.0

        poly = QPolygonF()
        for i in range(6):
            deg = 60 * i - 30
            rad = math.radians(deg)
            poly.append(QPointF(cx + r * math.cos(rad), cy + r * math.sin(rad)))

        if self.is_maintenance:
            bg_color = QColor(16, 18, 24, 210) if not self._hover else QColor(24, 28, 38, 240)
            border_color = QColor("#ef4444") if self._hover else QColor(45, 52, 68, 180)
            icon_color = QColor("#94a3b8") if not self._hover else QColor("#ef4444")
        elif self.is_active:
            bg_color = QColor(30, 41, 59, 240)
            border_color = QColor("#818cf8")
            icon_color = QColor("#a5b4fc")
        else:
            bg_color = QColor(16, 18, 24, 210) if not self._hover else QColor(30, 36, 50, 240)
            border_color = QColor("#818cf8") if self._hover else QColor(45, 52, 68, 180)
            icon_color = QColor("#f1f5f9") if self._hover else QColor("#94a3b8")

        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(border_color, 1.6))
        p.drawPolygon(poly)

        p.setPen(QPen(icon_color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        s = r * 0.44

        if self.icon_type == 'target':
            p.drawEllipse(QPointF(cx, cy), s*0.85, s*0.85)
            p.drawEllipse(QPointF(cx, cy), s*0.35, s*0.35)
            p.drawLine(QPointF(cx - s*1.15, cy), QPointF(cx - s*0.5, cy))
            p.drawLine(QPointF(cx + s*0.5, cy), QPointF(cx + s*1.15, cy))
            p.drawLine(QPointF(cx, cy - s*1.15), QPointF(cx, cy - s*0.5))
            p.drawLine(QPointF(cx, cy + s*0.5), QPointF(cx, cy + s*1.15))

        elif self.icon_type == 'user':
            p.drawEllipse(QPointF(cx, cy - s*0.45), s*0.4, s*0.4)
            path.moveTo(cx - s*0.75, cy + s*0.8)
            path.quadTo(cx - s*0.75, cy + s*0.15, cx, cy + s*0.15)
            path.quadTo(cx + s*0.75, cy + s*0.15, cx + s*0.75, cy + s*0.8)
            p.drawPath(path)

        elif self.icon_type == 'shield':
            path.moveTo(cx, cy - s*0.85)
            path.lineTo(cx + s*0.75, cy - s*0.45)
            path.lineTo(cx + s*0.75, cy + s*0.15)
            path.quadTo(cx, cy + s*0.95, cx, cy + s*0.95)
            path.quadTo(cx, cy + s*0.95, cx - s*0.75, cy + s*0.15)
            path.lineTo(cx - s*0.75, cy - s*0.45)
            path.closeSubpath()
            p.drawPath(path)

        elif self.icon_type == 'diamond':
            path.moveTo(cx, cy - s*0.85)
            path.lineTo(cx + s*0.8, cy - s*0.15)
            path.lineTo(cx, cy + s*0.85)
            path.lineTo(cx - s*0.8, cy - s*0.15)
            path.closeSubpath()
            p.drawPath(path)
            p.drawLine(QPointF(cx - s*0.8, cy - s*0.15), QPointF(cx + s*0.8, cy - s*0.15))

        elif self.icon_type == 'chat':
            path.moveTo(cx - s*0.8, cy - s*0.6)
            path.lineTo(cx + s*0.8, cy - s*0.6)
            path.lineTo(cx + s*0.8, cy + s*0.4)
            path.lineTo(cx - s*0.1, cy + s*0.4)
            path.lineTo(cx - s*0.5, cy + s*0.85)
            path.lineTo(cx - s*0.5, cy + s*0.4)
            path.lineTo(cx - s*0.8, cy + s*0.4)
            path.closeSubpath()
            p.drawPath(path)

        elif self.icon_type == 'bars':
            p.drawLine(QPointF(cx - s*0.6, cy + s*0.6), QPointF(cx - s*0.6, cy - s*0.1))
            p.drawLine(QPointF(cx, cy + s*0.6), QPointF(cx, cy - s*0.75))
            p.drawLine(QPointF(cx + s*0.6, cy + s*0.6), QPointF(cx + s*0.6, cy + s*0.15))

        elif self.icon_type == 'gear':
            p.drawEllipse(QPointF(cx, cy), s*0.45, s*0.45)
            for deg in [0, 45, 90, 135, 180, 225, 270, 315]:
                rad = math.radians(deg)
                p.drawLine(
                    QPointF(cx + s*0.55 * math.cos(rad), cy + s*0.55 * math.sin(rad)),
                    QPointF(cx + s*0.9 * math.cos(rad), cy + s*0.9 * math.sin(rad))
                )

        p.end()

# ================= TOP LEFT HONEYCOMB OVERLAY =================
class TopLeftHoneycombOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        r = 21
        dx = math.sqrt(3) * r + 2.5
        dy = 1.5 * r + 2.0
        center_x, center_y = 80, 75

        self.setFixedSize(165, 155)
        self.hex_buttons = {}

        nodes = [
            (center_x, center_y, 'target', "Fake Lag", False, 0),
            (center_x - dx/2, center_y - dy, 'user', "Thông Tin", False, 2),
            (center_x + dx/2, center_y - dy, 'shield', "Antiban (Bảo trì)", True, 4),
            (center_x - dx, center_y, 'diamond', "VIP (Bảo trì)", True, 4),
            (center_x + dx, center_y, 'chat', "Feedback & Chat", False, 3),
            (center_x - dx/2, center_y + dy, 'bars', "Thống Kê (Bảo trì)", True, 4),
            (center_x + dx/2, center_y + dy, 'gear', "Cài Đặt", False, 1)
        ]

        for x, y, icon_t, tip, is_maint, target_idx in nodes:
            btn = VectorHexagonButton(icon_t, tip, is_maintenance=is_maint, radius=r, parent=self)
            btn.move(int(x - r), int(y - r))
            btn.clicked.connect(lambda idx=target_idx: signals.open_tab_requested.emit(idx))
            self.hex_buttons[target_idx] = btn

        self.move(20, 30)

        signals.stream_toggle.connect(lambda enabled: self.hide() if enabled else (self.show() if net_state.is_injected else None))
        signals.show_honeycomb.connect(self.show_after_init)

    def show_after_init(self):
        self.move(20, 30)
        self.show()

    def update_active_node(self, active_idx):
        for k, btn in self.hex_buttons.items():
            btn.is_active = (k == active_idx)
            btn.update()

# ================= CÁC THÀNH PHẦN GIAO DIỆN CƠ BẢN =================
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
        self.particles = [Particle(360, 265) for _ in range(30)]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_particles)
        self.timer.start(33)

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
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

        p.setPen(Qt.PenStyle.NoPen)
        for pt in self.particles:
            p.setBrush(QBrush(QColor(255, 255, 255, pt.alpha)))
            p.drawEllipse(QPointF(pt.x, pt.y), pt.size / 2.0, pt.size / 2.0)
        p.end()

# ================= TOPBAR DÙNG CHUNG =================
class TopBar(QWidget):
    def __init__(self, title_text, on_close=None, on_minimize=None, on_logo_click=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        bar_layout = QHBoxLayout(self)
        bar_layout.setContentsMargins(8, 0, 8, 0)
        bar_layout.setSpacing(6)

        bar_layout.addWidget(GlowingCircleDot())

        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet("color: #d1d5db; font-size: 10px; font-weight: 700; font-family: 'Consolas', 'Segoe UI', Arial; background: transparent; border: none;")
        if on_logo_click:
            self.title_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            self.title_lbl.mousePressEvent = lambda e: on_logo_click()
        bar_layout.addWidget(self.title_lbl)
        bar_layout.addStretch()

        if on_minimize:
            min_btn = QPushButton("—")
            min_btn.setFixedSize(16, 16)
            min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            min_btn.setStyleSheet("QPushButton { background: transparent; color: #6b7280; border: none; font-size: 10px; font-weight: bold; } QPushButton:hover { color: #ffffff; }")
            min_btn.clicked.connect(on_minimize)
            bar_layout.addWidget(min_btn)

        if on_close:
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(16, 16)
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setStyleSheet("QPushButton { background: transparent; color: #6b7280; border: none; font-size: 11px; font-weight: bold; } QPushButton:hover { color: #ef4444; }")
            close_btn.clicked.connect(on_close)
            bar_layout.addWidget(close_btn)

# ================= CLASS CỬA SỔ FLOATING PANEL =================
class FloatingTabWindow(QWidget):
    def __init__(self, title_text, initial_w=285, initial_h=190, is_fake_lag_tab=False):
        super().__init__()
        self.is_fake_lag_tab = is_fake_lag_tab
        self.setWindowTitle(title_text)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(initial_w, initial_h)

        main_box = QVBoxLayout(self)
        main_box.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = CustomParticleFrame(self)
        main_box.addWidget(self.bg_frame)

        self.content_layout = QVBoxLayout(self.bg_frame)
        self.content_layout.setContentsMargins(8, 4, 8, 8)
        self.content_layout.setSpacing(4)

        self.top_bar = TopBar(title_text, on_close=self.hide_panel, on_minimize=self.hide_panel)
        self.content_layout.addWidget(self.top_bar)

        self._drag = False
        self._pos = None

    def hide_panel(self):
        self.hide()
        if self.is_fake_lag_tab:
            net_state.is_fake_lag_tab_open = False
            stop_all_features()

    def show_panel(self):
        self.show()
        self.raise_()
        self.activateWindow()
        if self.is_fake_lag_tab:
            net_state.is_fake_lag_tab_open = True

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and self._pos:
            self.move(e.globalPosition().toPoint() - self._pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = False
        e.accept()

# ================= 1. TAB FAKE LAG WINDOW =================
class FakeLagWindow(FloatingTabWindow):
    def __init__(self):
        super().__init__("ZeroX - Fake Lag", initial_w=280, initial_h=180, is_fake_lag_tab=True)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

        self.btn_tele = self.create_key_row(layout, "TELEKILL", app_config.tele_hotkey, 'tele_hotkey')
        self.btn_freeze = self.create_key_row(layout, "FREEZE", app_config.freeze_hotkey, 'freeze_hotkey')
        self.btn_ghost = self.create_key_row(layout, "GHOST", app_config.ghost_hotkey, 'ghost_hotkey')
        self.btn_aimlag = self.create_key_row(layout, "AIM LAG", app_config.aimlag_hotkey, 'aimlag_hotkey')

        self.content_layout.addLayout(layout)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_key_expiry_display)
        self.countdown_timer.start(1000)

    def create_key_row(self, parent_layout, label_text, config_obj, config_key):
        row = QHBoxLayout()
        row.setContentsMargins(4, 1, 4, 1)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #f4f4f5; font-size: 11px; font-weight: 700; font-family: 'Segoe UI', Arial; letter-spacing: 0.8px;")
        row.addWidget(lbl)
        row.addStretch()

        btn = QPushButton(config_obj.key.upper())
        btn.setFixedSize(58, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #12151c;
                color: #ffffff;
                border: 1px solid #222733;
                border-radius: 5px;
                font-size: 10.5px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial;
            }
            QPushButton:hover { background-color: #1a1f2c; border-color: #3b4252; }
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
                signals.key_expired.emit()
                return
            else:
                days = int(rem // 86400)
                hrs = int((rem % 86400) // 3600)
                mins = int((rem % 3600) // 60)
                secs = int(rem % 60)

                time_str = f"{days}d {hrs:02d}h {mins:02d}m {secs:02d}s" if days > 0 else f"{hrs:02d}h {mins:02d}m {secs:02d}s"
                time_badge = f'<span style="color:#00ff66; font-weight:800; font-size:9.5px;">[{time_str}]</span>'

        self.top_bar.title_lbl.setText(f"{key_badge} {time_badge}")

# ================= 2. TAB SETTING WINDOW =================
class SettingWindow(FloatingTabWindow):
    def __init__(self):
        super().__init__("ZeroX - Cài Đặt", initial_w=280, initial_h=175)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(4)

        self.btn_beep_tele = QPushButton()
        self.btn_beep_freeze = QPushButton()
        self.btn_beep_ghost = QPushButton()
        self.btn_beep_aimlag = QPushButton()

        for b in [self.btn_beep_tele, self.btn_beep_freeze, self.btn_beep_ghost, self.btn_beep_aimlag]:
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_beep_tele.clicked.connect(lambda: self.toggle_beep('tele'))
        self.btn_beep_freeze.clicked.connect(lambda: self.toggle_beep('freeze'))
        self.btn_beep_ghost.clicked.connect(lambda: self.toggle_beep('ghost'))
        self.btn_beep_aimlag.clicked.connect(lambda: self.toggle_beep('aimlag'))

        grid.addWidget(self.btn_beep_tele, 0, 0)
        grid.addWidget(self.btn_beep_freeze, 0, 1)
        grid.addWidget(self.btn_beep_ghost, 1, 0)
        grid.addWidget(self.btn_beep_aimlag, 1, 1)

        layout.addLayout(grid)

        self.fix_dame_btn = QPushButton()
        self.fix_dame_btn.setFixedHeight(26)
        self.fix_dame_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fix_dame_btn.clicked.connect(self.toggle_fix_dame)
        layout.addWidget(self.fix_dame_btn)

        self.content_layout.addLayout(layout)
        self.update_all_buttons()

    def update_btn_style(self, btn, text, enabled):
        btn.setText(f"{text}: {'ON' if enabled else 'OFF'}")
        color = "#00ff66" if enabled else "#9ca3af"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #0e1117;
                color: {color};
                border: 1px solid #27272a;
                border-radius: 5px;
                font-size: 9.5px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial;
            }}
            QPushButton:hover {{ background-color: #141821; border-color: #3f3f46; color: #ffffff; }}
        """)

    def update_all_buttons(self):
        self.update_btn_style(self.btn_beep_tele, "Beep Tele", app_config.beep_tele)
        self.update_btn_style(self.btn_beep_freeze, "Beep Freeze", app_config.beep_freeze)
        self.update_btn_style(self.btn_beep_ghost, "Beep Ghost", app_config.beep_ghost)
        self.update_btn_style(self.btn_beep_aimlag, "Beep AimLag", app_config.beep_aimlag)
        self.update_btn_style(self.fix_dame_btn, "Fix Dame", app_config.fix_dame_enabled)

    def toggle_beep(self, kind):
        if kind == 'tele': app_config.beep_tele = not app_config.beep_tele
        elif kind == 'freeze': app_config.beep_freeze = not app_config.beep_freeze
        elif kind == 'ghost': app_config.beep_ghost = not app_config.beep_ghost
        elif kind == 'aimlag': app_config.beep_aimlag = not app_config.beep_aimlag
        save_config()
        self.update_all_buttons()

    def toggle_fix_dame(self):
        app_config.fix_dame_enabled = not app_config.fix_dame_enabled
        save_config()
        self.update_all_buttons()
        stop_all_features()

# ================= 3. TAB INFO WINDOW =================
class InfoWindow(FloatingTabWindow):
    def __init__(self):
        super().__init__("ZeroX - Thông Tin", initial_w=290, initial_h=215)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: #11141b;
                border: 1px solid #1f2633;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(4)

        title = QLabel("THÔNG TIN TÀI KHOẢN & MÁY")
        title.setStyleSheet("color: #ffffff; font-size: 10px; font-weight: 800; font-family: 'Segoe UI', Arial; border-bottom: 1px solid #1e2533; padding-bottom: 4px;")
        card_layout.addWidget(title)

        self.lbl_key = QLabel("LICENSE KEY: Đang tải...")
        self.lbl_key.setStyleSheet("color: #60a5fa; font-size: 9.5px; font-weight: 700; font-family: 'Consolas', monospace;")
        card_layout.addWidget(self.lbl_key)

        self.lbl_hwid = QLabel(f"HWID: {CURRENT_HWID}")
        self.lbl_hwid.setStyleSheet("color: #9ca3af; font-size: 9px; font-family: 'Consolas', monospace;")
        card_layout.addWidget(self.lbl_hwid)

        self.lbl_ip = QLabel("IP: Đang tải...")
        self.lbl_ip.setStyleSheet("color: #9ca3af; font-size: 9px; font-family: 'Consolas', monospace;")
        card_layout.addWidget(self.lbl_ip)

        self.lbl_expiry = QLabel("Hạn Dùng: Đang tải...")
        self.lbl_expiry.setStyleSheet("color: #22c55e; font-size: 9px; font-weight: 700; font-family: 'Segoe UI', Arial;")
        card_layout.addWidget(self.lbl_expiry)

        self.lbl_version = QLabel(f"Phiên bản: {APP_VERSION}  |  Ngày: {BUILD_DATE}")
        self.lbl_version.setStyleSheet("color: #64748b; font-size: 8.5px; font-family: 'Segoe UI', Arial;")
        card_layout.addWidget(self.lbl_version)

        self.lbl_user = QLabel(f"Tên hiển thị: <span style='color:#22c55e; font-weight:bold;'>✔ {app_config.custom_nickname}</span>")
        self.lbl_user.setStyleSheet("color: #cbd5e1; font-size: 9px; font-family: 'Segoe UI', Arial;")
        card_layout.addWidget(self.lbl_user)

        layout.addWidget(self.card)
        self.content_layout.addLayout(layout)

    def show_panel(self):
        self.update_info()
        super().show_panel()

    def update_info(self):
        curr_key = net_state.active_key or load_saved_key() or "KEY"
        exp_at = net_state.key_expires_at
        
        if exp_at == -1:
            role_badge = "<span style='color:#f59e0b; font-weight:800;'>[VIP]</span>"
            time_str = "Vĩnh viễn"
        elif exp_at > 0:
            rem = max(0, exp_at - time.time())
            days = int(rem // 86400)
            hrs = int((rem % 86400) // 3600)
            mins = int((rem % 3600) // 60)
            
            role_badge = "<span style='color:#f59e0b; font-weight:800;'>[VIP]</span>" if (rem > 86400 or days > 0) else "<span style='color:#60a5fa; font-weight:800;'>[FREE]</span>"
            time_str = f"{days}d {hrs:02d}h {mins:02d}m" if days > 0 else f"{hrs:02d}h {mins:02d}m"
        else:
            role_badge = "<span style='color:#ef4444;'>[Hết hạn]</span>"
            time_str = "Hết hạn"

        self.lbl_key.setText(f"LICENSE KEY: {curr_key} {role_badge}")
        self.lbl_ip.setText(f"IP: {net_state.cached_ip}")
        self.lbl_expiry.setText(f"Thời hạn còn lại: {time_str}")
        self.lbl_user.setText(f"Tên hiển thị: <span style='color:#22c55e; font-weight:bold;'>✔ {app_config.custom_nickname}</span>")

# ================= 4. TAB FEEDBACK & CHAT WINDOW =================
class FeedbackChatWindow(FloatingTabWindow):
    def __init__(self):
        super().__init__("ZeroX - Feedback & Chat", initial_w=310, initial_h=240)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(3)

        sub_tab_layout = QHBoxLayout()
        sub_tab_layout.setSpacing(4)

        self.btn_tab_fb = QPushButton("✉ Feedback")
        self.btn_tab_chat = QPushButton("💬 Chat")
        self.btn_tab_fb.setFixedHeight(22)
        self.btn_tab_chat.setFixedHeight(22)
        self.btn_tab_fb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_chat.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_tab_fb.clicked.connect(lambda: self.switch_sub_tab(0))
        self.btn_tab_chat.clicked.connect(lambda: self.switch_sub_tab(1))

        sub_tab_layout.addWidget(self.btn_tab_fb)
        sub_tab_layout.addWidget(self.btn_tab_chat)
        layout.addLayout(sub_tab_layout)

        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        lbl_n = QLabel("Tên hiển thị:")
        lbl_n.setStyleSheet("color:#9ca3af; font-size:8.8px; font-weight:bold;")
        
        self.name_input = QLineEdit()
        self.name_input.setText(app_config.custom_nickname)
        self.name_input.setPlaceholderText("Nhập tên...")
        self.name_input.setFixedHeight(22)
        
        self.lock_name_btn = QPushButton("Lưu & Khóa")
        self.lock_name_btn.setFixedHeight(22)
        self.lock_name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_name_btn.clicked.connect(self.lock_custom_name)

        if app_config.is_name_locked:
            self.name_input.setReadOnly(True)
            self.name_input.setStyleSheet("background-color:#161922; border:1px solid #272f3d; border-radius:4px; color:#22c55e; font-size:9.5px; font-weight:bold; padding:0 5px;")
            self.lock_name_btn.setText("🔒 Đã khóa")
            self.lock_name_btn.setEnabled(False)
            self.lock_name_btn.setStyleSheet("background-color:#1e2430; color:#64748b; border:none; border-radius:4px; font-size:8.5px; padding:0 6px;")
        else:
            self.name_input.setStyleSheet("background-color:#12141a; border:1px solid #1c202a; border-radius:4px; color:#38bdf8; font-size:9.5px; font-weight:bold; padding:0 5px;")
            self.lock_name_btn.setStyleSheet("background-color:#0284c7; color:#fff; border:none; border-radius:4px; font-size:8.5px; font-weight:bold; padding:0 6px;")

        name_row.addWidget(lbl_n)
        name_row.addWidget(self.name_input)
        name_row.addWidget(self.lock_name_btn)
        layout.addLayout(name_row)

        self.sub_stack = QStackedWidget()
        
        # VIEW 1: FEEDBACK
        fb_view = QWidget()
        fb_layout = QVBoxLayout(fb_view)
        fb_layout.setContentsMargins(0, 2, 0, 0)
        fb_layout.setSpacing(3)

        tip_lbl = QLabel("💡 Panel tự động chụp màn hình game gửi lên Discord.")
        tip_lbl.setWordWrap(True)
        tip_lbl.setStyleSheet("color: #facc15; font-size: 8.5px; font-family: 'Segoe UI', Arial; background: rgba(234, 179, 8, 0.1); padding: 3px; border-radius: 4px;")
        fb_layout.addWidget(tip_lbl)

        self.fb_input = QLineEdit()
        self.fb_input.setPlaceholderText("Ghi chú phản hồi / báo lỗi (có thể bỏ trống)...")
        self.fb_input.setFixedHeight(26)
        self.fb_input.setStyleSheet("background-color: #12141a; border: 1px solid #1c202a; border-radius: 5px; color: #fff; font-size: 9.5px; padding: 0 6px;")
        fb_layout.addWidget(self.fb_input)

        self.send_fb_btn = QPushButton("📷 GỬI FEEDBACK")
        self.send_fb_btn.setFixedHeight(26)
        self.send_fb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_fb_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; border-radius: 5px; font-size: 10px; font-weight: 800;")
        self.send_fb_btn.clicked.connect(self.handle_send_feedback)
        fb_layout.addWidget(self.send_fb_btn)

        # VIEW 2: CHAT TRỰC TIẾP VPS + DISCORD
        chat_view = QWidget()
        chat_layout = QVBoxLayout(chat_view)
        chat_layout.setContentsMargins(0, 2, 0, 0)
        chat_layout.setSpacing(3)

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setFixedHeight(85)
        self.chat_box.setStyleSheet("background-color: #11141a; border: 1px solid #1c202a; border-radius: 5px; color: #d1d5db; font-size: 9px; font-family: 'Consolas', monospace; padding: 3px;")
        chat_layout.addWidget(self.chat_box)

        send_row = QHBoxLayout()
        send_row.setSpacing(4)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Nhập tin nhắn...")
        self.chat_input.setFixedHeight(24)
        self.chat_input.setStyleSheet("background-color: #12141a; border: 1px solid #1c202a; border-radius: 5px; color: #fff; font-size: 9.5px; padding: 0 6px;")
        self.chat_input.returnPressed.connect(self.handle_send_chat)

        self.send_chat_btn = QPushButton("Gửi")
        self.send_chat_btn.setFixedSize(45, 24)
        self.send_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_chat_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; border-radius: 5px; font-size: 9.5px; font-weight: 800;")
        self.send_chat_btn.clicked.connect(self.handle_send_chat)

        send_row.addWidget(self.chat_input)
        send_row.addWidget(self.send_chat_btn)
        chat_layout.addLayout(send_row)

        self.sub_stack.addWidget(fb_view)
        self.sub_stack.addWidget(chat_view)
        layout.addWidget(self.sub_stack)

        self.content_layout.addLayout(layout)
        self.switch_sub_tab(0)

        self.chat_timer = QTimer(self)
        self.chat_timer.timeout.connect(self.fetch_vps_chat)
        self.chat_timer.start(3000)

    def lock_custom_name(self):
        val = self.name_input.text().strip() or DEFAULT_USERNAME
        app_config.custom_nickname = val
        app_config.is_name_locked = True
        save_config()
        self.name_input.setText(val)
        self.name_input.setReadOnly(True)
        self.name_input.setStyleSheet("background-color:#161922; border:1px solid #272f3d; border-radius:4px; color:#22c55e; font-size:9.5px; font-weight:bold; padding:0 5px;")
        self.lock_name_btn.setText("🔒 Đã khóa")
        self.lock_name_btn.setEnabled(False)
        self.lock_name_btn.setStyleSheet("background-color:#1e2430; color:#64748b; border:none; border-radius:4px; font-size:8.5px; padding:0 6px;")

    def switch_sub_tab(self, idx):
        self.sub_stack.setCurrentIndex(idx)
        style_active = "background-color: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 4px; font-size: 9px; font-weight: bold;"
        style_inactive = "background-color: #0e1117; color: #9ca3af; border: 1px solid #27272a; border-radius: 4px; font-size: 9px;"
        self.btn_tab_fb.setStyleSheet(style_active if idx == 0 else style_inactive)
        self.btn_tab_chat.setStyleSheet(style_active if idx == 1 else style_inactive)
        if idx == 1:
            self.fetch_vps_chat()

    def get_role_tag(self):
        exp_at = net_state.key_expires_at
        if exp_at == -1 or (exp_at - time.time()) > 86400:
            return "VIP"
        return "FREE"

    def fetch_vps_chat(self):
        def _fetch():
            try:
                r = requests.get(VPS_CHAT_URL, timeout=3)
                if r.status_code == 200:
                    messages = r.json().get("messages", [])
                    QTimer.singleShot(0, lambda: self._render_messages(messages))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _render_messages(self, messages):
        if not messages: return
        html_lines = []
        for m in messages:
            t = m.get("time", "00:00")
            role = m.get("role", "FREE")
            user = m.get("user", "User")
            txt = m.get("text", "")
            col = "#f59e0b" if role == "VIP" else "#60a5fa"
            html_lines.append(f"<span style='color:#6b7280;'>[{t}]</span> <span style='color:{col}; font-weight:bold;'>[{role}]</span> <b>{user}:</b> {txt}")
        
        self.chat_box.setHtml("<br>".join(html_lines))
        self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())

    def handle_send_feedback(self):
        if not app_config.is_name_locked:
            self.lock_custom_name()

        note_text = self.fb_input.text().strip() or "Không có ghi chú"
        self.send_fb_btn.setText("ĐANG GỬI...")
        self.send_fb_btn.setEnabled(False)

        img_data = None
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                byte_array = QBuffer()
                byte_array.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(byte_array, "PNG")
                img_data = bytes(byte_array.data())
        except Exception as e:
            debug_log(f"Screen capture error: {e}")

        user_name = app_config.custom_nickname

        def _send():
            try:
                payload_json = {
                    "content": "📸 **BÁO CÁO FEEDBACK / LỖI TỪ PANEL PC**",
                    "embeds": [
                        {
                            "title": f"Feedback từ User: {user_name}",
                            "color": 3447003,
                            "fields": [
                                {
                                    "name": "👤 Username",
                                    "value": f"`{user_name}`",
                                    "inline": False
                                },
                                {
                                    "name": "📝 Ghi chú",
                                    "value": note_text,
                                    "inline": False
                                }
                            ],
                            "image": {
                                "url": "attachment://screenshot.png"
                            },
                            "footer": {
                                "text": f"ZeroX Feedback System • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                            }
                        }
                    ]
                }

                if img_data:
                    files = {
                        "payload_json": (None, json.dumps(payload_json), "application/json"),
                        "file": ("screenshot.png", img_data, "image/png")
                    }
                    requests.post(DISCORD_FEEDBACK_WEBHOOK, files=files, timeout=10)
                else:
                    requests.post(DISCORD_FEEDBACK_WEBHOOK, json=payload_json, timeout=10)
            except Exception as e:
                debug_log(f"Feedback error: {e}")
            finally:
                QTimer.singleShot(0, self._on_fb_sent)

        threading.Thread(target=_send, daemon=True).start()

    def _on_fb_sent(self):
        self.send_fb_btn.setText("✔ ĐÃ GỬI THÀNH CÔNG")
        self.fb_input.setText("")
        QTimer.singleShot(2000, self._reset_fb_button)

    def _reset_fb_button(self):
        self.send_fb_btn.setText("📷 GỬI FEEDBACK")
        self.send_fb_btn.setEnabled(True)

    def handle_send_chat(self):
        if not app_config.is_name_locked:
            self.lock_custom_name()

        text = self.chat_input.text().strip()
        if not text: return

        role = self.get_role_tag()
        user_name = app_config.custom_nickname
        curr_time_str = datetime.now().strftime("%H:%M")
        col = "#f59e0b" if role == "VIP" else "#60a5fa"

        self.chat_box.append(f"<span style='color:#6b7280;'>[{curr_time_str}]</span> <span style='color:{col}; font-weight:bold;'>[{role}]</span> <b>{user_name}:</b> {text}")
        self.chat_box.verticalScrollBar().setValue(self.chat_box.verticalScrollBar().maximum())
        self.chat_input.setText("")

        def _send_vps():
            try:
                requests.post(VPS_CHAT_URL, json={"role": role, "user": user_name, "text": text}, timeout=4)
                requests.post(DISCORD_CHAT_WEBHOOK, json={"content": f"💬 **[{role}] {user_name}**: {text}"}, timeout=4)
            except Exception:
                pass
            finally:
                self.fetch_vps_chat()

        threading.Thread(target=_send_vps, daemon=True).start()

# ================= 5. TAB COMING SOON WINDOW =================
class ComingSoonWindow(FloatingTabWindow):
    def __init__(self):
        super().__init__("ZeroX - Bảo Trì", initial_w=280, initial_h=150)

        layout = QVBoxLayout()
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #11141b;
                border: 1px solid #1f2633;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(15, 15, 15, 15)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.setSpacing(5)

        lbl_cs = QLabel("COMING SOON")
        lbl_cs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_cs.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 900; font-family: 'Consolas', sans-serif; letter-spacing: 2px;")
        c_layout.addWidget(lbl_cs)

        lbl_sub = QLabel("Tính năng đang trong quá trình bảo trì.")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("color: #64748b; font-size: 9px; font-family: 'Segoe UI', Arial;")
        c_layout.addWidget(lbl_sub)

        layout.addWidget(card)
        self.content_layout.addLayout(layout)

# ================= QUẢN LÝ TẤT CẢ CỬA SỔ FLOATING =================
class WindowManager:
    def __init__(self):
        self.fake_lag_win = FakeLagWindow()
        self.setting_win = SettingWindow()
        self.info_win = InfoWindow()
        self.feedback_chat_win = FeedbackChatWindow()
        self.coming_soon_win = ComingSoonWindow()

        signals.open_tab_requested.connect(self.handle_tab_toggle)

    def handle_tab_toggle(self, index):
        wins = {
            0: self.fake_lag_win,
            1: self.setting_win,
            2: self.info_win,
            3: self.feedback_chat_win,
            4: self.coming_soon_win
        }
        target_win = wins.get(index)
        if target_win:
            if target_win.isVisible():
                target_win.hide_panel()
            else:
                target_win.show_panel()

# ================= CỬA SỔ KHỞI ĐỘNG (LAUNCHER CONTAINER) =================
class MainContainerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(AntiBan.get_title())
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(300, 205)

        main_box = QVBoxLayout(self)
        main_box.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = CustomParticleFrame(self)
        main_box.addWidget(self.bg_frame)

        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        bg_layout.addWidget(self.stack)

        self.init_gui_view = InitialGuiWidget(self.on_adb_clicked, cleanup_and_exit, self.showMinimized)
        self.adb_loading_view = AdbLoadingWidget(self.on_adb_choice_done, cleanup_and_exit, self.showMinimized)
        self.login_view = LoginWidget(self.on_login_success, cleanup_and_exit, self.showMinimized)
        self.download_view = DownloadWidget(self.on_inject_clicked, cleanup_and_exit)
        self.init_view = InitializingWidget(self.on_init_finished)
        self.expired_view = KeyExpiredWidget(self.on_expired_relogin, cleanup_and_exit)

        self.stack.addWidget(self.init_gui_view)      # 0
        self.stack.addWidget(self.adb_loading_view)    # 1
        self.stack.addWidget(self.login_view)          # 2
        self.stack.addWidget(self.download_view)       # 3
        self.stack.addWidget(self.init_view)           # 4
        self.stack.addWidget(self.expired_view)        # 5

        self.stack.setCurrentIndex(0)

        self.sync_key_timer = QTimer(self)
        self.sync_key_timer.timeout.connect(self.sync_key_with_server)

        signals.toggle_visibility.connect(self.toggle_visibility)
        signals.key_expired.connect(self.handle_key_expired)

        self._drag = False
        self._pos = None

    def sync_key_with_server(self):
        if not net_state.is_authenticated or not net_state.active_key:
            return
        
        def _do_sync():
            valid, msg, exp_at = verify_key_with_vps(net_state.active_key)
            if valid:
                net_state.key_expires_at = exp_at
            else:
                signals.key_expired.emit()
                
        threading.Thread(target=_do_sync, daemon=True).start()

    def on_adb_clicked(self):
        self.stack.setCurrentIndex(1)
        self.adb_loading_view.start_loading()

    def on_adb_choice_done(self):
        self.stack.setCurrentIndex(2)

    def on_login_success(self):
        net_state.is_authenticated = True
        self.sync_key_timer.start(3500)
        self.stack.setCurrentIndex(3)
        self.download_view.start_download()

    def on_inject_clicked(self):
        signals.start_tracking.emit()
        self.stack.setCurrentIndex(4)
        self.init_view.start()

    def on_init_finished(self):
        net_state.is_injected = True
        self.hide()
        signals.show_honeycomb.emit()
        signals.open_tab_requested.emit(0)

    def handle_key_expired(self):
        self.sync_key_timer.stop()
        stop_all_features()
        net_state.is_authenticated = False
        net_state.is_injected = False
        audio.beep(300, 150)

        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self.stack.setCurrentIndex(5)

    def on_expired_relogin(self):
        self.login_view.status_msg.setText("")
        self.stack.setCurrentIndex(2)

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and self._pos:
            self.move(e.globalPosition().toPoint() - self._pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = False
        e.accept()

# ================= OVERLAYS (HUD & RAINBOW) =================
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
        self.setFixedSize(220, 24)

        self.hue_offset = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_rainbow)
        self.timer.start(33)

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

        p.setPen(QPen(QBrush(grad), 1))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ZeroX Mods")
        p.end()

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
        self.setFixedSize(160, 200)

        hud_layout = QVBoxLayout(self)
        hud_layout.setContentsMargins(0, 0, 0, 0)
        hud_layout.setSpacing(5)
        hud_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.items = {}
        for key, text, color in [("Freeze", "FREEZE ACTIVE", "#00f0ff"),
                                 ("Telekill", "TELEKILL ACTIVE", "#7000ff"),
                                 ("Ghost", "GHOST ACTIVE", "#00ff88"),
                                 ("AimLag", "AIMLAG ACTIVE", "#ffaa00")]:
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
            hud_layout.addWidget(lbl)
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

def cleanup_and_exit():
    net_state.running = False
    stop_all_features()
    try: keyboard.unhook_all()
    except Exception: pass
    QApplication.quit()
    os._exit(0)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)

    main_win = MainContainerWindow()
    main_win.show()

    # Quản lý mở nhiều tab độc lập & Tổ ong
    win_manager = WindowManager()
    honeycomb_overlay = TopLeftHoneycombOverlay()
    signals.open_tab_requested.connect(honeycomb_overlay.update_active_node)

    hud = OverlayHUD()
    rainbow = RainbowHeaderOverlay()

    threading.Thread(target=divert_freeze_fix_dame_worker, daemon=True).start()
    threading.Thread(target=hotkey_loop, daemon=True).start()

    mouse_listener = pynput_mouse.Listener(on_click=on_mouse_click)
    mouse_listener.daemon = True
    mouse_listener.start()

    keyboard.add_hotkey('f10', cleanup_and_exit)
    app.aboutToQuit.connect(cleanup_and_exit)
    sys.exit(app.exec())
