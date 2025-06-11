# FastAPIProject/app.py

from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.routing import Mount, APIRoute
from fastapi import WebSocket, WebSocketDisconnect
import psutil
import asyncio
from datetime import datetime
from typing import List
from urllib.parse import quote

import asyncio
import json
import os
import io
import sys
import tempfile
from datetime import datetime

from fastapi import UploadFile, File, Form
from typing import Optional

# 添加聊天请求模型
from pydantic import BaseModel
from contextlib import asynccontextmanager


# 取得当前脚本（app.py）所在的绝对路径
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
template_dir = BASE_DIR / "templates"

print(">>> static_dir 存在吗？", static_dir.exists(), static_dir.is_dir())
print(">>> static_dir 下的文件列表：", os.listdir(static_dir))
# 增加打印，帮助排查
print(">>> 当前工作目录 (cwd):", os.getcwd())
print(">>> __file__ 绝对路径:", Path(__file__).resolve())
print(">>> 计算出的 static 目录:", (BASE_DIR / "static").resolve())
print(">>> 计算出的 templates 目录:", (BASE_DIR / "templates").resolve())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动事件
    print("\n" + "=" * 50)
    print("✓ 控制阀装配任务分解系统已启动")
    print("✓ 双重执行问题已修复")
    print("✓ 缓存系统已启用")
    print("=" * 50 + "\n")

    yield

    # 关闭事件（如果需要的话）
    print("系统正在关闭...")


# 创建 FastAPI 应用时传入 lifespan
app = FastAPI(lifespan=lifespan)
# 挂载项目根下的 static 文件夹
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 4. 模板
templates = Jinja2Templates(directory=str(template_dir))


# 检查并导入后端模块
try:
    from backend.decomposition import run_decompose_stream, run_full_decomposition

    print("✓ 成功导入 backend.decomposition 模块")
except ImportError as e:
    print(f"✗ 导入错误: {e}")


    # 创建占位函数
    async def run_decompose_stream(task):
        async def gen():
            yield "event: status\ndata: 模块导入失败\n\n"
            yield "event: complete\ndata: 错误\n\n"

        return gen()


    async def run_full_decomposition(task):
        return {"error": "模块导入失败"}

# 尝试导入Excel处理库
try:
    import pandas as pd
    import xlsxwriter

    EXCEL_SUPPORT = True
    print("✓ Excel导出功能可用")
except ImportError:
    EXCEL_SUPPORT = False
    print("✗ Excel导出功能不可用，请安装: pip install pandas xlsxwriter")


# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 根路径直接返回HTML内容
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    print("访问根路径 /")
    return templates.TemplateResponse("index.html", {"request": request})


# 测试接口
@app.get("/test")
async def test():
    return {"message": "服务器正常运行"}


