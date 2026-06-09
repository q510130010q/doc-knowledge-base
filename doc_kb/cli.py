import sys
from pathlib import Path

import click

from doc_kb.converter import Converter, ConversionError
from doc_kb.chunker import Chunker
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
def import_doc(path, chunk_size, chunk_overlap, reset, replace):
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
        for ext in Converter.SUPPORTED_EXTENSIONS:
            files.extend(input_path.glob(f"*{ext}"))
            files.extend(input_path.glob(f"*{ext.upper()}"))

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
@click.argument("query")
@click.option("--top-k", default=5, show_default=True, help="Number of results")
def query(query, top_k):
    store = VectorStore()
    results = store.search(query, top_k=top_k)
    if not results:
        click.echo("No results found.")
        return
    click.echo(f"Top {len(results)} results for: {query}\n")
    for r in results:
        heading = r["metadata"].get("heading_path", "")
        source = r["metadata"].get("source", "")
        dist = r.get("distance", 0)
        click.echo(f"[{source}] {heading}  (score: {1 - dist:.4f})")
        click.echo(f"  {r['text'][:200]}...")
        click.echo()


@cli.command()
def serve():
    from doc_kb.mcp_server import main
    main()


if __name__ == "__main__":
    cli()
