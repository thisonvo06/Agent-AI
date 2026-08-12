"""
LLM 调用服务 —— 基于 langchain_openai.ChatOpenAI
----------------------------------------------------------------
所有智能体的语义理解、推理、文本生成均通过此服务调用千问。
百炼平台使用 OpenAI 兼容模式，ChatOpenAI 直接适配。
LangChain 1.x 架构：支持 LCEL 链、with_structured_output、with_fallbacks
"""
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("LLMService")
settings = get_settings()


class LLMService:
    """千问大模型调用服务（LangChain ChatOpenAI 封装）"""

    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.base_url = settings.dashscope_base_url

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def get_llm(
        self,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1600,
    ) -> ChatOpenAI:
        """
        获取 ChatOpenAI 实例
        百炼平台 OpenAI 兼容模式直接适配
        """
        return ChatOpenAI(
            model=model or settings.qwen_model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )

    def get_strong_llm(
        self, temperature: float = 0.6, max_tokens: int = 2000
    ) -> ChatOpenAI:
        """高难度推理用 qwen-max（假设生成、辩论）"""
        return self.get_llm(
            model=settings.qwen_model_strong,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def get_fast_llm(
        self, temperature: float = 0.3, max_tokens: int = 800
    ) -> ChatOpenAI:
        """轻量任务用 qwen-turbo（分类、摘要）"""
        return self.get_llm(
            model=settings.qwen_model_fast,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1600,
    ) -> str:
        """
        调用千问 chat completion（LCEL 链）
        返回模型生成的文本
        """
        if not self.enabled:
            logger.warning("未配置 DASHSCOPE_API_KEY，返回空字符串（离线模式）")
            return ""

        llm = self.get_llm(model, temperature, max_tokens)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | llm | StrOutputParser()

        try:
            result = await chain.ainvoke({"input": user_prompt})
            logger.debug(f"千问返回 {len(result)} 字符")
            return result.strip()
        except Exception as e:
            logger.error(f"千问调用失败: {e}")
            return ""

    async def chat_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema,  # Pydantic BaseModel class
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        """
        调用千问并返回结构化 Pydantic 对象
        使用 LangChain with_structured_output() 强制 JSON Schema
        """
        if not self.enabled:
            logger.warning("未配置 API Key，返回 None（离线模式）")
            return None

        llm = self.get_llm(model, temperature, max_tokens)
        structured_llm = llm.with_structured_output(output_schema)
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        chain = prompt | structured_llm

        try:
            result = await chain.ainvoke({"input": user_prompt})
            logger.info(f"千问返回结构化对象 [{output_schema.__name__}]")
            return result
        except Exception as e:
            logger.error(f"千问结构化输出失败: {e}")
            return None

    async def test_connection(self) -> dict:
        """连通性测试"""
        import time
        t0 = time.time()
        try:
            out = await self.chat(
                "你是连通性测试助手。",
                "请只回复两个字：正常。",
                temperature=0,
                max_tokens=16,
            )
            ms = round((time.time() - t0) * 1000)
            return {"ok": True, "ms": ms, "output": out}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def build_evidence_context(self, refs: dict) -> str:
        """把证据库打包成给模型的上下文（防止模型自由发挥引用）"""
        lines = []
        for ref_id, ref in refs.items():
            if hasattr(ref, "model_dump"):
                ref = ref.model_dump()
            lines.append(
                f"[{ref_id}] {ref.get('authors', '')} 《{ref.get('title', '')}》 "
                f"{ref.get('venue', '')}, {ref.get('year', '')}。"
                f"要点：{ref.get('description', '')}"
            )
        return (
            "【可引用文献清单（只能引用这些，不得新增）】\n"
            + "\n".join(lines)
        )


# 单例
llm_service = LLMService()
