# doc-knowledge-base 项目计划

将大型文档转 Markdown、切片、存入向量库，并通过 MCP Server 供 opencode 等 CLI 工具检索调用，大幅节省 token 消耗。

## 架构概览

```
document.pdf/.docx/...
    │
    ▼
┌──────────────────┐
│  doc2md 转换器    │  ← markitdown (微软出品)
└────────┬─────────┘
         ▼  .md
┌──────────────────┐
│  text 切片器      │  ← 语义分块 + overlap
└────────┬─────────┘
         ▼  chunks
┌──────────────────┐
│  向量化 + 存储    │  ← sentence-transformers + ChromaDB
└────────┬─────────┘
         ▼
┌──────────────────┐
│  MCP Server      │  ← 供 opencode 调用 (search_docs / list_docs)
└──────────────────┘
```

## 技术栈

| 模块 | 方案 |
|------|------|
| 文档→MD | `markitdown` (微软出品，支持 PDF/DOCX/PPTX/HTML 等) |
| 切片 | 自定义 markdown 结构感知分块器 |
| 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` (本地，~80MB) |
| 向量库 | `ChromaDB` (纯本地嵌入式，零配置) |
| MCP 协议 | `mcp` Python SDK (stdio 传输) |
| CLI | `click` 命令行框架 |

## 项目结构

```
doc-knowledge-base/
├── doc_kb/                  # Python 包
│   ├── __init__.py
│   ├── converter.py         # 文档 → Markdown
│   ├── chunker.py           # Markdown → 切片
│   ├── vector_store.py      # 向量库 CRUD + 检索
│   ├── cli.py               # CLI 入口
│   └── mcp_server.py        # MCP Server
├── data/
│   ├── raw/                 # 原始文档
│   ├── md/                  # 转换后的 Markdown
│   └── chroma/              # ChromaDB 持久化
├── pyproject.toml
├── PLAN.md
└── README.md
```

## 实施步骤

### 阶段 1：文档 → MD 转换
- 使用 `markitdown` 实现 PDF/DOCX/PPTX/HTML → Markdown
- 支持单文件和批量目录导入
- 输出到 `data/md/`

### 阶段 2：Markdown 切片
- 按标题层级（h1-h6）解析文档结构
- 维护标题路径作为上下文元数据
- 对超长段落实行递归字符分割
- 可配置 chunk_size / chunk_overlap

### 阶段 3：向量化 + 存储
- ChromaDB PersistentClient 持久化到 `data/chroma/`
- sentence-transformers 本地嵌入
- 增量导入去重（按文档名 + 块哈希）
- 余弦相似度检索，返回 top-k 结果

### 阶段 4：CLI 工具
- `doc-kb import <file/dir>` — 导入文档
- `doc-kb list` — 列出已导入文档
- `doc-kb query "<text>"` — 检索测试
- `doc-kb serve` — 启动 MCP Server

### 阶段 5：MCP Server
- 实现 MCP 协议 stdio 传输
- 暴露 tools:
  - `search_docs(query, top_k=5)`: 语义搜索
  - `list_docs()`: 列出知识库文档
- opencode 侧配置:

```json
{
  "mcp": {
    "doc-kb": {
      "type": "local",
      "command": ["doc-kb", "serve"],
      "enabled": true
    }
  }
}
```

## 集成效果

在 opencode 对话中，LLM 会自动调用 `search_docs` 检索相关文档片段，**只把命中片段送入上下文**，而非整篇文档，大幅减少 token 消耗。
