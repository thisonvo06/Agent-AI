"""
日志工具 —— 基于 loguru
统一格式：时间 | 级别 | 模块 | 消息
"""
import sys
from loguru import logger

# 移除默认 handler
logger.remove()

# 控制台输出
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | "
           "<cyan>{module}</cyan> | <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# 文件输出（按天轮转，保留 7 天）
logger.add(
    "data/outputs/logs/ai_scientist_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {module}:{function}:{line} | {message}",
    level="DEBUG",
    rotation="1 day",
    retention="7 days",
    encoding="utf-8",
)


def get_logger(name: str = "ai_scientist"):
    """获取带名称的 logger"""
    return logger.bind(name=name)
