"""
ClipMate - 剪贴板列表控件
可指定内容类型的卡片列表（文本 or 图片）
"""

import pyperclip
import win32clipboard
import win32con
from io import BytesIO
from datetime import datetime
from PIL import Image

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea,
                             QPushButton, QHBoxLayout, QLabel, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction

from .clip_card import ClipCard, ImageClipCard
from app.database import (get_clips, get_clip_by_id, get_connection,
                          delete_clip, toggle_favorite, get_clip_tags)


class ClipListWidget(QWidget):
    """单一类型的剪贴板列表控件"""

    clip_copied = pyqtSignal(str)
    image_preview = pyqtSignal(bytes)   # 点击图片 → 请求预览
    status_message = pyqtSignal(str)

    def __init__(self, content_type: str = 'text', title: str = '',
                 parent=None):
        super().__init__(parent)
        self._content_type = content_type
        self._search_text = ''
        self._favorite_only = False
        self._title = title
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── 标题行 ──
        header = QHBoxLayout()
        header.setContentsMargins(12, 6, 8, 0)

        icon = '📝' if self._content_type == 'text' else '🖼️'
        header_label = QLabel(f'{icon} {self._title}')
        header_label.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        header_label.setStyleSheet('color: #374151; background: transparent;')
        header.addWidget(header_label)

        header.addStretch()

        self.count_label = QLabel('')
        self.count_label.setFont(QFont('Microsoft YaHei', 9))
        self.count_label.setStyleSheet('color: #6B7280; background: transparent;')
        header.addWidget(self.count_label)

        layout.addLayout(header)

        # ── 滚动列表 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 6px; background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(8, 0, 8, 8)
        self.list_layout.setSpacing(4)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 空状态
        empty_text = '还没有文本记录\n复制一些文字试试 ✨' if self._content_type == 'text' else '还没有图片记录\n截图或复制图片试试 🖼️'
        self.empty_label = QLabel(empty_text)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(QFont('Microsoft YaHei', 10))
        self.empty_label.setStyleSheet('color: #9CA3AF; padding: 30px;')
        self.empty_label.hide()
        self.list_layout.addWidget(self.empty_label)

        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

    # ── 外部调用接口 ──

    def set_filters(self, search: str = '', favorite_only: bool = False):
        self._search_text = search
        self._favorite_only = favorite_only
        self.refresh()

    def refresh(self):
        clips = get_clips(
            limit=200,
            search=self._search_text if self._search_text else None,
            favorite_only=self._favorite_only,
            content_type=self._content_type
        )

        for clip in clips:
            clip['tags'] = get_clip_tags(clip['id'])

        # 清旧卡片
        for i in reversed(range(self.list_layout.count())):
            w = self.list_layout.itemAt(i).widget()
            if w and w != self.empty_label:
                w.deleteLater()

        self.count_label.setText(f'{len(clips)} 条')

        if not clips:
            self.empty_label.show()
            return

        self.empty_label.hide()

        for clip in clips:
            if clip['content_type'] == 'image':
                card = ImageClipCard(clip)
                card.double_clicked.connect(self._on_image_double_clicked)
            else:
                card = ClipCard(clip)

            card.clicked.connect(self._on_card_clicked)
            card.favorite_toggled.connect(self._on_favorite_toggled)
            card.delete_requested.connect(self._on_delete_requested)

            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(
                lambda pos, cid=clip['id']: self._show_card_menu(pos, cid)
            )

            self.list_layout.addWidget(card)

    # ── 卡片交互 ──

    def _on_card_clicked(self, clip_id: int):
        clip = get_clip_by_id(clip_id)
        if not clip:
            return

        if clip['content_type'] == 'text' and clip['text_content']:
            pyperclip.copy(clip['text_content'])
            self._mark_self_copy('text', clip['text_content'])
            self.clip_copied.emit('✅ 已复制到剪贴板')
            conn = get_connection()
            conn.execute("UPDATE clips SET updated_at=? WHERE id=?",
                         (datetime.now(), clip_id))
            conn.commit()
            conn.close()
            preview = (clip.get('preview') or '')[:40]
            self.status_message.emit(f'已复制: {preview}...')

        elif clip['content_type'] == 'image' and clip['image_data']:
            try:
                img = Image.open(BytesIO(clip['image_data']))
                bmp_buf = BytesIO()
                img.convert('RGB').save(bmp_buf, format='BMP')
                dib_data = bmp_buf.getvalue()[14:]

                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
                finally:
                    win32clipboard.CloseClipboard()
                self._mark_self_copy('image', clip['image_data'])
                self.status_message.emit('✅ 图片已复制到剪贴板')
            except Exception as e:
                self.status_message.emit(f'复制失败: {e}')

    def _mark_self_copy(self, content_type: str, data):
        """告知监听器：这是我复制的，别再存回数据库"""
        win = self.window()
        if win and hasattr(win, 'monitor'):
            if content_type == 'text':
                win.monitor.mark_text_seen(data)
            else:
                win.monitor.mark_image_seen(data)

    def _on_image_double_clicked(self, clip_id: int):
        clip = get_clip_by_id(clip_id)
        if clip and clip.get('image_data'):
            self.image_preview.emit(clip['image_data'])

    def _on_favorite_toggled(self, clip_id: int, is_fav: bool):
        toggle_favorite(clip_id)
        self.refresh()
        self.status_message.emit('★ 已收藏' if is_fav else '☆ 已取消收藏')

    def _on_delete_requested(self, clip_id: int):
        delete_clip(clip_id)
        self.refresh()
        self.status_message.emit('🗑️ 已删除')

    def _show_card_menu(self, pos, clip_id: int):
        menu = QMenu(self)

        # 查当前收藏状态（只读，不 toggle）
        clip = get_clip_by_id(clip_id)
        is_fav = bool(clip.get('is_favorite', 0)) if clip else False
        fav_label = '★ 取消收藏' if is_fav else '☆ 收藏'
        fav_action = QAction(fav_label, self)
        fav_action.triggered.connect(
            lambda: self._on_favorite_toggled(clip_id, not is_fav))
        menu.addAction(fav_action)

        tag_action = QAction('🏷️ 设置标签', self)
        tag_action.triggered.connect(lambda: self._on_set_tags(clip_id))
        menu.addAction(tag_action)

        menu.addSeparator()

        delete_action = QAction('🗑️ 删除', self)
        delete_action.triggered.connect(lambda: self._on_delete_requested(clip_id))
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))

    def _on_set_tags(self, clip_id: int):
        """弹出标签选择对话框"""
        from .tag_dialog import TagSelectDialog
        dialog = TagSelectDialog(clip_id, self.window())
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.refresh()
            self.status_message.emit('🏷️ 标签已更新')
