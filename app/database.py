"""
ClipMate - 数据库层
SQLite 存储剪贴板历史、标签、分类
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional


DB_DIR = os.path.join(os.path.expanduser("~"), ".clipmate")
DB_PATH = os.path.join(DB_DIR, "clipmate.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（确保目录和表已存在）"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 写入性能优化
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clips (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type TEXT NOT NULL DEFAULT 'text',  -- 'text', 'image', 'file'
                text_content TEXT,
                image_data  BLOB,
                image_thumb BLOB,
                file_path   TEXT,
                preview     TEXT,          -- 列表显示的摘要
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_favorite INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tags (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#5B9BD5'
            );

            CREATE TABLE IF NOT EXISTS clip_tags (
                clip_id INTEGER NOT NULL,
                tag_id  INTEGER NOT NULL,
                PRIMARY KEY (clip_id, tag_id),
                FOREIGN KEY (clip_id) REFERENCES clips(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id)  REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_clips_created
                ON clips(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_clips_favorite
                ON clips(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_clips_content_type
                ON clips(content_type);
        """)
        conn.commit()
    finally:
        conn.close()


# ─── 剪贴板记录 CRUD ────────────────────────────────────────

def add_clip(content_type: str, text_content: Optional[str] = None,
             image_data: Optional[bytes] = None,
             image_thumb: Optional[bytes] = None,
             file_path: Optional[str] = None) -> int:
    """添加一条剪贴板记录，返回 id"""
    conn = get_connection()
    try:
        # 生成预览
        preview = None
        if content_type == 'text' and text_content:
            preview = text_content[:120].replace('\n', ' ').strip()
        elif content_type == 'image':
            preview = '[图片]'
        elif content_type == 'file' and file_path:
            preview = f'[文件] {os.path.basename(file_path)}'

        # 去重：如果是文本且最后一条相同，不重复添加
        if content_type == 'text' and text_content:
            last = conn.execute(
                "SELECT text_content FROM clips WHERE content_type='text' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if last and last['text_content'] == text_content:
                # 只更新时间戳，不新增
                conn.execute(
                    "UPDATE clips SET updated_at=? WHERE id=?",
                    (datetime.now(), last['id'])
                )
                conn.commit()
                return last['id']

        cursor = conn.execute("""
            INSERT INTO clips (content_type, text_content, image_data,
                               image_thumb, file_path, preview)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content_type, text_content, image_data, image_thumb, file_path, preview))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_clips(limit: int = 100, offset: int = 0,
              search: Optional[str] = None,
              tag_id: Optional[int] = None,
              favorite_only: bool = False,
              content_type: Optional[str] = None) -> list:
    """查询剪贴板历史，支持搜索/标签/收藏过滤"""
    conn = get_connection()
    try:
        conditions = []
        params = []

        if search:
            conditions.append("(preview LIKE ? OR text_content LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])

        if tag_id is not None:
            conditions.append("id IN (SELECT clip_id FROM clip_tags WHERE tag_id=?)")
            params.append(tag_id)

        if favorite_only:
            conditions.append("is_favorite = 1")

        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        where = " AND ".join(conditions) if conditions else "1"
        # 收藏的排前面，然后按时间倒序
        sql = f"""
            SELECT * FROM clips
            WHERE {where}
            ORDER BY is_favorite DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# 列表卡片只需要的字段：不读 image_data，避免每次刷新搬运大 BLOB
_LIST_COLUMNS = "id, content_type, preview, created_at, is_favorite, image_thumb"


def get_clips_for_list(limit: int = 200, offset: int = 0,
                       search: Optional[str] = None,
                       tag_id: Optional[int] = None,
                       favorite_only: bool = False,
                       content_type: Optional[str] = None,
                       after_id: Optional[int] = None,
                       conn: Optional[sqlite3.Connection] = None) -> list:
    """
    列表页专用查询。
    - 只取卡片需要的列，不取 image_data / text_content
    - after_id 用于增量刷新：只取比它新的记录
    - conn 传入时复用调用方的连接
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        conditions = []
        params = []

        if search:
            conditions.append("(preview LIKE ? OR text_content LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])

        if tag_id is not None:
            conditions.append("id IN (SELECT clip_id FROM clip_tags WHERE tag_id=?)")
            params.append(tag_id)

        if favorite_only:
            conditions.append("is_favorite = 1")

        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        if after_id is not None:
            conditions.append("id > ?")
            params.append(after_id)

        where = " AND ".join(conditions) if conditions else "1"
        sql = f"""
            SELECT {_LIST_COLUMNS} FROM clips
            WHERE {where}
            ORDER BY is_favorite DESC, created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            conn.close()


def get_tags_for_clips(clip_ids: list,
                       conn: Optional[sqlite3.Connection] = None) -> dict:
    """一次查出多条记录的标签，避免每条记录开一次连接。"""
    if not clip_ids:
        return {}

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        placeholders = ','.join('?' * len(clip_ids))
        rows = conn.execute(f"""
            SELECT ct.clip_id, t.id, t.name, t.color
            FROM clip_tags ct
            JOIN tags t ON t.id = ct.tag_id
            WHERE ct.clip_id IN ({placeholders})
            ORDER BY t.name
        """, list(clip_ids)).fetchall()

        result = {cid: [] for cid in clip_ids}
        for row in rows:
            result[row['clip_id']].append({
                'id': row['id'],
                'name': row['name'],
                'color': row['color'],
            })
        return result
    finally:
        if own_conn:
            conn.close()


def get_max_clip_id(content_type: Optional[str] = None,
                    conn: Optional[sqlite3.Connection] = None) -> int:
    """返回当前最大 id，GUI 用它判断是否需要增量刷新。"""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        if content_type:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS max_id FROM clips "
                "WHERE content_type=?",
                (content_type,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS max_id FROM clips"
            ).fetchone()
        return int(row['max_id'])
    finally:
        if own_conn:
            conn.close()


def get_clip_by_id(clip_id: int) -> Optional[dict]:
    """获取单条记录"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_clip(clip_id: int):
    """删除一条记录"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM clips WHERE id=?", (clip_id,))
        conn.commit()
    finally:
        conn.close()


def toggle_favorite(clip_id: int) -> bool:
    """切换收藏状态，返回新状态"""
    conn = get_connection()
    try:
        current = conn.execute(
            "SELECT is_favorite FROM clips WHERE id=?", (clip_id,)
        ).fetchone()
        if current is None:
            return False
        new_val = 0 if current['is_favorite'] else 1
        conn.execute("UPDATE clips SET is_favorite=? WHERE id=?", (new_val, clip_id))
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def clear_history(content_type: Optional[str] = None):
    """清空记录（可指定类型 text/image，不指定则全部）"""
    conn = get_connection()
    try:
        if content_type:
            conn.execute("DELETE FROM clips WHERE content_type=?", (content_type,))
        else:
            conn.execute("DELETE FROM clips")
        conn.commit()
    finally:
        conn.close()


# ─── 标签 CRUD ──────────────────────────────────────────────

def add_tag(name: str, color: str = '#5B9BD5') -> int:
    """添加标签"""
    conn = get_connection()
    try:
        cursor = conn.execute("INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
                              (name, color))
        conn.commit()
        # 如果已存在，返回现有 id
        row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
        return row['id'] if row else cursor.lastrowid
    finally:
        conn.close()


def get_all_tags() -> list:
    """获取所有标签（附带数量）"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT t.*, COUNT(ct.clip_id) as clip_count
            FROM tags t
            LEFT JOIN clip_tags ct ON t.id = ct.tag_id
            GROUP BY t.id
            ORDER BY t.name
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_tag(tag_id: int):
    """删除标签"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
        conn.commit()
    finally:
        conn.close()


def set_clip_tags(clip_id: int, tag_ids: list):
    """设置一条记录的标签（先清空再写入）"""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM clip_tags WHERE clip_id=?", (clip_id,))
        for tid in tag_ids:
            conn.execute("INSERT INTO clip_tags (clip_id, tag_id) VALUES (?, ?)",
                         (clip_id, tid))
        conn.commit()
    finally:
        conn.close()


def get_clip_tags(clip_id: int) -> list:
    """获取一条记录的标签"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT t.* FROM tags t
            JOIN clip_tags ct ON t.id = ct.tag_id
            WHERE ct.clip_id=?
        """, (clip_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
    print(f"数据库已初始化: {DB_PATH}")
