"""
ClipMate - 开机自启动管理
通过 Windows 注册表 Run 键控制
"""

import sys
import os
import winreg


REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "ClipMate"


def _get_startup_command() -> str:
    """获取启动命令：打包后直接用 exe + --hidden，源码运行时用 pythonw.exe + --hidden"""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}" --hidden'

    pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    if sys.argv[0] in ('-c', ''):
        script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', 'main.py'))
    else:
        script = os.path.abspath(sys.argv[0])

    return f'"{pythonw}" "{script}" --hidden'


def is_enabled() -> bool:
    """检查开机自启是否已启用"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, REG_NAME)
        winreg.CloseKey(key)
        return bool(value)
    except FileNotFoundError:
        return False


def enable():
    """启用开机自启"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        cmd = _get_startup_command()
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to enable autostart: {e}")
        return False


def disable():
    """禁用开机自启"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, REG_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True  # 本来就没启用
    except Exception as e:
        print(f"Failed to disable autostart: {e}")
        return False


def toggle() -> bool:
    """切换状态，返回新状态"""
    if is_enabled():
        disable()
        return False
    else:
        enable()
        return True


def heal():
    """
    启动时自动修复失效的自启注册表键。
    如果用户已启用自启，但注册表命令指向失效路径
    （Python 升级/项目移动等导致），自动用当前正确路径重写。
    """
    if not is_enabled():
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        current_cmd, _ = winreg.QueryValueEx(key, REG_NAME)
        winreg.CloseKey(key)
    except Exception:
        return  # 读不到就放弃

    correct_cmd = _get_startup_command()
    if current_cmd == correct_cmd:
        return  # 路径没变，不需要修复

    # 路径变了 → 静默重写
    try:
        enable()
    except Exception:
        pass  # 修复失败也不影响正常运行
