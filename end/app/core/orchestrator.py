"""
主控编排器 —— LangGraph StateGraph
================================================================
LangChain 1.x / LangGraph 1.x 架构
将原自研 while 循环改为声明式 StateGraph：

  START → S1_S2 → S3_S4 → S5 → S6 → S7 → S8
                                         │
                                   条件边：三重闸门
                                   ├─ 全通过 或 达最大轮次 → S9 → S10 → S11 → END
                                   └─ 有闸门未通过 & 轮次未满 → 回 S5
"""
import json
from datetime import datetime
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from app.models.schemas import (
    PipelineState, ResearchPlan, GateStates,
)
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.core.config import get_settings
from app.agents.literature_miner import s1s2_node
from app.agents.hypothesis_generator import s5_node
from app.agents.debate_agent import s6_node
from app.agents.verifier_agent import s7_node
from app.agents.causal_tester import s8_node
from app.agents.base_agent import _log_stage, _emit_progress
from app.utils.logger import get_logger

logger = get_logger("Orchestrator")
settings = get_settings()


# ============================================================
# S3+S4: 知识整合 + 跨域关联（轻量 node）
# ============================================================

async def s3s4_node(state: PipelineState) -> dict:
    """S3 知识整合 + S4 跨域关联发现"""
    topic = state["topic"]
    facts = state.get("facts", {"consensus": [], "dispute": [], "gap": []})

    _log_stage("S3_S4", "知识整合 + 跨域关联")

    # S3: 知识整合（用千问总结证据图谱格局）
    synthesis = ""
    try:
        consensus_text = "\n".join(
            f"- {c.get('t', c) if isinstance(c, dict) else c}"
            for c in facts.get("consensus", [])
        )
        dispute_text = "\n".join(
            f"- {d.get('t', d) if isinstance(d, dict) else d}"
            for d in facts.get("dispute", [])
        )
        gap_text = "\n".join(
            f"- {g.get('t', g) if isinstance(g, dict) else g}"
            for g in facts.get("gap", [])
        )

        synthesis = await llm_service.chat(
            system_prompt=prompt_guard.KNOWLEDGE_SYNTHESIZER_SYS,
            user_prompt=(
                f"【已提取事实】\n"
                f"共识({len(facts.get('consensus', []))}条)：\n{consensus_text}\n"
                f"争议({len(facts.get('dispute', []))}条)：\n{dispute_text}\n"
                f"空白({len(facts.get('gap', []))}条)：\n{gap_text}\n\n"
                f"请构建证据图谱并指出假设生成方向。"
            ),
            temperature=0.4,
            max_tokens=800,
        )
    except Exception as e:
        logger.warning(f"S3 知识整合失败: {e}")
        synthesis = f"共识{len(facts.get('consensus', []))}条 + " \
                    f"争议{len(facts.get('dispute', []))}条 + " \
                    f"空白{len(facts.get('gap', []))}条"

    _log_stage("S3", f"知识整合完成: {synthesis[:60]}...")

    # S4: 跨域关联（用千问寻找跨学科迁移路径）
    cross_link = ""
    try:
        barriers = "；".join(
            b.get("text", str(b)) if isinstance(b, dict) else str(b)
            for b in topic.barriers
        ) if topic.barriers else "暂无明确瓶颈描述"

        cross_link = await llm_service.chat(
            system_prompt=prompt_guard.LINK_DISCOVERER_SYS,
            user_prompt=(
                f"【研究问题】{topic.title}\n"
                f"【本领域瓶颈】{barriers}\n\n"
                f"请寻找结构同构的跨学科迁移路径。"
            ),
            temperature=0.5,
            max_tokens=600,
        )
    except Exception as e:
        logger.warning(f"S4 跨域关联失败: {e}")
        cross_link = ""

    _log_stage("S4", f"跨域关联: {cross_link[:60]}..." if cross_link else "S4 跳过")

    return {
        "progress": _emit_progress(state, "S3_S4", "知识整合+跨域关联", "done"),
    }


# ============================================================
# S9: 人在回路（占位 node，实际由前端交互）
# ============================================================

