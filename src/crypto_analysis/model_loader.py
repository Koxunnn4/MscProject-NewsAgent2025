"""
统一的模型加载器模块
避免重复加载 spaCy 和 KeyBERT 模型，提升性能
"""
import spacy
import logging

logger = logging.getLogger(__name__)

# 全局模型缓存
_spacy_model_cache = {}
_keybert_model = None


def get_spacy_model(model_name: str = "zh_core_web_sm") -> spacy.Language:
    """
    获取 spaCy 模型（单例模式，避免重复加载）

    支持的模型优先级：
    1. zh_core_web_lg (最大，质量最好)
    2. zh_core_web_trf (Transformer 模型)
    3. zh_core_web_md (中等)
    4. zh_core_web_sm (最小，最快)

    Args:
        model_name: 首选模型名称，如果加载失败会尝试其他模型

    Returns:
        加载好的 spaCy 模型

    Raises:
        RuntimeError: 如果没有找到任何可用的模型
    """
    if model_name in _spacy_model_cache:
        logger.debug(f"✓ 使用缓存的 spaCy 模型: {model_name}")
        return _spacy_model_cache[model_name]

    # 优先级列表
    model_priority = [
        model_name,  # 首选
        "zh_core_web_lg",
        "zh_core_web_trf",
        "zh_core_web_md",
        "zh_core_web_sm"
    ]

    # 去重
    model_priority = list(dict.fromkeys(model_priority))

    for model in model_priority:
        try:
            logger.info(f"正在加载 spaCy 模型: {model}...")
            nlp = spacy.load(model)
            _spacy_model_cache[model] = nlp
            logger.info(f"✓ 成功加载 spaCy 模型: {model}")
            return nlp
        except OSError:
            logger.debug(f"⚠️  模型 {model} 未找到，尝试下一个...")
            continue
        except Exception as e:
            logger.warning(f"⚠️  加载模型 {model} 失败: {e}")
            continue

    raise RuntimeError(
        f"未找到可用的 spaCy 中文模型。\n"
        f"请运行以下命令之一安装：\n"
        f"  python -m spacy download zh_core_web_lg\n"
        f"  python -m spacy download zh_core_web_md\n"
        f"  python -m spacy download zh_core_web_sm"
    )


def get_keybert_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
    """
    获取 KeyBERT 模型（单例模式，避免重复加载）

    Args:
        model_name: 模型名称

    Returns:
        加载好的 KeyBERT 模型，如果加载失败返回 None
    """
    global _keybert_model

    if _keybert_model is not None:
        logger.debug(f"✓ 使用缓存的 KeyBERT 模型")
        return _keybert_model

    try:
        from keybert import KeyBERT
        logger.info(f"正在加载 KeyBERT 模型: {model_name}...")
        _keybert_model = KeyBERT(model=model_name)
        logger.info(f"✓ 成功加载 KeyBERT 模型: {model_name}")
        return _keybert_model
    except ImportError:
        logger.error("⚠️  KeyBERT 未安装，请运行: pip install keybert sentence-transformers")
        return None
    except Exception as e:
        logger.error(f"⚠️  KeyBERT 模型加载失败: {e}")
        return None


def clear_model_cache():
    """清空模型缓存（用于测试或节省内存）"""
    global _spacy_model_cache, _keybert_model
    _spacy_model_cache.clear()
    _keybert_model = None
    logger.info("✓ 模型缓存已清空")


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    print("测试 spaCy 模型加载...")
    nlp = get_spacy_model()
    print(f"加载的模型: {nlp.meta['name']}")

    print("\n测试 KeyBERT 模型加载...")
    kb = get_keybert_model()
    if kb:
        print(f"✓ KeyBERT 已加载")
    else:
        print(f"⚠️  KeyBERT 不可用")
