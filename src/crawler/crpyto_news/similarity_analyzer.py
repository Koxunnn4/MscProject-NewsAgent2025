import sqlite3
import re
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

class SimilarityAnalyzer:
    SPLIT_RE = re.compile(r"[,，]+")

    def __init__(self,
                 db_path=r"history.db",
                 table="messages",
                 keyword_column="keywords",
                 currency_column="industry",
                 min_count=5,
                 top_n=100):
        self.db_path = db_path
        self.table = table
        self.keyword_column = keyword_column
        self.currency_column = currency_column
        self.min_count = min_count
        self.top_n = top_n

    def load_spacy_model(self):
        """按优先级加载中文 spaCy 模型"""
        for model in ["zh_core_web_lg", "zh_core_web_trf", "zh_core_web_md", "zh_core_web_sm"]:
            try:
                nlp = spacy.load(model)
                print(f"✓ 已加载 spaCy 模型: {model}\n")
                return nlp
            except Exception:
                continue
        raise RuntimeError("未找到可用的中文 spaCy 模型，请安装: python -m spacy download zh_core_web_lg")

    def get_total_rows(self):
        """获取数据库表的总行数"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {self.table}")
            total = cur.fetchone()[0]
        finally:
            conn.close()
        return total

    def fetch_column_data(self, column):
        """从数据库读取指定列的所有数据"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT {column} FROM {self.table} WHERE {column} IS NOT NULL")
            rows = cur.fetchall()
        finally:
            conn.close()
        return rows

    def count_items_with_occurrence(self, rows, case_insensitive=True):
        """
        统计分隔字符串中各项的出现次数和在多少行中出现过
        Returns:
            tuple: (item_counter, occurrence_counter)
                - item_counter: {item: 总出现次数}
                - occurrence_counter: {item: 出现在多少行}
        """
        item_counter = Counter()
        occurrence_counter = Counter()

        for (item_str,) in rows:
            if not item_str:
                continue
            parts = [p.strip() for p in self.SPLIT_RE.split(item_str) if p and p.strip()]
            if case_insensitive:
                parts = [p.lower() for p in parts]
            item_counter.update(parts)
            occurrence_counter.update(set(parts))

        return item_counter, occurrence_counter

    def print_counter_with_ratio(self, item_counter, occurrence_counter, total_rows, title, top_n=None):
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
            print(f"{i:<6}{item:<30}{count:<12}{ratio:.2f}%")

    def print_counter(self, counter, title, top_n=None):
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")
        print(f"总种类数: {len(counter)}")
        print(f"总出现次数: {sum(counter.values())}\n")

        items = counter.most_common(top_n) if top_n else counter.most_common()
        for i, (item, count) in enumerate(items, 1):
            print(f"{i:>4}. {item}: {count}")

    def calculate_similarity(self, nlp, counter):
        # 过滤低频词
        terms = [t for t, c in counter.items() if c >= self.min_count]
        print(f"\n{'='*60}")
        print(f"关键词相似度分析 (词频 ≥ {self.min_count})")
        print(f"{'='*60}")
        print(f"总关键词种类: {len(counter)}")
        print(f"筛选后关键词: {len(terms)}\n")

        if len(terms) < 2:
            print("关键词数量不足，无法计算相似度")
            return []

        term_docs = {}
        skipped = []
        for t in terms:
            doc = nlp(t)
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

        pairs = []
        keys = list(term_docs.keys())
        total_pairs = len(keys) * (len(keys) - 1) // 2
        print(f"开始计算 {total_pairs} 对相似度...\n")

        import itertools
        for a, b in itertools.combinations(keys, 2):
            sim = term_docs[a].similarity(term_docs[b])
            pairs.append((a, counter[a], b, counter[b], float(sim)))

        pairs.sort(key=lambda x: x[4], reverse=True)

        print(f"按相似度降序输出前 {min(self.top_n, len(pairs))} 对结果:")
        print(f"{'-'*60}")
        for i, (a, ca, b, cb, s) in enumerate(pairs[:self.top_n], 1):
            print(f"{i:>4} | {a}({ca}) — {b}({cb}) : {s:.4f}")

        return pairs

    def query_keyword_similarity(self, nlp, input_keyword, keyword_counter):
        """
        用户输入关键词查询及相似度推荐

        Args:
            nlp: spaCy模型
            input_keyword: 用户输入的关键词 (str)
            keyword_counter: 数据库统计的关键词Counter对象

        Returns:
            tuple:
                - exists (bool): 关键词是否存在于数据库关键词中(忽略大小写)
                - top_similar (list): 前10个最相似关键词的列表 [(word, count, similarity), ...]
        """
        input_norm = input_keyword.lower().strip()
        # 判断是否存在
        exists = input_norm in (k.lower() for k in keyword_counter.keys())

        # 过滤高频词
        high_freq_terms = [t for t, c in keyword_counter.items() if c >= self.min_count]

        # 创建高频词的Doc向量
        term_docs = {}
        for t in high_freq_terms:
            doc = nlp(t)
            if hasattr(doc, "vector_norm") and doc.vector_norm > 0:
                term_docs[t] = doc

        # 计算输入关键词的Doc
        input_doc = nlp(input_norm)
        if not (hasattr(input_doc, "vector_norm") and input_doc.vector_norm > 0):
            # 无向量时，无法计算相似度，返回空列表
            return exists, []

        # 计算相似度
        similarities = []
        for term, doc in term_docs.items():
            sim = input_doc.similarity(doc)
            similarities.append((term, keyword_counter[term], float(sim)))

        # 排序取top10
        similarities.sort(key=lambda x: x[2], reverse=True)
        top_similar = similarities[:10]

        return exists, top_similar

