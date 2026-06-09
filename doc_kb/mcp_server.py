import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from doc_kb.vector_store import VectorStore


server = Server("doc-kb")
_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_docs",
            description="Search the document knowledge base. Returns relevant text snippets from imported documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query to search for",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (1-20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_docs",
            description="List all documents available in the knowledge base.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    store = get_store()

    if name == "search_docs":
        query = arguments.get("query", "")
        top_k = min(int(arguments.get("top_k", 5)), 20)
        results = await asyncio.to_thread(store.search, query, top_k)
        if not results:
            return [TextContent(type="text", text="No relevant documents found in the knowledge base.")]

        lines = [f"Found {len(results)} result(s):\n"]
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            source = meta.get("source", "?")
            heading = meta.get("heading_path", "")
            score = 1 - r.get("distance", 0)
            lines.append(f"[{i}] {source}  {heading}  (relevance: {score:.3f})")
            lines.append(r["text"].strip())
            lines.append("")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "list_docs":
        sources = await asyncio.to_thread(store.list_sources)
        count = await asyncio.to_thread(store.count_chunks)
        if not sources:
            return [TextContent(type="text", text="Knowledge base is empty. Import documents using `doc-kb import`.")]
        lines = [f"Knowledge base: {count} chunks from {len(sources)} document(s):"]
        for s in sources:
            lines.append(f"- {s}")
        return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def main():
    async def _run():
        async with stdio_server() as (read, write):
            await server.run(
                read,
                write,
                server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
