# FastAPIProject/backend/decomposition.py

import asyncio, json, time
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

# —— 禁用 tracing ——
set_tracing_disabled(True)

# —— OpenAI 客户端配置 ——
import os

BASE_URL = "https://cloud.infini-ai.com/maas/v1"
MODEL_NAME = "deepseek-v3"

# 从环境变量读取 API 密钥，避免在代码中硬编码
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise EnvironmentError("OPENAI_API_KEY environment variable not set")

client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)

# —— 背景信息 ——
BACKGROUND = """
1. 产线架构：
   主/副阀体上料单元 → 波形弹簧安装单元 → 阀座、阀杆、阀芯安装单元 → 双头螺柱安装单元 → 
   缠绕垫片安装单元 → 阀体合装单元 → 螺母拧紧单元 → 填料压装单元 → 成品下料单元

2. 现场设备明细：
   - 主/副阀体上料单元：
     • 倍速链输送线及托盘系统  
     • 工位1阻挡气缸、工位1抬升气缸、工位1两销定位机构  
     • 节卡 Zu20 协作机器人（主/副阀体上料）  
     • 工业相机视觉系统（梅卡曼德 ProM，大视野）
   - 波形弹簧安装单元：
     • 倍速链输送线及托盘系统  
     • 工位2阻挡气缸  
     • ER6-700-SR 四轴 SCARA 机器人（波形弹簧安装）
   - 阀座、阀杆、阀芯安装单元：
     • 倍速链输送线及托盘系统  
     • 工位3阻挡气缸、工位3抬升气缸、工位4阻挡气缸、工位4抬升气缸、工位5阻挡气缸  
     • 节卡 Zu18 协作机器人（球芯安装、密封阀座安装，具备可换手爪库）  
     • Flexiv Rizon 10 协作机器人（阀杆安装，具备可换手爪库）
   - 双头螺柱安装单元：
     • 倍速链输送线及托盘系统  
     • 工位6阻挡气缸、工位6抬升气缸  
     • 双头螺柱振动盘送料器  
     • 工业相机视觉系统（梅卡曼德 Nano）  
     • 摆动气缸（螺柱翻转）、姿态调整气缸（螺柱竖直）  
     • 三轴机械手（双头螺柱安装）
   - 缠绕垫片安装单元：
     • 倍速链输送线及托盘系统  
     • 工位7阻挡气缸、工位7抬升气缸  
     • ER6-700-SR 四轴 SCARA 机器人（缠绕垫片安装）  
     • 垫片压装机构
   - 阀体合装单元：
     • 倍速链输送线及托盘系统  
     • 工位8阻挡气缸、工位8抬升气缸  
     • UR20 协作机器人（阀体合装）
   - 螺母拧紧单元：
     • 工位9阻挡气缸、工位9顶升旋转机构  
     • 螺母振动盘送料器  
     • ER6-700-SR 四轴 SCARA 机器人（螺母供料）  
     • 伺服压机（阀体压紧夹持）、三轴机械手（拧紧支撑）、拧紧机（螺母拧紧设备）
   - 填料压装单元：
     • 倍速链输送线及托盘系统  
     • 伺服压机（填料压装）
   - 成品下料单元：
     • 倍速链输送线及托盘系统  
     • 工位11阻挡气缸  
     • 珞石六轴机器人（成品下料）

3. 各单元功能能力简述：
   - 主/副阀体上料单元：托盘自动输送与定位，支持视觉检测和主/副阀体上料。  
   - 波形弹簧安装单元：SCARA 机器人高速精确完成弹簧装配。  
   - 阀座/阀杆/阀芯安装单元：协作机器人与视觉系统结合，实现多类部件自动化精装配。  
   - 双头螺柱安装单元：机械手配合振动盘与气缸，实现双螺柱精准送料与安装。  
   - 缠绕垫片安装单元：SCARA 机器人与压装机构结合，高效完成垫片绕装。  
   - 阀体合装单元：UR20 协作机器人可将主阀体合装至副阀体上。  
   - 螺母拧紧单元：伺服压机与螺母拧紧机联动，确保紧固扭矩可控、可靠。  
   - 填料压装单元：伺服压机精确完成填料压装，保证密封性能。  
   - 成品下料单元：六轴机器人完成成品卸料。  
"""

