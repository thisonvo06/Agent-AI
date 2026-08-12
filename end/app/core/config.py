"""
核心配置管理
所有配置项均可通过环境变量 / .env 文件覆盖
LangChain 1.x / LangGraph 1.x 架构
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os

# LangSmith trace（可选，设为 false 关闭）
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # end/
DATA_DIR = BASE_DIR / "data"
LITERATURE_DIR = DATA_DIR / "literature"
DATASETS_DIR = DATA_DIR / "datasets"
OUTPUTS_DIR = DATA_DIR / "outputs"


class Settings(BaseSettings):
    """全局配置 —— 通过环境变量或 .env 文件注入"""

    # === 阿里云百炼 / Qwen ===
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    qwen_model_strong: str = "qwen-max"
    qwen_model_fast: str = "qwen-turbo"
    llm_timeout: int = 60
    llm_max_retries: int = 3

    # === 向量数据库 Milvus ===
    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: int = int(os.getenv("MILVUS_PORT", "19530"))
    milvus_collection: str = "literature_vectors"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    # === MySQL ===
    mysql_url: str = os.getenv(
        "MYSQL_URL",
        "mysql+aiomysql://root:root@localhost:3306/ai_scientist",
    )
    mysql_echo: bool = False

    # === 流水线参数 ===
    max_iterations: int = 2
    con_threshold: int = 3
    grounding_threshold: float = 0.05
    causal_p_threshold: float = 0.05

    # === 文件存储 ===
    upload_dir: str = str(LITERATURE_DIR)
    output_dir: str = str(OUTPUTS_DIR)

    # === LangSmith ===
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = "ai-scientist"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """单例配置"""
    return Settings()


# 确保数据目录存在
for d in [LITERATURE_DIR, DATASETS_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
