#kb_manager.py
import argparse
import sys
import asyncio
from pathlib import Path
from typing import Optional
from tabulate import tabulate
import json

# 假设上面的代码保存在 rag_system.py 中
from rag_system import KnowledgeBase, RAGQueryEngine, API_KEY, BASE_URL


class KnowledgeBaseManager:
    """知识库管理器 - 提供命令行和编程接口"""

    def __init__(self, base_dir: str = "./knowledge_base", api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self.kb = KnowledgeBase(
            base_dir=base_dir,
            api_key=api_key or API_KEY,
            base_url=base_url or BASE_URL
        )
        self.query_engine = RAGQueryEngine(self.kb)

    def add_document_interactive(self):
        """交互式添加文档"""
        print("\n=== 添加新文档 ===")
        print("1. 从PDF URL添加")
        print("2. 从本地PDF文件添加")
        print("3. 从文本添加")

        choice = input("请选择 (1-3): ").strip()

        title = input("文档标题: ").strip()
        domain = input("专业领域: ").strip()
        version = input("版本 (默认: 1.0): ").strip() or "1.0"

        try:
            if choice == "1":
                url = input("PDF URL: ").strip()
                max_pages = input("最大页数 (可选): ").strip()
                max_pages = int(max_pages) if max_pages else None
                doc_id = self.kb.add_document_from_url(url, title, domain, max_pages, version)

            elif choice == "2":
                file_path = input("PDF文件路径: ").strip()
                max_pages = input("最大页数 (可选): ").strip()
                max_pages = int(max_pages) if max_pages else None
                doc_id = self.kb.add_document_from_file(file_path, title, domain, max_pages, version)

            elif choice == "3":
                print("请输入文档内容 (输入END单独一行结束):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    lines.append(line)
                text = "\n".join(lines)
                doc_id = self.kb.add_document_from_text(text, title, domain, version)

            else:
                print("无效选择")
                return

            print(f"\n✅ 文档添加成功！ID: {doc_id}")

        except Exception as e:
            print(f"❌ 添加文档失败: {e}")

    def list_documents_formatted(self, domain: Optional[str] = None):
        """格式化列出文档"""
        docs = self.kb.list_documents(domain=domain)

        if not docs:
            print("📝 知识库中暂无文档")
            return

        headers = ["ID", "标题", "领域", "版本", "页数", "词数", "Token数", "创建时间"]
        rows = []

        for doc in docs:
            rows.append([
                doc.doc_id[:8] + "...",
                doc.title[:30] + ("..." if len(doc.title) > 30 else ""),
                doc.domain,
                doc.version,
                doc.page_count or "N/A",
                f"{doc.word_count:,}",
                f"{doc.token_count:,}",
                doc.created_at[:10]
            ])

        print(f"\n📚 知识库文档 ({len(docs)} 个)")
        if domain:
            print(f"🔍 过滤领域: {domain}")
        print(tabulate(rows, headers=headers, tablefmt="grid"))

    def show_domains(self):
        """显示所有领域"""
        domains = self.kb.get_domains()
        print(f"\n🏷️  知识领域 ({len(domains)} 个):")
        for i, domain in enumerate(sorted(domains), 1):
            count = len(self.kb.list_documents(domain=domain))
            print(f"  {i}. {domain} ({count} 个文档)")

    def query_interactive(self):
        """交互式查询"""
        print("\n=== 智能问答 ===")

        # 选择查询范围
        print("查询范围选择:")
        print("1. 全部文档")
        print("2. 指定领域")
        print("3. 指定文档ID")

        scope_choice = input("请选择 (1-3): ").strip()
        domain = None
        doc_ids = None

        if scope_choice == "2":
            self.show_domains()
            domain = input("请输入领域名称: ").strip()
        elif scope_choice == "3":
            self.list_documents_formatted()
            doc_ids_str = input("请输入文档ID (多个用逗号分隔): ").strip()
            doc_ids = [id.strip() for id in doc_ids_str.split(",")]

        question = input("\n❓ 请输入你的问题: ").strip()

        if not question:
            print("问题不能为空")
            return

        print("\n🔍 正在搜索相关信息...")

        try:
            # 使用同步方法查询
            result = self.query_engine.query_sync(
                question=question,
                domain=domain,
                doc_ids=doc_ids,
                max_depth=2
            )

            print(f"\n💡 答案:")
            print("=" * 60)
            print(result["answer"])
            print("=" * 60)

            print(f"\n📊 置信度: {result['confidence']}")

            if result["citations"]:
                print(f"\n📚 引用段落: {', '.join(result['citations'])}")

            # 显示引用的段落内容
            if result["paragraphs"]:
                show_sources = input("\n是否显示引用的原文段落? (y/n): ").strip().lower()
                if show_sources == 'y':
                    print(f"\n📄 引用段落内容:")
                    for i, para in enumerate(result["paragraphs"][:3], 1):  # 只显示前3个
                        display_id = para.get("display_id", str(para["id"]))
                        doc_title = para.get("doc_title", "未知文档")
                        print(f"\n段落 {i} (ID: {display_id}, 来源: {doc_title}):")
                        print("-" * 40)
                        print(para["text"][:500] + ("..." if len(para["text"]) > 500 else ""))
                        print("-" * 40)

        except Exception as e:
            print(f"❌ 查询失败: {e}")

    def remove_document_interactive(self):
        """交互式删除文档"""
        self.list_documents_formatted()

        if not self.kb.documents_metadata:
            return

        doc_id = input("\n请输入要删除的文档ID: ").strip()

        if doc_id not in self.kb.documents_metadata:
            print("❌ 未找到该文档ID")
            return

        doc_info = self.kb.documents_metadata[doc_id]
        print(f"\n将要删除文档: {doc_info.title} ({doc_info.domain})")
        confirm = input("确认删除? (y/n): ").strip().lower()

        if confirm == 'y':
            if self.kb.remove_document(doc_id):
                print("✅ 文档删除成功！")
            else:
                print("❌ 删除失败")
        else:
            print("❌ 取消删除")

    def export_knowledge_base(self, export_path: str):
        """导出知识库信息"""
        export_data = {
            "metadata": {doc_id: {
                "title": meta.title,
                "domain": meta.domain,
                "version": meta.version,
                "source_type": meta.source_type,
                "created_at": meta.created_at,
                "word_count": meta.word_count,
                "token_count": meta.token_count
            } for doc_id, meta in self.kb.documents_metadata.items()},
            "api_config": {
                "base_url": self.kb.base_url,
                "model_name": self.kb.model_name
            },
            "domains": self.kb.get_domains(),
            "total_docs": len(self.kb.documents_metadata),
            "export_time": str(Path().resolve())
        }

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 知识库信息已导出到: {export_path}")

    def show_statistics(self):
        """显示知识库统计信息"""
        docs = list(self.kb.documents_metadata.values())
        domains = self.kb.get_domains()

        if not docs:
            print("📊 知识库为空")
            return

        total_words = sum(doc.word_count for doc in docs)
        total_tokens = sum(doc.token_count for doc in docs)
        total_pages = sum(doc.page_count for doc in docs if doc.page_count)

        print("\n📊 知识库统计")
        print("=" * 40)
        print(f"🤖 AI模型: {self.kb.model_name}")
        print(f"🔗 API服务: {self.kb.base_url}")
        print(f"📚 总文档数: {len(docs)}")
        print(f"🏷️  领域数量: {len(domains)}")
        print(f"📄 总页数: {total_pages:,}")
        print(f"📝 总词数: {total_words:,}")
        print(f"🔤 总Token数: {total_tokens:,}")

        print(f"\n🏷️  按领域分布:")
        for domain in sorted(domains):
            domain_docs = self.kb.list_documents(domain=domain)
            domain_words = sum(doc.word_count for doc in domain_docs)
            print(f"  • {domain}: {len(domain_docs)} 文档, {domain_words:,} 词")

    def batch_add_documents(self, documents_config: str):
        """批量添加文档"""
        try:
            with open(documents_config, 'r', encoding='utf-8') as f:
                config = json.load(f)

            print(f"\n=== 批量添加 {len(config['documents'])} 个文档 ===")

            success_count = 0
            for i, doc_info in enumerate(config['documents'], 1):
                try:
                    print(f"\n处理文档 {i}/{len(config['documents'])}: {doc_info['title']}")

                    if doc_info['type'] == 'url':
                        doc_id = self.kb.add_document_from_url(
                            url=doc_info['source'],
                            title=doc_info['title'],
                            domain=doc_info['domain'],
                            max_pages=doc_info.get('max_pages'),
                            version=doc_info.get('version', '1.0')
                        )
                    elif doc_info['type'] == 'file':
                        doc_id = self.kb.add_document_from_file(
                            file_path=doc_info['source'],
                            title=doc_info['title'],
                            domain=doc_info['domain'],
                            max_pages=doc_info.get('max_pages'),
                            version=doc_info.get('version', '1.0')
                        )
                    elif doc_info['type'] == 'text':
                        doc_id = self.kb.add_document_from_text(
                            text=doc_info['source'],
                            title=doc_info['title'],
                            domain=doc_info['domain'],
                            version=doc_info.get('version', '1.0')
                        )

                    print(f"✅ 成功添加: {doc_id}")
                    success_count += 1

                except Exception as e:
                    print(f"❌ 添加失败: {e}")

            print(f"\n📊 批量添加完成: {success_count}/{len(config['documents'])} 成功")

        except Exception as e:
            print(f"❌ 批量添加失败: {e}")

    def run_interactive_menu(self):
        """运行交互式菜单"""
        while True:
            print("\n" + "=" * 60)
            print("🧠 专家知识库管理系统 (DeepSeek-V3)")
            print(f"🔗 API服务: {self.kb.base_url}")
            print("=" * 60)
            print("1. 📝 添加文档")
            print("2. 📚 查看文档列表")
            print("3. 🏷️ 查看知识领域")
            print("4. ❓ 智能问答")
            print("5. 🗑️ 删除文档")
            print("6. 📊 统计信息")
            print("7. 💾 导出知识库信息")
            print("8. 📦 批量添加文档")
            print("9. 🧪 测试API连接")
            print("0. 🚪 退出")

            choice = input("\n请选择功能 (0-9): ").strip()

            try:
                if choice == "1":
                    self.add_document_interactive()
                elif choice == "2":
                    domain = input("过滤领域 (可选): ").strip() or None
                    self.list_documents_formatted(domain)
                elif choice == "3":
                    self.show_domains()
                elif choice == "4":
                    self.query_interactive()
                elif choice == "5":
                    self.remove_document_interactive()
                elif choice == "6":
                    self.show_statistics()
                elif choice == "7":
                    export_path = input("导出文件路径 (默认: kb_export.json): ").strip() or "kb_export.json"
                    self.export_knowledge_base(export_path)
                elif choice == "8":
                    config_path = input("配置文件路径 (默认: batch_config.json): ").strip() or "batch_config.json"
                    self.batch_add_documents(config_path)
                elif choice == "9":
                    self.test_api_connection()
                elif choice == "0":
                    print("👋 再见！")
                    break
                else:
                    print("❌ 无效选择，请重试")

            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"❌ 操作失败: {e}")

    def test_api_connection(self):
        """测试API连接"""
        print("\n=== 测试API连接 ===")
        try:
            # 使用同步方式测试连接
            result = self.query_engine.query_sync("测试连接")
            print("✅ API连接正常")
            print(f"🤖 模型: {self.kb.model_name}")
            print(f"🔗 服务: {self.kb.base_url}")
        except Exception as e:
            print(f"❌ API连接失败: {e}")
            print("请检查API密钥和网络连接")


def create_batch_config_template():
    """创建批量添加文档的配置模板"""
    template = {
        "documents": [
            {
                "type": "text",
                "source": "这里放入文档的文本内容...",
                "title": "文档标题1",
                "domain": "专业领域1",
                "version": "1.0",
                "max_pages": None
            },
            {
                "type": "file",
                "source": "./path/to/document.pdf",
                "title": "文档标题2",
                "domain": "专业领域2",
                "version": "1.0",
                "max_pages": 100
            },
            {
                "type": "url",
                "source": "https://example.com/document.pdf",
                "title": "文档标题3",
                "domain": "专业领域3",
                "version": "1.0",
                "max_pages": 50
            }
        ]
    }

    with open("batch_config_template.json", 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    print("📝 批量配置模板已创建: batch_config_template.json")


def create_cli():
    """创建命令行接口"""
    parser = argparse.ArgumentParser(description="专家知识库管理系统 (DeepSeek-V3)")
    parser.add_argument("--base-dir", default="./knowledge_base", help="知识库目录")
    parser.add_argument("--api-key", help="API密钥")
    parser.add_argument("--base-url", help="API服务地址")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 添加文档命令
    add_parser = subparsers.add_parser("add", help="添加文档")
    add_parser.add_argument("--type", choices=["url", "file", "text"], required=True, help="文档类型")
    add_parser.add_argument("--source", required=True, help="文档源 (URL/文件路径/文本)")
    add_parser.add_argument("--title", required=True, help="文档标题")
    add_parser.add_argument("--domain", required=True, help="知识领域")
    add_parser.add_argument("--version", default="1.0", help="版本号")
    add_parser.add_argument("--max-pages", type=int, help="最大页数")

    # 查询命令
    query_parser = subparsers.add_parser("query", help="查询问答")
    query_parser.add_argument("question", help="问题")
    query_parser.add_argument("--domain", help="限制查询领域")
    query_parser.add_argument("--doc-ids", nargs="+", help="限制查询文档ID")
    query_parser.add_argument("--max-depth", type=int, default=2, help="最大搜索深度")

    # 列出文档命令
    list_parser = subparsers.add_parser("list", help="列出文档")
    list_parser.add_argument("--domain", help="过滤领域")

    # 删除文档命令
    remove_parser = subparsers.add_parser("remove", help="删除文档")
    remove_parser.add_argument("doc_id", help="文档ID")

    # 批量添加命令
    batch_parser = subparsers.add_parser("batch", help="批量添加文档")
    batch_parser.add_argument("config_file", help="配置文件路径")

    # 统计命令
    subparsers.add_parser("stats", help="显示统计信息")

    # 测试连接命令
    subparsers.add_parser("test", help="测试API连接")

    # 创建模板命令
    subparsers.add_parser("template", help="创建批量配置模板")

    # 交互模式命令
    subparsers.add_parser("interactive", help="进入交互模式")

    return parser


def main():
    """主函数"""
    parser = create_cli()
    args = parser.parse_args()

    if not args.command:
        # 如果没有提供命令，进入交互模式
        manager = KnowledgeBaseManager(args.base_dir, args.api_key, args.base_url)
        manager.run_interactive_menu()
        return

    if args.command == "template":
        create_batch_config_template()
        return

    manager = KnowledgeBaseManager(args.base_dir, args.api_key, args.base_url)

    try:
        if args.command == "add":
            if args.type == "url":
                doc_id = manager.kb.add_document_from_url(
                    args.source, args.title, args.domain, args.max_pages, args.version
                )
            elif args.type == "file":
                doc_id = manager.kb.add_document_from_file(
                    args.source, args.title, args.domain, args.max_pages, args.version
                )
            elif args.type == "text":
                doc_id = manager.kb.add_document_from_text(
                    args.source, args.title, args.domain, args.version
                )
            print(f"✅ 文档添加成功！ID: {doc_id}")

        elif args.command == "query":
            result = manager.query_engine.query_sync(
                args.question, args.domain, args.doc_ids, args.max_depth
            )
            print(f"💡 答案: {result['answer']}")
            print(f"📊 置信度: {result['confidence']}")
            if result['citations']:
                print(f"📚 引用: {', '.join(result['citations'])}")

        elif args.command == "list":
            manager.list_documents_formatted(args.domain)

        elif args.command == "remove":
            if manager.kb.remove_document(args.doc_id):
                print("✅ 文档删除成功！")
            else:
                print("❌ 未找到该文档")

        elif args.command == "batch":
            manager.batch_add_documents(args.config_file)

        elif args.command == "stats":
            manager.show_statistics()

        elif args.command == "test":
            manager.test_api_connection()

        elif args.command == "interactive":
            manager.run_interactive_menu()

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()