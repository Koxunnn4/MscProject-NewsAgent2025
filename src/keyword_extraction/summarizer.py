"""
新闻摘要生成模块
"""
import os
import sys

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from config import SUMMARY_MODEL, SUMMARY_MIN_LENGTH, SUMMARY_MAX_LENGTH

# 尝试导入 BART 模型
try:
    from transformers import BartTokenizer, BartForConditionalGeneration
    BART_AVAILABLE = True
except ImportError:
    BART_AVAILABLE = False
    print("⚠️  transformers 未安装，BART摘要功能不可用")


class NewsSummarizer:
    """新闻摘要生成器"""
    
    def __init__(self, model_name: str = None):
        """
        初始化摘要生成器
        
        Args:
            model_name: BART 模型名称
        """
        self.model_name = model_name or SUMMARY_MODEL
        self.tokenizer = None
        self.model = None
        self.use_bart = False
        
        if BART_AVAILABLE:
            try:
                print(f"正在加载 BART 模型: {self.model_name}...")
                print("（首次加载可能需要下载模型，请耐心等待）")
                self.tokenizer = BartTokenizer.from_pretrained(self.model_name)
                self.model = BartForConditionalGeneration.from_pretrained(self.model_name)
                self.use_bart = True
                print("✓ BART 模型加载完成")
            except Exception as e:
                print(f"⚠️  BART 模型加载失败: {e}")
                print("将使用简单截取方式生成摘要")
                self.use_bart = False
    
    def generate_summary(self, text: str, method: str = 'auto') -> str:
        """
        生成新闻摘要
        
        Args:
            text: 原始新闻文本
            method: 摘要方法 ('bart', 'simple', 'auto')
            
        Returns:
            摘要文本
        """
        if not text or len(text.strip()) == 0:
            return ""
        
        # 自动选择方法
        if method == 'auto':
            method = 'bart' if self.use_bart else 'simple'
        
        # 使用 BART 模型生成摘要
        if method == 'bart' and self.use_bart:
            return self._generate_bart_summary(text)
        else:
            return self._generate_simple_summary(text)
    
    def _generate_bart_summary(self, text: str) -> str:
        """
        使用 BART 模型生成摘要
        
        Args:
            text: 原始文本
            
        Returns:
            摘要文本
        """
        try:
            # 1. 文本编码（处理长文本，截断到模型最大输入长度）
            inputs = self.tokenizer(
                text,
                max_length=1024,  # BART模型最大输入长度
                truncation=True,
                return_tensors="pt"  # 返回PyTorch张量
            )
            
            # 2. 生成摘要（控制长度，避免过短或过长）
            summary_ids = self.model.generate(
                inputs["input_ids"],
                max_length=SUMMARY_MAX_LENGTH,
                min_length=SUMMARY_MIN_LENGTH,
                num_beams=4,  # 束搜索，提升摘要质量
                early_stopping=True  # 当生成达到最小长度且符合逻辑时停止
            )
            
            # 3. 解码摘要（将张量转为字符串，去除特殊符号）
            summary = self.tokenizer.decode(
                summary_ids[0],
                skip_special_tokens=True  # 跳过[CLS]、[SEP]等特殊符号
            )
            
            return summary
            
        except Exception as e:
            print(f"BART 摘要生成失败: {e}，使用简单方法")
            return self._generate_simple_summary(text)
    
    def _generate_simple_summary(self, text: str, max_len: int = None) -> str:
        """
        简单摘要生成：提取文本前N个字符（在句子边界截断）
        
        Args:
            text: 原始文本
            max_len: 最大长度
            
        Returns:
            摘要文本
        """
        max_len = max_len or SUMMARY_MAX_LENGTH
        
        if len(text) <= max_len:
            return text
        
        # 尝试在句子边界截断
        summary = text[:max_len]
        
        # 查找最后一个句号/问号/感叹号
        for punct in ['。', '！', '？', '.', '!', '?']:
            last_punct = summary.rfind(punct)
            if last_punct > max_len * 0.5:  # 确保不会截断太多
                return summary[:last_punct + 1]
        
        # 如果找不到合适的标点，直接截断并加省略号
        return summary.rstrip() + "..."
    
    def generate_batch(self, texts: list, method: str = 'auto') -> list:
        """
        批量生成摘要
        
        Args:
            texts: 文本列表
            method: 摘要方法
            
        Returns:
            摘要列表
        """
        summaries = []
        for text in texts:
            summary = self.generate_summary(text, method)
            summaries.append(summary)
        return summaries


# 单例模式
_summarizer = None

def get_summarizer() -> NewsSummarizer:
    """获取摘要生成器单例"""
    global _summarizer
    if _summarizer is None:
        _summarizer = NewsSummarizer()
    return _summarizer


if __name__ == "__main__":
    # 测试
    summarizer = get_summarizer()
    
    test_text = """
    比特币价格今日突破 $65,000，创下近期新高。
    分析师认为这与美联储降息预期有关，投资者情绪乐观。
    市场交易量显著增加，显示出强劲的买盘支撑。
    技术分析显示，比特币已突破关键阻力位，可能继续上涨。
    """
    
    print("原文:")
    print(test_text)
    print("\n简单摘要:")
    print(summarizer.generate_summary(test_text, method='simple'))
    
    if summarizer.use_bart:
        print("\nBART摘要:")
        print(summarizer.generate_summary(test_text, method='bart'))

