# doc-knowledge-base

将大型文档转 Markdown → 切片 → 存向量库 → 通过 MCP Server 供 Claude Code、opencode 等 CLI 工具检索，大幅节省 token 消耗。

## 快速开始

```bash
# 从源码安装
git clone https://github.com/q510130010q/doc-knowledge-base.git
cd doc-knowledge-base
pip install .

# 导入文档
doc-kb import-doc document.pdf

# 查询
doc-kb query "你的问题"

# 启动 MCP Server（供 opencode 调用）
doc-kb serve
```

> 本项目尚未发布到 PyPI，需从源码安装。开发模式可使用 `pip install -e .`。

## 架构

```
document.pdf/.docx → MarkItDown → Markdown → 切片器 → ChromaDB → MCP Server
```

## opencode 集成

在 `opencode.json` 中添加：

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

之后在 opencode 对话中，LLM 会自动调用 `search_docs` 检索知识库。

## Claude Code 集成

在项目根目录创建 `claude.json`：

```json
{
  "mcpServers": {
    "doc-kb": {
      "command": "doc-kb",
      "args": ["serve"]
    }
  }
}
```

或在全局配置 `~/.claude/settings.json` 中添加相同内容。之后在 Claude Code 中即可通过 MCP 工具 `search_docs` 检索知识库。

## CLI 命令

| 命令 | 说明 |
|------|------|
| `doc-kb import-doc <file/dir>` | 导入文档（PDF/DOCX/PPTX/HTML/...） |
| `doc-kb list` | 列出知识库文档 |
| `doc-kb query <text>` | 检索知识库 |
| `doc-kb serve` | 启动 MCP Server |

## 技术栈

- **文档转换**: [markitdown](https://github.com/microsoft/markitdown) (微软)
- **切片**: `langchain-text-splitters` + 自定义结构感知分块
- **嵌入**: `sentence-transformers/all-MiniLM-L6-v2` (本地)
- **向量库**: ChromaDB (本地持久化)
- **协议**: MCP (Model Context Protocol) via stdio
