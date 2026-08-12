"""
FastAPI 应用入口 —— LangChain 1.x / LangGraph 1.x 架构
启动：uvicorn main:app --reload --port 8000
"""
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 加载 .env
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import json
import shutil
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import nest_asyncio

nest_asyncio.apply()

from app.core.config import get_settings, LITERATURE_DIR, OUTPUTS_DIR
from app.core.orchestrator import pipeline_graph, execute_pipeline
from app.services.llm_service import llm_service
from app.services.pdf_parser import pdf_parser
from app.services.vector_service import vector_service
from app.models.schemas import Topic, Reference, ResearchPlan
from app.utils.logger import get_logger

logger = get_logger("Main")
settings = get_settings()

app = FastAPI(
    title="AI Scientist API",
    description="基于国产开源大模型 Qwen 的 AI Scientist 系统（LangChain 1.x / LangGraph 1.x）",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 健康检查 & 连通性测试
# ============================================================

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": settings.qwen_model,
        "framework": "LangChain 1.x + LangGraph 1.x",
    }


@app.post("/api/llm/test")
async def test_llm():
    """千问连通性测试"""
    result = await llm_service.test_connection()
    return result


# ============================================================
# 文献管理
# ============================================================

@app.post("/api/literature/upload")
async def upload_literature(file: UploadFile = File(...)):
    """上传 PDF/文本文献"""
    if not file.filename:
        raise HTTPException(400, "文件名为空")

    file_path = LITERATURE_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if file.filename.lower().endswith(".pdf"):
        parsed = pdf_parser.parse(str(file_path))
    else:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        parsed = pdf_parser.parse_text(content)

    return {
        "filename": file.filename,
        "metadata": parsed["metadata"],
        "paragraphs": len(parsed["paragraphs"]),
        "full_text_length": len(parsed["full_text"]),
    }


@app.post("/api/literature/parse")
async def parse_literature(
    ref_id: str = Form(...),
    file: UploadFile = File(...),
):
    """解析文献并构建向量索引"""
    file_path = LITERATURE_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if file.filename.lower().endswith(".pdf"):
        parsed = pdf_parser.parse(str(file_path))
    else:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        parsed = pdf_parser.parse_text(content)

    count = await vector_service.insert_literature(ref_id, parsed["paragraphs"])

    return {
        "ref_id": ref_id,
        "metadata": parsed["metadata"],
        "paragraphs_indexed": count,
    }


# ============================================================
# 假设生成（完整流水线）—— LangGraph ainvoke
# ============================================================

class RunRequest(BaseModel):
    """流水线运行请求"""
    topic: dict
    refs: dict
    max_iter: int = 2
    con_threshold: int = 3


@app.post("/api/hypothesis/generate")
async def generate_hypothesis(req: RunRequest):
    """
    输入问题+文献，执行完整 11 阶段流水线
    使用 LangGraph StateGraph ainvoke 执行
    """
    topic = Topic(**req.topic)
    refs = {k: Reference(**v) for k, v in req.refs.items()}

    logger.info(f"收到流水线请求: 议题={topic.title}")

    # 使用 LangGraph 执行
    final_state = await execute_pipeline(
        topic=topic,
        refs=refs,
        seed=42,
    )

    # 序列化结果
    gates = final_state.get("gates", {})
    report = final_state.get("report", {})
    self_score = final_state.get("self_score", {})
    progress = final_state.get("progress", [])
    hypothesis = final_state.get("hypothesis")
    debate = final_state.get("debate_result")
    grounding = final_state.get("grounding_result")
    causal = final_state.get("causal_result")

    return {
        "run_id": f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "round": final_state.get("round", 1),
        "gates": gates,
        "research_plan": report,
        "self_score": self_score,
        "progress": progress,
        "hypothesis": hypothesis.model_dump() if hypothesis else None,
        "debate_result": debate.model_dump() if debate else None,
        "grounding_result": grounding.model_dump() if grounding else None,
        "causal_result": causal.model_dump() if causal else None,
    }


# ============================================================
# SSE 流式流水线 —— LangGraph astream_events
# ============================================================

