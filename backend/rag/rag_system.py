#rag_system.py
import os
import json
import pickle
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from pydantic import BaseModel, field_validator
import requests
from io import BytesIO
from pypdf import PdfReader
import re
import tiktoken
from nltk.tokenize import sent_tokenize
import nltk
from openai import AsyncOpenAI

# 确保nltk数据可用
try:
    nltk.download('punkt', quiet=True)
except:
    pass

# API配置
BASE_URL = "https://cloud.infini-ai.com/maas/v1"
MODEL_NAME = "deepseek-v3"

import os

# 从环境变量读取 API 密钥
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise EnvironmentError("OPENAI_API_KEY environment variable not set")


@dataclass
class DocumentMetadata:
    """文档元数据"""
    doc_id: str
    title: str
    source_type: str  # 'url', 'file', 'text'
    source_path: str
    domain: str  # 专业领域
    version: str
    created_at: str
    updated_at: str
    hash: str
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    token_count: Optional[int] = None


@dataclass
class DocumentChunk:
    """文档块"""
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    parent_chunk_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeBase:
    """可扩展的RAG知识库"""

    def __init__(self, base_dir: str = "./knowledge_base", api_key: str = None, base_url: str = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        # 创建必要的子目录
        (self.base_dir / "documents").mkdir(exist_ok=True)
        (self.base_dir / "chunks").mkdir(exist_ok=True)
        (self.base_dir / "metadata").mkdir(exist_ok=True)

        self.tokenizer = tiktoken.get_encoding("o200k_base")

        # 使用用户提供的API配置
        self.api_key = api_key or API_KEY
        self.base_url = base_url or BASE_URL
        self.model_name = MODEL_NAME

        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

        # 加载现有的元数据
        self.documents_metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, DocumentMetadata]:
        """加载文档元数据"""
        metadata_file = self.base_dir / "metadata" / "documents.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {doc_id: DocumentMetadata(**meta) for doc_id, meta in data.items()}
        return {}

    def _save_metadata(self):
        """保存文档元数据"""
        metadata_file = self.base_dir / "metadata" / "documents.json"
        data = {doc_id: asdict(meta) for doc_id, meta in self.documents_metadata.items()}
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _calculate_hash(self, text: str) -> str:
        """计算文本哈希"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _extract_text_from_pdf_url(self, url: str, max_pages: Optional[int] = None) -> str:
        """从PDF URL提取文本"""
        print(f"正在下载PDF文档: {url}")
        response = requests.get(url)
        response.raise_for_status()

        pdf_bytes = BytesIO(response.content)
        pdf_reader = PdfReader(pdf_bytes)

        full_text = ""
        page_limit = min(len(pdf_reader.pages), max_pages) if max_pages else len(pdf_reader.pages)

        for i in range(page_limit):
            full_text += pdf_reader.pages[i].extract_text() + "\n"

        return full_text, len(pdf_reader.pages)

    def _extract_text_from_pdf_file(self, file_path: str, max_pages: Optional[int] = None) -> str:
        """从PDF文件提取文本"""
        print(f"正在读取PDF文件: {file_path}")
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)

            full_text = ""
            page_limit = min(len(pdf_reader.pages), max_pages) if max_pages else len(pdf_reader.pages)

            for i in range(page_limit):
                full_text += pdf_reader.pages[i].extract_text() + "\n"

        return full_text, len(pdf_reader.pages)

    def _split_into_chunks(self, text: str, chunk_count: int = 20, min_tokens: int = 500) -> List[Dict[str, Any]]:
        """将文本分割成块"""
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk_sentences = []
        current_chunk_tokens = 0

        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))

            if (current_chunk_tokens + sentence_tokens > min_tokens * 2) and current_chunk_tokens >= min_tokens:
                chunk_text = " ".join(current_chunk_sentences)
                chunks.append({
                    "id": len(chunks),
                    "text": chunk_text
                })
                current_chunk_sentences = [sentence]
                current_chunk_tokens = sentence_tokens
            else:
                current_chunk_sentences.append(sentence)
                current_chunk_tokens += sentence_tokens

        # 添加最后一个块
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append({
                "id": len(chunks),
                "text": chunk_text
            })

        # 如果块数超过目标数量，重新分配
        if len(chunks) > chunk_count:
            all_text = " ".join(chunk["text"] for chunk in chunks)
            sentences = sent_tokenize(all_text)
            sentences_per_chunk = len(sentences) // chunk_count + (1 if len(sentences) % chunk_count > 0 else 0)

            chunks = []
            for i in range(0, len(sentences), sentences_per_chunk):
                chunk_sentences = sentences[i:i + sentences_per_chunk]
                chunk_text = " ".join(chunk_sentences)
                chunks.append({
                    "id": len(chunks),
                    "text": chunk_text
                })

        return chunks

    def add_document_from_url(self, url: str, title: str, domain: str,
                              max_pages: Optional[int] = None, version: str = "1.0") -> str:
        """从URL添加PDF文档"""
        doc_id = hashlib.md5(f"{url}_{title}_{domain}".encode()).hexdigest()[:16]

        # 检查是否已存在
        if doc_id in self.documents_metadata:
            print(f"文档 {title} 已存在，ID: {doc_id}")
            return doc_id

        try:
            text, page_count = self._extract_text_from_pdf_url(url, max_pages)
            return self._process_document(doc_id, title, "url", url, domain, version, text, page_count)
        except Exception as e:
            print(f"处理URL文档失败: {e}")
            raise

    def add_document_from_file(self, file_path: str, title: str, domain: str,
                               max_pages: Optional[int] = None, version: str = "1.0") -> str:
        """从文件添加PDF文档"""
        file_path = Path(file_path).resolve()
        doc_id = hashlib.md5(f"{file_path}_{title}_{domain}".encode()).hexdigest()[:16]

        if doc_id in self.documents_metadata:
            print(f"文档 {title} 已存在，ID: {doc_id}")
            return doc_id

        try:
            text, page_count = self._extract_text_from_pdf_file(str(file_path), max_pages)
            return self._process_document(doc_id, title, "file", str(file_path), domain, version, text, page_count)
        except Exception as e:
            print(f"处理文件文档失败: {e}")
            raise

    def add_document_from_text(self, text: str, title: str, domain: str, version: str = "1.0") -> str:
        """从纯文本添加文档"""
        doc_id = hashlib.md5(f"{text[:100]}_{title}_{domain}".encode()).hexdigest()[:16]

        if doc_id in self.documents_metadata:
            print(f"文档 {title} 已存在，ID: {doc_id}")
            return doc_id

        return self._process_document(doc_id, title, "text", "direct_input", domain, version, text)

    def _process_document(self, doc_id: str, title: str, source_type: str, source_path: str,
                          domain: str, version: str, text: str, page_count: Optional[int] = None) -> str:
        """处理文档的通用方法"""
        now = datetime.now().isoformat()
        word_count = len(re.findall(r'\b\w+\b', text))
        token_count = len(self.tokenizer.encode(text))
        text_hash = self._calculate_hash(text)

        # 创建元数据
        metadata = DocumentMetadata(
            doc_id=doc_id,
            title=title,
            source_type=source_type,
            source_path=source_path,
            domain=domain,
            version=version,
            created_at=now,
            updated_at=now,
            hash=text_hash,
            page_count=page_count,
            word_count=word_count,
            token_count=token_count
        )

        # 保存原始文档
        doc_file = self.base_dir / "documents" / f"{doc_id}.txt"
        with open(doc_file, 'w', encoding='utf-8') as f:
            f.write(text)

        # 分割并保存chunks
        chunks = self._split_into_chunks(text)
        self._save_chunks(doc_id, chunks)

        # 更新元数据
        self.documents_metadata[doc_id] = metadata
        self._save_metadata()

        print(f"文档已添加: {title}")
        print(f"  ID: {doc_id}")
        print(f"  领域: {domain}")
        print(f"  页数: {page_count or 'N/A'}")
        print(f"  词数: {word_count}")
        print(f"  Token数: {token_count}")
        print(f"  分块数: {len(chunks)}")

        return doc_id

    def _save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]):
        """保存文档块"""
        chunks_file = self.base_dir / "chunks" / f"{doc_id}.pkl"
        with open(chunks_file, 'wb') as f:
            pickle.dump(chunks, f)

    def _load_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """加载文档块"""
        chunks_file = self.base_dir / "chunks" / f"{doc_id}.pkl"
        if chunks_file.exists():
            with open(chunks_file, 'rb') as f:
                return pickle.load(f)
        return []

    def list_documents(self, domain: Optional[str] = None) -> List[DocumentMetadata]:
        """列出文档"""
        docs = list(self.documents_metadata.values())
        if domain:
            docs = [doc for doc in docs if doc.domain == domain]
        return sorted(docs, key=lambda x: x.created_at, reverse=True)

    def get_domains(self) -> List[str]:
        """获取所有领域"""
        return list(set(doc.domain for doc in self.documents_metadata.values()))

    def remove_document(self, doc_id: str) -> bool:
        """删除文档"""
        if doc_id not in self.documents_metadata:
            return False

        # 删除文件
        doc_file = self.base_dir / "documents" / f"{doc_id}.txt"
        chunks_file = self.base_dir / "chunks" / f"{doc_id}.pkl"

        doc_file.unlink(missing_ok=True)
        chunks_file.unlink(missing_ok=True)

        # 删除元数据
        del self.documents_metadata[doc_id]
        self._save_metadata()

        return True


class RAGQueryEngine:
    """RAG查询引擎"""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.client = knowledge_base.client
        self.model_name = knowledge_base.model_name

    async def _route_chunks(self, question: str, chunks: List[Dict[str, Any]],
                            depth: int, scratchpad: str = "") -> Dict[str, Any]:
        """路由相关chunks"""
        print(f"\n==== 路由层级 {depth} ====")
        print(f"评估 {len(chunks)} 个块的相关性")

        system_message = """你是一个专业的文档导航专家。你的任务是：
                        1. 识别哪些文本块可能包含回答用户问题的信息
                        2. 在记事本中记录你的推理过程以供后续参考
                        3. 选择最可能相关的块。要有选择性，但要全面。选择足够多的块来回答问题，但避免选择过多。
                        
                        首先仔细思考什么信息有助于回答问题，然后评估每个块。
                        请直接返回选中的块ID列表，格式为JSON: {"chunk_ids": [1, 3, 5]}
                        """

        user_message = f"问题: {question}\n\n"

        if scratchpad:
            user_message += f"当前记事本:\n{scratchpad}\n\n"

        user_message += "文本块:\n\n"

        for chunk in chunks:
            user_message += f"块 {chunk['id']}:\n{chunk['text'][:500]}...\n\n"

        user_message += "\n请分析并选择相关的块ID，记录推理过程。"

        try:
            # 使用简化的方式调用API
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            response_text = response.choices[0].message.content

            # 尝试提取JSON格式的选择结果
            selected_ids = []
            new_scratchpad = scratchpad

            # 查找JSON格式的chunk_ids
            try:
                # 尝试解析包含chunk_ids的JSON
                import re
                json_match = re.search(r'\{[^}]*"chunk_ids"[^}]*\}', response_text)
                if json_match:
                    chunk_data = json.loads(json_match.group())
                    selected_ids = chunk_data.get("chunk_ids", [])
                else:
                    # 如果没有找到JSON格式，尝试从文本中提取数字
                    numbers = re.findall(r'\b\d+\b', response_text)
                    selected_ids = [int(n) for n in numbers if int(n) < len(chunks)][:5]  # 限制最多5个
            except:
                # 如果解析失败，随机选择前几个有意义的块
                selected_ids = list(range(min(3, len(chunks))))

            # 更新scratchpad
            scratchpad_entry = f"层级 {depth} 推理:\n{response_text[:300]}..."
            if new_scratchpad:
                new_scratchpad += "\n\n" + scratchpad_entry
            else:
                new_scratchpad = scratchpad_entry

            # 确保选中的ID有效
            selected_ids = [id for id in selected_ids if 0 <= id < len(chunks)]

            print(f"选中的块: {', '.join(str(id) for id in selected_ids)}")

            return {
                "selected_ids": selected_ids,
                "scratchpad": new_scratchpad
            }

        except Exception as e:
            print(f"路由过程中出错: {e}")
            # 降级处理：选择前几个块
            fallback_ids = list(range(min(3, len(chunks))))
            return {"selected_ids": fallback_ids, "scratchpad": scratchpad}

    async def _navigate_to_paragraphs(self, doc_ids: List[str], question: str, max_depth: int = 1) -> Dict[str, Any]:
        """导航到相关段落"""
        scratchpad = ""
        all_chunks = []

        # 收集所有文档的chunks
        for doc_id in doc_ids:
            chunks = self.kb._load_chunks(doc_id)
            doc_info = self.kb.documents_metadata.get(doc_id)
            for chunk in chunks:
                chunk["doc_id"] = doc_id
                chunk["doc_title"] = doc_info.title if doc_info else "未知文档"
            all_chunks.extend(chunks)

        if not all_chunks:
            return {"paragraphs": [], "scratchpad": scratchpad}

        # 重新分配chunk ID以避免冲突
        for i, chunk in enumerate(all_chunks):
            chunk["id"] = i

        chunk_paths = {chunk["id"]: str(chunk["id"]) for chunk in all_chunks}
        chunks = all_chunks

        # 导航层级
        for current_depth in range(max_depth + 1):
            result = await self._route_chunks(question, chunks, current_depth, scratchpad)
            scratchpad = result["scratchpad"]
            selected_ids = result["selected_ids"]
            selected_chunks = [c for c in chunks if c["id"] in selected_ids]

            if not selected_chunks:
                print("\n未找到相关块。")
                return {"paragraphs": [], "scratchpad": scratchpad}

            if current_depth == max_depth:
                print(f"\n在层级 {current_depth} 返回 {len(selected_chunks)} 个相关块")
                for chunk in selected_chunks:
                    chunk["display_id"] = chunk_paths[chunk["id"]]
                return {"paragraphs": selected_chunks, "scratchpad": scratchpad}

            # 准备下一层级：进一步分割选中的块
            next_level_chunks = []
            next_chunk_id = 0

            for chunk in selected_chunks:
                sub_chunks = self.kb._split_into_chunks(chunk["text"], chunk_count=10, min_tokens=200)

                for sub_chunk in sub_chunks:
                    path = f"{chunk_paths[chunk['id']]}.{sub_chunk['id']}"
                    sub_chunk["id"] = next_chunk_id
                    sub_chunk["doc_id"] = chunk["doc_id"]
                    sub_chunk["doc_title"] = chunk["doc_title"]
                    chunk_paths[next_chunk_id] = path
                    next_level_chunks.append(sub_chunk)
                    next_chunk_id += 1

            chunks = next_level_chunks

        return {"paragraphs": [], "scratchpad": scratchpad}

    async def query(self, question: str, domain: Optional[str] = None,
                    doc_ids: Optional[List[str]] = None, max_depth: int = 2) -> Dict[str, Any]:
        """查询知识库"""
        print(f"\n==== 查询: {question} ====")

        # 确定要搜索的文档
        if doc_ids:
            target_docs = doc_ids
        elif domain:
            docs = self.kb.list_documents(domain=domain)
            target_docs = [doc.doc_id for doc in docs]
        else:
            target_docs = list(self.kb.documents_metadata.keys())

        if not target_docs:
            return {
                "answer": "未找到相关文档。",
                "citations": [],
                "confidence": "low",
                "paragraphs": []
            }

        print(f"搜索 {len(target_docs)} 个文档")

        # 导航到相关段落
        navigation_result = await self._navigate_to_paragraphs(target_docs, question, max_depth)

        if not navigation_result["paragraphs"]:
            return {
                "answer": "在现有文档中未找到相关信息来回答此问题。",
                "citations": [],
                "confidence": "low",
                "paragraphs": []
            }

        # 生成答案
        answer_result = await self._generate_answer(question, navigation_result["paragraphs"],
                                                    navigation_result["scratchpad"])

        return {
            "answer": answer_result["answer"],
            "citations": answer_result["citations"],
            "confidence": answer_result["confidence"],
            "paragraphs": navigation_result["paragraphs"],
            "scratchpad": navigation_result["scratchpad"]
        }

    async def _generate_answer(self, question: str, paragraphs: List[Dict[str, Any]],
                               scratchpad: str) -> Dict[str, Any]:
        """生成答案"""
        print("\n==== 生成答案 ====")

        if not paragraphs:
            return {
                "answer": "未找到相关信息来回答此问题。",
                "citations": [],
                "confidence": "low"
            }

        # 准备上下文
        context = ""
        valid_citations = []
        for paragraph in paragraphs:
            display_id = paragraph.get("display_id", str(paragraph["id"]))
            doc_title = paragraph.get("doc_title", "未知文档")
            context += f"段落 {display_id} (来源: {doc_title}):\n{paragraph['text']}\n\n"
            valid_citations.append(display_id)

        system_prompt = f"""你是一个专业的知识助手，基于提供的文档段落回答问题。
                        仅基于提供的段落回答问题。不要依赖任何基础知识或外部信息，也不要从段落中推断。
                        引用与答案相关的段落短语。这将帮助你更具体和准确。
                        为答案中的每个陈述标注段落ID引用，格式如[段落ID]。
                        保持答案清晰、准确和专业。
                        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": f"问题: {question}\n\n记事本 (导航推理):\n{scratchpad}\n\n段落:\n{context}"}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            answer = response.choices[0].message.content

            # 简单提取引用
            citations = []
            for citation in valid_citations:
                if citation in answer:
                    citations.append(citation)

            # 评估置信度
            confidence = "high" if len(citations) > 0 else "medium"

            print(f"\n答案: {answer}")
            print(f"引用: {citations}")

            return {
                "answer": answer,
                "citations": citations,
                "confidence": confidence
            }

        except Exception as e:
            print(f"生成答案时出错: {e}")
            return {
                "answer": "生成答案时出现错误。",
                "citations": [],
                "confidence": "low"
            }

    # 同步封装方法，便于使用
    def query_sync(self, question: str, domain: Optional[str] = None,
                   doc_ids: Optional[List[str]] = None, max_depth: int = 2) -> Dict[str, Any]:
        """同步查询方法"""
        return asyncio.run(self.query(question, domain, doc_ids, max_depth))


