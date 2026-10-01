"""修复 SGP.11-4, SGP.16-1 等子系列文档的 document_code 和 revision"""

import sys
import re
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartcard_kb.docs_compile.database import init_database, get_connection

# 需要修复的记录
FIX_RECORDS = [
    ("a89bdeb7-bd18-4bd8-a95f-63347bbfa185", "SGP.11-4.2.1.pdf", "SGP.11-4", "2.1"),
    ("fd2a4b98-4c3d-476d-ab9d-77bca84ba175", "SGP.16-1.3.1.pdf", "SGP.16-1", "3.1"),
    ("fd09a23d-25f4-440c-9990-433a84ba082a", "SGP.16-1.3.2.pdf", "SGP.16-1", "3.2"),
    ("cb255ffb-fc31-4063-8e39-5d4864af4163", "SGP.21-2.3.pdf", "SGP.21-2", "3"),
    ("72ef41f2-bd36-4d45-984e-11a439456940", "SGP.22-2.4.pdf", "SGP.22-2", "4"),
    ("b2e24313-5066-4827-a40c-66d35f17cae3", "SGP.24-2.4.1.pdf", "SGP.24-2", "4.1"),
    ("abf72a8c-3962-4070-8608-06afed5e826d", "SGP.24-2.4.3.pdf", "SGP.24-2", "4.3"),
    ("a731ca62-87e8-42dc-bc5c-ff6b8d2b2c5d", "SGP.24-2.4.pdf", "SGP.24-2", "4"),
    ("98ce8c08-bb19-4eb8-9118-2b81f097f181", "SGP.25.pdf", "SGP.25", None),
    ("03654900-7f6a-4272-9213-763356f4bd64", "SGP.26-1.5.pdf", "SGP.26-1", "5"),
    ("c5b96615-73be-4531-89f5-58bc0901fd0b", "SGP.29-1.0.pdf", "SGP.29-1", "1.0"),
    ("949eaace-4cae-4964-8537-9c5daf821e5d", "SGP.32-1.0.1.pdf", "SGP.32-1", "1.0.1"),
]


def main():
    print("="*60)
    print("修复 SGP 子系列文档的 document_code 和 revision")
    print("="*60)
    
    # 初始化数据库
    init_database()
    conn = get_connection()
    cursor = conn.cursor()
    
    fixed = 0
    for doc_id, file_name, series_id, revision in FIX_RECORDS:
        # 构建 document_code
        if revision:
            document_code = f"{series_id}-v{revision}"
        else:
            document_code = series_id
        
        # 更新数据库
        cursor.execute(
            """
            UPDATE doc_info 
            SET document_code = %s, 
                series_id = %s, 
                revision = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (document_code, series_id, revision, doc_id)
        )
        fixed += 1
        print(f"✅ 已修复: {file_name} → document_code={document_code}, revision={revision}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"修复完成! 共修复 {fixed} 条记录")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
