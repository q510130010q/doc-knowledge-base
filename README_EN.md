# doc-knowledge-base

Convert large documents to Markdown → Chunk → Store in Vector DB → Search via MCP Server for CLI tools like Claude Code and opencode, saving ~50% in token usage.

## Quick Start

```bash
# 1. Install from source
git clone https://github.com/q510130010q/doc-knowledge-base.git
cd doc-knowledge-base
pip install .

# 2. Configure integration (e.g., for opencode)
# Add the MCP configuration to opencode.json (see details under Integration below)

# 3. Start opencode; the MCP Server will automatically run with it
# For Claude Code, you may need to start it manually: doc-kb serve

# 4. Import documents into the knowledge base
doc-kb import-doc document.pdf

# 5. Ask questions in your chat; the LLM will automatically call search_docs to query the KB
```

> This project is not yet published on PyPI. It must be installed from source. For development, use `pip install -e .`.

> Correct workflow: **Install → Configure Integration → Run opencode (MCP runs automatically) → Import → Query**

## Architecture

```
document.pdf/.docx/.md → (MarkItDown / Direct Read) → Markdown → Chunker → ChromaDB → MCP Server
```

## opencode Integration

Add the following to your `opencode.json`:

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

Once configured, the LLM will automatically call the `search_docs` tool to retrieve knowledge from your database.

## Claude Code Integration

Create a `claude.json` file in the root of your project:

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

Alternatively, add the same configuration block to the global settings at `~/.claude/settings.json`. Claude Code will then be able to retrieve knowledge via the `search_docs` MCP tool.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `doc-kb import-doc [options] <file/dir>` | Import documents (PDF, DOCX, PPTX, HTML, MD, TXT, etc.) |
| `doc-kb list` | List all documents in the knowledge base (Fast sub-second startup) |
| `doc-kb query [options] <text>` | Search the knowledge base |
| `doc-kb remove <source>` | Delete all chunks associated with a specific document |
| `doc-kb serve` | Start the MCP Server |

### import-doc Options

| Option | Description |
|--------|-------------|
| `--reset` | Clear the entire vector store before importing. |
| `--replace` | Replace only documents with the same name (deletes old chunks before importing the new version). |
| `-r`, `--recursive` | **[New]** Recursively scan and import documents from subdirectories. |
| `--chunk-size` | Target character count per chunk (default: 1000). |
| `--chunk-overlap` | Overlap character count between chunks (default: 200). |

> **Re-import Strategy**: Use `--replace` instead of `--reset` to update individual files in place without losing other imported documents.

### query Options

| Option | Description |
|--------|-------------|
| `--top-k <num>` | Number of retrieval results to return (default: 5). |
| `-i`, `--interactive` | **[New]** Enter interactive query mode. The embedding model stays loaded in memory, enabling instant subsequent queries—perfect for debugging and testing. |
| `-v`, `--verbose` | **[New]** Print the full chunk text (with formatting) instead of truncating to 200 characters. |

---

## Tech Stack

- **Document Conversion**: [markitdown](https://github.com/microsoft/markitdown) (by Microsoft) + native Markdown parser
- **Chunking**: `langchain-text-splitters` + custom structure-aware chunking (with Chinese sentence splitting)
- **Embeddings**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (local, supporting English & Chinese)
- **Vector Database**: ChromaDB (local persistence)
- **Protocol**: MCP (Model Context Protocol) via stdio

---

## Optimized Features

- **Direct Markdown Support**: Automatically recognizes `.md` and `.markdown` files to bypass `markitdown` processing, allowing for instant and lossless document imports.
- **Fast CLI Responsiveness**: Leverages lazy loading for `VectorStore` initialization and heavy imports (`langchain`, `markitdown`). Management commands like `list` and `remove` launch in sub-seconds by skipping the neural network loading phase.
- **Chinese Sentence Boundary Detection**: The chunker respects Chinese punctuation marks (`。`, `？`, `！`) as sentence boundaries, producing more coherent and natural chunks.
- **Chinese Heading Recognition**: Built-in rules identify Chinese chapter and section markers (e.g. `第N章`, `第N节`, `一、`, `（一）`) to construct section paths.
- **Hybrid Search Code Identifiers**: Automatically detects code identifiers (supporting PascalCase, camelCase, and snake_case API naming styles) and boosts chunks containing target instructions.
- **Asynchronous MCP Server**: Defers VectorStore initialization until the first tool request. Synchronous operations run in a background thread to prevent blocking the event loop.
