#!/usr/bin/env python3
"""
初始化数据库
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """初始化数据库"""
    print("="*60)
    print("初始化数据库")
    print("="*60)
    
    try:
        from src.database.db_manager import get_db_manager
        
        print("\n正在创建数据库连接...")
        db_manager = get_db_manager()
        
        print("✓ 数据库初始化成功！")
        print(f"✓ 数据库路径: {db_manager.history_db_path}")
        
        # 验证表是否创建成功
        print("\n验证表结构...")
        tables = db_manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            (),
            db_manager.history_db_path
        )
        
        if tables:
            print(f"\n已创建 {len(tables)} 个表:")
            for table in tables:
                # table 可能是元组或字典
                table_name = table[0] if isinstance(table, (tuple, list)) else table.get('name', table)
                print(f"  - {table_name}")
        
        print("\n" + "="*60)
        print("数据库就绪，可以开始使用！")
        print("="*60)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
