#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库关键词和币种分析脚本

功能:
1. 统计 keywords 列中关键词出现次数
2. 统计 industry 列中币种出现次数
3. 计算高频关键词(出现次数≥5)之间的相似度并降序排列

用法:
    python analyse.py
"""
import sqlite3
import re
import collections
import itertools
import spacy
from collections import Counter

# ======= 配置参数 =======
DB_PATH = r"E:\msc_proj\MscProject-NewsAgent2025\src\crawler\crpyto_news\history.db"
TABLE = "messages"
KEYWORD_COLUMN = "keywords"
CURRENCY_COLUMN = "industry"
MIN_COUNT = 5  # 相似度计算的最小词频阈值
TOP_N = 100  # 打印前 N 对相似度结果

SPLIT_RE = re.compile(r"[,，]+")  # 英文逗号/中文逗号分隔符


def load_spacy_model():
    """按优先级加载中文 spaCy 模型"""
    for model in ["zh_core_web_lg", "zh_core_web_trf", "zh_core_web_md", "zh_core_web_sm"]:
        try:
            nlp = spacy.load(model)
            print(f"✓ 已加载 spaCy 模型: {model}\n")
            return nlp
        except Exception:
            continue
    raise RuntimeError("未找到可用的中文 spaCy 模型，请安装: python -m spacy download zh_core_web_lg")


def get_total_rows(db_path, table):
    """获取数据库表的总行数"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
    finally:
        conn.close()
    return total


def fetch_column_data(db_path, table, column):
    """从数据库读取指定列的所有数据"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL")
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def count_items_with_occurrence(rows, split_pattern=SPLIT_RE, case_insensitive=True):
    """
    统计分隔字符串中各项的出现次数和在多少行中出现过

    Args:
        rows: 数据库查询结果 [(value,), ...]
        split_pattern: 分隔符正则表达式
        case_insensitive: 是否不区分大小写(英文)

    Returns:
        tuple: (item_counter, occurrence_counter)
            - item_counter: {item: 总出现次数}
            - occurrence_counter: {item: 出现在多少行}
    """
    item_counter = Counter()  # 统计总出现次数
    occurrence_counter = Counter()  # 统计出现在多少行

    for (item_str,) in rows:
        if not item_str:
            continue
        parts = [p.strip() for p in split_pattern.split(item_str) if p and p.strip()]
        if case_insensitive:
            parts = [p.lower() for p in parts]

        # 统计总次数
        item_counter.update(parts)

        # 统计出现行数(去重)
        unique_parts = set(parts)
        occurrence_counter.update(unique_parts)

    return item_counter, occurrence_counter


def print_counter_with_ratio(item_counter, occurrence_counter, total_rows, title, top_n=None):
    """
    打印统计结果(包含出现次数和占比)

    Args:
        item_counter: {item: 总出现次数}
        occurrence_counter: {item: 出现在多少行}
        total_rows: 数据库总行数
        title: 标题
        top_n: 只打印前N个结果
    """
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"总种类数: {len(item_counter)}")
    print(f"总出现次数: {sum(item_counter.values())}")
    print(f"数据库总行数: {total_rows}\n")

    print(f"{'序号':<6}{'项目':<30}{'出现次数':<12}{'占比':<10}")
    print(f"{'-'*60}")

    items = item_counter.most_common(top_n) if top_n else item_counter.most_common()
    for i, (item, count) in enumerate(items, 1):
        occur_count = occurrence_counter[item]
        ratio = (occur_count / total_rows * 100) if total_rows > 0 else 0
        # 没有跟上面的对齐
        print(f"{i:<6}{item:<30}{count:<12}{ratio:.2f}%")


def print_counter(counter, title, top_n=None):
    """打印统计结果(旧版,保留用于相似度分析)"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"总种类数: {len(counter)}")
    print(f"总出现次数: {sum(counter.values())}\n")

    items = counter.most_common(top_n) if top_n else counter.most_common()
    for i, (item, count) in enumerate(items, 1):
        print(f"{i:>4}. {item}: {count}")