def main():
    print(f"\n{'#'*80}")
    print(f"# 数据库分析工具")
    print(f"# 数据库: {DB_PATH}")
    print(f"{'#'*80}")

    analyzer = SimilarityAnalyzer(
        db_path=DB_PATH,
        table=TABLE,
        keyword_column=KEYWORD_COLUMN,
        currency_column=CURRENCY_COLUMN,
        min_count=MIN_COUNT,
        top_n=TOP_N,
    )

    print("\n[0/4] 统计数据库总行数...")
    total_rows = analyzer.get_total_rows()
    print(f"✓ 数据库总行数: {total_rows}")

    print("\n[1/4] 读取关键词数据...")
    keyword_rows = analyzer.fetch_column_data(analyzer.keyword_column)
    keyword_counter, keyword_occurrence = analyzer.count_items_with_occurrence(keyword_rows, case_insensitive=True)
    # analyzer.print_counter_with_ratio(
    #     keyword_counter,
    #     keyword_occurrence,
    #     total_rows,
    #     "关键词统计 (Keywords)",
    #     top_n=50
    # )

    print("\n[2/4] 读取币种数据...")
    currency_rows = analyzer.fetch_column_data(analyzer.currency_column)
    currency_counter, currency_occurrence = analyzer.count_items_with_occurrence(currency_rows, case_insensitive=True)
    # analyzer.print_counter_with_ratio(
    #     currency_counter,
    #     currency_occurrence,
    #     total_rows,
    #     "币种统计 (Currency)",
    #     top_n=None
    # )

    print("\n[3/4] 加载 spaCy 模型...")
    nlp = analyzer.load_spacy_model()

    print("[4/4] 计算关键词相似度...")
    pairs = analyzer.calculate_similarity(nlp, keyword_counter)


    print(f"\n{'='*80}")
    print("分析完成!")
    print(f"{'='*80}")
    print(f"✓ 数据库总行数: {total_rows}")
    print(f"✓ 关键词种类: {len(keyword_counter)}")
    print(f"✓ 币种种类: {len(currency_counter)}")
    print(f"✓ 相似度对数: {len(pairs)}")
    print(f"{'='*80}\n")

    while True:
        input_keyword = input("请输入你感兴趣的关键词: ")
        exists, top_similar = analyzer.query_keyword_similarity(nlp, input_keyword, keyword_counter)

        if exists:
            print(f"关键词'{input_keyword}'在数据库中存在。")
        else:
            print(f"关键词'{input_keyword}'在数据库中不存在。")

        print("与输入关键词最接近的 top 10 关键词及相似度：")
        for i, (word, count, sim) in enumerate(top_similar, 1):
            print(f"{i}. {word} (出现次数: {count}) - 相似度: {sim:.4f}")

if __name__ == "__main__":
    main()