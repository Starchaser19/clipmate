"""
ClipMate - 数据库维护
每天最多清理一次旧记录，并回收 SQLite 文件空间。
"""

import os
import time
import logging

from .database import DB_DIR, get_connection

log = logging.getLogger(__name__)

CLEANUP_STAMP = os.path.join(DB_DIR, 'last_cleanup')
CLEANUP_INTERVAL = 24 * 3600

IMAGE_RETENTION_DAYS = 90
TEXT_RETENTION_DAYS = 365
IMAGE_MAX_BYTES = 300 * 1024 * 1024
DELETE_BATCH = 400


def _protected_clause() -> str:
    """收藏和已打标签的记录永远不删。"""
    return "is_favorite = 0 AND id NOT IN (SELECT clip_id FROM clip_tags)"


def _db_file_size(db_path: str) -> int:
    try:
        return os.path.getsize(db_path) if db_path and os.path.exists(db_path) else 0
    except OSError:
        return 0


def cleanup_old_clips(image_days: int = IMAGE_RETENTION_DAYS,
                      text_days: int = TEXT_RETENTION_DAYS,
                      image_max_bytes: int = IMAGE_MAX_BYTES) -> dict:
    """
    删除旧记录并执行 VACUUM。
    - 图片超过 image_days 天，或图片总量超过 image_max_bytes
    - 文本超过 text_days 天
    - 收藏和已打标签的记录永远保留
    """
    conn = get_connection()
    stats = {
        'images': 0,
        'texts': 0,
        'image_bytes_before': 0,
        'image_bytes_after': 0,
        'file_before': 0,
        'file_after': 0,
    }
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        db_path = row['file'] if row else ''
        stats['file_before'] = _db_file_size(db_path)

        # 1) 按时间删除旧图片
        cur = conn.execute(f"""
            DELETE FROM clips
            WHERE content_type = 'image'
              AND {_protected_clause()}
              AND created_at < datetime('now', ?)
        """, (f'-{int(image_days)} days',))
        stats['images'] += cur.rowcount
        conn.commit()

        # 2) 按时间删除旧文本
        cur = conn.execute(f"""
            DELETE FROM clips
            WHERE content_type = 'text'
              AND {_protected_clause()}
              AND created_at < datetime('now', ?)
        """, (f'-{int(text_days)} days',))
        stats['texts'] += cur.rowcount
        conn.commit()

        # 3) 图片总量上限：从最旧的开始删，收藏/标签图片不动
        row = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(image_data)), 0) AS total "
            "FROM clips WHERE content_type = 'image'"
        ).fetchone()
        total = int(row['total'])
        stats['image_bytes_before'] = total

        if total > image_max_bytes:
            excess = total - image_max_bytes
            rows = conn.execute(f"""
                SELECT id, LENGTH(image_data) AS size
                FROM clips
                WHERE content_type = 'image' AND {_protected_clause()}
                ORDER BY created_at ASC, id ASC
            """).fetchall()

            to_delete = []
            freed = 0
            for item in rows:
                if freed >= excess:
                    break
                to_delete.append(item['id'])
                freed += int(item['size'] or 0)

            for i in range(0, len(to_delete), DELETE_BATCH):
                chunk = to_delete[i:i + DELETE_BATCH]
                placeholders = ','.join('?' * len(chunk))
                conn.execute(
                    f"DELETE FROM clips WHERE id IN ({placeholders})", chunk)
            conn.commit()
            stats['images'] += len(to_delete)

        row = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(image_data)), 0) AS total "
            "FROM clips WHERE content_type = 'image'"
        ).fetchone()
        stats['image_bytes_after'] = int(row['total'])

        # 4) 有删除或已有空闲页时回收文件空间
        freelist = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        if stats['images'] or stats['texts'] or freelist > 0:
            try:
                conn.execute("VACUUM")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                log.exception("VACUUM failed; space will be reclaimed later")

        stats['file_after'] = _db_file_size(db_path)

        if stats['image_bytes_after'] > image_max_bytes:
            log.warning(
                "Image data still %s bytes after cleanup "
                "(protected by favorites/tags)",
                stats['image_bytes_after'])
        return stats
    finally:
        conn.close()


def maybe_cleanup() -> None:
    """每天最多执行一次清理。清理失败不影响程序启动。"""
    try:
        if os.path.exists(CLEANUP_STAMP):
            age = time.time() - os.path.getmtime(CLEANUP_STAMP)
            if age < CLEANUP_INTERVAL:
                return
    except OSError:
        pass

    try:
        stats = cleanup_old_clips()
        log.info(
            "Cleanup: images=%s texts=%s image_bytes=%s->%s db=%s->%s",
            stats['images'], stats['texts'],
            stats['image_bytes_before'], stats['image_bytes_after'],
            stats['file_before'], stats['file_after'],
        )
        os.makedirs(DB_DIR, exist_ok=True)
        with open(CLEANUP_STAMP, 'w', encoding='utf-8') as f:
            f.write(str(int(time.time())))
    except Exception:
        log.exception("Cleanup failed")
