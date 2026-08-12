"""
Pydantic 数据结构 —— 贯穿 11 阶段流水线的类型定义
对齐前端 pipeline.js 的数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum
from datetime import datetime


# ============================================================
# 枚举
# ============================================================

class EvidenceLevel(str, Enum):
    """证据强度分层"""
    CONSENSUS = "consensus"   # 已验证共识
    DISPUTE = "dispute"       # 存在争议
    GAP = "gap"               # 研究空白


class GateStatus(str, Enum):
    """闸门状态"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class StageState(str, Enum):
    """阶段执行状态"""
    IDLE = "idle"
    RUNNING = "run"
    DONE = "done"
    WARN = "warn"
    ERROR = "error"


class HypothesisStatus(str, Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    FINAL = "final"
    REJECTED = "rejected"


class CausalLevel(str, Enum):
    OK = "ok"
    WARN = "warn"
    BAD = "bad"


# ============================================================
# 文献引用
# ============================================================

class Reference(BaseModel):
    """文献引用条目（对应前端 REFS[id]）"""
    ref_id: str = Field(..., description="文献编号，如 R12")
    title: str
    authors: str
    venue: str
    year: int
    description: str = Field("", description="要点摘要")


# ============================================================
# 证据条目
# ============================================================

class Evidence(BaseModel):
    """科学事实条目（共识/争议/空白）"""
    text: str = Field(..., alias="t", description="事实陈述")
    refs: list[str] = Field(default_factory=list, description="引用文献编号列表")
    level: EvidenceLevel = EvidenceLevel.CONSENSUS

    class Config:
        populate_by_name = True


# ============================================================
# 辩论
# ============================================================

class DebateArgument(BaseModel):
    """辩论论据"""
    text: str = Field(..., alias="t", description="论点")
    refs: list[str] = Field(default_factory=list)
    resolved: bool = False  # 反方论据是否已被消解

    class Config:
        populate_by_name = True


class DebateResult(BaseModel):
    """一轮辩论的完整结果"""
    round: int
    pro_arguments: list[DebateArgument] = Field(default_factory=list)
    con_arguments: list[DebateArgument] = Field(default_factory=list)
    judge_verdict: str = ""
    is_biased: bool = False
    con_active_count: int = 0
    scope_limit: str | None = None  # 若判定片面，生成的范围收窄指令


# ============================================================
# 溯源校验
# ============================================================

class GroundingItem(BaseModel):
    """单条前提—原文比对结果"""
    text: str
    ref: str
    score: float = Field(..., description="Jaccard 重合度")
    status: str = Field(..., description="ok / weak")
    kind: str = Field(..., description="共识/争议/空白前提")
    rewritten: bool = False


class GroundingResultData(BaseModel):
    """溯源校验结果"""
    total_refs: int = 0
    dangling_refs: list[str] = Field(default_factory=list)
    sampled: int = 0
    weak_count: int = 0
    ok_count: int = 0
    passed: bool = False
    detail: list[GroundingItem] = Field(default_factory=list)


# ============================================================
# 因果量化检验
# ============================================================

class CausalSpec(BaseModel):
    """因果检验参数"""
    label: str
    var_x: str
    var_y: str
    group_name: str
    group_a: str
    group_b: str
    sample_n: int
    note: str = ""


class CorrelationResult(BaseModel):
    """相关性检验结果"""
    r: float
    t: float
    p: float
    df: int
    n: int


class GroupTestResult(BaseModel):
    """分组检验结果"""
    t: float
    p: float
    d: float  # Cohen's d


class CausalResultData(BaseModel):
    """因果检验完整结果"""
    label: str
    corr: CorrelationResult
    grp: GroupTestResult
    level: CausalLevel
    verdict: str
    advice: str
    passed: bool


# ============================================================
# 假设（对应 10 字段输出规范）
# ============================================================

class HypothesisData(BaseModel):
    """科学假设数据（含 10 个标准化字段）"""
    title: str
    problem: str = Field("", description="待研究问题")
    idea: str = Field("", description="解决思路")
    tech: str = Field("", description="技术手段")
    dataset_source: str = Field("", description="Source 数据集")
    dataset_target: str = Field("", description="Target 数据集")
    abstract: str = ""
    methodology: str = ""
    experiment: str = ""
    results: str = ""
    refs: list[str] = Field(default_factory=list)
    scope_limit: str = ""


# ============================================================
# 跨域关联
# ============================================================

class CrossLink(BaseModel):
    """跨学科迁移线索"""
    source_domain: str = Field(..., alias="from")
    target_domain: str = Field(..., alias="to")
    insight: str = ""

    class Config:
        populate_by_name = True


# ============================================================
# 议题（流水线输入）
# ============================================================

class Topic(BaseModel):
    """研究议题 —— 流水线的完整输入"""
    id: int
    code: str
    title: str
    summary: str
    domain: str = "人工智能"
    barriers: list[dict] = Field(default_factory=list, description="技术瓶颈")
    consensus: list[Evidence] = Field(default_factory=list)
    disputes: list[Evidence] = Field(default_factory=list)
    gaps: list[Evidence] = Field(default_factory=list)
    cross_link: CrossLink | None = None
    hypothesis: HypothesisData | None = None
    debate: DebateResult | None = None
    causal: CausalSpec | None = None


# ============================================================
# 流水线运行上下文
# ============================================================

class StageLog(BaseModel):
    """阶段日志条目"""
    type: str  # key/dim/ok/warn/err
    text: str


class StageBlock(BaseModel):
    """阶段输出块（前端渲染用）"""
    type: str  # h/p/kvlist/facts/flow/hypo/evi/verdict/ground/stat/checklist/score/note
    data: Any = None


class StageStatus(BaseModel):
    """单个阶段的状态"""
    id: str
    name: str
    agent: str
    sub: str
    state: StageState = StageState.IDLE
    logs: list[StageLog] = Field(default_factory=list)
    blocks: list[StageBlock] = Field(default_factory=list)


class GateStates(BaseModel):
    """三重闸门状态"""
    debate: bool | None = None
    grounding: bool | None = None
    causal: bool | None = None


class RunContext(BaseModel):
    """流水线运行上下文（对应前端 Run 类）"""
    topic: Topic
    max_iter: int = 2
    con_threshold: int = 3
    seed: int = 0
    round: int = 1
    scope_limits: list[str] = Field(default_factory=list)
    gates: GateStates = Field(default_factory=GateStates)
    stages: dict[str, StageStatus] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    # 最终输出
    report: dict | None = None
    self_score: dict | None = None
    grounding_detail: GroundingResultData | None = None
    causal_result: CausalResultData | None = None


# ============================================================
# 研究计划最终输出（10 字段）
# ============================================================

class ResearchPlan(BaseModel):
    """《科学假设与研究计划》标准化输出"""
    # 1. 待研究问题
    problem_statement: str
    # 2. 解决思路
    rationale: str
    # 3. 技术手段
    technical_details: str
    # 4. 数据集
    dataset_source: str
    dataset_target: str
    # 5. 标题
    paper_title: str
    # 6. 摘要
    paper_abstract: str
    # 7. 方法论
    methods: str
    # 8. 实验设计
    experiments: str
    # 9. 实验结果
    results: str
    # 10. 参考论文
    references: list[str] = Field(default_factory=list)
    # 元数据
    scope: str = ""
    round: int = 1
    gates: GateStates = Field(default_factory=GateStates)
    validation: dict | None = None
    generated_at: str = ""


# ============================================================
# LangGraph 状态定义 —— StateGraph 的 state schema
# ============================================================

from typing import TypedDict, Annotated
from operator import add as _add


class PipelineState(TypedDict, total=False):
    """
    LangGraph StateGraph 的全局状态
    每个 node 函数接收 state → 返回 dict 片段更新 state
    """
    # 输入
    topic: Topic
    refs: dict                           # {ref_id: Reference}
    max_iter: int
    con_threshold: int
    seed: int
    # 迭代控制
    round: int
    scope_limits: Annotated[list[str], _add]  # 累加模式
    gates: dict                          # {debate, grounding, causal}
    # 阶段输出
    problem_statement: str
    facts: dict                          # {consensus, dispute, gap}
    hypothesis: HypothesisData
    debate_result: DebateResult
    grounding_result: GroundingResultData
    causal_result: CausalResultData
    human_passed: bool
    # 最终输出
    report: dict
    self_score: dict
    progress: Annotated[list[dict], _add]  # 累加模式：阶段进度
