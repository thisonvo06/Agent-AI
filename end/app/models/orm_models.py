"""
SQLAlchemy ORM 模型
对应数据库表结构：文献、假设、辩论记录、研究计划、运行记录
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float,
    Boolean, JSON, ForeignKey, Index,
)
from sqlalchemy.orm import relationship

from app.models.database import Base


class Literature(Base):
    """文献表 —— 存储上传文献的元数据与解析状态"""
    __tablename__ = "literatures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ref_id = Column(String(20), unique=True, nullable=False, comment="文献编号，如 R12")
    title = Column(String(500), nullable=False, comment="标题")
    authors = Column(String(500), comment="作者")
    venue = Column(String(300), comment="期刊/会议")
    year = Column(Integer, comment="发表年份")
    abstract = Column(Text, comment="摘要")
    key_points = Column(Text, comment="要点摘要（千问提取）")
    file_path = Column(String(500), comment="原始文件路径")
    source = Column(String(50), default="upload", comment="来源：upload/manual/api")
    # 向量索引状态
    vector_indexed = Column(Boolean, default=False, comment="是否已向量化入库")
    # 结构化事实（JSON：consensus/disputes/gaps）
    extracted_facts = Column(JSON, comment="千问提取的结构化科学事实")
    created_at = Column(DateTime, default=datetime.utcnow)

    hypotheses = relationship("Hypothesis", back_populates="literature")

    __table_args__ = (
        Index("idx_ref_id", "ref_id"),
        Index("idx_year", "year"),
    )


class Hypothesis(Base):
    """假设表 —— 存储每轮生成的科学假设"""
    __tablename__ = "hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    round = Column(Integer, default=1, comment="迭代轮次")
    title = Column(String(500), nullable=False, comment="假设标题")
    problem = Column(Text, comment="待研究问题")
    idea = Column(Text, comment="解决思路/核心假设表述")
    tech = Column(Text, comment="技术手段")
    dataset_source = Column(Text, comment="Source 数据集")
    dataset_target = Column(Text, comment="Target 数据集")
    abstract = Column(Text, comment="摘要")
    methodology = Column(Text, comment="方法论")
    experiment = Column(Text, comment="实验设计")
    results = Column(Text, comment="实验结果")
    refs = Column(JSON, comment="引用文献编号列表")
    scope_limit = Column(Text, comment="适用范围限定")
    # 三重闸门状态
    gate_debate = Column(Boolean, nullable=True, comment="辩论闸门")
    gate_grounding = Column(Boolean, nullable=True, comment="溯源闸门")
    gate_causal = Column(Boolean, nullable=True, comment="因果闸门")
    status = Column(String(20), default="draft", comment="draft/validating/final/rejected")
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("RunRecord", back_populates="hypotheses")

    __table_args__ = (
        Index("idx_run_id", "run_id"),
    )


class DebateRecord(Base):
    """辩论记录表 —— 存储每轮正反方对抗的完整记录"""
    __tablename__ = "debate_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    round = Column(Integer, nullable=False, comment="辩论轮次")
    # 正方论据 [{t: 论点, refs: [引用编号]}]
    pro_arguments = Column(JSON, comment="正方论据列表")
    # 反方论据 [{t: 论点, refs: [引用编号], resolved: bool}]
    con_arguments = Column(JSON, comment="反方论据列表")
    judge_verdict = Column(Text, comment="裁判裁定")
    is_biased = Column(Boolean, comment="是否判定假设片面")
    con_active_count = Column(Integer, comment="反方有效论据数")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_debate_run", "run_id"),
    )


class GroundingResult(Base):
    """溯源校验结果表"""
    __tablename__ = "grounding_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    round = Column(Integer, nullable=False)
    total_refs = Column(Integer, comment="总引用数")
    dangling_refs = Column(JSON, comment="虚构/缺失引用编号列表")
    weak_count = Column(Integer, comment="贴合度弱的引用数")
    passed = Column(Boolean, comment="是否通过")
    detail = Column(JSON, comment="逐条比对详情")
    created_at = Column(DateTime, default=datetime.utcnow)


class CausalResult(Base):
    """因果量化检验结果表"""
    __tablename__ = "causal_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("run_records.run_id"), nullable=False)
    round = Column(Integer, nullable=False)
    label = Column(String(200), comment="因果链路描述")
    var_x = Column(String(200), comment="自变量")
    var_y = Column(String(200), comment="因变量")
    group_name = Column(String(200), comment="分组因子")
    group_a = Column(String(200), comment="组A")
    group_b = Column(String(200), comment="组B")
    sample_n = Column(Integer, comment="样本量")
    pearson_r = Column(Float, comment="Pearson 相关系数")
    pearson_p = Column(Float, comment="Pearson p 值")
    group_t = Column(Float, comment="分组检验 t 值")
    group_p = Column(Float, comment="分组检验 p 值")
    cohen_d = Column(Float, comment="Cohen's d 效应量")
    level = Column(String(10), comment="ok/warn/bad")
    verdict = Column(Text, comment="检验结论")
    advice = Column(Text, comment="建议")
    passed = Column(Boolean, comment="是否通过")
    created_at = Column(DateTime, default=datetime.utcnow)


class RunRecord(Base):
    """运行记录表 —— 一次完整的流水线执行"""
    __tablename__ = "run_records"

    run_id = Column(String(36), primary_key=True, comment="UUID")
    topic_title = Column(String(500), comment="议题标题")
    topic_code = Column(String(20), comment="议题编号")
    domain = Column(String(50), default="人工智能", comment="研究领域")
    max_iterations = Column(Integer, default=2)
    con_threshold = Column(Integer, default=3)
    total_rounds = Column(Integer, default=0, comment="实际迭代轮次")
    final_status = Column(String(20), default="running", comment="running/success/failed")
    # 最终研究计划（JSON，10字段）
    research_plan = Column(JSON, comment="《科学假设与研究计划》完整输出")
    # 自评分
    self_score = Column(JSON, comment="对照评分标准的自评结果")
    # 闸门最终状态
    gates_final = Column(JSON, comment="{debate, grounding, causal}")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    hypotheses = relationship("Hypothesis", back_populates="run")
    debates = relationship("DebateRecord", backref="run")
    groundings = relationship("GroundingResult", backref="run")
    causals = relationship("CausalResult", backref="run")