# SSE流式接口
@app.get("/api/decompose/stream")
async def decompose_stream(task: str = Query(...)):
    print(f"收到SSE请求: task={task}")

    async def event_generator():
        try:
            async for event in await run_decompose_stream(task):
                yield event
        except Exception as e:
            print(f"SSE错误: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# JSON完整数据接口
@app.get("/api/decompose/json")
async def decompose_json(task: str = Query(...)):
    print(f"[JSON接口] 收到请求: task={task}")
    try:
        result = await run_full_decomposition(task)
        print(f"[JSON接口] 返回结果，工序数: {len(result.get('processes', []))}")
        return JSONResponse(content=result)
    except Exception as e:
        print(f"[JSON接口] 错误: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )


# Excel导出接口 - 修复版本兼容性
@app.get("/api/export/excel")
async def export_excel(task: str = Query(...)):
    if not EXCEL_SUPPORT:
        return JSONResponse(
            content={"error": "Excel导出功能未安装，请安装pandas和xlsxwriter"},
            status_code=501
        )

    try:
        print(f"[Excel导出] 收到请求: task={task}")

        # 获取数据
        result = await run_full_decomposition(task)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            excel_path = tmp.name

        # 转换为DataFrame
        processes = result.get('processes', [])
        flat_data = []

        for proc in processes:
            if proc.get('steps'):
                for step in proc['steps']:
                    flat_data.append({
                        'process_id': proc.get('process_id'),
                        'process_name': proc.get('name', ''),
                        'process_description': proc.get('description', ''),
                        'unit': step.get('unit', ''),
                        'step_id': step.get('step_id'),
                        'device': step.get('device', ''),
                        'action': step.get('action', '')
                    })
            else:
                flat_data.append({
                    'process_id': proc.get('process_id'),
                    'process_name': proc.get('name', ''),
                    'process_description': proc.get('description', ''),
                    'unit': '-',
                    'step_id': '-',
                    'device': '-',
                    'action': '暂无步骤信息'
                })

        df = pd.DataFrame(flat_data)

        # 修复pandas版本兼容性 - 移除options参数
        try:
            # 尝试新版本pandas语法
            with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='AssemblyProcess', index=False)

                workbook = writer.book
                worksheet = writer.sheets['AssemblyProcess']

                # 定义格式
                header_format = workbook.add_format({
                    'bold': True,
                    'align': 'center',
                    'valign': 'vcenter',
                    'text_wrap': True,
                    'bg_color': '#217346',
                    'font_color': 'white',
                    'border': 1
                })
                cell_format = workbook.add_format({
                    'align': 'center',
                    'valign': 'vcenter',
                    'text_wrap': True,
                    'border': 1
                })
                merge_format = workbook.add_format({
                    'align': 'center',
                    'valign': 'vcenter',
                    'text_wrap': True,
                    'bg_color': '#e7f3ff',
                    'border': 1
                })

                # 重新写入表头
                headers = ['工序ID', '工序名称', '工序描述', '单元', '步骤ID', '设备', '操作']
                for col_num, header in enumerate(headers):
                    worksheet.write(0, col_num, header, header_format)

                # 重新写入数据
                for row_idx, row in df.iterrows():
                    worksheet.write(row_idx + 1, 0, str(row['process_id']), cell_format)
                    worksheet.write(row_idx + 1, 1, str(row['process_name']), cell_format)
                    worksheet.write(row_idx + 1, 2, str(row['process_description']), cell_format)
                    worksheet.write(row_idx + 1, 3, str(row['unit']), cell_format)
                    worksheet.write(row_idx + 1, 4, str(row['step_id']), cell_format)
                    worksheet.write(row_idx + 1, 5, str(row['device']), cell_format)
                    worksheet.write(row_idx + 1, 6, str(row['action']), cell_format)

                # 设置列宽
                worksheet.set_column(0, 0, 10)  # 工序ID
                worksheet.set_column(1, 1, 20)  # 工序名称
                worksheet.set_column(2, 2, 30)  # 工序描述
                worksheet.set_column(3, 3, 25)  # 单元
                worksheet.set_column(4, 4, 10)  # 步骤ID
                worksheet.set_column(5, 5, 25)  # 设备
                worksheet.set_column(6, 6, 40)  # 操作

        except Exception as writer_error:
            print(f"ExcelWriter失败，使用直接xlsxwriter: {writer_error}")
            # 如果pandas ExcelWriter失败，直接使用xlsxwriter
            import xlsxwriter

            workbook = xlsxwriter.Workbook(excel_path)
            worksheet = workbook.add_worksheet('AssemblyProcess')

            # 定义格式
            header_format = workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'bg_color': '#217346',
                'font_color': 'white',
                'border': 1
            })
            cell_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
                'border': 1
            })

            # 写入表头
            headers = ['工序ID', '工序名称', '工序描述', '单元', '步骤ID', '设备', '操作']
            for col_num, header in enumerate(headers):
                worksheet.write(0, col_num, header, header_format)

            # 写入数据
            for row_idx, row in df.iterrows():
                worksheet.write(row_idx + 1, 0, str(row['process_id']), cell_format)
                worksheet.write(row_idx + 1, 1, str(row['process_name']), cell_format)
                worksheet.write(row_idx + 1, 2, str(row['process_description']), cell_format)
                worksheet.write(row_idx + 1, 3, str(row['unit']), cell_format)
                worksheet.write(row_idx + 1, 4, str(row['step_id']), cell_format)
                worksheet.write(row_idx + 1, 5, str(row['device']), cell_format)
                worksheet.write(row_idx + 1, 6, str(row['action']), cell_format)

            # 设置列宽
            worksheet.set_column(0, 0, 10)
            worksheet.set_column(1, 1, 20)
            worksheet.set_column(2, 2, 30)
            worksheet.set_column(3, 3, 25)
            worksheet.set_column(4, 4, 10)
            worksheet.set_column(5, 5, 25)
            worksheet.set_column(6, 6, 40)

            workbook.close()

        # 读取文件内容
        with open(excel_path, 'rb') as f:
            content = f.read()

        # 删除临时文件
        os.unlink(excel_path)

        # 创建安全的文件名
        import re
        safe_task_name = re.sub(r'[^\w\s-]', '', task).strip()
        safe_task_name = re.sub(r'[-\s]+', '_', safe_task_name)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"工艺工序分解结果_{safe_task_name}_{timestamp}.xlsx"

        # 使用URL编码的文件名
        from urllib.parse import quote
        encoded_filename = quote(filename.encode('utf-8'))

        print(f"[Excel导出] 生成文件: {filename}")

        # 返回文件
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )

    except Exception as e:
        print(f"Excel导出错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={"error": f"Excel导出失败: {str(e)}"},
            status_code=500
        )


