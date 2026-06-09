import sys
from pathlib import Path

import click

from doc_kb.vector_store import VectorStore


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


@click.group()
def cli():
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--chunk-size", default=1000, show_default=True, help="Chunk size in characters")
@click.option("--chunk-overlap", default=200, show_default=True, help="Chunk overlap in characters")
@click.option("--reset", is_flag=True, help="Clear existing data before import")
@click.option("--replace", is_flag=True, help="Replace existing document if already imported")
@click.option("-r", "--recursive", is_flag=True, help="Recursively import documents from subdirectories")
def import_doc(path, chunk_size, chunk_overlap, reset, replace, recursive):
    from doc_kb.converter import Converter, ConversionError
    from doc_kb.chunker import Chunker

    converter = Converter()
    chunker = Chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    store = VectorStore()

    if reset:
        store.reset()
        click.echo("Vector store reset.")

    input_path = Path(path)
    if input_path.is_file():
        files = [input_path]
    else:
        files = []
        search_fn = input_path.rglob if recursive else input_path.glob
        for ext in Converter.SUPPORTED_EXTENSIONS:
            files.extend(search_fn(f"*{ext}"))
            files.extend(search_fn(f"*{ext.upper()}"))

    if not files:
        click.echo("No supported documents found.", err=True)
        sys.exit(1)

    total_chunks = 0
    for f in sorted(set(files)):
        try:
            md_path = converter.convert(f)
            source_name = md_path.stem

            if replace:
                deleted = store.delete_source(source_name)
                if deleted:
                    click.echo(f"  Removed {deleted} old chunks for '{source_name}'")

            chunks = chunker.chunk_file(md_path, source=source_name)
            added = store.add_chunks(chunks)
            total_chunks += added
            click.echo(f"  {source_name} -> {len(chunks)} chunks")
        except ConversionError as e:
            click.echo(f"  {f.name}: SKIPPED ({e})", err=True)

    click.echo(f"Done. {total_chunks} total chunks in knowledge base.")


@cli.command("list")
def list_docs():
    store = VectorStore()
    sources = store.list_sources()
    count = store.count_chunks()
    if not sources:
        click.echo("Knowledge base is empty.")
        return
    click.echo(f"Knowledge base: {count} chunks from {len(sources)} document(s)")
    for s in sources:
        click.echo(f"  - {s}")


@cli.command()
@click.argument("source")
def remove(source):
    store = VectorStore()
    deleted = store.delete_source(source)
    if deleted:
        click.echo(f"Removed {deleted} chunks for '{source}'.")
    else:
        click.echo(f"Source '{source}' not found.")


@cli.command()
@click.argument("query_str", required=False)
@click.option("--top-k", default=5, show_default=True, help="Number of results")
@click.option("-i", "--interactive", is_flag=True, help="Enter interactive query mode")
@click.option("-v", "--verbose", is_flag=True, help="Display the full content of chunks (no truncation)")
def query(query_str, top_k, interactive, verbose):
    if not query_str and not interactive:
        click.echo("Error: Missing argument 'QUERY_STR' or option '--interactive'.", err=True)
        sys.exit(1)

    store = VectorStore()

    def run_one_query(q):
        results = store.search(q, top_k=top_k)
        if not results:
            click.echo("No results found.")
            return
        click.echo(f"Top {len(results)} results for: {q}\n")
        for r in results:
            heading = r["metadata"].get("heading_path", "")
            source = r["metadata"].get("source", "")
            dist = r.get("distance", 0)
            click.echo(f"[{source}] {heading}  (score: {1 - dist:.4f})")
            
            text = r['text']
            if not verbose:
                display_text = text.replace("\n", " ")
                if len(display_text) > 200:
                    display_text = display_text[:200] + "..."
                click.echo(f"  {display_text}")
            else:
                indented = "\n".join("  " + line for line in text.split("\n"))
                click.echo(indented)
            click.echo()

    if interactive:
        click.echo("Entering interactive query mode. Press Ctrl+C or type 'exit' or 'quit' to exit.")
        click.echo("Loading embedding model, please wait...")
        _ = store.embedding_fn(["init"])
        click.echo("Model loaded. Ready.")
        click.echo()
        while True:
            try:
                q = click.prompt("query")
                q_strip = q.strip()
                if q_strip.lower() in {"exit", "quit"}:
                    break
                if not q_strip:
                    continue
                run_one_query(q_strip)
            except (KeyboardInterrupt, click.Abort):
                click.echo("\nExiting.")
                break
    else:
        run_one_query(query_str)


@cli.command()
def serve():
    from doc_kb.mcp_server import main
    main()


if __name__ == "__main__":
    cli()
