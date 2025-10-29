"""
环境检查脚本
运行此脚本检查所有依赖是否正确安装
"""

import sys
import os

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 版本过低，需要 3.8+")
        return False
    else:
        print("✓ Python 版本符合要求")
        return True

def check_dependencies():
    """检查依赖包"""
    dependencies = [
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('keybert', 'KeyBERT'),
        ('sklearn', 'scikit-learn'),
        ('transformers', 'transformers'),
        ('torch', 'PyTorch'),
        ('sentence_transformers', 'sentence-transformers'),
        ('jieba', 'jieba (中文分词)'),
    ]
    
    print("\n检查依赖包:")
    all_ok = True
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"  ✓ {display_name}")
        except ImportError:
            print(f"  ❌ {display_name} - 未安装")
            all_ok = False
    
    return all_ok

def check_database():
    """检查数据库文件"""
    print("\n检查数据库:")
    db_path = "testdb_history.db"
    
    if not os.path.exists(db_path):
        print(f"  ❌ 数据库文件不存在: {db_path}")
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查 messages 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            print("  ❌ messages 表不存在")
            return False
        
        # 统计记录数
        cursor.execute("SELECT COUNT(*) FROM messages")
        count = cursor.fetchone()[0]
        print(f"  ✓ 数据库存在，共 {count} 条新闻")
        
        # 显示示例数据
        cursor.execute("SELECT date, text FROM messages LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"\n  示例数据:")
            print(f"    日期: {row[0]}")
            print(f"    内容: {row[1][:100]}...")
        
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ 数据库检查失败: {e}")
        return False

def check_models():
    """检查模型加载"""
    print("\n检查模型:")
    
    # 检查 KeyBERT
    try:
        from keybert import KeyBERT
        print("  测试 KeyBERT 模型...")
        kw_model = KeyBERT(model='all-MiniLM-L6-v2')
        print("  ✓ KeyBERT 模型加载成功")
    except Exception as e:
        print(f"  ❌ KeyBERT 模型加载失败: {e}")
        return False
    
    # 检查 BART（可选，因为模型较大）
    print("\n  BART 模型检查（可选，首次运行会下载 1.6GB）:")
    print("  如果想跳过，请输入 'n'，否则按回车继续...")
    choice = input("  > ").strip().lower()
    
    if choice == 'n':
        print("  跳过 BART 模型检查")
        return True
    
    try:
        from transformers import BartTokenizer, BartForConditionalGeneration
        print("  正在加载 BART 模型（首次运行需要下载）...")
        
        # 设置使用国内镜像
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        
        tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')
        model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')
        print("  ✓ BART 模型加载成功")
        
        # 测试摘要生成
        test_text = "This is a test sentence for summarization."
        inputs = tokenizer(test_text, return_tensors="pt", max_length=1024, truncation=True)
        summary_ids = model.generate(inputs["input_ids"], max_length=50, min_length=10)
        summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        print(f"  测试摘要: {summary}")
        
    except Exception as e:
        print(f"  ❌ BART 模型加载失败: {e}")
        print("\n  建议:")
        print("  1. 检查网络连接")
        print("  2. 使用更小的模型 (bart-base)")
        print("  3. 或使用其他摘要方案")
        return False
    
    return True

def main():
    print("=" * 50)
    print("  新闻分析系统 - 环境检查")
    print("=" * 50)
    
    results = []
    
    # 1. Python 版本
    results.append(("Python 版本", check_python_version()))
    
    # 2. 依赖包
    results.append(("依赖包", check_dependencies()))
    
    # 3. 数据库
    results.append(("数据库", check_database()))
    
    # 4. 模型
    results.append(("模型", check_models()))
    
    # 总结
    print("\n" + "=" * 50)
    print("  检查结果汇总")
    print("=" * 50)
    
    for name, result in results:
        status = "✓" if result else "❌"
        print(f"{status} {name}")
    
    if all(r[1] for r in results):
        print("\n🎉 环境配置完成！可以运行 task1&2.py")
    else:
        print("\n⚠️  存在问题，请根据上述提示修复")
        print("\n常见解决方案:")
        print("1. 依赖包问题: pip install -r requirements.txt")
        print("2. 数据库问题: 检查 testdb_history.db 文件路径")
        print("3. 模型问题: 检查网络连接或使用更小的模型")

if __name__ == "__main__":
    main()