async def s9_node(state: PipelineState) -> dict:
    """S9: 人在回路确认（当前自动通过，可扩展为中断等待人工反馈）"""
    _log_stage("S9", "人在回路确认（自动通过）")
    return {
        "human_passed": True,
        "progress": _emit_progress(state, "S9", "人在回路", "done"),
    }


# ============================================================
# S10: 研究计划输出
# ============================================================

async def s10_node(state: PipelineState) -> dict:
    """S10: 汇编《科学假设与研究计划》10 字段"""
    hypothesis = state.get("hypothesis")
    debate = state.get("debate_result")
    causal = state.get("causal_result")
    round_num = state.get("round", 1)
    gates = state.get("gates", {})

    _log_stage("S10", "汇编研究计划")

    report = {}
    if hypothesis:
        # 尝试用千问汇编完整计划
        try:
            hypo_json = hypothesis.model_dump_json(indent=2)
            debate_summary = ""
            if debate:
                debate_summary = (
                    f"正方{len(debate.pro_arguments)}论据, "
                    f"反方{len(debate.con_arguments)}论据, "
                    f"裁定: {debate.judge_verdict[:100]}"
                )
            causal_summary = ""
            if causal:
                causal_summary = f"{causal.verdict} (r={causal.corr.r:.3f})"

            raw = await llm_service.chat(
                system_prompt=prompt_guard.PLAN_REPORTER_SYS,
                user_prompt=(
                    f"【假设数据】\n{hypo_json}\n\n"
                    f"【辩论记录】\n{debate_summary}\n\n"
                    f"【因果检验】\n{causal_summary}\n\n"
                    f"请汇编完整的《科学假设与研究计划》。"
                ),
                temperature=0.4,
                max_tokens=2000,
            )
            if raw:
                report = {
                    "problem_statement": hypothesis.problem,
                    "rationale": hypothesis.idea,
                    "technical_details": hypothesis.tech,
                    "dataset_source": hypothesis.dataset_source,
                    "dataset_target": hypothesis.dataset_target,
                    "paper_title": hypothesis.title,
                    "paper_abstract": hypothesis.abstract,
                    "methods": hypothesis.methodology,
                    "experiments": hypothesis.experiment,
                    "results": hypothesis.results,
                    "references": hypothesis.refs,
                    "scope": hypothesis.scope_limit,
                    "round": round_num,
                    "gates": gates,
                    "generated_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.warning(f"S10 千问汇编失败，使用原始数据: {e}")
            report = {
                "problem_statement": hypothesis.problem,
                "rationale": hypothesis.idea,
                "technical_details": hypothesis.tech,
                "dataset_source": hypothesis.dataset_source,
                "dataset_target": hypothesis.dataset_target,
                "paper_title": hypothesis.title,
                "paper_abstract": hypothesis.abstract,
                "methods": hypothesis.methodology,
                "experiments": hypothesis.experiment,
                "results": hypothesis.results,
                "references": hypothesis.refs,
                "scope": hypothesis.scope_limit,
                "round": round_num,
                "gates": gates,
                "generated_at": datetime.now().isoformat(),
            }

    _log_stage("S10", f"研究计划生成完成, {len(report)} 字段")

    return {
        "report": report,
        "progress": _emit_progress(state, "S10", "研究计划输出", "done"),
    }


# ============================================================
# S11: 评分自检
# ============================================================

async def s11_node(state: PipelineState) -> dict:
    """S11: 对照赛题评分标准自评"""
    report = state.get("report", {})

    _log_stage("S11", "评分自检")

    self_score = {}
    try:
        plan_json = json.dumps(report, ensure_ascii=False, indent=2)
        raw = await llm_service.chat(
            system_prompt=prompt_guard.RUBRIC_CHECKER_SYS,
            user_prompt=(
                f"【研究计划】\n{plan_json}\n\n"
                f"请对照赛题评分标准自评并给出改进建议。"
            ),
            temperature=0.3,
            max_tokens=800,
        )
        if raw:
            self_score = {"raw": raw, "dimensions": {
                "science_value": 0,
                "tech_depth": 0,
                "application": 0,
            }}
    except Exception as e:
        logger.warning(f"S11 评分自检失败: {e}")
        self_score = {"error": str(e)}

    _log_stage("S11", "评分自检完成")

    return {
        "self_score": self_score,
        "progress": _emit_progress(state, "S11", "评分自检", "done"),
    }


# ============================================================
# 条件边：三重闸门判定
# ============================================================

def _should_loop_back(state: PipelineState) -> str:
    """
    S8 → 条件边：
    - 三重闸门全通过 → S9
    - 有闸门未通过 & 轮次 < max_iter → S5（回环迭代）
    - 轮次已达上限 → S9（强制通过）
    """
    gates = state.get("gates", {})
    round_num = state.get("round", 1)
    max_iter = state.get("max_iter", settings.max_iterations)

    all_passed = all(gates.get(k, True) for k in ["debate", "grounding", "causal"])

    if all_passed:
        _log_stage("GATE", "三重闸门全通过 → S9")
        return "S9"
    elif round_num < max_iter:
        _log_stage("GATE", f"闸门未通过, 第{round_num}轮 < {max_iter} → 回S5")
        return "S5"
    else:
        _log_stage("GATE", f"轮次已达上限 {max_iter} → 强制S9")
        return "S9"


# ============================================================
# 轮次自增 node（插在 S5 之前）
# ============================================================

def _increment_round(state: PipelineState) -> dict:
    """轮次自增（在回环到 S5 时触发）"""
    current = state.get("round", 1)
    _log_stage("ROUND", f"轮次 {current} → {current + 1}")
    return {"round": current + 1}


# ============================================================
# 构建 StateGraph
# ============================================================

def build_graph():
    """
    构建 LangGraph StateGraph
    返回编译后的 CompiledStateGraph，支持 ainvoke / astream
    """
    builder = StateGraph(PipelineState)

    # 注册节点
    builder.add_node("S1_S2", s1s2_node)
    builder.add_node("S3_S4", s3s4_node)
    builder.add_node("S5", s5_node)
    builder.add_node("S6", s6_node)
    builder.add_node("S7", s7_node)
    builder.add_node("S8", s8_node)
    builder.add_node("S9", s9_node)
    builder.add_node("S10", s10_node)
    builder.add_node("S11", s11_node)

    # 线性边
    builder.add_edge(START, "S1_S2")
    builder.add_edge("S1_S2", "S3_S4")
    builder.add_edge("S3_S4", "S5")
    builder.add_edge("S5", "S6")
    builder.add_edge("S6", "S7")
    builder.add_edge("S7", "S8")

    # 条件边：S8 → S9（通过）或 S5（回环）
    builder.add_conditional_edges("S8", _should_loop_back, {
        "S9": "S9",
        "S5": "S5",
    })

    # S9 → S10 → S11 → END
    builder.add_edge("S9", "S10")
    builder.add_edge("S10", "S11")
    builder.add_edge("S11", END)

    # 编译（带 checkpoint 支持断点续跑）
    graph = builder.compile(checkpointer=MemorySaver())

    logger.info("LangGraph StateGraph 编译完成")
    return graph


# 全局编译图实例
pipeline_graph = build_graph()


# ============================================================
# 对外执行接口（兼容旧 API）
# ============================================================

async def execute_pipeline(
    topic,
    refs: dict,
    on_stage=None,
    seed: int = 0,
) -> dict:
    """
    执行完整流水线
    兼容旧版 orchestrator.execute() 调用方式
    返回最终 state
    """
    import nest_asyncio
    nest_asyncio.apply()

    _log_stage("PIPELINE", f"启动流水线: {topic.title}")

    initial_state: PipelineState = {
        "topic": topic,
        "refs": refs,
        "max_iter": settings.max_iterations,
        "con_threshold": settings.con_threshold,
        "seed": seed,
        "round": 1,
        "scope_limits": [],
        "gates": {},
        "progress": [],
    }

    # 使用 LangGraph ainvoke 执行
    config = {"configurable": {"thread_id": f"run-{seed}-{datetime.now().strftime('%Y%m%d%H%M%S')}"}}

    final_state = await pipeline_graph.ainvoke(initial_state, config=config)

    _log_stage("PIPELINE", "流水线完成")

    # 回调通知
    if on_stage:
        for p in final_state.get("progress", []):
            on_stage(p.get("stage", ""), p.get("name", ""), p.get("status", ""))

    return final_state
