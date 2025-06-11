#app.py
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import aiofiles
import os
import tempfile
from pathlib import Path
import asyncio
from datetime import datetime

# 导入你的RAG系统模块
from rag_system import KnowledgeBase, RAGQueryEngine, API_KEY, BASE_URL

# FastAPI应用初始化
app = FastAPI(title="RAG知识库系统", version="1.0.0")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory="templates")

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    username = os.getenv("APP_USERNAME", "admin")
    password = os.getenv("APP_PASSWORD", "secret")
    import secrets
    if not (secrets.compare_digest(credentials.username, username) and
            secrets.compare_digest(credentials.password, password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局知识库实例
kb = KnowledgeBase(
    base_dir="./web_knowledge_base",
    api_key=API_KEY,
    base_url=BASE_URL
)
query_engine = RAGQueryEngine(kb)


# Pydantic模型定义
class TextDocument(BaseModel):
    text: str
    title: str
    domain: str
    version: str = "1.0"


class URLDocument(BaseModel):
    url: str
    title: str
    domain: str
    max_pages: Optional[int] = None
    version: str = "1.0"


class QueryRequest(BaseModel):
    question: str
    domain: Optional[str] = None
    doc_ids: Optional[List[str]] = None
    max_depth: int = Field(default=2, ge=1, le=5)


class DeleteRequest(BaseModel):
    doc_id: str


# 路由定义

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, username: str = Depends(get_current_username)):
    # 渲染 templates/index.html，传入 request 和其他上下文
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/documents")
async def get_documents(domain: Optional[str] = None, username: str = Depends(get_current_username)):
    """获取文档列表"""
    docs = kb.list_documents(domain=domain)
    return [
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "domain": doc.domain,
            "version": doc.version,
            "source_type": doc.source_type,
            "created_at": doc.created_at,
            "word_count": doc.word_count,
            "token_count": doc.token_count,
            "page_count": doc.page_count
        }
        for doc in docs
    ]


@app.get("/api/domains")
async def get_domains(username: str = Depends(get_current_username)):
    """获取所有领域"""
    return kb.get_domains()


@app.get("/api/stats")
async def get_stats(username: str = Depends(get_current_username)):
    """获取统计信息"""
    docs = list(kb.documents_metadata.values())
    total_words = sum(doc.word_count for doc in docs)
    total_tokens = sum(doc.token_count for doc in docs)

    return {
        "total_docs": len(docs),
        "total_domains": len(kb.get_domains()),
        "total_words": total_words,
        "total_tokens": total_tokens,
        "model_name": kb.model_name,
        "base_url": kb.base_url
    }


@app.post("/api/document/text")
async def add_text_document(doc: TextDocument, username: str = Depends(get_current_username)):
    """添加文本文档"""
    try:
        doc_id = kb.add_document_from_text(
            text=doc.text,
            title=doc.title,
            domain=doc.domain,
            version=doc.version
        )
        return {"doc_id": doc_id, "message": "文档添加成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/document/url")
async def add_url_document(doc: URLDocument, username: str = Depends(get_current_username)):
    """添加URL文档"""
    try:
        doc_id = kb.add_document_from_url(
            url=doc.url,
            title=doc.title,
            domain=doc.domain,
            max_pages=doc.max_pages,
            version=doc.version
        )
        return {"doc_id": doc_id, "message": "文档添加成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/document/file")
async def add_file_document(
        file: UploadFile = File(...),
        title: str = Form(...),
        domain: str = Form(...),
        max_pages: Optional[int] = Form(None),
        version: str = Form("1.0"),
        username: str = Depends(get_current_username)
):
    """添加文件文档"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF文件")

    try:
        # 保存上传的文件到临时目录
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 添加文档
        doc_id = kb.add_document_from_file(
            file_path=tmp_path,
            title=title,
            domain=domain,
            max_pages=max_pages,
            version=version
        )

        # 删除临时文件
        os.unlink(tmp_path)

        return {"doc_id": doc_id, "message": "文档添加成功"}
    except Exception as e:
        if 'tmp_path' in locals():
            os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/query")
async def query_knowledge(query: QueryRequest, username: str = Depends(get_current_username)):
    """查询知识库"""
    try:
        result = await query_engine.query(
            question=query.question,
            domain=query.domain,
            doc_ids=query.doc_ids,
            max_depth=query.max_depth
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/document")
async def delete_document(req: DeleteRequest, username: str = Depends(get_current_username)):
    """删除文档"""
    if kb.remove_document(req.doc_id):
        return {"message": "文档删除成功"}
    else:
        raise HTTPException(status_code=404, detail="文档不存在")


# 健康检查端点
@app.get("/health")
async def health_check(username: str = Depends(get_current_username)):
    """健康检查"""
    return {
        "status": "healthy",
        "model": kb.model_name,
        "documents_count": len(kb.documents_metadata)
    }


if __name__ == "__main__":
    print("🚀 启动RAG知识库系统...")
    print("📍 访问地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )