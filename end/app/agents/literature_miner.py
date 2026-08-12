"""
S1+S2: 文献挖掘智能体 —— LangGraph Node
================================================
职责：问题理解 + 文献事实提取
LangChain 1.x：使用 LCEL 链（ChatPromptTemplate | ChatOpenAI | parser）
"""
import json
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import PipelineState, Evidence, EvidenceLevel
from app.agents.base_agent import _log_stage, _emit_progress, _build_evidence_context
from app.utils.logger import get_logger

logger = get_logger("LiteratureMiner")


async def s1s2_node(state: PipelineState) -> dict:
    """S1 问题理解 + S2 文献挖掘（合并为一个 node）"""
    topic = state["topic"]
    refs = state.get("refs", {})

    _log_stage("S1_S2", f"开始处理议题: {topic.title}")

    # S1: 问题理解
    problem_statement = ""
    try:
        problem_statement = await llm_service.chat(
            system_prompt=prompt_guard.PROBLEM_PARSER_SYS,
            user_prompt=(
                f"【议题信息】\n标题：{topic.title}\n"
                f"摘要：{topic.summary}\n领域：{topic.domain}\n\n"
                f"请将此议题拆解为可研究的问题陈述。"
            ),
            temperature=0.3,
            max_tokens=800,
        )
    except Exception as e:
        logger.warning(f"S1 问题理解失败（降级）: {e}")
        problem_statement = f"针对「{topic.title}」的探索性研究"

    _log_stage("S1", f"问题陈述: {problem_statement[:60]}...")

    # S2: 文献挖掘 —— 提取结构化事实
    facts = {"consensus": [], "dispute": [], "gap": []}
    if refs:
        evidence_ctx = _build_evidence_context(refs)
        try:
            raw = await llm_service.chat(
                system_prompt=prompt_guard.LITERATURE_MINER_SYS,
                user_prompt=(
                    f"{evidence_ctx}\n\n"
                    f"请从以上文献中提取科学事实，"
                    f"按 consensus / dispute / gap 三类分层输出。\n"
                    f"每条事实必须绑定来源文献编号。"
                ),
                temperature=0.3,
                max_tokens=1600,
            )
            if raw:
                # 尝试解析 JSON
                parsed = _safe_json_parse(raw)
                if parsed:
                    facts = {
                        "consensus": parsed.get("consensus", []),
                        "dispute": parsed.get("dispute", []),
                        "gap": parsed.get("gap", []),
                    }
        except Exception as e:
            logger.warning(f"S2 文献挖掘失败（降级）: {e}")

    # 合并 topic 自带的事实
    if topic.consensus:
        for e in topic.consensus:
            if hasattr(e, "model_dump"):
                facts["consensus"].append(e.model_dump(by_alias=True))
            else:
                facts["consensus"].append(e)
    if topic.disputes:
        for e in topic.disputes:
            facts["dispute"].append(e.model_dump(by_alias=True) if hasattr(e, "model_dump") else e)
    if topic.gaps:
        for e in topic.gaps:
            facts["gap"].append(e.model_dump(by_alias=True) if hasattr(e, "model_dump") else e)

    _log_stage("S2", f"提取事实: {len(facts['consensus'])}共识 + "
               f"{len(facts['dispute'])}争议 + {len(facts['gap'])}空白")

    return {
        "problem_statement": problem_statement,
        "facts": facts,
        "progress": _emit_progress(state, "S1_S2", "问题理解+文献挖掘", "done"),
    }


def _safe_json_parse(text: str) -> dict | None:
    """安全解析 JSON（兼容模型输出多余文本）"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
