"""
ClipMate - 自定义标题栏控件
支持窗口拖拽移动（Windows 原生，丝滑不卡）、自定义最小化和关闭按钮
"""

import sys
import ctypes
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QMouseEvent
from app.utils import resource_path


class TitleBar(QWidget):
    """无边框窗口的自定义标题栏 — 原生拖拽 + 最小化/关闭按钮"""

    BTN_HOVER_CLOSE = '#EF4444'  # 关闭按钮悬停颜色

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setObjectName('titleBar')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 4, 0)
        layout.setSpacing(10)

        # ── App 图标 ──
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        pixmap = QPixmap(resource_path('resources/icons/app_icon.png')).scaled(
            24, 24,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # ── 标题文字 ──
        title_label = QLabel('ClipMate')
        title_label.setFont(QFont('Microsoft YaHei', 12, QFont.Weight.Bold))
        title_label.setStyleSheet('color: #1F2937; background: transparent;')
        layout.addWidget(title_label)

        layout.addStretch()

        # ── 最小化按钮 ──
        self.min_btn = QPushButton('─')
        self.min_btn.setFixedSize(46, 32)
        self.min_btn.setFont(QFont('Segoe UI', 11))
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.setToolTip('最小化到任务栏')
        self.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self._style_button(self.min_btn, hover_bg='#E5E7EB', hover_color='#1F2937')
        layout.addWidget(self.min_btn)

        # ── 关闭按钮 ──
        self.close_btn = QPushButton('✕')
        self.close_btn.setFixedSize(46, 32)
        self.close_btn.setFont(QFont('Segoe UI', 11))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip('关闭到系统托盘')
        self.close_btn.clicked.connect(lambda: self.window().close())
        self._style_button(self.close_btn, hover_bg=self.BTN_HOVER_CLOSE, hover_color='#FFFFFF')
        layout.addWidget(self.close_btn)

        # ── 标题栏整体样式 ──
        self.setStyleSheet("""
            QWidget#titleBar {
                background-color: #FFFFFF;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #E5E7EB;
            }
        """)

    @staticmethod
    def _style_button(btn: QPushButton, hover_bg: str, hover_color: str):
        """为标题栏按钮设置样式"""
        btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: 4px;
                background: transparent;
                color: #6B7280;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                color: {hover_color};
            }}
        """)

    # ── 窗口拖拽（Windows 原生 → 丝滑不卡） ──

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # 使用 Windows 原生拖拽：ReleaseCapture + SC_MOVE
            # Windows 接管鼠标移动，硬件加速，零延迟
            self._start_system_move()
            return
        super().mousePressEvent(event)

    def _start_system_move(self):
        """调用 Windows API 让系统接管窗口拖拽"""
        if sys.platform != 'win32':
            return
        hwnd = int(self.window().winId())
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(
            hwnd,
            0x0112,   # WM_SYSCOMMAND
            0xF012,   # SC_MOVE | HTCAPTION
            0,
        )
