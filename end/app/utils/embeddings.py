"""
向量嵌入工具 —— 基于 langchain_openai.OpenAIEmbeddings
百炼 text-embedding-v3 模型，OpenAI 兼容模式
"""
from langchain_openai import OpenAIEmbeddings
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("Embeddings")
settings = get_settings()


def get_embeddings() -> OpenAIEmbeddings:
    """获取百炼向量嵌入模型实例"""
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
        dimensions=settings.embedding_dim,
    )