@app.post("/api/hypothesis/generate/stream")
async def generate_hypothesis_stream(req: RunRequest):
    """
    SSE 流式执行流水线，逐阶段推送进度
    使用 LangGraph astream_events() 事件流
    """
    topic = Topic(**req.topic)
    refs = {k: Reference(**v) for k, v in req.refs.items()}

    logger.info(f"收到流式流水线请求: 议题={topic.title}")

    initial_state = {
        "topic": topic,
        "refs": refs,
        "max_iter": req.max_iter,
        "con_threshold": req.con_threshold,
        "seed": 42,
        "round": 1,
        "scope_limits": [],
        "gates": {},
        "progress": [],
    }

    config = {
        "configurable": {
            "thread_id": f"stream-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }
    }

    async def event_stream():
        """SSE 事件流生成器"""
        try:
            # 使用 LangGraph astream 逐节点输出
            async for event in pipeline_graph.astream(
                initial_state, config=config, stream_mode="updates"
            ):
                # event 是 (node_name, update_dict) 元组
                node_name, update = event if isinstance(event, tuple) else (None, event)

                # 推送阶段进度
                if update and "progress" in update:
                    for p in update["progress"]:
                        yield f"data: {json.dumps(p, ensure_ascii=False)}\n\n"

                # 推送闸门状态
                if update and "gates" in update:
                    gates_data = {
                        "stage": node_name or "unknown",
                        "type": "gates",
                        "gates": update["gates"],
                    }
                    yield f"data: {json.dumps(gates_data, ensure_ascii=False)}\n\n"

            # 最终结果
            final_state = await pipeline_graph.aget_state(config)
            final_data = {
                "type": "final",
                "round": final_state.values.get("round", 1),
                "gates": final_state.values.get("gates", {}),
                "report": final_state.values.get("report", {}),
                "self_score": final_state.values.get("self_score", {}),
            }
            yield f"data: {json.dumps(final_data, ensure_ascii=False, default=str)}\n\n"

        except Exception as e:
            logger.error(f"流式执行失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 辩论 & 因果检验（单独调用）
# ============================================================

@app.post("/api/debate/run")
async def run_debate(
    hypothesis: dict,
    refs: dict,
    round: int = 1,
    con_threshold: int = 3,
):
    """单独启动辩论验证"""
    from app.models.schemas import HypothesisData
    from app.agents.debate_agent import s6_node

    h = HypothesisData(**hypothesis)
    refs_obj = {k: Reference(**v) for k, v in refs.items()}
    topic = Topic(id=0, code="", title="", summary="")

    state = {
        "topic": topic,
        "refs": refs_obj,
        "hypothesis": h,
        "round": round,
        "con_threshold": con_threshold,
        "gates": {},
        "progress": [],
    }

    result = await s6_node(state)
    return result["debate_result"].model_dump()


@app.post("/api/hypothesis/causal-test")
async def causal_test(spec: dict, round: int = 1, seed: int = 42):
    """对假设进行统计因果检验"""
    from app.services.statistics_service import statistics_service
    result = statistics_service.run_causal_check(spec, seed=seed + round)
    return result


# ============================================================
# 向量检索
# ============================================================

@app.get("/api/vector/search")
async def vector_search(query: str, top_k: int = 5):
    """语义检索文献段落"""
    results = await vector_service.search(query, top_k=top_k)
    return {"query": query, "hits": results}


# ============================================================
# 流水线阶段信息
# ============================================================

# 11 阶段定义（对齐前端 pipeline.js）
STAGES = [
    {"id": "S1_S2", "name": "问题理解+文献挖掘", "agent": "LiteratureMiner"},
    {"id": "S3_S4", "name": "知识整合+跨域关联", "agent": "KnowledgeSynthesizer"},
    {"id": "S5",    "name": "假设生成",          "agent": "HypothesisGenerator"},
    {"id": "S6",    "name": "辩论对抗",          "agent": "DebateAgent"},
    {"id": "S7",    "name": "原文溯源校验",      "agent": "GroundingVerifier"},
    {"id": "S8",    "name": "因果量化检验",      "agent": "CausalTester"},
    {"id": "S9",    "name": "人在回路",          "agent": "HumanInLoop"},
    {"id": "S10",   "name": "研究计划输出",      "agent": "PlanReporter"},
    {"id": "S11",   "name": "评分自检",          "agent": "RubricChecker"},
]


@app.get("/api/pipeline/stages")
async def get_stages():
    """获取流水线阶段定义"""
    return {"stages": STAGES, "framework": "LangGraph 1.x"}


@app.get("/api/pipeline/graph")
async def get_graph_info():
    """获取 LangGraph 图结构信息"""
    return {
        "nodes": [s["id"] for s in STAGES],
        "edges": [
            {"from": "START", "to": "S1_S2"},
            {"from": "S1_S2", "to": "S3_S4"},
            {"from": "S3_S4", "to": "S5"},
            {"from": "S5", "to": "S6"},
            {"from": "S6", "to": "S7"},
            {"from": "S7", "to": "S8"},
            {"from": "S8", "to": "S9", "condition": "gates_passed"},
            {"from": "S8", "to": "S5", "condition": "gates_failed_and_round<max"},
            {"from": "S9", "to": "S10"},
            {"from": "S10", "to": "S11"},
            {"from": "S11", "to": "END"},
        ],
        "checkpointer": "MemorySaver",
    }


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
