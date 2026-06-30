#!/usr/bin/env python3
"""
ClipMate - Windows 剪贴板历史管理工具
运行: python main.py
打包: pyinstaller --onefile --windowed --name ClipMate --icon resources/icons/app_icon.ico main.py
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from app.utils import resource_path
from app.autostart import heal as autostart_heal
from ui.main_window import MainWindow


def main():
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
