"""SQLite 数据库模块"""

import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """获取数据库路径"""
    return Path("data/knowledge.db")


def init_database():
    """初始化数据库"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # TODO: 实现数据库初始化
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # TODO: 创建表结构
    # cursor.execute("""
    #     CREATE TABLE IF NOT EXISTS documents (
    #         id INTEGER PRIMARY KEY,
    #         title TEXT,
    #         content TEXT,
    #         category TEXT,
    #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    #     )
    # """)
    
    conn.commit()
    conn.close()


def close_connection(conn: sqlite3.Connection):
    """关闭数据库连接
    
    Args:
        conn: 数据库连接
    """
    if conn:
        conn.close()
