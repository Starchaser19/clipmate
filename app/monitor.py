"""
ClipMate - 剪贴板监听模块
后台线程轮询 Windows 剪贴板，检测文本和图片变化
"""

import time
import hashlib
import traceback
import logging
import os
from threading import Thread, Event
from typing import Optional
from io import BytesIO

import pyperclip
from PIL import Image, ImageGrab

from .database import add_clip

# 日志写入用户目录，方便排查问题
LOG_DIR = os.path.join(os.path.expanduser("~"), ".clipmate")
LOG_PATH = os.path.join(LOG_DIR, "monitor.log")

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

log = logging.getLogger(__name__)


class ClipboardMonitor(Thread):
    """后台线程：轮询剪贴板，检测变化后存入数据库"""

    def __init__(self, interval: float = 0.5):
        super().__init__(daemon=True)
        self.interval = interval
        self._stop_event = Event()
        self._last_text: Optional[str] = None
        self._last_image_hash: Optional[str] = None
        self._paused = False

    def run(self):
        """主循环：持续检测剪贴板变化"""
        log.info("ClipMate monitor started")
        self._init_last_content()

        while not self._stop_event.is_set():
            try:
                if not self._paused:
                    self._check_clipboard()
            except Exception:
                log.exception("Unexpected error in monitor loop")
            time.sleep(self.interval)

        log.info("ClipMate monitor stopped")

    def stop(self):
        self._stop_event.set()

    def pause(self):
        self._paused = True
        log.info("Monitor paused")

    def resume(self):
        self._paused = False
        log.info("Monitor resumed")

    def mark_text_seen(self, text: str):
        """ClipMate 自己复制了文本 → 更新基线，避免回环重复记录"""
        self._last_text = text

    def mark_image_seen(self, img_data: bytes):
        """ClipMate 自己复制了图片 → 更新基线"""
        self._last_image_hash = hashlib.md5(img_data).hexdigest()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def _init_last_content(self):
        """记录当前剪贴板内容作为基线，避免启动时误添加"""
        try:
            self._last_text = pyperclip.paste()
        except Exception:
            self._last_text = None
            log.exception("Failed to capture text baseline")

        try:
            img = ImageGrab.grabclipboard()
            if img and isinstance(img, Image.Image):
                buf = BytesIO()
                img.save(buf, format='PNG')
                self._last_image_hash = hashlib.md5(buf.getvalue()).hexdigest()
                log.info(f"Image baseline captured: {img.size}")
        except Exception:
            log.exception("Failed to capture image baseline")

    def _check_clipboard(self):
        """检查剪贴板是否有新内容"""
        # ── 文本 ──
        try:
            current_text = pyperclip.paste()
            if current_text and current_text != self._last_text:
                self._last_text = current_text
                cid = add_clip(content_type='text', text_content=current_text)
                log.info(f"New text clip #{cid}: {current_text[:50]}...")
        except Exception:
            log.exception("Text clipboard check failed")

        # ── 图片 ──
        try:
            self._check_image()
        except Exception:
            log.exception("Image check failed")

    def _check_image(self):
        """用 PIL ImageGrab 检测剪贴板图片（支持所有 Windows 格式）"""
        try:
            img = ImageGrab.grabclipboard()
        except Exception:
            return  # 剪贴板被锁定

        if img is None or not isinstance(img, Image.Image):
            return

        # 转为 RGB（处理 RGBA/PNG 等格式）
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        # PNG 字节用于哈希去重
        png_buf = BytesIO()
        img.save(png_buf, format='PNG')
        png_data = png_buf.getvalue()

        h = hashlib.md5(png_data).hexdigest()
        if h == self._last_image_hash:
            return
        self._last_image_hash = h

        # 缩略图
        thumb = img.copy()
        thumb.thumbnail((200, 200))

        thumb_buf = BytesIO()
        thumb.save(thumb_buf, format='PNG')

        # 原图（重新编码，png_buf 可能已被消费）
        img_buf = BytesIO()
        img.save(img_buf, format='PNG')

        cid = add_clip(
            content_type='image',
            image_data=img_buf.getvalue(),
            image_thumb=thumb_buf.getvalue()
        )
        log.info(f"New image clip #{cid}: {img.size}")
