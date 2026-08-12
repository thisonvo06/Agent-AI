"""
向量数据库服务 —— 基于 langchain_milvus.Milvus
负责文献段落的语义存储与检索，支撑原文溯源校验与跨文献关联发现
LangChain 1.x 架构：使用 langchain_milvus 集成
"""
from langchain_milvus import Milvus
from app.core.config import get_settings
from app.utils.embeddings import get_embeddings
from app.utils.logger import get_logger

logger = get_logger("VectorService")
settings = get_settings()


class VectorService:
    """Milvus 向量检索服务（LangChain 集成）"""

    def __init__(self):
        self._vectorstore: Milvus | None = None

    @property
    def vectorstore(self) -> Milvus | None:
        """获取 Milvus 向量库实例（懒加载）"""
        if self._vectorstore is None:
            try:
                self._vectorstore = Milvus(
                    embedding_function=get_embeddings(),
                    connection_args={
                        "host": settings.milvus_host,
                        "port": str(settings.milvus_port),
                    },
                    collection_name=settings.milvus_collection,
                    auto_create_collection=True,
                )
                logger.info(
                    f"Milvus 连接成功 {settings.milvus_host}:{settings.milvus_port}"
                )
            except Exception as e:
                logger.warning(f"Milvus 连接失败（离线降级）: {e}")
                self._vectorstore = None
        return self._vectorstore

    async def insert_literature(
        self,
        ref_id: str,
        paragraphs: list[str],
    ) -> int:
        """将文献段落向量化并插入 Milvus"""
        vs = self.vectorstore
        if not vs or not paragraphs:
            return 0

        try:
            metadatas = [{"ref_id": ref_id, "index": i} for i in range(len(paragraphs))]
            vs.add_texts(texts=paragraphs, metadatas=metadatas)
            logger.info(f"文献 {ref_id} 插入 {len(paragraphs)} 段向量")
            return len(paragraphs)
        except Exception as e:
            logger.error(f"向量化插入失败: {e}")
            return 0

    async def search(
        self,
        query: str,
        top_k: int = 5,
        ref_filter: str | None = None,
    ) -> list[dict]:
        """语义检索文献段落"""
        vs = self.vectorstore
        if not vs:
            return []

        try:
            # langchain_milvus 支持 filter 表达式
            expr = f'ref_id == "{ref_filter}"' if ref_filter else None
            docs = vs.similarity_search_with_score(
                query, k=top_k, filter=expr if expr else None,
            )
            hits = []
            for doc, score in docs:
                hits.append({
                    "ref_id": doc.metadata.get("ref_id", ""),
                    "text": doc.page_content,
                    "score": float(score),
                })
            logger.debug(f"检索 '{query[:30]}...' 命中 {len(hits)} 条")
            return hits
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    def delete_by_ref(self, ref_id: str):
        """删除指定文献的所有向量"""
        vs = self.vectorstore
        if not vs:
            return
        try:
            vs.delete(expr=f'ref_id == "{ref_id}"')
            logger.info(f"删除文献 {ref_id} 的向量")
        except Exception as e:
            logger.warning(f"删除向量失败: {e}")


vector_service = VectorService()