def calculate_similarity(nlp, counter, min_count=5, top_n=100):
    """
    计算高频关键词之间的相似度

    Args:
        nlp: spaCy 模型
        counter: 关键词计数器
        min_count: 最小词频阈值
        top_n: 打印前 N 对结果

    Returns:
        list: [(word1, count1, word2, count2, similarity), ...]
    """
    # 1) 过滤低频词
    terms = [t for t, c in counter.items() if c >= min_count]
    print(f"\n{'='*60}")
    print(f"关键词相似度分析 (词频 ≥ {min_count})")
    print(f"{'='*60}")
    print(f"总关键词种类: {len(counter)}")
    print(f"筛选后关键词: {len(terms)}\n")

    if len(terms) < 2:
        print("关键词数量不足，无法计算相似度")
        return []

    # 2) 为可计算向量的关键词创建 Doc
    term_docs = {}
    skipped = []
    for t in terms:
        doc = nlp(t)
        # 检查是否有可用向量
        if hasattr(doc, "vector_norm") and doc.vector_norm > 0:
            term_docs[t] = doc
        else:
            skipped.append(t)

    print(f"可计算相似度的关键词: {len(term_docs)}")
    if skipped:
        print(f"跳过无向量的关键词: {len(skipped)}")
        print(f"示例: {skipped[:10]}\n")

    if len(term_docs) < 2:
        print("有效关键词数量不足，无法计算相似度")
        return []

    # 3) 计算两两相似度
    pairs = []
    keys = list(term_docs.keys())
    total_pairs = len(keys) * (len(keys) - 1) // 2
    print(f"开始计算 {total_pairs} 对相似度...\n")

    for a, b in itertools.combinations(keys, 2):
        sim = term_docs[a].similarity(term_docs[b])
        pairs.append((a, counter[a], b, counter[b], float(sim)))

    # 4) 按相似度降序排序
    pairs.sort(key=lambda x: x[4], reverse=True)

    # 5) 打印结果
    print(f"按相似度降序输出前 {min(top_n, len(pairs))} 对结果:")
    print(f"{'-'*60}")
    for i, (a, ca, b, cb, s) in enumerate(pairs[:top_n], 1):
        print(f"{i:>4} | {a}({ca}) — {b}({cb}) : {s:.4f}")

    return pairs


def main():
    """主函数"""
    print(f"\n{'#'*80}")
    print(f"# 数据库分析工具")
    print(f"# 数据库: {DB_PATH}")
    print(f"{'#'*80}")

    # 0. 获取数据库总行数
    print("\n[0/4] 统计数据库总行数...")
    total_rows = get_total_rows(DB_PATH, TABLE)
    print(f"✓ 数据库总行数: {total_rows}")

    # 1. 统计关键词
    print("\n[1/4] 读取关键词数据...")
    keyword_rows = fetch_column_data(DB_PATH, TABLE, KEYWORD_COLUMN)
    keyword_counter, keyword_occurrence = count_items_with_occurrence(keyword_rows, case_insensitive=True)
    print_counter_with_ratio(
        keyword_counter,
        keyword_occurrence,
        total_rows,
        "关键词统计 (Keywords)",
        top_n=50
    )

    # 2. 统计币种
    print("\n[2/4] 读取币种数据...")
    currency_rows = fetch_column_data(DB_PATH, TABLE, CURRENCY_COLUMN)
    currency_counter, currency_occurrence = count_items_with_occurrence(currency_rows, case_insensitive=True)
    print_counter_with_ratio(
        currency_counter,
        currency_occurrence,
        total_rows,
        "币种统计 (Currency)",
        top_n=None
    )

    # 3. 加载 spaCy 模型
    print("\n[3/4] 加载 spaCy 模型...")
    nlp = load_spacy_model()

    # 4. 计算关键词相似度
    print("[4/4] 计算关键词相似度...")
    pairs = calculate_similarity(nlp, keyword_counter, min_count=MIN_COUNT, top_n=TOP_N)

    # 总结
    print(f"\n{'='*80}")
    print("分析完成!")
    print(f"{'='*80}")
    print(f"✓ 数据库总行数: {total_rows}")
    print(f"✓ 关键词种类: {len(keyword_counter)}")
    print(f"✓ 币种种类: {len(currency_counter)}")
    print(f"✓ 相似度对数: {len(pairs)}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        print(f"\n[ERROR] 数据库文件不存在: {DB_PATH}")
        print("请检查路径是否正确\n")
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}\n")
        import traceback
        traceback.print_exc()