# 添加CSV导出接口
@app.get("/api/export/csv")
async def export_csv(task: str = Query(...)):
    """CSV导出接口"""
    try:
        print(f"[CSV导出] 收到请求: task={task}")

        # 获取数据
        result = await run_full_decomposition(task)
        processes = result.get('processes', [])

        # 创建CSV内容
        csv_lines = []
        csv_lines.append('工序ID,工序名称,工序描述,单元,步骤ID,设备,操作')

        for proc in processes:
            if proc.get('steps'):
                for step in proc['steps']:
                    line = f'"{proc.get("process_id", "")}","{proc.get("name", "")}","{proc.get("description", "")}","{step.get("unit", "")}","{step.get("step_id", "")}","{step.get("device", "")}","{step.get("action", "")}"'
                    csv_lines.append(line)
            else:
                line = f'"{proc.get("process_id", "")}","{proc.get("name", "")}","{proc.get("description", "")}","-","-","-","暂无步骤信息"'
                csv_lines.append(line)

        csv_content = '\ufeff' + '\n'.join(csv_lines)  # 添加BOM用于Excel正确显示中文

        # 创建安全的文件名
        import re
        safe_task_name = re.sub(r'[^\w\s-]', '', task).strip()
        safe_task_name = re.sub(r'[-\s]+', '_', safe_task_name)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"工艺工序分解结果_{safe_task_name}_{timestamp}.csv"

        from urllib.parse import quote
        encoded_filename = quote(filename.encode('utf-8'))

        print(f"[CSV导出] 生成文件: {filename}")

        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )

    except Exception as e:
        print(f"CSV导出错误: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={"error": f"CSV导出失败: {str(e)}"},
            status_code=500
        )

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 缓存状态接口
@app.get("/api/cache/status")
async def cache_status():
    try:
        from backend.decomposition import _result_cache, _cache_hits, _cache_misses
        total_requests = _cache_hits + _cache_misses
        hit_rate = (_cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_size": len(_result_cache),
            "cached_tasks": list(_result_cache.keys()),
            "cache_hits": _cache_hits,
            "cache_misses": _cache_misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }
    except:
        return {"error": "无法获取缓存状态"}


