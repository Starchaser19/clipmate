"""
ClipMate - 主窗口
负责整体布局、自定义标题栏、系统托盘、边缘调整大小
"""

import sys
import os
import ctypes

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QApplication, QSystemTrayIcon, QMenu, QPushButton,
                             QLabel, QMessageBox, QInputDialog, QLineEdit,
                             QGraphicsDropShadowEffect, QSizeGrip)
from PyQt6.QtCore import Qt, QTimer, QSize, QPoint
from PyQt6.QtGui import (QIcon, QAction, QFont, QPixmap, QPainter,
                         QColor, QBrush)

from .title_bar import TitleBar
from .split_view import SplitClipView
from app.database import init_db, get_all_tags, add_tag, delete_tag, clear_history
from app.maintenance import maybe_cleanup
from app.monitor import ClipboardMonitor
from app.autostart import is_enabled as autostart_enabled, toggle as autostart_toggle
from app.utils import resource_path


class MainWindow(QMainWindow):
    """剪贴板管理主窗口 — 无边框 + 自定义标题栏"""

    RESIZE_MARGIN = 12  # 边缘检测宽度：够四角命中，不挡滚动条

    def __init__(self):
        super().__init__()

        # ── 1. 无边框窗口标志 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # ── 2. 窗口尺寸 ──
        self.setWindowTitle('ClipMate')
        self.setMinimumSize(400, 280)
        self.resize(960, 593)

        # ── 3. 窗口图标 ──
        self._set_window_icon()

        # ── 4. 数据库 + 监听器 ──
        init_db()
        maybe_cleanup()   # 每天最多一次；清理旧记录并回收空间
        self.monitor = ClipboardMonitor()
        self.monitor.start()

        # ── 5. 构建 UI ──
        self._setup_ui()
        self._setup_tray()
        self._setup_style()

        # ── 6. 自动刷新 ──
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(2000)

        # 首次加载数据。先记下变更计数，避免刷新期间新到的记录被漏掉
        self._last_change_seq = self.monitor.change_seq()
        self.split_view.refresh()

        # 修复无边框窗口的边缘缩放（加回 WS_THICKFRAME）
        QTimer.singleShot(0, self._fix_window_frame)

    # ═══════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════

    def _setup_ui(self):
        """构建无边框窗口布局"""

        # 外层：让出 12px 给阴影
        outer = QWidget()
        self.setCentralWidget(outer)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        # ── 投影 ──
        shadow = QGraphicsDropShadowEffect(outer)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 50))
        outer.setGraphicsEffect(shadow)

        # ── 内容容器（圆角矩形） ──
        container = QWidget()
        container.setObjectName('mainContainer')
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # ── 自定义标题栏 ──
        self.title_bar = TitleBar(self)
        container_layout.addWidget(self.title_bar)

        # ── 标题栏下方的工具栏（标签 + 清空按钮） ──
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("background-color: #FAFAFA;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 0, 16, 0)
        toolbar_layout.setSpacing(8)

        toolbar_layout.addStretch()

        tag_btn = QPushButton('🏷️ 标签')
        tag_btn.setFont(QFont('Microsoft YaHei', 9))
        tag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tag_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 14px; border: 1px solid #D1D5DB;
                border-radius: 6px; background: #FFFFFF; color: #374151;
                font-size: 9pt;
            }
            QPushButton:hover { background: #F3F4F6; border-color: #6366F1; }
        """)
        tag_btn.clicked.connect(self._show_tag_manager)
        toolbar_layout.addWidget(tag_btn)

        clear_btn = QPushButton('🗑️ 清空 ▾')
        clear_btn.setFont(QFont('Microsoft YaHei', 9))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 14px; border: 1px solid #D1D5DB;
                border-radius: 6px; background: #FFFFFF; color: #374151;
                font-size: 9pt;
            }
            QPushButton:hover { background: #FEE2E2; border-color: #EF4444; color: #DC2626; }
            QPushButton::menu-indicator { image: none; }
        """)
        # 清空子菜单
        clear_menu = QMenu(clear_btn)
        clear_menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF; color: #1F2937;
                border: 1px solid #E5E7EB; border-radius: 8px; padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px; border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #FEE2E2; color: #DC2626;
            }
        """)
        clear_text = QAction('📝 清空文本记录', self)
        clear_text.triggered.connect(lambda: self._clear_history('text'))
        clear_menu.addAction(clear_text)
        clear_image = QAction('🖼️ 清空图片记录', self)
        clear_image.triggered.connect(lambda: self._clear_history('image'))
        clear_menu.addAction(clear_image)
        clear_menu.addSeparator()
        clear_all = QAction('🗑️ 清空全部', self)
        clear_all.triggered.connect(lambda: self._clear_history())
        clear_menu.addAction(clear_all)
        clear_btn.setMenu(clear_menu)
        toolbar_layout.addWidget(clear_btn)

        container_layout.addWidget(toolbar)

        # ── 双栏内容（左文本 | 右图片） ──
        self.split_view = SplitClipView()
        self.split_view.status_message.connect(self._show_status)
        container_layout.addWidget(self.split_view, 1)

        # ── 底部状态栏 ──
        self.status_bar = QLabel('就绪 | 后台监听中...')
        self.status_bar.setFixedHeight(28)
        self.status_bar.setFont(QFont('Microsoft YaHei', 9))
        self.status_bar.setStyleSheet("""
            background-color: #FAFAFA;
            color: #6B7280;
            padding: 0 14px;
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)
        container_layout.addWidget(self.status_bar)

        outer_layout.addWidget(container)

    def _set_window_icon(self):
        self.setWindowIcon(QIcon(resource_path('resources/icons/app_icon.png')))

    # ═══════════════════════════════════════════
    #  系统托盘
    # ═══════════════════════════════════════════

    def _setup_tray(self):
        """系统托盘菜单"""
        icon = self._create_tray_icon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('ClipMate - 剪贴板管理')

        tray_menu = QMenu()
        show_action = QAction('📋 显示主窗口', self)
        show_action.triggered.connect(self.show_and_raise)
        tray_menu.addAction(show_action)

        pause_action = QAction('⏸️ 暂停监听', self)
        pause_action.setCheckable(True)
        pause_action.triggered.connect(self._toggle_monitor)
        self._pause_action = pause_action
        tray_menu.addAction(pause_action)

        autostart_action = QAction('🚀 开机自启', self)
        autostart_action.setCheckable(True)
        autostart_action.setChecked(autostart_enabled())
        autostart_action.triggered.connect(self._toggle_autostart)
        self._autostart_action = autostart_action
        tray_menu.addAction(autostart_action)

        tray_menu.addSeparator()

        quit_action = QAction('🚪 退出', self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _create_tray_icon(self) -> QIcon:
        return QIcon(resource_path('resources/icons/app_icon.png'))

    # ═══════════════════════════════════════════
    #  样式
    # ═══════════════════════════════════════════

    def _setup_style(self):
        """全局清新浅色主题"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
            QWidget#mainContainer {
                background-color: #FFFFFF;
                border-radius: 10px;
                border: 1px solid #E5E7EB;
            }
            QToolTip {
                background-color: #FFFFFF;
                color: #1F2937;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QMenu {
                background-color: #FFFFFF;
                color: #1F2937;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #EEF2FF;
                color: #6366F1;
            }
        """)

    # ═══════════════════════════════════════════
    #  边缘调整大小
    # ═══════════════════════════════════════════

    def _fix_window_frame(self):
        """恢复窗口样式：边框缩放 + 任务栏点击最小化/还原"""
        if sys.platform != 'win32':
            return
        hwnd = int(self.winId())
        GWL_STYLE = -16
        # 这些样式被 FramelessWindowHint 移除了，需要加回来
        WS_THICKFRAME = 0x00040000     # 可调整大小的边框
        WS_SYSMENU = 0x00080000        # 窗口菜单 + 任务栏右键
        WS_MINIMIZEBOX = 0x00020000    # 最小化按钮 + 任务栏点击行为
        SWP_FLAGS = 0x0020 | 0x0002 | 0x0001 | 0x0004  # FRAMECHANGED|NOMOVE|NOSIZE|NOZORDER
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        style |= WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)

    def nativeEvent(self, eventType, message):
        """处理 Windows WM_NCHITTEST → 边缘拖拽调整大小"""
        if sys.platform != 'win32':
            return False, 0

        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message != 0x0084:  # WM_NCHITTEST
            return False, 0

        x = ctypes.c_int16(msg.lParam & 0xFFFF).value
        y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value
        local_pos = self.mapFromGlobal(QPoint(x, y))

        rect = self.rect()
        margin = self.RESIZE_MARGIN

        on_left = local_pos.x() <= margin
        on_right = local_pos.x() >= rect.width() - margin
        on_top = local_pos.y() <= margin
        on_bottom = local_pos.y() >= rect.height() - margin

        if on_left and on_top:
            result = 13       # HTTOPLEFT
        elif on_right and on_top:
            result = 14       # HTTOPRIGHT
        elif on_left and on_bottom:
            result = 16       # HTBOTTOMLEFT
        elif on_right and on_bottom:
            result = 17       # HTBOTTOMRIGHT
        elif on_left:
            result = 10       # HTLEFT
        elif on_right:
            result = 11       # HTRIGHT
        elif on_top:
            result = 12       # HTTOP
        elif on_bottom:
            result = 15       # HTBOTTOM
        else:
            return False, 0

        return True, result

    # ═══════════════════════════════════════════
    #  窗口操作
    # ═══════════════════════════════════════════

    def show_and_raise(self):
        """显示窗口并提升到最前。先让窗口显示，再做列表更新。"""
        self.show()
        self.raise_()
        self.activateWindow()
        # 不在 show 的同一个事件里做重活：让任务栏先取到窗口图标
        QTimer.singleShot(0, self._after_show)

    def _after_show(self):
        """窗口显示后的轻量更新 + 图标兜底。"""
        self._last_change_seq = self.monitor.change_seq()
        self.split_view.refresh_new()
        # 任务栏在窗口刚显示时查询图标可能超时，刷新后再设一次，
        # 确保显示应用图标，而不是 Windows 通用图标
        self._set_window_icon()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_and_raise()

    def _toggle_monitor(self, checked):
        if checked:
            self.monitor.pause()
            self._pause_action.setText('▶️ 恢复监听')
            self.status_bar.setText('⏸️ 监听已暂停')
        else:
            self.monitor.resume()
            self._pause_action.setText('⏸️ 暂停监听')
            self.status_bar.setText('▶️ 监听中...')

    def _toggle_autostart(self, checked):
        """切换开机自启"""
        autostart_toggle()
        # 读注册表确认实际状态
        actual = autostart_enabled()
        self._autostart_action.setChecked(actual)
        self._show_status('🚀 开机自启已开启' if actual else '开机自启已关闭')

    def _show_status(self, msg: str):
        self.status_bar.setText(msg)
        QTimer.singleShot(3000, lambda: self.status_bar.setText('就绪 | 后台监听中...'))

    def _auto_refresh(self):
        if not self.isVisible():
            return

        # 搜索/仅收藏时，新记录不会出现在当前列表里
        if self.split_view.search_input.text() or self.split_view.fav_btn.isChecked():
            self._last_change_seq = self.monitor.change_seq()
            return

        seq = self.monitor.change_seq()
        if seq == self._last_change_seq:
            return
        self._last_change_seq = seq
        self.split_view.refresh_new()

    def _show_tag_manager(self):
        from .tag_dialog import TagManageDialog
        dialog = TagManageDialog(self)
        dialog.exec()
        self.split_view.refresh()

    def _clear_history(self, content_type: str = None):
        labels = {'text': '文本', 'image': '图片'}
        label = labels.get(content_type, '全部')
        reply = QMessageBox.question(
            self, '确认清空',
            f'确定要清空所有{label}记录吗？\n此操作不可撤销！',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_history(content_type)
            self.split_view.refresh()
            self._show_status(f'已清空{label}记录')

    def _quit_app(self):
        self.monitor.stop()
        QApplication.quit()

    # ═══════════════════════════════════════════
    #  窗口事件
    # ═══════════════════════════════════════════

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_F5:
            self.split_view.refresh()
        super().keyPressEvent(event)
