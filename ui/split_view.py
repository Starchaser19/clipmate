"""
ClipMate - 双栏视图
左侧文本列表 + 右侧图片列表
"""

import os
import tempfile

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
                             QLineEdit, QPushButton, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from .clip_list import ClipListWidget


class SplitClipView(QWidget):
    """左右双栏：文本 | 图片"""

    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 搜索栏 + 收藏过滤 ──
        search_bar = QWidget()
        search_bar.setStyleSheet('background-color: #FAFAFA;')
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(12, 6, 12, 6)
        search_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('🔍 搜索剪贴板历史...')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFont(QFont('Microsoft YaHei', 10))
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px; border: 1px solid #D1D5DB;
                border-radius: 8px; background: #F9FAFB; color: #1F2937;
            }
            QLineEdit:focus {
                border-color: #6366F1; background: #FFFFFF;
            }
        """)
        self.search_input.textChanged.connect(lambda: self._search_timer.start(300))
        search_layout.addWidget(self.search_input, 1)

        self.fav_btn = QPushButton('☆ 仅收藏')
        self.fav_btn.setCheckable(True)
        self.fav_btn.setFont(QFont('Microsoft YaHei', 9))
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px; border: 1px solid #D1D5DB;
                border-radius: 8px; background: #FFFFFF; color: #6B7280;
            }
            QPushButton:hover { background: #F3F4F6; }
            QPushButton:checked {
                background: #EEF2FF; color: #6366F1; border-color: #6366F1;
            }
        """)
        self.fav_btn.clicked.connect(self._apply_search)
        search_layout.addWidget(self.fav_btn)

        layout.addWidget(search_bar)

        # ── 分隔线 ──
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet('background-color: #E5E7EB;')
        layout.addWidget(sep)

        # ── 双栏内容 ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E5E7EB;
            }
        """)

        self.text_list = ClipListWidget(
            content_type='text', title='文本记录'
        )
        self.text_list.status_message.connect(self.status_message)
        self.text_list.image_preview.connect(self._preview_image)

        self.image_list = ClipListWidget(
            content_type='image', title='图片记录'
        )
        self.image_list.status_message.connect(self.status_message)
        self.image_list.image_preview.connect(self._preview_image)

        splitter.addWidget(self.text_list)
        splitter.addWidget(self.image_list)
        # 文本区 65%，图片区 35%
        splitter.setSizes([650, 350])

        layout.addWidget(splitter, 1)

    def _apply_search(self):
        search = self.search_input.text().strip()
        fav = self.fav_btn.isChecked()
        self.text_list.set_filters(search=search, favorite_only=fav)
        self.image_list.set_filters(search=search, favorite_only=fav)

    def _preview_image(self, image_data: bytes):
        """用系统默认图片查看器打开原图（支持缩放/拖动）"""
        try:
            tmp_dir = os.path.join(tempfile.gettempdir(), 'clipmate')
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, 'preview.png')
            with open(tmp_path, 'wb') as f:
                f.write(image_data)
            os.startfile(tmp_path)
        except Exception as e:
            self.status_message.emit(f'无法打开图片: {e}')

    def refresh(self):
        self.text_list.refresh()
        self.image_list.refresh()
