"""
ClipMate - 图标生成器
用 QPainter 绘制精美的剪贴板图标，输出 PNG 和 ICO 文件

运行: python resources/generate_icons.py
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QFont, QPainterPath, QLinearGradient
from PyQt6.QtCore import Qt, QRectF, QPointF


def generate_icon(size: int = 256) -> QPixmap:
    """绘制剪贴板图标 — 蓝色底板 + 银色夹子 + 白色文字线条"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.08
    body_left = margin
    body_top = size * 0.22
    body_width = size - 2 * margin
    body_height = size - body_top - margin

    # ── 底板阴影 ──
    shadow_path = QPainterPath()
    shadow_rect = QRectF(body_left + size * 0.02, body_top + size * 0.02,
                         body_width, body_height)
    shadow_path.addRoundedRect(shadow_rect, size * 0.08, size * 0.08)
    painter.fillPath(shadow_path, QColor(0, 0, 0, 60))

    # ── 底板主体 (渐变蓝) ──
    body_path = QPainterPath()
    body_rect = QRectF(body_left, body_top, body_width, body_height)
    body_path.addRoundedRect(body_rect, size * 0.08, size * 0.08)

    gradient = QLinearGradient(
        body_rect.topLeft(), body_rect.bottomRight()
    )
    gradient.setColorAt(0.0, QColor('#818CF8'))
    gradient.setColorAt(0.5, QColor('#6366F1'))
    gradient.setColorAt(1.0, QColor('#4F46E5'))
    painter.fillPath(body_path, gradient)

    # 底板边框
    pen = QPen(QColor('#4F46E5'), size * 0.015)
    painter.setPen(pen)
    painter.drawPath(body_path)
    painter.setPen(Qt.PenStyle.NoPen)

    # ── 银色夹子 ──
    clip_width = size * 0.38
    clip_height = size * 0.16
    clip_x = (size - clip_width) / 2
    clip_y = size * 0.06

    # 金属渐变
    clip_path = QPainterPath()
    clip_rect = QRectF(clip_x, clip_y, clip_width, clip_height)
    clip_path.addRoundedRect(clip_rect, size * 0.04, size * 0.04)

    clip_gradient = QLinearGradient(clip_rect.topLeft(), clip_rect.bottomLeft())
    clip_gradient.setColorAt(0.0, QColor('#E8E8E8'))
    clip_gradient.setColorAt(0.3, QColor('#FFFFFF'))
    clip_gradient.setColorAt(0.5, QColor('#D0D0D0'))
    clip_gradient.setColorAt(0.7, QColor('#E0E0E0'))
    clip_gradient.setColorAt(1.0, QColor('#B0B0B0'))
    painter.fillPath(clip_path, clip_gradient)

    painter.setPen(QPen(QColor('#999999'), size * 0.012))
    painter.drawPath(clip_path)
    painter.setPen(Qt.PenStyle.NoPen)

    # ── 白色文字线条 ──
    line_color = QColor(255, 255, 255, 200)
    line_x = body_left + size * 0.18
    line_y_start = body_top + size * 0.14
    line_spacing = size * 0.11
    line_corner = size * 0.02

    for i in range(3):
        if i == 0:
            w = size * 0.52
        elif i == 1:
            w = size * 0.44
        else:
            w = size * 0.30
        h = size * 0.055
        painter.setBrush(QBrush(line_color))
        painter.drawRoundedRect(
            QRectF(line_x, line_y_start + i * line_spacing, w, h),
            line_corner, line_corner
        )

    painter.end()
    return pixmap


def save_ico(pixmap: QPixmap, path: str):
    """将 QPixmap 保存为多分辨率 ICO（使用 Pillow）"""
    from PIL import Image
    from PyQt6.QtCore import QBuffer, QByteArray
    from io import BytesIO

    qimage = pixmap.toImage()
    byte_array = QByteArray()
    buf = QBuffer(byte_array)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    qimage.save(buf, 'PNG')
    buf.close()

    img = Image.open(BytesIO(byte_array.data()))
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    img.save(path, format='ICO', sizes=sizes)
    print(f'  ICO saved: {path} ({sizes})')


def main():
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    os.makedirs(icon_dir, exist_ok=True)

    # 需要 QApplication 才能用 QPixmap
    app = QApplication(sys.argv)

    print('Generating ClipMate icons...')

    # 生成 256x256 主图标
    pixmap = generate_icon(256)
    png_path = os.path.join(icon_dir, 'app_icon.png')
    pixmap.save(png_path, 'PNG')
    print(f'  PNG saved: {png_path}')

    # 保存 ICO
    ico_path = os.path.join(icon_dir, 'app_icon.ico')
    save_ico(pixmap, ico_path)

    print('Done! Icons generated successfully.')
    sys.exit(0)


if __name__ == '__main__':
    main()
