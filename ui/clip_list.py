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
from app.database import (get_clips_for_list, get_tags_for_clips,
                          get_max_clip_id, get_clip_by_id, get_connection,
                          delete_clip, toggle_favorite)


class ClipListWidget(QWidget):
    """单一类型的剪贴板列表控件"""

    LIMIT = 200

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
        self._cards = []            # 按显示顺序保存卡片，便于增量插入
        self._last_max_id = None    # 上次刷新时的最大 id
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
        """全量刷新：筛选、删除、收藏、标签变化时调用。"""
        conn = get_connection()
        try:
            clips = get_clips_for_list(
                limit=self.LIMIT,
                search=self._search_text or None,
                favorite_only=self._favorite_only,
                content_type=self._content_type,
                conn=conn
            )
            tags = get_tags_for_clips([clip['id'] for clip in clips], conn=conn)
            self._last_max_id = get_max_clip_id(self._content_type, conn=conn)
        finally:
            conn.close()

        for clip in clips:
            clip['tags'] = tags.get(clip['id'], [])

        self._clear_cards()
        self.count_label.setText(f'{len(clips)} 条')

        if not clips:
            self.empty_label.show()
            return

        self.empty_label.hide()

        for clip in clips:
            card = self._make_card(clip)
            self._cards.append(card)
            self.list_layout.addWidget(card)

    def refresh_new(self) -> bool:
        """
        增量刷新：只追加比上次刷新更新的记录。
        没有新记录时只执行一次轻量查询，不重建任何卡片。
        """
        if self._favorite_only or self._search_text:
            return False
        if self._last_max_id is None:
            return False

        conn = get_connection()
        try:
            clips = get_clips_for_list(
                limit=self.LIMIT,
                content_type=self._content_type,
                after_id=self._last_max_id,
                conn=conn
            )
            if not clips:
                return False
            tags = get_tags_for_clips([clip['id'] for clip in clips], conn=conn)
        finally:
            conn.close()

        for clip in clips:
            clip['tags'] = tags.get(clip['id'], [])

        if not self.empty_label.isHidden():
            self.empty_label.hide()

        # 收藏卡片固定在最上面，新记录插到收藏区之后
        insert_pos = sum(1 for card in self._cards if card.is_favorite)
        layout_base = self.list_layout.indexOf(self.empty_label) + 1

        for clip in clips:
            card = self._make_card(clip)
            self._cards.insert(insert_pos, card)
            self.list_layout.insertWidget(layout_base + insert_pos, card)
            insert_pos += 1

        self._last_max_id = max(self._last_max_id, max(clip['id'] for clip in clips))
        self._trim_to_limit()
        self.count_label.setText(f'{len(self._cards)} 条')
        return True

    def _make_card(self, clip: dict):
        """创建卡片并连接信号/右键菜单。"""
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
        return card

    def _clear_cards(self):
        for card in self._cards:
            card.hide()
            self.list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def _trim_to_limit(self):
        while len(self._cards) > self.LIMIT:
            card = self._cards.pop()
            card.hide()
            self.list_layout.removeWidget(card)
            card.deleteLater()

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
