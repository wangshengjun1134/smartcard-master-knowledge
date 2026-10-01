"""修复 doc_info表中的文件路径（将反斜杠改为正斜杠）"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartcard_kb.docs_compile.database import init_database, get_connection


def main():
    print("="*60)
    print("修复 doc_info表中的文件路径")
    print("="*60)
    
    # 初始化数据库
    init_database()
    conn = get_connection()
    cursor = conn.cursor()
    
    # 查询所有需要修复的记录
    cursor.execute("SELECT id, file_path FROM doc_info")
    records = cursor.fetchall()
    
    print(f"找到 {len(records)} 条记录\n")
    
    fixed = 0
    for doc_id, file_path in records:
        # 将反斜杠改为正斜杠
        if '\\' in file_path:
            new_path = file_path.replace('\\', '/')
            
            # 更新数据库
            cursor.execute(
                "UPDATE doc_info SET file_path = %s, updated_at = NOW() WHERE id = %s",
                (new_path, doc_id)
            )
            fixed += 1
            print(f"✅ {file_path} -> {new_path}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"修复完成! 共修复 {fixed} 条记录")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
