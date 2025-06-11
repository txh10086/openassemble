# FastAPIProject/app.py

from fastapi import FastAPI, Query, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path
from fastapi.routing import Mount, APIRoute
import secrets

import asyncio
import json
import os
import io
import tempfile
from datetime import datetime

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

app = FastAPI()
# 挂载项目根下的 static 文件夹
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 4. 模板
templates = Jinja2Templates(directory=str(template_dir))

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    username = os.getenv("APP_USERNAME", "admin")
    password = os.getenv("APP_PASSWORD", "secret")
    correct_username = secrets.compare_digest(credentials.username, username)
    correct_password = secrets.compare_digest(credentials.password, password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


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

# 启动事件
@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 50)
    print("✓ 控制阀装配任务分解系统已启动")
    print("✓ 双重执行问题已修复")
    print("✓ 缓存系统已启用")
    print("=" * 50 + "\n")


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
async def decompose_stream(task: str = Query(...), username: str = Depends(get_current_username)):
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
async def decompose_json(task: str = Query(...), username: str = Depends(get_current_username)):
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


# Excel导出接口
@app.get("/api/export/excel")
async def export_excel(task: str = Query(...), username: str = Depends(get_current_username)):
    if not EXCEL_SUPPORT:
        return JSONResponse(
            content={"error": "Excel导出功能未安装，请安装pandas和xlsxwriter"},
            status_code=501
        )

    try:
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

        # 写入Excel
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            worksheet = workbook.add_worksheet('AssemblyProcess')
            writer.sheets['AssemblyProcess'] = worksheet

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

            # 写入表头
            headers = ['工序ID', '工序名称', '工序描述', '单元', '步骤ID', '设备', '操作']
            for col_num, header in enumerate(headers):
                worksheet.write(0, col_num, header, header_format)

            # 写入数据
            for row_idx, row in df.iterrows():
                worksheet.write(row_idx + 1, 0, row['process_id'], cell_format)
                worksheet.write(row_idx + 1, 1, row['process_name'], cell_format)
                worksheet.write(row_idx + 1, 2, row['process_description'], cell_format)
                worksheet.write(row_idx + 1, 3, row['unit'], cell_format)
                worksheet.write(row_idx + 1, 4, row['step_id'], cell_format)
                worksheet.write(row_idx + 1, 5, row['device'], cell_format)
                worksheet.write(row_idx + 1, 6, row['action'], cell_format)

            # 合并相同的process单元格
            grouped = df.groupby(['process_id', 'process_name', 'process_description'], sort=False).size()
            start_row = 1
            for (pid, pname, pdesc), count in grouped.items():
                end_row = start_row + count - 1
                if count > 1:
                    worksheet.merge_range(start_row, 0, end_row, 0, pid, merge_format)
                    worksheet.merge_range(start_row, 1, end_row, 1, pname, merge_format)
                    worksheet.merge_range(start_row, 2, end_row, 2, pdesc, merge_format)
                start_row = end_row + 1

            # 设置列宽
            worksheet.set_column(0, 0, 10)  # 工序ID
            worksheet.set_column(1, 1, 20)  # 工序名称
            worksheet.set_column(2, 2, 30)  # 工序描述
            worksheet.set_column(3, 3, 25)  # 单元
            worksheet.set_column(4, 4, 10)  # 步骤ID
            worksheet.set_column(5, 5, 25)  # 设备
            worksheet.set_column(6, 6, 40)  # 操作

        # 读取文件内容
        with open(excel_path, 'rb') as f:
            content = f.read()

        # 删除临时文件
        os.unlink(excel_path)

        # 返回文件
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''工艺工序分解结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            }
        )

    except Exception as e:
        print(f"Excel导出错误: {e}")
        return JSONResponse(
            content={"error": str(e)},
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
