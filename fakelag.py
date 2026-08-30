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
VPS_VERIFY_URL = "http://103.78.3.222:53689/api/verify_key"
GET_KEY_URL = "http://103.78.3.222:53689/"
LICENSE_FILE = "zerox_license.json"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1543470614025863308/SD9lOHs2pxJZFrdFFuYQMBOkKAF_6xgY8xetSagvXEU8fUc4O5e_jriDdIIbO1vylQrL"

APP_VERSION = "1.3.4"
BUILD_DATE = "30/08/2026"
BUILD_TIME = "11:00:00"

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
LOCAL_USERNAME = os.environ.get('USERNAME', os.environ.get('USER', 'User'))

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

HOTKEY_FILE = 'zerox_hotkey.json'

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
            'fix_dame_enabled': app_config.fix_dame_enabled
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
    show_maint_toast = pyqtSignal(str)

signals = AppSignals()

class NetState:
    def __init__(self):
        self.lock = threading.Lock()
        self.tele_mode = False
        self.freeze_mode = False
        self.ghost_mode = False
        
        self.aimlag_armed = False
        self.mouse_held = False

        self.running = True
        self.is_authenticated = False
        self.is_injected = False
        self.active_key = ""
        self.key_expires_at = -1
        self.cached_ip = "Đang tải..."
        
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

def toggle_freeze():
    if not net_state.is_injected: return
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
    if not net_state.is_injected: return
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
    if not net_state.is_injected: return
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
    if not net_state.is_injected: return
    with net_state.lock:
        net_state.aimlag_armed = not net_state.aimlag_armed
        active = net_state.aimlag_armed
        if not active:
            net_state.mouse_held = False
            aimlag_session.stop_and_flush()

    audio.play_aimlag(active)
    signals.notify.emit('AimLag', active)

def on_mouse_click(x, y, button, pressed):
    if not net_state.is_authenticated or not net_state.is_injected:
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

