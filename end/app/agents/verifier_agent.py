"""
S7: 原文溯源校验智能体 —— LangGraph Node
================================================
职责：引用完整性校验 + 前提—原文 Jaccard 贴合度比对
权威闸门：引用的文献编号必须真实存在于 refs，零虚构
"""
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import PipelineState, GroundingResultData, GroundingItem
from app.agents.base_agent import _log_stage, _emit_progress
from app.utils.logger import get_logger

logger = get_logger("GroundingVerifier")


def _jaccard_similarity(a: str, b: str) -> float:
    """字符级 Jaccard 相似度"""
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


async def s7_node(state: PipelineState) -> dict:
    """S7: 原文溯源校验"""
    topic = state["topic"]
    refs = state.get("refs", {})
    hypothesis = state.get("hypothesis")
    round_num = state.get("round", 1)

    if not hypothesis:
        _log_stage("S7", "无假设，跳过溯源", "warn")
        return {
            "grounding_result": GroundingResultData(),
            "gates": {**state.get("gates", {}), "grounding": True},
            "progress": _emit_progress(state, "S7", "溯源校验（跳过）", "done"),
        }

    _log_stage("S7", f"第{round_num}轮溯源校验")

    valid_ref_ids = set(refs.keys())
    hypo_refs = set(hypothesis.refs)

    # 1. 引用完整性（权威闸门）
    dangling = hypo_refs - valid_ref_ids
    total_refs = len(hypo_refs)

    # 2. 前提—原文贴合度（辅助信号）
    detail = []
    # 逐条前提与绑定文献的要点比对
    premises = []
    if hypothesis.idea:
        premises.append(("解决思路", hypothesis.idea))
    if hypothesis.methodology:
        premises.append(("方法论", hypothesis.methodology))
    if hypothesis.problem:
        premises.append(("问题", hypothesis.problem))

    for kind, text in premises:
        for ref_id in hypo_refs & valid_ref_ids:
            ref = refs[ref_id]
            if hasattr(ref, "model_dump"):
                ref = ref.model_dump()
            ref_text = ref.get("description", "") or ref.get("title", "")
            score = _jaccard_similarity(text[:200], ref_text[:200])
            status = "ok" if score >= 0.05 else "weak"
            detail.append(GroundingItem(
                text=text[:100],
                ref=ref_id,
                score=round(score, 4),
                status=status,
                kind=kind,
            ))

    sampled = len(detail)
    weak_count = sum(1 for d in detail if d.status == "weak")
    ok_count = sampled - weak_count

    # 闸门：引用完整性必须通过（零虚构）
    # 贴合度仅作辅助信号，不作为硬闸门
    passed = len(dangling) == 0

    _log_stage("S7", f"引用完整性: {len(dangling)}个虚构, "
               f"贴合度: {ok_count}ok/{weak_count}weak, gate={passed}")

    result = GroundingResultData(
        total_refs=total_refs,
        dangling_refs=list(dangling),
        sampled=sampled,
        weak_count=weak_count,
        ok_count=ok_count,
        passed=passed,
        detail=detail,
    )

    return {
        "grounding_result": result,
        "gates": {**state.get("gates", {}), "grounding": passed},
        "progress": _emit_progress(state, "S7", f"溯源校验(第{round_num}轮)", "done"),
    }
