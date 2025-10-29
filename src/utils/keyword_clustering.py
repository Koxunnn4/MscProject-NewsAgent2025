"""
关键词聚类与同义词识别
"""
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np
from collections import defaultdict

class KeywordClusteringService:
    """关键词聚类服务"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    def cluster_all_keywords(self, eps: float = 0.3, min_samples: int = 2):
        """
        对所有关键词进行聚类
        
        Args:
            eps: DBSCAN 邻域半径（越小越严格）
            min_samples: 簇的最小样本数
        """
        print("开始关键词聚类分析...")
        
        # 1. 获取所有关键词及其频率
        query = """
        SELECT keyword, COUNT(*) as count
        FROM news_keywords
        GROUP BY keyword
        HAVING count >= 2
        ORDER BY count DESC
        """
        keywords_data = self.db.execute_query(query)
        
        keywords = [k['keyword'] for k in keywords_data]
        counts = [k['count'] for k in keywords_data]
        
        print(f"共有 {len(keywords)} 个关键词待聚类")
        
        # 2. 计算词向量
        print("计算词向量...")
        embeddings = self.model.encode(keywords, show_progress_bar=True)
        
        # 3. DBSCAN 聚类
        print("执行聚类分析...")
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        labels = clustering.fit_predict(embeddings)
        
        # 4. 整理聚类结果
        clusters = defaultdict(list)
        for keyword, label, count in zip(keywords, labels, counts):
            if label != -1:  # -1 表示噪音点
                clusters[label].append((keyword, count))
        
        print(f"识别出 {len(clusters)} 个同义词簇")
        
        # 5. 选择代表词并存入数据库
        synonym_count = 0
        for cluster_id, words in clusters.items():
            # 按频率排序，选择最常见的作为代表词
            words.sort(key=lambda x: x[1], reverse=True)
            representative = words[0][0]
            
            print(f"\n簇 {cluster_id}: 代表词 = {representative}")
            
            # 将其他词映射到代表词
            for word, count in words[1:]:
                print(f"  → {word} (出现{count}次)")
                
                # 计算相似度
                word_embedding = self.model.encode([word])
                rep_embedding = self.model.encode([representative])
                similarity = np.dot(word_embedding, rep_embedding.T)[0][0]
                
                # 存入数据库
                self.db.save_keyword_synonym(word, representative, similarity)
                synonym_count += 1
        
        print(f"\n✓ 完成！共识别 {synonym_count} 对同义词关系")
        return synonym_count
    
    def cluster_by_industry(self):
        """
        按行业/领域聚类
        
        例如:
        - 加密货币: BTC, Bitcoin, 比特币, ETH, 以太坊...
        - 传统金融: 美联储, 降息, 利率...
        - 科技公司: 特斯拉, Tesla, 马斯克...
        """
        # 使用更大的 eps 值进行粗粒度聚类
        # 这会将相关但不完全同义的词聚到一起
        pass  # 类似实现