#!/usr/bin/env python3
"""
环境检查脚本 - 验证所有依赖是否正确安装
"""

import sys
import importlib
from typing import List, Tuple

def check_import(module_name: str, package_name: str = None) -> Tuple[bool, str]:
    """
    检查模块是否可以导入
    
    Args:
        module_name: 模块名
        package_name: pip 包名（如果与模块名不同）
    
    Returns:
        (成功状态, 消息)
    """
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, '__version__', 'unknown')
        return True, f"✓ {package_name or module_name}: {version}"
    except ImportError as e:
        return False, f"✗ {package_name or module_name}: 未安装"

def main():
    print("=" * 70)
    print("  新闻分析系统 - 环境检查")
    print("=" * 70)
    print()
    
    # 检查 Python 版本
    print(f"Python 版本: {sys.version}")
    py_version = sys.version_info
    if py_version.major == 3 and 9 <= py_version.minor <= 11:
        print("✓ Python 版本符合要求 (3.9-3.11)")
    else:
        print("⚠️  推荐使用 Python 3.9-3.11")
    print()
    
    # 核心依赖检查
    print("检查核心依赖:")
    print("-" * 70)
    
    core_deps = [
        # Web 框架
        ('fastapi', 'fastapi'),
        ('flask', 'flask'),
        ('uvicorn', 'uvicorn'),
        ('jinja2', 'jinja2'),
        
        # NLP 和机器学习
        ('transformers', 'transformers'),
        ('torch', 'torch'),
        ('sentence_transformers', 'sentence-transformers'),
        ('keybert', 'keybert'),
        ('sklearn', 'scikit-learn'),
        ('numpy', 'numpy'),
        ('jieba', 'jieba'),
        ('spacy', 'spacy'),
        
        # 爬虫
        ('requests', 'requests'),
        ('bs4', 'beautifulsoup4'),
        ('telethon', 'telethon'),
        
        # 其他
        ('redis', 'redis'),
        ('matplotlib', 'matplotlib'),
    ]
    
    success_count = 0
    failed = []
    
    for module, package in core_deps:
        ok, msg = check_import(module, package)
        print(f"  {msg}")
        if ok:
            success_count += 1
        else:
            failed.append(package)
    
    print()
    print("-" * 70)
    print(f"安装进度: {success_count}/{len(core_deps)}")
    
    # 可选依赖检查
    print()
    print("检查可选依赖:")
    print("-" * 70)
    
    optional_deps = [
        ('telegram', 'python-telegram-bot'),
        ('dotenv', 'python-dotenv'),
    ]
    
    for module, package in optional_deps:
        ok, msg = check_import(module, package)
        print(f"  {msg}")
    
    # spaCy 模型检查
    print()
    print("检查 spaCy 模型:")
    print("-" * 70)
    
    try:
        import spacy
        models = ['zh_core_web_sm', 'zh_core_web_lg']
        model_found = False
        for model_name in models:
            try:
                nlp = spacy.load(model_name)
                print(f"  ✓ {model_name}: 已安装")
                model_found = True
            except OSError:
                print(f"  ✗ {model_name}: 未安装")
        
        if not model_found:
            print()
            print("  建议运行: python -m spacy download zh_core_web_sm")
    except ImportError:
        print("  ✗ spacy 未安装，无法检查模型")
    
    # 数据目录检查
    print()
    print("检查项目目录:")
    print("-" * 70)
    
    import os
    dirs = ['data', 'logs', 'src', 'api', 'templates_UI']
    for dir_name in dirs:
        if os.path.exists(dir_name):
            print(f"  ✓ {dir_name}/ 存在")
        else:
            print(f"  ✗ {dir_name}/ 不存在")
    
    # 总结
    print()
    print("=" * 70)
    
    if not failed:
        print("✓ 所有核心依赖已正确安装!")
        print()
        print("下一步:")
        print("  1. 配置环境变量: cp .env.example .env")
        print("  2. 下载 spaCy 模型: python -m spacy download zh_core_web_sm")
        print("  3. 启动服务: python web_app.py")
        return 0
    else:
        print("⚠️  以下依赖缺失:")
        for pkg in failed:
            print(f"     - {pkg}")
        print()
        print("安装缺失依赖:")
        print(f"  uv pip install {' '.join(failed)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