# 添加WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 定期发送系统状态
            status = {
                "type": "system_status",
                "cpu": psutil.cpu_percent(),
                "memory": psutil.virtual_memory().percent,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(status)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


class ChatRequest(BaseModel):
    message: str


# 添加AI聊天接口
@app.post("/api/chat")
async def ai_chat(request: ChatRequest):
    """AI助手聊天接口"""
    try:
        # 这里整合你的RAG系统
        print(f"[AI聊天] 收到问题: {request.message}")

        # 尝试使用现有的RAG系统
        try:
            # 导入RAG系统（如果可用）
            from backend.rag.rag_system import RAGQueryEngine, KnowledgeBase

            kb = KnowledgeBase(base_dir="./backend/rag/web_knowledge_base")
            query_engine = RAGQueryEngine(kb)

            result = await query_engine.query(request.message)

            return {
                "response": result["answer"],
                "confidence": result.get("confidence", "medium"),
                "sources": result.get("citations", [])
            }
        except ImportError:
            # 如果RAG系统不可用，提供基础回复
            basic_responses = {
                "工艺": "工艺流程通常包括上料、装配、检测等环节，具体需要根据产品类型来定制。",
                "设备": "我们的产线配备了协作机器人、SCARA机器人、视觉系统等先进设备。",
                "质量": "质量控制包括在线检测、最终验证等多个环节，确保产品符合标准。",
                "安全": "请始终遵循安全操作规程，佩戴防护设备，注意设备运行状态。"
            }

            response = "感谢您的提问！"
            for keyword, answer in basic_responses.items():
                if keyword in request.message:
                    response = answer
                    break
            else:
                response = f"关于'{request.message}'，建议您查阅相关技术文档或联系技术支持。我主要能帮助解答工艺流程、设备操作、质量控制等方面的问题。"

            return {
                "response": response,
                "confidence": "medium",
                "sources": []
            }

    except Exception as e:
        print(f"[AI聊天] 错误: {e}")
        return {
            "response": "抱歉，我暂时无法处理您的问题。请稍后再试或联系技术支持。",
            "error": True,
            "confidence": "low"
        }


# 添加系统监控接口
@app.get("/api/system/metrics")
async def get_system_metrics():
    """系统监控数据"""
    try:
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "memory_total": memory.total,
            "memory_used": memory.used,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"获取系统指标失败: {e}")
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# 添加favicon路由
@app.get("/favicon.ico")
async def favicon():
    """返回favicon"""
    return {"message": "favicon not found"}

# 添加RAG系统路径
sys.path.append(str(Path(__file__).parent / "backend" / "rag"))

try:
    from rag_system import KnowledgeBase, RAGQueryEngine
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("RAG系统不可用，请检查依赖安装")

# 初始化RAG系统（如果可用）
if RAG_AVAILABLE:
    try:
        kb = KnowledgeBase(
            base_dir="./backend/rag/web_knowledge_base",
            api_key="sk-c7owrjsep4p7gk3d",  # 使用你的API密钥
            base_url="https://cloud.infini-ai.com/maas/v1"
        )
        query_engine = RAGQueryEngine(kb)
        print("RAG知识库系统初始化成功")
    except Exception as e:
        RAG_AVAILABLE = False
        print(f"RAG系统初始化失败: {e}")


# RAG知识库API路由
@app.get("/api/documents")
async def get_documents(domain: Optional[str] = None):
    """获取文档列表"""
    if not RAG_AVAILABLE:
        return []

    try:
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
    except Exception as e:
        return JSONResponse(
            content={"error": f"获取文档列表失败: {str(e)}"},
            status_code=500
        )


@app.get("/api/domains")
async def get_domains():
    """获取所有领域"""
    if not RAG_AVAILABLE:
        return []

    try:
        return kb.get_domains()
    except Exception as e:
        return JSONResponse(
            content={"error": f"获取领域列表失败: {str(e)}"},
            status_code=500
        )


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    if not RAG_AVAILABLE:
        return {
            "total_docs": 0,
            "total_domains": 0,
            "total_words": 0,
            "total_tokens": 0,
            "model_name": "N/A",
            "base_url": "N/A"
        }

    try:
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
    except Exception as e:
        return JSONResponse(
            content={"error": f"获取统计信息失败: {str(e)}"},
            status_code=500
        )


