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
VK_Z = 0x5A

HOTKEY_ID_Q = 1
HOTKEY_ID_Z = 2

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
