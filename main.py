#!/usr/bin/env python3
"""
ClipMate - Windows 剪贴板历史管理工具
运行: python main.py
打包: pyinstaller --onefile --windowed --name ClipMate --icon resources/icons/app_icon.ico main.py
"""

import ctypes
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from app.utils import resource_path
from app.autostart import heal as autostart_heal
from ui.main_window import MainWindow


_single_instance_mutex = None


def _acquire_single_instance():
    """
    创建一个会话级命名互斥体，防止同时运行多个 ClipMate。
    返回 (handle, already_running)。
    """
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    handle = kernel32.CreateMutexW(
        None, False, r'Local\ClipMate.SingleInstance')
    if not handle:
        return None, False  # 创建失败就放行，避免程序打不开

    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None, True
    return handle, False


def main():
    global _single_instance_mutex

    _single_instance_mutex, already_running = _acquire_single_instance()
    if already_running:
        if '--hidden' not in sys.argv:
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.MessageBoxW.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p,
                ctypes.c_wchar_p, ctypes.c_uint]
            user32.MessageBoxW(
                None, 'ClipMate 已在运行（系统托盘）', 'ClipMate', 0x40)
        sys.exit(0)

    # 如果启用了开机自启但注册表键失效 → 自动修复
    autostart_heal()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName('ClipMate')
    app.setOrganizationName('ClipMate')

    app.setWindowIcon(QIcon(resource_path('resources/icons/app_icon.png')))

    # 创建主窗口（内部初始化数据库 + 启动监听）
    window = MainWindow()

    # --hidden: 开机自启模式，直接隐藏到托盘，不弹出窗口
    if '--hidden' not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