@app.post("/api/document/text")
async def add_text_document(doc: dict):
    """添加文本文档"""
    if not RAG_AVAILABLE:
        return JSONResponse(
            content={"error": "RAG系统不可用"},
            status_code=501
        )

    try:
        doc_id = kb.add_document_from_text(
            text=doc["text"],
            title=doc["title"],
            domain=doc["domain"],
            version=doc.get("version", "1.0")
        )
        return {"doc_id": doc_id, "message": "文档添加成功"}
    except Exception as e:
        return JSONResponse(
            content={"error": f"添加文档失败: {str(e)}"},
            status_code=500
        )


@app.post("/api/document/url")
async def add_url_document(doc: dict):
    """添加URL文档"""
    if not RAG_AVAILABLE:
        return JSONResponse(
            content={"error": "RAG系统不可用"},
            status_code=501
        )

    try:
        doc_id = kb.add_document_from_url(
            url=doc["url"],
            title=doc["title"],
            domain=doc["domain"],
            max_pages=doc.get("max_pages"),
            version=doc.get("version", "1.0")
        )
        return {"doc_id": doc_id, "message": "文档添加成功"}
    except Exception as e:
        return JSONResponse(
            content={"error": f"添加文档失败: {str(e)}"},
            status_code=500
        )


@app.post("/api/document/file")
async def add_file_document(
        file: UploadFile = File(...),
        title: str = Form(...),
        domain: str = Form(...),
        max_pages: Optional[int] = Form(None),
        version: str = Form("1.0")
):
    """添加文件文档"""
    if not RAG_AVAILABLE:
        return JSONResponse(
            content={"error": "RAG系统不可用"},
            status_code=501
        )

    if not file.filename.endswith('.pdf'):
        return JSONResponse(
            content={"error": "只支持PDF文件"},
            status_code=400
        )

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
        return JSONResponse(
            content={"error": f"添加文档失败: {str(e)}"},
            status_code=500
        )


@app.post("/api/query")
async def query_knowledge(query: dict):
    """查询知识库"""
    if not RAG_AVAILABLE:
        return JSONResponse(
            content={"error": "RAG系统不可用"},
            status_code=501
        )

    try:
        result = await query_engine.query(
            question=query["question"],
            domain=query.get("domain"),
            doc_ids=query.get("doc_ids"),
            max_depth=query.get("max_depth", 2)
        )
        return result
    except Exception as e:
        return JSONResponse(
            content={"error": f"查询失败: {str(e)}"},
            status_code=500
        )


@app.delete("/api/document")
async def delete_document(req: dict):
    """删除文档"""
    if not RAG_AVAILABLE:
        return JSONResponse(
            content={"error": "RAG系统不可用"},
            status_code=501
        )

    try:
        if kb.remove_document(req["doc_id"]):
            return {"message": "文档删除成功"}
        else:
            return JSONResponse(
                content={"error": "文档不存在"},
                status_code=404
            )
    except Exception as e:
        return JSONResponse(
            content={"error": f"删除文档失败: {str(e)}"},
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn

    port = 8001  # 改用8001端口
    print("=" * 50)
    print("启动 FastAPI 服务器...")
    print(f"主页面: http://127.0.0.1:{port}")
    print(f"测试页: http://127.0.0.1:{port}/test")
    print(f"缓存状态: http://127.0.0.1:{port}/api/cache/status")
    print("=" * 50)
    print("\n=== 已注册路由列表 ===")
    for route in app.router.routes:
        if isinstance(route, Mount):
            print(f"🗂 Mount → prefix: {route.path}, app: {route.app}")
        elif isinstance(route, APIRoute):
            print(f"🔗 APIRoute → path: {route.path}, methods: {route.methods}")
    print("=== 以上 ===\n")
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)  # 关闭自动重载
