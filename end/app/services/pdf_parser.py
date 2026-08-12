"""
PDF 解析服务 —— 提取文献元数据与正文段落
基于 PyMuPDF (fitz) + pdfplumber 双引擎
"""
import fitz  # PyMuPDF
from app.utils.logger import get_logger

logger = get_logger("PDFParser")


class PDFParser:
    """PDF 文献解析器"""

    @staticmethod
    def parse(file_path: str) -> dict:
        """
        解析 PDF 文件
        返回:
        {
            "metadata": {"title", "authors", "year"},
            "full_text": str,
            "paragraphs": list[str],  # 段落列表（用于向量化）
            "sections": list[dict],   # 章节结构
        }
        """
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            logger.error(f"PDF 打开失败 {file_path}: {e}")
            return {"metadata": {}, "full_text": "", "paragraphs": [], "sections": []}

        # 元数据
        meta = doc.metadata or {}
        metadata = {
            "title": meta.get("title", "") or "",
            "authors": meta.get("author", "") or "",
            "year": _extract_year(meta),
        }

        # 逐页提取文本
        all_text = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            all_text.append(text)

        full_text = "\n\n".join(all_text)
        paragraphs = _split_paragraphs(full_text)
        sections = _extract_sections(all_text)

        logger.info(
            f"PDF 解析完成: {len(doc)} 页, {len(paragraphs)} 段落, "
            f"{len(full_text)} 字符"
        )
        doc.close()

        return {
            "metadata": metadata,
            "full_text": full_text,
            "paragraphs": paragraphs,
            "sections": sections,
        }

    @staticmethod
    def parse_text(text: str) -> dict:
        """解析纯文本（非 PDF）"""
        paragraphs = _split_paragraphs(text)
        return {
            "metadata": {},
            "full_text": text,
            "paragraphs": paragraphs,
            "sections": [],
        }


def _split_paragraphs(text: str, min_len: int = 20) -> list[str]:
    """将全文切分为段落（按空行 + 句号分割）"""
    # 先按双换行分段
    raw_paras = text.split("\n\n")
    paragraphs = []
    for para in raw_paras:
        para = para.strip()
        if len(para) >= min_len:
            # 超长段落按句号再切
            if len(para) > 500:
                sentences = para.replace("。", "。\n").split("\n")
                buf = ""
                for s in sentences:
                    buf += s
                    if len(buf) >= 200:
                        paragraphs.append(buf.strip())
                        buf = ""
                if buf.strip():
                    paragraphs.append(buf.strip())
            else:
                paragraphs.append(para)
    return paragraphs


def _extract_year(meta: dict) -> int | None:
    """从元数据中提取年份"""
    date_str = meta.get("creationDate", "") or meta.get("modDate", "")
    if len(date_str) >= 4:
        try:
            return int(date_str[:4])
        except ValueError:
            pass
    return None


def _extract_sections(pages: list[str]) -> list[dict]:
    """粗略提取章节结构（基于标题模式）"""
    sections = []
    for page_num, text in enumerate(pages):
        for line in text.split("\n"):
            line = line.strip()
            # 简单启发式：以数字开头、较短、不以句号结尾
            if (
                len(line) < 80
                and line
                and not line.endswith(("。", ".", "；", ";"))
                and _looks_like_heading(line)
            ):
                sections.append({"page": page_num + 1, "heading": line})
    return sections


def _looks_like_heading(line: str) -> bool:
    """判断是否像标题"""
    import re
    # 以数字编号开头：1. / 1.1 / 第一章 等
    if re.match(r"^(\d+\.?)+\s*\S", line):
        return True
    if line.startswith(("第", "Abstract", "Introduction", "Method", "Result", "Conclusion")):
        return True
    return False


pdf_parser = PDFParser()
