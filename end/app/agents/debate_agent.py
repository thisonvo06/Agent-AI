"""
S6: 双辩论智能体对抗 —— LangGraph Node
================================================
职责：正方/反方/裁判三轮对抗思辨
LangChain 1.x：三次独立 LCEL 链调用
"""
import json
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import PipelineState, DebateResult, DebateArgument
from app.agents.base_agent import _log_stage, _emit_progress, _build_evidence_context
from app.agents.literature_miner import _safe_json_parse
from app.utils.logger import get_logger

logger = get_logger("DebateAgent")

# 攻击方向关键词分类
SCOPE_KEYWORDS = ["范围", "外推", "效度", "适用", "场景", "人群", "样本", "context", "external"]
MECHANISM_KEYWORDS = ["机制", "逻辑", "因果", "假设", "推理", "内因", "矛盾", "mechanism", "internal"]


def _classify_argument(text: str) -> str:
    """分类论据方向：scope / mechanism"""
    text_lower = text.lower()
    for kw in MECHANISM_KEYWORDS:
        if kw in text_lower:
            return "mechanism"
    for kw in SCOPE_KEYWORDS:
        if kw in text_lower:
            return "scope"
    return "scope"  # 默认归为外部效度


async def s6_node(state: PipelineState) -> dict:
    """S6: 辩论对抗（正方→反方→裁判）"""
    topic = state["topic"]
    refs = state.get("refs", {})
    hypothesis = state.get("hypothesis")
    round_num = state.get("round", 1)
    con_threshold = state.get("con_threshold", 3)

    if not hypothesis:
        _log_stage("S6", "无假设，跳过辩论", "warn")
        return {
            "debate_result": DebateResult(round=round_num),
            "gates": {**state.get("gates", {}), "debate": True},
            "progress": _emit_progress(state, "S6", "辩论（跳过）", "done"),
        }

    evidence_ctx = _build_evidence_context(refs)
    hypothesis_text = f"标题：{hypothesis.title}\n解决思路：{hypothesis.idea}"

    _log_stage("S6", f"第{round_num}轮辩论开始")

    # --- 正方 ---
    pro_args = []
    try:
        raw = await llm_service.chat(
            system_prompt=prompt_guard.DEBATE_PROPONENT_SYS,
            user_prompt=(
                f"{evidence_ctx}\n\n"
                f"作为正方，论证以下假设的合理性。\n"
                f"待辩论假设：{hypothesis_text}\n"
                f"请引用文献清单中的具体证据。"
            ),
            temperature=0.5,
            max_tokens=1200,
        )
        parsed = _safe_json_parse(raw)
        if parsed and "arguments" in parsed:
            for arg in parsed["arguments"]:
                pro_args.append(DebateArgument(
                    t=arg.get("t", ""),
                    refs=arg.get("refs", []),
                ))
    except Exception as e:
        logger.warning(f"正方生成失败: {e}")

    _log_stage("S6", f"正方提出 {len(pro_args)} 个论据")

    # --- 反方 ---
    con_args = []
    try:
        raw = await llm_service.chat(
            system_prompt=prompt_guard.DEBATE_OPPONENT_SYS,
            user_prompt=(
                f"{evidence_ctx}\n\n"
                f"作为反方，找出以下假设的漏洞。\n"
                f"待辩论假设：{hypothesis_text}\n"
                f"请引用文献清单中的反例或矛盾证据来反驳。"
            ),
            temperature=0.5,
            max_tokens=1200,
        )
        parsed = _safe_json_parse(raw)
        if parsed and "arguments" in parsed:
            for arg in parsed["arguments"]:
                arg_type = arg.get("type", _classify_argument(arg.get("t", "")))
                con_args.append(DebateArgument(
                    t=arg.get("t", ""),
                    refs=arg.get("refs", []),
                ))
    except Exception as e:
        logger.warning(f"反方生成失败: {e}")

    _log_stage("S6", f"反方提出 {len(con_args)} 个论据")

    # --- 裁判 ---
    judge_verdict = ""
    is_biased = False
    con_active_count = sum(
        1 for a in con_args
        if _classify_argument(a.t) == "mechanism"
    )
    scope_limit = None

    try:
        pro_text = "\n".join(f"- {a.t}" for a in pro_args)
        con_text = "\n".join(f"- {a.t}" for a in con_args)
        raw = await llm_service.chat(
            system_prompt=prompt_guard.DEBATE_JUDGE_SYS,
            user_prompt=(
                f"【正方论点】\n{pro_text}\n\n"
                f"【反方论点】\n{con_text}\n\n"
                f"反方有效论据阈值：{con_threshold}\n"
                f"请裁定假设是否片面，若片面请给出范围收窄指令。"
            ),
            temperature=0.3,
            max_tokens=800,
        )
        parsed = _safe_json_parse(raw)
        if parsed:
            judge_verdict = parsed.get("verdict", "")
            is_biased = parsed.get("is_biased", False)
            con_active_count = parsed.get("con_active_count", con_active_count)
            scope_limit = parsed.get("scope_limit")
    except Exception as e:
        logger.warning(f"裁判生成失败: {e}")

    # 闸门判定：反方内在机制类有效论据 >= 阈值 → 判定片面
    gate_passed = con_active_count < con_threshold

    _log_stage("S6", f"裁判裁定: biased={is_biased}, "
               f"con_active={con_active_count}, gate={gate_passed}")

    debate_result = DebateResult(
        round=round_num,
        pro_arguments=pro_args,
        con_arguments=con_args,
        judge_verdict=judge_verdict,
        is_biased=is_biased,
        con_active_count=con_active_count,
        scope_limit=scope_limit,
    )

    return {
        "debate_result": debate_result,
        "gates": {**state.get("gates", {}), "debate": gate_passed},
        "scope_limits": [scope_limit] if scope_limit else [],
        "progress": _emit_progress(state, "S6", f"辩论对抗(第{round_num}轮)", "done"),
    }
