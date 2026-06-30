"""
ClipMate - 标签管理对话框
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem,
                             QInputDialog, QMessageBox, QWidget,
                             QLineEdit, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from app.database import get_all_tags, add_tag, delete_tag


class TagManageDialog(QDialog):
    """标签管理窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('🏷️ 标签管理')
        self.setMinimumSize(360, 400)
        self.resize(400, 480)

        self._setup_ui()
        self._load_tags()

        # 应用主题
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QLabel { color: #1F2937; }
            QListWidget {
                background-color: #F9FAFB;
                color: #1F2937;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #EEF2FF;
                color: #6366F1;
            }
            QListWidget::item:hover {
                background-color: #F3F4F6;
            }
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background: #FFFFFF;
                color: #374151;
                font-family: 'Microsoft YaHei';
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #F3F4F6;
                border-color: #6366F1;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background: #F9FAFB;
                color: #1F2937;
            }
            QLineEdit:focus {
                border-color: #6366F1;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel('管理你的标签')
        title.setFont(QFont('Microsoft YaHei', 12, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel('标签可用于分类和筛选剪贴板内容')
        desc.setStyleSheet('color: #888;')
        layout.addWidget(desc)

        # 标签列表
        self.tag_list = QListWidget()
        self.tag_list.setFont(QFont('Microsoft YaHei', 10))
        layout.addWidget(self.tag_list, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        add_btn = QPushButton('➕ 添加标签')
        add_btn.clicked.connect(self._add_tag)
        btn_layout.addWidget(add_btn)

        delete_btn = QPushButton('🗑️ 删除选中')
        delete_btn.clicked.connect(self._delete_tag)
        delete_btn.setStyleSheet("""
            QPushButton:hover { background: #5a2d2d; border-color: #c44; }
        """)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton('关闭')
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_tags(self):
        """加载所有标签到列表"""
        self.tag_list.clear()
        tags = get_all_tags()
        for tag in tags:
            count = tag.get('clip_count', 0)
            text = f'  {tag["name"]}  ({count})'
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, tag['id'])
            # 用颜色标识
            if tag.get('color'):
                item.setForeground(QColor(tag['color']))
            self.tag_list.addItem(item)

    def _add_tag(self):
        """添加新标签"""
        name, ok = QInputDialog.getText(
            self, '添加标签', '标签名称:',
            QLineEdit.EchoMode.Normal, ''
        )
        if ok and name.strip():
            add_tag(name.strip())
            self._load_tags()

    def _delete_tag(self):
        """删除选中的标签"""
        item = self.tag_list.currentItem()
        if not item:
            QMessageBox.information(self, '提示', '请先选中一个标签')
            return

        tag_id = item.data(Qt.ItemDataRole.UserRole)
        tag_name = item.text().split('  (')[0].strip()

        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除标签"{tag_name}"吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_tag(tag_id)
            self._load_tags()


class TagSelectDialog(QDialog):
    """为单条记录选择标签（多选框）"""

    def __init__(self, clip_id: int, parent=None):
        super().__init__(parent)
        self.clip_id = clip_id
        self.setWindowTitle('🏷️ 设置标签')
        self.setMinimumSize(300, 320)
        self.resize(340, 380)

        self._setup_ui()
        self._load_tags()

        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; }
            QLabel { color: #1F2937; }
            QCheckBox {
                color: #1F2937; font-family: 'Microsoft YaHei'; font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px; height: 18px; border-radius: 4px;
                border: 2px solid #D1D5DB; background: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background: #6366F1; border-color: #6366F1;
            }
            QPushButton {
                padding: 6px 16px; border: 1px solid #D1D5DB;
                border-radius: 6px; background: #FFFFFF; color: #374151;
                font-family: 'Microsoft YaHei'; font-size: 9pt;
            }
            QPushButton:hover { background: #F3F4F6; border-color: #6366F1; }
        """)

    def _setup_ui(self):
        from PyQt6.QtWidgets import QCheckBox, QScrollArea

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel('选择标签')
        title.setFont(QFont('Microsoft YaHei', 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # 可滚动的复选框区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        check_container = QWidget()
        self.check_layout = QVBoxLayout(check_container)
        self.check_layout.setContentsMargins(0, 0, 0, 0)
        self.check_layout.setSpacing(6)
        self.check_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(check_container)
        layout.addWidget(scroll, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton('💾 保存')
        save_btn.setStyleSheet("""
            QPushButton {
                background: #6366F1; color: white; border: none;
                padding: 6px 20px;
            }
            QPushButton:hover { background: #4F46E5; }
        """)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_tags(self):
        from PyQt6.QtWidgets import QCheckBox
        from app.database import get_all_tags, get_clip_tags

        # 清旧
        for i in reversed(range(self.check_layout.count())):
            w = self.check_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        all_tags = get_all_tags()
        assigned = {t['id'] for t in get_clip_tags(self.clip_id)}

        self._checkboxes = {}
        for tag in all_tags:
            cb = QCheckBox(tag['name'])
            cb.setChecked(tag['id'] in assigned)
            cb.setProperty('tag_id', tag['id'])
            self._checkboxes[tag['id']] = cb
            self.check_layout.addWidget(cb)

        if not all_tags:
            hint = QLabel('暂无标签，请先在"标签管理"中添加')
            hint.setStyleSheet('color: #9CA3AF; padding: 20px;')
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.check_layout.addWidget(hint)

    def _save_and_close(self):
        from app.database import set_clip_tags
        selected = [tid for tid, cb in self._checkboxes.items() if cb.isChecked()]
        set_clip_tags(self.clip_id, selected)
        self.accept()
