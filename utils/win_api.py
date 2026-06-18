import ctypes
from ctypes import wintypes
import sys

# --- 🛡️ Windows API 常量 (商业级稳定快捷键) ---
WM_HOTKEY = 0x0312
WM_CLIPBOARDUPDATE = 0x031D
WM_POWERBROADCAST = 0x0218
PBT_APMRESUMEAUTOMATIC = 0x0012

MOD_ALT = 0x0001
VK_Q = 0x51
VK_E = 0x45

HOTKEY_ID_SHOW = 1
HOTKEY_ID_SNIP = 2

# 🛠️ Windows 底层工具箱
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def is_admin():
    """检测当前进程是否拥有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def force_focus_window(hwnd):
    """强制获取窗口焦点"""
    if not hwnd: return
    h_foreground = user32.GetForegroundWindow()
    u_foreground_thread = user32.GetWindowThreadProcessId(h_foreground, None)
    u_current_thread = kernel32.GetCurrentThreadId()
    
    if u_foreground_thread != u_current_thread:
        try:
            user32.AttachThreadInput(u_foreground_thread, u_current_thread, True)
            user32.ShowWindow(hwnd, 9) 
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            user32.AttachThreadInput(u_foreground_thread, u_current_thread, False)
    else:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)

def elevate_privileges():
    """请求提升管理员权限"""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

VK_MAP = {
    # 字母 A-Z
    **{chr(i): i for i in range(0x41, 0x5B)},
    # 数字 0-9
    **{str(i): i + 0x30 for i in range(10)},
    # 功能键 F1-F12
    **{f"F{i}": 0x70 + i - 1 for i in range(1, 13)},
}

MOD_MAP = {
    "Alt": 0x0001,
    "Ctrl": 0x0002,
    "Control": 0x0002,
    "Shift": 0x0004,
    "Win": 0x0008,
}

def parse_hotkey_string(hotkey_str: str) -> tuple[int, int]:
    """
    将 "Alt+Q", "Ctrl+Alt+S" 等快捷键字符串解析为 Windows RegisterHotKey 所需的 (modifiers, vk)
    若解析失败返回 (0, 0)
    """
    if not hotkey_str:
        return 0, 0
    
    parts = [p.strip() for p in hotkey_str.split('+') if p.strip()]
    modifiers = 0
    vk = 0
    
    for part in parts:
        part_cap = part.capitalize()
        if part_cap in MOD_MAP:
            modifiers |= MOD_MAP[part_cap]
        else:
            part_upper = part.upper()
            if part_upper in VK_MAP:
                vk = VK_MAP[part_upper]
            elif len(part) == 1:
                vk = ord(part_upper)
                
    return modifiers, vk