# —— 任务分解智能体 ——
agent_TaskDecomposition = Agent(
    name="TaskDecomposition_agent",
    instructions=(
        "你的角色：控制阀装配自动线的任务分解智能体，擅长根据整体装配任务制定合理的工序计划。"
        f"\n产线现场背景信息：{BACKGROUND}"
        "\n任务目标：请将给定的装配任务\"装配DN50球阀\"拆解为若干典型工序。每个工序应独立成段，清晰定义其在装配流程中的作用，符合实际工业装配顺序和现场设备作业能力。"
        "\n专业语境：装配DN50球阀是阀门制造中的一项典型任务，涉及多个零部件（阀体、阀座、阀球、阀杆、密封件、弹簧等）的逐步组装和检测。请充分考虑工业现场的实际流程和专业术语，确保工序划分全面且合理（涵盖从零部件准备、各组件装配到最终测试检验的主要阶段）。"
        "\n输出格式要求：仅输出JSON，包含任务名称和工序列表两个主要部分："
        "\n- task（字符串）：整体任务名称，即 \"装配DN50球阀\"。"
        "\n- processes（数组）：工序列表，按实际顺序排列。每个工序用一个JSON对象表示，包含以下字段："
        "\n  - process_id（整数）：工序序号，从1开始递增。"
        "\n  - name（字符串）：工序名称，精准概括该工序内容。"
        "\n  - description（字符串）：对该工序的详细描述，涵盖该阶段需完成的操作或目标。"
        "\n  - description（字符串）：对该工序的详细描述，涵盖该阶段需完成的操作或目标。"
        "\n格式示例：（请严格遵循此JSON结构，不要附加额外说明）"
        "```json\n{\n  \"task\": \"装配DN50球阀\",\n  \"processes\": [\n    {\"process_id\": 1, \"name\": \"工序名称1\", \"description\": \"工序描述1\"},\n    {\"process_id\": 2, \"name\": \"工序名称2\", \"description\": \"工序描述2\"}\n  ]\n}```"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[]
)

# —— 工序分解智能体 ——
agent_ProcessDecomposition = Agent(
    name="ProcessDecompositionIntelligent_agent",
    instructions=(
        "你的角色：控制阀装配自动线的工序分解智能体，擅长将某一道装配工序细化为具体的操作步骤。"
        f"\n产线现场背景信息：{BACKGROUND}"
        "\n任务目标：针对给定的装配工序（例如：\"安装阀座\"），将其进一步分解为有序的工步列表。每个工步需明确描述具体动作、参数要求、执行顺序和目的，体现实际自动化工业装配细节。"
        "\n专业语境：阀门装配工序通常包含多个细节步骤。例如，在\"安装阀座\"工序中，需要先检查阀体和阀座部件状况，然后按顺序完成阀座的就位和固定等操作。请使用专业且严谨的语言描述每个工步，确保符合实际装配流程（包括安全检查、零件安装、定位固定、检查验证等环节）。"
        "\n输出格式要求：仅输出JSON，包含工序名称和步骤列表两个部分："
        "\n- process（字符串）：工序名称，即所需分解的工序（例如 \"安装阀座\"）。"
        "\n- steps（数组）：工步列表，按执行先后顺序排列。每个工步用一个JSON对象表示，包含以下字段："
        "\n  - step_id（整数）：工步序号，从1开始递增。"
        "\n  - unit（字符串）：单元名称，明确该步涉及到的装配单元。"
        "\n  - device（字符串）：设备名称，明确该步涉及到的设备。"
        "\n  - action（字符串）：具体操作描述，明确该步要执行的内容和目标。"
        "\n格式示例：（请严格遵循此JSON结构，不要输出额外解释）"
        "```json\n{\n  \"process\": \"主副阀体上料\",\n  \"steps\": [\n    {\"step_id\": 1, \"unit\": \"主/副阀体上料单元\", \"device\": \"倍速链输送线及托盘系统\", \"action\": \"托盘到达工位并停止，接近传感器检测托盘已到位\"},\n    {\"step_id\": 2, \"unit\": \"主/副阀体上料单元\", \"device\": \"节卡Zu20协作机器人\", \"action\": \"抓取任务分配的主阀体\"}\n  ]\n}```"
    ),
    model=OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client),
    tools=[]
)

# —— 文本清理函数 ——
def clean_markdown(raw: str) -> str:
    """
    移除可能的 Markdown 代码块标记 ``` 或 ```json
    """
    if raw.startswith("```"):
        lines = raw.splitlines()
        # 去掉开头的 ``` 或 ```json
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # 去掉结尾的 ```
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)
    return raw


# —— 并行分解单个工序 ——
async def decompose_single_process(process_name: str) -> dict:
    """分解单个工序并返回步骤"""
    try:
        # print(f"  - 开始分解工序: {process_name}")  # 减少日志噪音
        step_res = await Runner.run(agent_ProcessDecomposition, input=process_name)
        raw_steps = clean_markdown(step_res.final_output or getattr(step_res, 'content', '') or "")
        steps = json.loads(raw_steps).get("steps", [])
        # print(f"  - 完成分解工序: {process_name}, 工步数: {len(steps)}")
        return {"name": process_name, "steps": steps}
    except Exception as e:
        print(f"  ✗ 分解工序 {process_name} 时出错: {e}")
        return {"name": process_name, "steps": []}


# —— 缓存机制 ——
# 用于存储最近的分解结果，避免重复计算
_result_cache = {}
_cache_lock = asyncio.Lock()  # 添加锁以避免并发问题
_cache_hits = 0  # 缓存命中次数统计
_cache_misses = 0  # 缓存未命中次数统计


