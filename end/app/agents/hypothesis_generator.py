"""
S5: 假设生成智能体 —— LangGraph Node
================================================
职责：基于归纳+演绎推理生成可验证科学假设
LangChain 1.x：使用 LCEL 链 + with_structured_output(HypothesisData)
"""
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import PipelineState, HypothesisData
from app.agents.base_agent import (
    _log_stage, _emit_progress, _build_evidence_context, _fallback_hypothesis,
)
from app.utils.logger import get_logger

logger = get_logger("HypothesisGen")


async def s5_node(state: PipelineState) -> dict:
    """S5: 假设生成（归纳+演绎推理）"""
    topic = state["topic"]
    refs = state.get("refs", {})
    round_num = state.get("round", 1)
    scope_limits = state.get("scope_limits", [])
    current_scope = scope_limits[-1] if scope_limits else None

    _log_stage("S5", f"第{round_num}轮假设生成")

    # 构建证据上下文
    evidence_ctx = _build_evidence_context(refs)

    # 构建迭代修订提示
    scope_hint = prompt_guard.build_scope_hint(round_num, current_scope)

    # 使用 LCEL 链 + 结构化输出
    try:
        result = await llm_service.chat_structured(
            system_prompt=prompt_guard.HYPOTHESIS_GENERATOR_SYS,
            user_prompt=(
                f"{evidence_ctx}\n\n"
                f"【任务】基于以上文献事实，针对问题「{topic.title}」，"
                f"生成一个可验证的科学假设。\n"
                f"当前轮次：第 {round_num} 轮\n"
                f"{scope_hint}"
                f"请输出结构化假设。"
            ),
            output_schema=HypothesisData,
            model="qwen-max",          # 高难度推理用 max
            temperature=0.6,
            max_tokens=2000,
        )

        if result and isinstance(result, HypothesisData):
            if current_scope:
                result.scope_limit = current_scope
            _log_stage("S5", f"假设生成成功: {result.title[:40]}...")
            hypothesis = result
        else:
            logger.warning("千问结构化输出失败，使用降级假设")
            hypothesis = _fallback_hypothesis(topic.title, current_scope or "")

    except Exception as e:
        logger.error(f"S5 假设生成失败: {e}")
        hypothesis = _fallback_hypothesis(topic.title, current_scope or "")

    return {
        "hypothesis": hypothesis,
        "progress": _emit_progress(state, "S5", f"假设生成(第{round_num}轮)", "done"),
    }