# ================= VECTOR CUSTOM ICON HEXAGON BUTTON (TỰ VẼ BẰNG QPAINTER) =================
class VectorHexagonButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_type, tooltip_text, is_maintenance=False, is_active=False, radius=22, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type  # 'target', 'user', 'shield', 'diamond', 'chat', 'bars', 'gear'
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

        # Vẽ hình lục giác
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

        # Vẽ Icon Vector đơn sắc (Không màu mè / Không dùng icon có sẵn)
        p.setPen(QPen(icon_color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        s = r * 0.44

        if self.icon_type == 'target': # Trung tâm: Crosshair / Target Aim
            p.drawEllipse(QPointF(cx, cy), s*0.85, s*0.85)
            p.drawEllipse(QPointF(cx, cy), s*0.35, s*0.35)
            p.drawLine(QPointF(cx - s*1.15, cy), QPointF(cx - s*0.5, cy))
            p.drawLine(QPointF(cx + s*0.5, cy), QPointF(cx + s*1.15, cy))
            p.drawLine(QPointF(cx, cy - s*1.15), QPointF(cx, cy - s*0.5))
            p.drawLine(QPointF(cx, cy + s*0.5), QPointF(cx, cy + s*1.15))

        elif self.icon_type == 'user': # Info: Hình người
            p.drawEllipse(QPointF(cx, cy - s*0.45), s*0.4, s*0.4)
            path.moveTo(cx - s*0.75, cy + s*0.8)
            path.quadTo(cx - s*0.75, cy + s*0.15, cx, cy + s*0.15)
            path.quadTo(cx + s*0.75, cy + s*0.15, cx + s*0.75, cy + s*0.8)
            p.drawPath(path)

        elif self.icon_type == 'shield': # Bảo trì: Khiên
            path.moveTo(cx, cy - s*0.85)
            path.lineTo(cx + s*0.75, cy - s*0.45)
            path.lineTo(cx + s*0.75, cy + s*0.15)
            path.quadTo(cx, cy + s*0.95, cx, cy + s*0.95)
            path.quadTo(cx, cy + s*0.95, cx - s*0.75, cy + s*0.15)
            path.lineTo(cx - s*0.75, cy - s*0.45)
            path.closeSubpath()
            p.drawPath(path)

        elif self.icon_type == 'diamond': # Bảo trì: Kim cương
            path.moveTo(cx, cy - s*0.85)
            path.lineTo(cx + s*0.8, cy - s*0.15)
            path.lineTo(cx, cy + s*0.85)
            path.lineTo(cx - s*0.8, cy - s*0.15)
            path.closeSubpath()
            p.drawPath(path)
            p.drawLine(QPointF(cx - s*0.8, cy - s*0.15), QPointF(cx + s*0.8, cy - s*0.15))

        elif self.icon_type == 'chat': # Feedback / Chat: Hộp thoại
            path.moveTo(cx - s*0.8, cy - s*0.6)
            path.lineTo(cx + s*0.8, cy - s*0.6)
            path.lineTo(cx + s*0.8, cy + s*0.4)
            path.lineTo(cx - s*0.1, cy + s*0.4)
            path.lineTo(cx - s*0.5, cy + s*0.85)
            path.lineTo(cx - s*0.5, cy + s*0.4)
            path.lineTo(cx - s*0.8, cy + s*0.4)
            path.closeSubpath()
            p.drawPath(path)

        elif self.icon_type == 'bars': # Bảo trì: Cột sóng
            p.drawLine(QPointF(cx - s*0.6, cy + s*0.6), QPointF(cx - s*0.6, cy - s*0.1))
            p.drawLine(QPointF(cx, cy + s*0.6), QPointF(cx, cy - s*0.75))
            p.drawLine(QPointF(cx + s*0.6, cy + s*0.6), QPointF(cx + s*0.6, cy + s*0.15))

        elif self.icon_type == 'gear': # Setting: Bánh răng
            p.drawEllipse(QPointF(cx, cy), s*0.45, s*0.45)
            for deg in [0, 45, 90, 135, 180, 225, 270, 315]:
                rad = math.radians(deg)
                p.drawLine(
                    QPointF(cx + s*0.55 * math.cos(rad), cy + s*0.55 * math.sin(rad)),
                    QPointF(cx + s*0.9 * math.cos(rad), cy + s*0.9 * math.sin(rad))
                )

        p.end()

# ================= MENU TỔ ONG NẰM GÓC TRÊN BÊN TRÁI MÀN HÌNH =================
class TopLeftHoneycombOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        r = 21
        dx = math.sqrt(3) * r + 2.5
        dy = 1.5 * r + 2.0
        center_x, center_y = 80, 75

        self.setFixedSize(165, 155)
        self.hex_buttons = {}

        # 7 ô tổ ong đúng chuẩn:
        nodes = [
            (center_x, center_y, 'target', "Fake Lag (Bấm mở Menu)", False, 0),
            (center_x - dx/2, center_y - dy, 'user', "Thông Tin Máy & Key", False, 2),
            (center_x + dx/2, center_y - dy, 'shield', "Bảo vệ Antiban", True, "Antiban"),
            (center_x - dx, center_y, 'diamond', "Chức Năng VIP", True, "VIP"),
            (center_x + dx, center_y, 'chat', "Feedback & Chat", False, 3),
            (center_x - dx/2, center_y + dy, 'bars', "Thống Kê", True, "Statistics"),
            (center_x + dx/2, center_y + dy, 'gear', "Cài Đặt", False, 1)
        ]

        for x, y, icon_t, tip, is_maint, target in nodes:
            btn = VectorHexagonButton(icon_t, tip, is_maintenance=is_maint, radius=r, parent=self)
            btn.move(int(x - r), int(y - r))
            
            if is_maint:
                btn.clicked.connect(lambda t=target: signals.show_maint_toast.emit(t))
            else:
                btn.clicked.connect(lambda idx=target: signals.open_tab_requested.emit(idx))
            
            self.hex_buttons[target] = btn

        self.target_hwnd = None
        self.track_timer = QTimer(self)
        self.track_timer.timeout.connect(self.sync_position_top_left)

        signals.stream_toggle.connect(lambda enabled: self.hide() if enabled else self.show())
        signals.start_tracking.connect(self.enable_tracking)

    def enable_tracking(self):
        hwnd, _ = find_emulator_window()
        self.target_hwnd = hwnd
        self.track_timer.start(30)
        self.show()

    def sync_position_top_left(self):
        if not self.target_hwnd or not ctypes.windll.user32.IsWindow(self.target_hwnd):
            hwnd, _ = find_emulator_window()
            self.target_hwnd = hwnd
            if not self.target_hwnd:
                self.move(25, 35)
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

        # Neo chặt vào góc trên bên trái màn hình game
        self.move(pt.x + 18, pt.y + 35)

    def update_active_node(self, active_idx):
        for k, btn in self.hex_buttons.items():
            if not btn.is_maintenance:
                btn.is_active = (k == active_idx)
                btn.update()

# ================= TAB CONTENT PAGES (GIAO DIỆN CO GIÃN TỰ ĐỘNG) =================
class MainTabPage(QWidget):
    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

        self.btn_tele = self.create_key_row(layout, "TELEKILL", app_config.tele_hotkey, 'tele_hotkey')
        self.btn_freeze = self.create_key_row(layout, "FREEZE", app_config.freeze_hotkey, 'freeze_hotkey')
        self.btn_ghost = self.create_key_row(layout, "GHOST", app_config.ghost_hotkey, 'ghost_hotkey')
        self.btn_aimlag = self.create_key_row(layout, "AIM LAG", app_config.aimlag_hotkey, 'aimlag_hotkey')

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

class SettingTabPage(QWidget):
    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

        layout = QVBoxLayout(self)
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

class InfoTabPage(QWidget):
    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(3)

        box = QFrame()
        box.setStyleSheet("background-color: #0e1117; border: 1px solid #1c202a; border-radius: 6px; padding: 6px;")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(6, 4, 6, 4)
        box_layout.setSpacing(2)

        title = QLabel("Thông tin Tài khoản & Máy")
        title.setStyleSheet("color: #d1d5db; font-size: 10px; font-weight: 700; font-family: 'Segoe UI', Arial; border-bottom: 1px solid #1f242d; padding-bottom: 3px; margin-bottom: 2px;")
        box_layout.addWidget(title)

        self.lbl_key = QLabel("LICENSE KEY: Đang tải...")
        self.lbl_key.setStyleSheet("color: #60a5fa; font-size: 9.5px; font-weight: 700; font-family: 'Consolas', monospace;")
        box_layout.addWidget(self.lbl_key)

        self.lbl_hwid = QLabel(f"HWID: {CURRENT_HWID}")
        self.lbl_hwid.setStyleSheet("color: #a1a1aa; font-size: 9px; font-family: 'Consolas', monospace;")
        box_layout.addWidget(self.lbl_hwid)

        self.lbl_ip = QLabel("IP: Đang tải...")
        self.lbl_ip.setStyleSheet("color: #a1a1aa; font-size: 9px; font-family: 'Consolas', monospace;")
        box_layout.addWidget(self.lbl_ip)

        self.lbl_expiry = QLabel("Hạn Dùng: Đang tải...")
        self.lbl_expiry.setStyleSheet("color: #00ff66; font-size: 9px; font-weight: bold; font-family: 'Segoe UI', Arial;")
        box_layout.addWidget(self.lbl_expiry)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #1f242d; margin: 2px 0;")
        box_layout.addWidget(line)

        self.lbl_version = QLabel(f"Phiên bản: {APP_VERSION}")
        self.lbl_version.setStyleSheet("color: #9ca3af; font-size: 9px; font-family: 'Segoe UI', Arial;")
        box_layout.addWidget(self.lbl_version)

        self.lbl_updated_date = QLabel(f"Ngày cập nhật: {BUILD_DATE}")
        self.lbl_updated_date.setStyleSheet("color: #9ca3af; font-size: 9px; font-family: 'Segoe UI', Arial;")
        box_layout.addWidget(self.lbl_updated_date)

        self.lbl_updated_time = QLabel(f"Giờ cập nhật: {BUILD_TIME}")
        self.lbl_updated_time.setStyleSheet("color: #9ca3af; font-size: 9px; font-family: 'Segoe UI', Arial;")
        box_layout.addWidget(self.lbl_updated_time)

        self.lbl_user = QLabel(f"Username máy: <span style='color:#00ff66; font-weight:bold;'>✔ {LOCAL_USERNAME}</span>")
        self.lbl_user.setStyleSheet("color: #d1d5db; font-size: 9px; font-family: 'Segoe UI', Arial; margin-top: 2px;")
        box_layout.addWidget(self.lbl_user)

        layout.addWidget(box)

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

class FeedbackChatTabPage(QWidget):
    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(4)

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

        self.sub_stack = QStackedWidget()
        
        # VIEW 1: FEEDBACK
        fb_view = QWidget()
        fb_layout = QVBoxLayout(fb_view)
        fb_layout.setContentsMargins(0, 2, 0, 0)
        fb_layout.setSpacing(4)

        tip_lbl = QLabel("💡 Panel tự động chụp màn hình game gửi lên Discord.")
        tip_lbl.setWordWrap(True)
        tip_lbl.setStyleSheet("color: #facc15; font-size: 8.5px; font-family: 'Segoe UI', Arial; background: rgba(234, 179, 8, 0.1); padding: 4px; border-radius: 4px;")
        fb_layout.addWidget(tip_lbl)

        self.fb_input = QLineEdit()
        self.fb_input.setPlaceholderText("Ghi chú phản hồi / báo lỗi...")
        self.fb_input.setFixedHeight(28)
        self.fb_input.setStyleSheet("background-color: #12141a; border: 1px solid #1c202a; border-radius: 5px; color: #fff; font-size: 9.5px; padding: 0 6px;")
        fb_layout.addWidget(self.fb_input)

        self.send_fb_btn = QPushButton("📷 GỬI FEEDBACK")
        self.send_fb_btn.setFixedHeight(28)
        self.send_fb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_fb_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; border-radius: 5px; font-size: 10px; font-weight: 800;")
        self.send_fb_btn.clicked.connect(self.handle_send_feedback)
        fb_layout.addWidget(self.send_fb_btn)

        # VIEW 2: CHAT
        chat_view = QWidget()
        chat_layout = QVBoxLayout(chat_view)
        chat_layout.setContentsMargins(0, 2, 0, 0)
        chat_layout.setSpacing(4)

        self.chat_box = QTextEdit()
        self.chat_box.setReadOnly(True)
        self.chat_box.setFixedHeight(85)
        self.chat_box.setStyleSheet("background-color: #11141a; border: 1px solid #1c202a; border-radius: 5px; color: #d1d5db; font-size: 9px; font-family: 'Consolas', monospace; padding: 3px;")
        self.chat_box.append("<span style='color:#6b7280;'>[Hệ Thống] Phòng chat trực tuyến</span>")
        chat_layout.addWidget(self.chat_box)

        send_row = QHBoxLayout()
        send_row.setSpacing(4)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Nhập tin nhắn...")
        self.chat_input.setFixedHeight(26)
        self.chat_input.setStyleSheet("background-color: #12141a; border: 1px solid #1c202a; border-radius: 5px; color: #fff; font-size: 9.5px; padding: 0 6px;")
        self.chat_input.returnPressed.connect(self.handle_send_chat)

        self.send_chat_btn = QPushButton("Gửi")
        self.send_chat_btn.setFixedSize(45, 26)
        self.send_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_chat_btn.setStyleSheet("background-color: #0284c7; color: #ffffff; border: none; border-radius: 5px; font-size: 9.5px; font-weight: 800;")
        self.send_chat_btn.clicked.connect(self.handle_send_chat)

        send_row.addWidget(self.chat_input)
        send_row.addWidget(self.send_chat_btn)
        chat_layout.addLayout(send_row)

        self.sub_stack.addWidget(fb_view)
        self.sub_stack.addWidget(chat_view)
        layout.addWidget(self.sub_stack)

        self.switch_sub_tab(0)

    def switch_sub_tab(self, idx):
        self.sub_stack.setCurrentIndex(idx)
        style_active = "background-color: #0284c7; color: #fff; border: 1px solid #38bdf8; border-radius: 4px; font-size: 9px; font-weight: bold;"
        style_inactive = "background-color: #0e1117; color: #9ca3af; border: 1px solid #27272a; border-radius: 4px; font-size: 9px;"
        self.btn_tab_fb.setStyleSheet(style_active if idx == 0 else style_inactive)
        self.btn_tab_chat.setStyleSheet(style_active if idx == 1 else style_inactive)

    def get_role_tag(self):
        exp_at = net_state.key_expires_at
        if exp_at == -1 or (exp_at - time.time()) > 86400:
            return "VIP"
        return "FREE"

    def handle_send_feedback(self):
        msg = self.fb_input.text().strip() or "Không có ghi chú"
        self.send_fb_btn.setText("ĐANG GỬI...")
        self.send_fb_btn.setEnabled(False)
        QApplication.processEvents()

        def _send():
            try:
                screen = QGuiApplication.primaryScreen()
                pixmap = screen.grabWindow(0)
                byte_array = QBuffer()
                byte_array.open(QIODevice.OpenModeFlag.WriteOnly)
                pixmap.save(byte_array, "PNG")
                img_data = byte_array.data().data()

                role = self.get_role_tag()
                payload = {
                    "content": f"📢 **FEEDBACK TỪ [{role}] {LOCAL_USERNAME}**\n📝 **Nội dung:** {msg}\n💻 **HWID:** `{CURRENT_HWID}`\n🌐 **IP:** `{net_state.cached_ip}`"
                }
                files = {
                    "file": ("screenshot.png", img_data, "image/png")
                }
                requests.post(DISCORD_WEBHOOK_URL, data=payload, files=files, timeout=8)
            except Exception as e:
                debug_log(f"Feedback error: {e}")
            finally:
                QTimer.singleShot(0, lambda: self._on_fb_sent())

        threading.Thread(target=_send, daemon=True).start()

    def _on_fb_sent(self):
        self.send_fb_btn.setText("✔ ĐÃ GỬI XONG")
        self.fb_input.setText("")
        QTimer.singleShot(2000, lambda: [self.send_fb_btn.setText("📷 GỬI FEEDBACK"), self.send_fb_btn.setEnabled(True)])

    def handle_send_chat(self):
        text = self.chat_input.text().strip()
        if not text: return

        role = self.get_role_tag()
        curr_time_str = datetime.now().strftime("%H:%M")
        color = "#f59e0b" if role == "VIP" else "#60a5fa"

        chat_line = f"<span style='color:#6b7280;'>[{curr_time_str}]</span> <span style='color:{color}; font-weight:bold;'>[{role}]</span> <b>{LOCAL_USERNAME}:</b> {text}"
        self.chat_box.append(chat_line)
        self.chat_input.setText("")

        def _send_chat():
            try:
                requests.post(DISCORD_WEBHOOK_URL, json={
                    "content": f"💬 **[{role}] {LOCAL_USERNAME}**: {text}"
                }, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_send_chat, daemon=True).start()

# ================= CONTAINER KEYBINDS & CÁC TAB CO GIÃN TỰ ĐỘNG =================
class KeybindsWidget(QWidget):
    def __init__(self, on_close_callback, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(4)

        self.top_bar = TopBar("ZeroX", on_close=on_close_callback)
        layout.addWidget(self.top_bar)

        # Thanh thông báo bảo trì
        self.maint_banner = QLabel("")
        self.maint_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.maint_banner.setFixedHeight(18)
        self.maint_banner.setStyleSheet("color: #ef4444; font-size: 9px; font-weight: bold; background: rgba(239, 68, 68, 0.12); border-radius: 3px;")
        self.maint_banner.hide()
        layout.addWidget(self.maint_banner)

        self.tab_stack = SlidingStackedWidget(self)
        self.main_page = MainTabPage(self)
        self.setting_page = SettingTabPage(self)
        self.info_page = InfoTabPage(self)
        self.feedback_page = FeedbackChatTabPage(self)

        self.tab_stack.addWidget(self.main_page)     # 0: Fake Lag
        self.tab_stack.addWidget(self.setting_page)  # 1: Setting
        self.tab_stack.addWidget(self.info_page)     # 2: Info
        self.tab_stack.addWidget(self.feedback_page) # 3: Feedback & Chat
        layout.addWidget(self.tab_stack)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_key_expiry_display)

        signals.open_tab_requested.connect(self.switch_tab_direct)
        signals.show_maint_toast.connect(self.show_maintenance_warning)

    def switch_tab_direct(self, index: int):
        if index == 2:
            self.info_page.update_info()
        self.tab_stack.slide_to_index(index)
        
        # Tự động co giãn kích thước panel theo nội dung
        QTimer.singleShot(210, self.adjust_panel_size)

    def adjust_panel_size(self):
        curr_idx = self.tab_stack.currentIndex()
        h_map = {0: 175, 1: 175, 2: 215, 3: 195}
        target_h = h_map.get(curr_idx, 180)
        
        if self.parentWidget() and hasattr(self.parentWidget(), 'resize'):
            p = self.parentWidget().parentWidget() if hasattr(self.parentWidget(), 'parentWidget') else None
            # Resize MainContainerWindow
            if p and hasattr(p, 'bg_frame'):
                p.resize(300, target_h + 30)
                p.bg_frame.setGeometry(0, 0, 300, target_h + 30)

    def show_maintenance_warning(self, feature_name):
        audio.beep(320, 100)
        self.maint_banner.setText(f"🔒 Tính năng [{feature_name}] đang được BẢO TRÌ!")
        self.maint_banner.show()
        QTimer.singleShot(2500, self.maint_banner.hide)

    def start_timer(self):
        self.countdown_timer.start(1000)
        self.update_key_expiry_display()

    def stop_timer(self):
        self.countdown_timer.stop()

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
                self.countdown_timer.stop()
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

# ================= OVERLAYS & CONTAINER WINDOW =================
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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(160, 200)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

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

class MainContainerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(AntiBan.get_title())
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(300, 205)

        self.bg_frame = CustomParticleFrame(self)
        self.bg_frame.setGeometry(0, 0, 300, 205)

        layout = QVBoxLayout(self.bg_frame)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.init_gui_view = InitialGuiWidget(self.on_adb_clicked, cleanup_and_exit, self.showMinimized)
        self.adb_loading_view = AdbLoadingWidget(self.on_adb_choice_done, cleanup_and_exit, self.showMinimized)
        self.login_view = LoginWidget(self.on_login_success, cleanup_and_exit, self.showMinimized)
        self.download_view = DownloadWidget(self.on_inject_clicked, cleanup_and_exit)
        self.init_view = InitializingWidget(self.on_init_finished)
        self.keybinds_view = KeybindsWidget(cleanup_and_exit)
        self.expired_view = KeyExpiredWidget(self.on_expired_relogin, cleanup_and_exit)

        self.stack.addWidget(self.init_gui_view)      # 0
        self.stack.addWidget(self.adb_loading_view)    # 1
        self.stack.addWidget(self.login_view)          # 2
        self.stack.addWidget(self.download_view)       # 3
        self.stack.addWidget(self.init_view)           # 4
        self.stack.addWidget(self.keybinds_view)       # 5
        self.stack.addWidget(self.expired_view)        # 6

        self.stack.setCurrentIndex(0)

        self.sync_key_timer = QTimer(self)
        self.sync_key_timer.timeout.connect(self.sync_key_with_server)

        signals.toggle_visibility.connect(self.toggle_visibility)
        signals.key_expired.connect(self.handle_key_expired)
        signals.open_tab_requested.connect(self.bring_to_front)

        self._drag = False
        self._pos = None

    def bring_to_front(self, _):
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

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
        self.keybinds_view.update_key_expiry_display()
        self.keybinds_view.setting_page.update_all_buttons()
        self.keybinds_view.start_timer()
        self.stack.setCurrentIndex(5)
        self.keybinds_view.adjust_panel_size()

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
        self.stack.setCurrentIndex(6)

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

def cleanup_and_exit():
    net_state.running = False
    stop_all_features()
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

    # Khởi tạo Menu Tổ Ong ở góc trên bên trái màn hình game
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
