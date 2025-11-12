"""
HKStocks News Analyzer

This module provides keyword extraction functionality for Hong Kong stock market news.
"""

import os
import re
from typing import List, Tuple, Set
from pathlib import Path

import jieba
import spacy
from keybert import KeyBERT
from sklearn.feature_extraction.text import CountVectorizer


class HKStocksAnalyzer:
    """Analyzer for HK Stocks news - extracts keywords from news content"""

    def __init__(self):
        """Initialize the analyzer with KeyBERT model and NLP tools"""
        self.model = None
        self.nlp = None
        self.stopwords = set()
        self._initialize_models()
        self._load_stopwords()

    def _initialize_models(self):
        """Initialize KeyBERT and spaCy models"""
        # Set Hugging Face mirror for China
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

        # Initialize KeyBERT with multilingual model
        print("Loading KeyBERT model...")
        self.model = KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')

        # Initialize spaCy Chinese model
        print("Loading spaCy Chinese model...")
        try:
            self.nlp = spacy.load('zh_core_web_sm')
        except OSError:
            print("spaCy Chinese model not found. Installing...")
            import subprocess
            subprocess.run(['python', '-m', 'spacy', 'download', 'zh_core_web_sm'])
            self.nlp = spacy.load('zh_core_web_sm')

    def _load_stopwords(self):
        """Load stopwords from file"""
        stopwords_path = Path(__file__).parent / 'stopwords.txt'

        if not stopwords_path.exists():
            print(f"Warning: Stopwords file not found at {stopwords_path}")
            return

        with open(stopwords_path, 'r', encoding='utf-8') as f:
            self.stopwords = set(line.strip() for line in f if line.strip())

        print(f"Loaded {len(self.stopwords)} stopwords")

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text to remove AAStocks-specific formatting

        Args:
            text: Raw news text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove "AASTOCKS新闻:" prefix
        text = re.sub(r'^AASTOCKS新[闻聞][：:]\s*', '', text, flags=re.IGNORECASE)

        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove common disclaimers
        disclaimers = [
            r'.*免責聲明.*',
            r'.*資料來源.*',
            r'.*延遲最少.*分鐘.*',
            r'.*報價.*延遲.*',
        ]
        for pattern in disclaimers:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def tokenize_and_filter(self, text: str) -> List[str]:
        """
        Custom tokenizer for KeyBERT using jieba segmentation

        Args:
            text: Input text

        Returns:
            List of filtered tokens
        """
        # Jieba segmentation
        tokens = jieba.lcut(text)

        # Remove stopwords
        tokens = [tok for tok in tokens if tok not in self.stopwords]

        # Validate keywords
        filtered_tokens = [tok.strip() for tok in tokens if self.is_valid_keyword(tok)]

        return filtered_tokens

    def is_valid_keyword(self, word: str) -> bool:
        """
        Validate if a word is a valid keyword

        Args:
            word: Word to validate

        Returns:
            True if valid keyword, False otherwise
        """
        if not word or len(word.strip()) == 0:
            return False

        word = word.strip()

        # Only allow alphanumeric and Chinese characters
        allowed_pattern = re.compile(r'^[A-Za-z0-9\u4e00-\u9fff]+$')

        # Filter rules:
        # 1. Single Chinese character not allowed
        if re.fullmatch(r'[\u4e00-\u9fff]', word):
            return False

        # 2. Single English letter not allowed
        if re.fullmatch(r'[A-Za-z]', word):
            return False

        # 3. Pure numbers: only allow years (1950-2050)
        if re.fullmatch(r'\d+', word):
            num = int(word)
            if not (1950 <= num <= 2050):
                return False

        # 4. Must match allowed pattern
        if not allowed_pattern.match(word):
            return False

        return True

    def extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        Extract keywords from text using KeyBERT

        Args:
            text: Input text
            top_n: Number of keywords to extract

        Returns:
            List of (keyword, weight) tuples
        """
        if not text or len(text.strip()) == 0:
            return []

        # Preprocess text
        text = self._preprocess_text(text)

        if len(text) < 10:  # Too short after preprocessing
            return []

        try:
            # Configure vectorizer with custom tokenizer
            vectorizer = CountVectorizer(
                tokenizer=self.tokenize_and_filter,
                token_pattern=None
            )

            # Extract keywords using KeyBERT
            keywords = self.model.extract_keywords(
                text,
                vectorizer=vectorizer,
                keyphrase_ngram_range=(1, 3),  # 1-3 word phrases
                top_n=top_n,
                diversity=0.3  # Balance between relevance and diversity
            )

            return keywords

        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return []

    def spacy_ner_keywords(self, text: str) -> List[str]:
        """
        Extract keywords using spaCy NER as alternative method

        Args:
            text: Input text

        Returns:
            List of extracted entities/keywords
        """
        if not text:
            return []

        text = self._preprocess_text(text)
        doc = self.nlp(text)

        entities = set()

        # Extract entities based on POS tags
        for token in doc:
            token_text = token.text.strip()

            # Filter by POS tags: proper nouns, nouns, verbs
            if token.pos_ in {"PROPN", "NOUN", "VERB", "ORG", "GPE", "LOC"}:
                if (token_text not in self.stopwords and
                    len(token_text) > 1 and
                    self.is_valid_keyword(token_text)):
                    entities.add(token_text)

        return list(entities)


# Singleton instance
_hkstocks_analyzer = None


def get_hkstocks_analyzer() -> HKStocksAnalyzer:
    """
    Get singleton instance of HKStocksAnalyzer

    Returns:
        HKStocksAnalyzer instance
    """
    global _hkstocks_analyzer
    if _hkstocks_analyzer is None:
        _hkstocks_analyzer = HKStocksAnalyzer()
    return _hkstocks_analyzer
