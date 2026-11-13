"""
ClipMate - 单条剪贴板记录的卡片控件
"""

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QPushButton, QFrame)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPixmapCache, QFont, QIcon, QColor
from io import BytesIO


class ClipCard(QFrame):
    """单条剪贴板记录的卡片"""

    clicked = pyqtSignal(int)       # 点击复制
    favorite_toggled = pyqtSignal(int, bool)
    delete_requested = pyqtSignal(int)
    tag_requested = pyqtSignal(int)

    def __init__(self, clip_data: dict, parent=None):
        super().__init__(parent)
        self.clip_id = clip_data['id']
        self.content_type = clip_data['content_type']
        self.is_favorite = bool(clip_data.get('is_favorite', 0))
        self.tags = clip_data.get('tags', [])
        self._setup_ui(clip_data)
        self._apply_style()

    def _setup_ui(self, data: dict):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(56)
        self.setMaximumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # 第一行：类型图标 + 预览文字 + 收藏按钮 + 时间
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # 类型图标
        icon_label = QLabel()
        if self.content_type == 'text':
            icon_label.setText('📝')
        elif self.content_type == 'image':
            icon_label.setText('🖼️')
        elif self.content_type == 'file':
            icon_label.setText('📎')
        icon_label.setFixedWidth(24)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(icon_label)

        # 预览文字
        self.preview_label = QLabel()
        preview = data.get('preview') or '(空)'
        self.preview_label.setText(preview)
        self.preview_label.setFont(QFont('Microsoft YaHei', 10))
        self.preview_label.setStyleSheet('color: #1F2937;')
        self.preview_label.setWordWrap(True)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.preview_label, 1)

        # 时间
        time_label = QLabel()
        created = data.get('created_at', '')
        if created:
            time_label.setText(created[11:19] if len(created) > 10 else created)
        time_label.setFont(QFont('Microsoft YaHei', 8))
        time_label.setStyleSheet('color: #6B7280;')
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(time_label)

        # 收藏按钮
        self.fav_btn = QPushButton()
        self.fav_btn.setFixedSize(24, 24)
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.setText('★' if self.is_favorite else '☆')
        self.fav_btn.setStyleSheet(
            'QPushButton { border: none; font-size: 16px; color: #F59E0B; background: transparent; }'
            'QPushButton:hover { color: #D97706; }'
        )
        self.fav_btn.clicked.connect(self._on_favorite)
        top_row.addWidget(self.fav_btn)

        layout.addLayout(top_row)

        # 第二行：标签
        if hasattr(self, 'tags') and self.tags:
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(32, 0, 0, 0)
            tag_row.setSpacing(4)
            for tag in self.tags[:3]:  # 最多显示3个标签
                tag_label = QLabel(f'#{tag.get("name", "")}')
                tag_label.setFont(QFont('Microsoft YaHei', 8))
                tag_label.setStyleSheet(f'color: {tag.get("color", "#5B9BD5")};')
                tag_row.addWidget(tag_label)
            if len(self.tags) > 3:
                more = QLabel(f'+{len(self.tags) - 3}')
                more.setStyleSheet('color: #9CA3AF; font-size: 8px;')
                tag_row.addWidget(more)
            tag_row.addStretch()
            layout.addLayout(tag_row)

    def _apply_style(self):
        self.setStyleSheet("""
            ClipCard {
                background-color: #FFFFFF;
                border-radius: 6px;
                border: 1px solid #E5E7EB;
            }
            ClipCard:hover {
                background-color: #F3F4F6;
                border: 1px solid #6366F1;
            }
        """)

    def _on_favorite(self):
        self.is_favorite = not self.is_favorite
        self.fav_btn.setText('★' if self.is_favorite else '☆')
        self.favorite_toggled.emit(self.clip_id, self.is_favorite)

    def mouseReleaseEvent(self, event):
        """左键点击 → 复制，右键仅呼出菜单"""
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.clip_id)


class ImageClipCard(ClipCard):
    """图片类型的剪贴板卡片 — 单击复制、双击预览"""

    double_clicked = pyqtSignal(int)  # 双击信号 → 弹出预览

    def __init__(self, clip_data: dict, parent=None):
        super().__init__(clip_data, parent)
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._do_single_click)
        self._skip_release = False  # 双击后跳过 release 重启计时器

    def _setup_ui(self, data: dict):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 缩略图
        thumb_data = data.get('image_thumb')
        if thumb_data:
            # 缓存缩放后的缩略图，筛选/收藏等全量刷新时不再重复解码
            cache_key = f'clipmate-thumb-{data["id"]}-{hash(bytes(thumb_data))}'
            pixmap = QPixmapCache.find(cache_key)
            if pixmap is None:
                pixmap = QPixmap()
                loaded = QPixmap()
                if loaded.loadFromData(thumb_data):
                    pixmap = loaded.scaled(
                        80, 80,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    QPixmapCache.insert(cache_key, pixmap)
            thumb_label = QLabel()
            if not pixmap.isNull():
                thumb_label.setPixmap(pixmap)
            thumb_label.setFixedSize(80, 80)
            thumb_label.setStyleSheet("background-color: #F3F4F6; border-radius: 4px;")
            layout.addWidget(thumb_label)
        else:
            icon_label = QLabel('🖼️')
            icon_label.setFixedSize(80, 80)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("font-size: 32px;")
            layout.addWidget(icon_label)

        # 右侧信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        preview = data.get('preview') or '[图片]'
        preview_label = QLabel(preview)
        preview_label.setFont(QFont('Microsoft YaHei', 10))
        preview_label.setStyleSheet('color: #1F2937;')
        info_layout.addWidget(preview_label)

        size_label = QLabel(f'ID: {data["id"]} | 图片')
        size_label.setFont(QFont('Microsoft YaHei', 8))
        size_label.setStyleSheet('color: #6B7280;')
        info_layout.addWidget(size_label)

        info_layout.addStretch()
        layout.addLayout(info_layout, 1)

        # 收藏按钮
        self.fav_btn = QPushButton()
        self.fav_btn.setFixedSize(24, 24)
        self.fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fav_btn.setText('★' if self.is_favorite else '☆')
        self.fav_btn.setStyleSheet(
            'QPushButton { border: none; font-size: 16px; color: #F59E0B; background: transparent; }'
            'QPushButton:hover { color: #D97706; }'
        )
        self.fav_btn.clicked.connect(self._on_favorite)
        layout.addWidget(self.fav_btn)

    # ── 单击复制 / 双击预览 ──
    #
    # Qt 双击事件序列: press → release → press → doubleClick → release
    # 第二次 release 在 doubleClick 之后, 如果不跳过会重新启动计时器,
    # 导致双击后仍触发单击复制, 复制内容又被监听器捡到形成重复记录。

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._skip_release:
                self._click_timer.start(250)
            self._skip_release = False
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._click_timer.stop()
        self._skip_release = True
        self.double_clicked.emit(self.clip_id)
        super().mouseDoubleClickEvent(event)

    def _do_single_click(self):
        self.clicked.emit(self.clip_id)
