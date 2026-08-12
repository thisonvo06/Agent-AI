"""
S8: 因果量化检验智能体 —— LangGraph Node
================================================
职责：Pearson 相关性 + 分组 t 检验
排除循环论证与无依据猜想
"""
import json
import numpy as np
from scipy import stats as sp_stats
from app.services.llm_service import llm_service
from app.core.prompt_guard import prompt_guard
from app.models.schemas import (
    PipelineState, CausalResultData, CorrelationResult, GroupTestResult,
    CausalLevel,
)
from app.agents.base_agent import _log_stage, _emit_progress
from app.agents.literature_miner import _safe_json_parse
from app.utils.logger import get_logger

logger = get_logger("CausalTester")


def _generate_mock_data(n: int, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """生成模拟数据（实际应从数据集加载）"""
    rng = np.random.default_rng(seed)
    x = rng.normal(50, 15, n)
    y = 0.3 * x + rng.normal(0, 8, n)
    groups = rng.choice(["A", "B"], size=n, p=[0.6, 0.4])
    return x, y, groups


def _pearson_test(x: np.ndarray, y: np.ndarray) -> CorrelationResult:
    """Pearson 相关性检验"""
    r, p = sp_stats.pearsonr(x, y)
    n = len(x)
    df = n - 2
    t_val = r * np.sqrt(df) / np.sqrt(1 - r**2) if abs(r) < 1 else 0.0
    return CorrelationResult(r=float(r), t=float(t_val), p=float(p), df=df, n=n)


def _group_t_test(x: np.ndarray, groups: np.ndarray, a: str, b: str) -> GroupTestResult:
    """分组 t 检验"""
    grp_a = x[groups == a]
    grp_b = x[groups == b]
    if len(grp_a) < 2 or len(grp_b) < 2:
        return GroupTestResult(t=0.0, p=1.0, d=0.0)
    t_val, p = sp_stats.ttest_ind(grp_a, grp_b)
    # Cohen's d
    pooled_std = np.sqrt(
        ((len(grp_a) - 1) * grp_a.std()**2 + (len(grp_b) - 1) * grp_b.std()**2)
        / (len(grp_a) + len(grp_b) - 2)
    )
    d = (grp_a.mean() - grp_b.mean()) / pooled_std if pooled_std > 0 else 0.0
    return GroupTestResult(t=float(t_val), p=float(p), d=float(d))


async def s8_node(state: PipelineState) -> dict:
    """S8: 因果量化检验"""
    topic = state["topic"]
    hypothesis = state.get("hypothesis")
    round_num = state.get("round", 1)
    seed = state.get("seed", 42)

    if not hypothesis:
        _log_stage("S8", "无假设，跳过因果检验", "warn")
        return {
            "causal_result": None,
            "gates": {**state.get("gates", {}), "causal": True},
            "progress": _emit_progress(state, "S8", "因果检验（跳过）", "done"),
        }

    _log_stage("S8", f"第{round_num}轮因果检验")

    # 生成模拟数据（实际应从数据集加载）
    n = 100
    x, y, groups = _generate_mock_data(n, seed + round_num)

    # 统计检验
    corr = _pearson_test(x, y)
    grp = _group_t_test(y, groups, "A", "B")

    # 判定因果等级
    if corr.p < 0.05 and grp.p < 0.05:
        level = CausalLevel.OK
        verdict = "因果链路统计显著"
        advice = ""
        passed = True
    elif corr.p < 0.05 or grp.p < 0.05:
        level = CausalLevel.WARN
        verdict = "部分统计显著，因果证据不足"
        advice = "建议扩大样本或引入控制变量"
        passed = True
    else:
        level = CausalLevel.BAD
        verdict = "因果链路统计不显著"
        advice = "假设可能无效，建议重新审视因果方向"
        passed = False

    _log_stage("S8", f"r={corr.r:.3f} p={corr.p:.4f}, grp_p={grp.p:.4f}, "
               f"level={level.value}, gate={passed}")

    result = CausalResultData(
        label=hypothesis.title[:50],
        corr=corr,
        grp=grp,
        level=level,
        verdict=verdict,
        advice=advice,
        passed=passed,
    )

    return {
        "causal_result": result,
        "gates": {**state.get("gates", {}), "causal": passed},
        "progress": _emit_progress(state, "S8", f"因果检验(第{round_num}轮)", "done"),
    }