# 使用示例
async def main():
    """使用示例"""
    # 初始化知识库（使用你的API配置）
    kb = KnowledgeBase(
        base_dir="../my_knowledge_base",
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # 添加示例文档
    print("=== 添加文档示例 ===")

    # 从文本添加文档
    sample_text = """
    人工智能技术指南

    第一章：机器学习基础
    机器学习是人工智能的一个重要分支，它使计算机能够在不被明确编程的情况下学习。
    主要的机器学习类型包括监督学习、无监督学习和强化学习。

    监督学习使用标记的训练数据来学习从输入到输出的映射。
    常见的监督学习算法包括线性回归、决策树、支持向量机和神经网络。

    第二章：深度学习
    深度学习是机器学习的一个子集，使用多层神经网络来学习数据的复杂模式。
    卷积神经网络（CNN）特别适用于图像处理任务。
    循环神经网络（RNN）和其变体如LSTM适用于序列数据处理。

    第三章：自然语言处理
    自然语言处理（NLP）是AI的一个分支，专注于计算机与人类语言的交互。
    预训练语言模型如BERT和GPT在各种NLP任务中取得了显著成果。
    Transformer架构是现代NLP的基础，支持了许多突破性的模型。
    """

    doc_id = kb.add_document_from_text(
        text=sample_text,
        title="AI技术指南",
        domain="人工智能"
    )

    # 列出文档
    print("\n=== 知识库文档 ===")
    all_docs = kb.list_documents()
    for doc in all_docs:
        print(f"- {doc.title} ({doc.domain}) - ID: {doc.doc_id}")

    # 查询示例
    print("\n=== 查询示例 ===")
    query_engine = RAGQueryEngine(kb)

    questions = [
        "什么是监督学习？",
        "深度学习有哪些类型的神经网络？",
        "BERT和GPT是什么？",
        "Transformer架构的作用是什么？"
    ]

    for question in questions:
        print(f"\n问题: {question}")
        result = await query_engine.query(question, domain="人工智能")
        print(f"答案: {result['answer']}")
        print(f"置信度: {result['confidence']}")
        if result['citations']:
            print(f"引用: {', '.join(result['citations'])}")
        print("-" * 50)


# 同步使用示例
def sync_example():
    """同步使用示例"""
    print("=== 同步使用示例 ===")

    # 初始化知识库
    kb = KnowledgeBase(
        base_dir="../sync_kb",
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # 添加文档
    kb.add_document_from_text(
        "Python是一种高级编程语言，以其简洁的语法和强大的功能而闻名。Python支持多种编程范式，包括面向对象、函数式和过程式编程。",
        "Python编程指南",
        "编程语言"
    )

    # 查询
    query_engine = RAGQueryEngine(kb)
    result = query_engine.query_sync("Python有什么特点？")
    print(f"答案: {result['answer']}")


if __name__ == "__main__":
    # 运行异步示例
    asyncio.run(main())

    # 运行同步示例
    sync_example()