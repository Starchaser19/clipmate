"""
ClipMate - 通用工具
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    获取资源文件的绝对路径。
    开发模式：相对于项目根目录
    PyInstaller 打包后：在临时解压目录 _MEIPASS 中
    """
    if getattr(sys, 'frozen', False):
        # 打包后的 exe 运行
        base = sys._MEIPASS
    else:
        # 源码运行：项目根目录（clipmate/）
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base, relative_path)
