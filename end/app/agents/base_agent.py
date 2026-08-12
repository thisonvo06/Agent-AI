"""
Agent 基类与公共工具 —— LangGraph 节点模式
================================================================
LangChain 1.x / LangGraph 1.x 架构：
- 每个 Agent 不再是独立类，而是 LangGraph StateGraph 的 node 函数
- node 函数签名：async def sX_node(state: PipelineState) -> dict
- node 返回 dict 片段更新 state（不是完整 state）
- LLM 调用统一走 LLMService（ChatOpenAI + LCEL 链）
"""
import json
from datetime import datetime
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import (
    PipelineState, HypothesisData, DebateResult, DebateArgument,
    GroundingResultData, CausalResultData, EvidenceLevel,
)
from app.utils.logger import get_logger

logger = get_logger("BaseAgent")


def _log_stage(stage_id: str, msg: str, level: str = "info"):
    """记录阶段日志"""
    getattr(logger, level, logger.info)(f"[{stage_id}] {msg}")


def _emit_progress(state: PipelineState, stage_id: str, name: str, status: str = "run") -> list:
    """生成进度条目（追加到 state.progress）"""
    return [{
        "stage": stage_id,
        "name": name,
        "status": status,
        "ts": datetime.now().isoformat(),
    }]


def _build_evidence_context(refs: dict) -> str:
    """构建文献上下文"""
    return prompt_guard.build_evidence_context(refs)


def _fallback_hypothesis(topic_title: str, scope_limit: str = "") -> HypothesisData:
    """离线降级假设"""
    return HypothesisData(
        title=f"[离线] {topic_title} 的探索性假设",
        problem=f"针对「{topic_title}」的探索性研究",
        idea="（离线模式：API 不可用，生成占位假设）",
        tech="统计检验 + 机器学习",
        dataset_source="公开数据集",
        dataset_target="待采集",
        abstract="离线模式占位摘要",
        methodology="待补充",
        experiment="待设计",
        results="待验证",
        refs=[],
        scope_limit=scope_limit,
    )
