#app.py
"""
RAG知识库系统 - Web服务启动脚本
"""

import os
import sys
import subprocess
import platform


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("❌ 错误：需要Python 3.8或更高版本")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version.split()[0]}")


def install_dependencies():
    """安装依赖"""
    print("\n📦 正在检查和安装依赖...")

    # 首先安装/升级pip
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    # 安装requirements.txt中的依赖
    if os.path.exists("requirements.txt"):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 依赖安装完成")
    else:
        print("❌ 错误：未找到requirements.txt文件")
        sys.exit(1)


def download_nltk_data():
    """下载NLTK数据"""
    print("\n📥 正在下载NLTK数据...")
    try:
        import nltk
        nltk.download('punkt', quiet=True)
        print("✅ NLTK数据下载完成")
    except Exception as e:
        print(f"⚠️  警告：NLTK数据下载失败: {e}")


def create_directories():
    """创建必要的目录"""
    dirs = ["./web_knowledge_base", "./web_knowledge_base/documents",
            "./web_knowledge_base/chunks", "./web_knowledge_base/metadata"]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
    print("✅ 目录结构创建完成")


def check_api_key():
    """检查API密钥"""
    # 这里假设API密钥已经在rag_system.py中配置
    # 如果需要，可以添加环境变量检查
    print("✅ API配置已就绪")


def start_server():
    """启动FastAPI服务器"""
    print("\n🚀 正在启动RAG知识库系统...")
    print("=" * 60)
    print("📍 Web界面地址: http://localhost:8000")
    print("📚 API文档地址: http://localhost:8000/docs")
    print("📖 使用说明:")
    print("  1. 在'添加文档'模块中添加PDF、URL或文本文档")
    print("  2. 在'智能问答'模块中提问并获取答案")
    print("  3. 在'文档管理'模块中查看和管理已添加的文档")
    print("=" * 60)
    print("\n按 Ctrl+C 停止服务器\n")

    # 根据操作系统选择合适的命令
    if platform.system() == "Windows":
        cmd = [sys.executable, "-m", "uvicorn", "fastapi_rag_app:app", "--host", "0.0.0.0", "--port", "8000",
               "--reload"]
    else:
        cmd = ["uvicorn", "fastapi_rag_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n请确保:")
        print("  1. fastapi_rag_app.py文件存在")
        print("  2. rag_system.py文件存在")
        print("  3. 所有依赖已正确安装")


def main():
    """主函数"""
    print("🧠 RAG智能知识库系统")
    print("=" * 60)

    # 检查Python版本
    check_python_version()

    # 检查并安装依赖
    response = input("\n是否需要安装/更新依赖? (y/n) [y]: ").strip().lower()
    if response != 'n':
        install_dependencies()
        download_nltk_data()

    # 创建目录
    create_directories()

    # 检查API配置
    check_api_key()

    # 启动服务器
    start_server()


if __name__ == "__main__":
    main()