# —— 主流程（并行版本） ——
async def run_full_decomposition(task: str) -> dict:
    """
    完整执行：先分解任务，再并行分解每个工序，返回带 steps 的字典
    """
    global _cache_hits, _cache_misses

    # 检查缓存
    async with _cache_lock:
        if task in _result_cache:
            _cache_hits += 1
            print(f"[缓存命中] 从缓存返回结果: {task} (命中率: {_cache_hits}/{_cache_hits + _cache_misses})")
            return _result_cache[task]
        else:
            _cache_misses += 1

    print(f"[开始分解] 任务: {task}")
    start_time = time.time()

    # 1) 任务分解
    task_res = await Runner.run(agent_TaskDecomposition, input=task)
    raw_task = clean_markdown(task_res.final_output or getattr(task_res, 'content', '') or "")
    try:
        task_json = json.loads(raw_task)
    except json.JSONDecodeError:
        task_json = {"processes": []}

    # 2) 并行分解所有工序
    procs = task_json.get("processes", [])
    if procs:
        # 创建并行任务
        tasks = [decompose_single_process(proc.get("name", "")) for proc in procs]
        # 并行执行
        results = await asyncio.gather(*tasks)

        # 将结果合并回原数据
        for proc, result in zip(procs, results):
            proc["steps"] = result.get("steps", [])

    end_time = time.time()
    print(f"[分解完成] 总耗时: {end_time - start_time:.2f}秒")

    # 缓存结果（保留最近10个）
    async with _cache_lock:
        _result_cache[task] = task_json
        if len(_result_cache) > 10:
            # 删除最早的缓存项
            oldest_key = next(iter(_result_cache))
            del _result_cache[oldest_key]
        print(f"[缓存更新] 当前缓存任务数: {len(_result_cache)}")

    return task_json


async def run_decompose_stream(task: str):
    """
    SSE 版本，优化推送策略以提供更好的实时反馈
    """

    async def event_generator():
        # 1) initial status
        yield "event: status\ndata: 已接收任务，开始分解…\n\n"

        # 2) 任务分解
        task_res = await Runner.run(agent_TaskDecomposition, input=task)
        raw_task = clean_markdown(task_res.final_output or getattr(task_res, 'content', '') or "")
        try:
            task_json = json.loads(raw_task)
        except json.JSONDecodeError:
            task_json = {"processes": []}
        procs = task_json.get("processes", [])

        # 3) 进度计算
        total = 1 + len(procs)
        step = 1
        yield f"event: progress\ndata: {int((step - 1) / total * 100)}\n\n"

        # 4) 推送任务分解 chunk - 包含初始工序列表（无steps）
        yield "event: status\ndata: 正在进行任务分解…\n\n"
        yield "event: chunk\n"
        # 发送初始的任务JSON（所有工序的steps为空数组）
        for proc in procs:
            proc["steps"] = []  # 确保有steps字段
        initial_json = json.dumps(task_json, ensure_ascii=False, indent=2)
        for line in initial_json.splitlines():
            yield f"data: {line}\n"
        yield "\n"
        yield f"event: progress\ndata: {int(step / total * 100)}\n\n"

        # 5) 并行分解所有工序
        if procs:
            yield f"event: status\ndata: 正在并行分解 {len(procs)} 个工序…\n\n"

            # 创建并行任务
            tasks = [decompose_single_process(proc.get("name", "")) for proc in procs]

            # 并行执行并获取结果
            start_parallel = time.time()
            results = await asyncio.gather(*tasks)
            end_parallel = time.time()
            print(f"并行分解 {len(procs)} 个工序耗时: {end_parallel - start_parallel:.2f}秒")

            # 一次性更新所有工序的步骤
            for proc, result in zip(procs, results):
                proc["steps"] = result.get("steps", [])

            # 推送最终的完整JSON（包含所有工步）
            yield f"event: status\ndata: 所有工序分解完成，正在整理数据…\n\n"
            yield "event: chunk\n"
            # 清空之前的累积，发送一个明确的分隔符
            yield "data: ===FINAL_JSON_START===\n"
            final_json = json.dumps(task_json, ensure_ascii=False, indent=2)
            for line in final_json.splitlines():
                yield f"data: {line}\n"
            yield "data: ===FINAL_JSON_END===\n"
            yield "\n"
            yield f"event: progress\ndata: 100\n\n"

            # 等待一下确保前端接收到数据
            await asyncio.sleep(0.5)

            # 缓存结果
            _result_cache[task] = task_json
            if len(_result_cache) > 5:
                oldest_key = next(iter(_result_cache))
                del _result_cache[oldest_key]

        # 6) 完成
        yield "event: status\ndata: 分解完成！\n\n"
        yield "event: complete\ndata: 生成成功 🎉\n\n"

    return event_generator()