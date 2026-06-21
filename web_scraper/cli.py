"""Command-line interface for the web scraper."""

import logging
import os
from pathlib import Path
from typing import Optional

import click
from validators import url as validate_url

from . import __version__
from .agent import ContentAgent, OllamaClient
from .constants import DEFAULT_OLLAMA_EMBED_MODEL, DEFAULT_OLLAMA_MODEL
from .logging_config import configure_logging
from .scraper import WebScraper
from .utils import extract_links_from_html


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--verbose", "-v", is_flag=True, help="Enable verbose logging"
)
def cli(verbose: bool) -> None:
    """Web Scraper v2 - Extract text content from websites."""
    configure_logging(verbose=verbose)


@cli.command()
@click.argument("url")
@click.option(
    "--output-dir",
    "-o",
    default="./scraped_docs/scraped_data",
    help="Output directory for scraped content (default: ./scraped_docs/scraped_data)",
)
@click.option(
    "--max-files",
    "-m",
    default=300,
    type=click.IntRange(1, 1000),
    help="Maximum number of files to create (default: 300)",
)
@click.option(
    "--delay",
    "-d",
    default=0.5,
    type=float,
    help="Delay between requests in seconds (default: 0.5, to avoid rate limits)",
)
@click.option(
    "--timeout",
    "-t",
    default=10,
    type=int,
    help="Request timeout in seconds (default: 10)",
)
@click.option(
    "--include-external",
    is_flag=True,
    help="Include external links (default: internal only)",
)
@click.option(
    "--subdomain",
    "-s",
    default=None,
    help="Only scrape pages under this host (e.g. docs.example.com). "
    "You can include a path (e.g. platform.claude.com/docs/en) to also restrict to that path.",
)
@click.option(
    "--path-prefix",
    "-p",
    default=None,
    help="Only scrape URLs whose path starts with this prefix (e.g. /docs/en).",
)
@click.option(
    "--yes",
    "-y",
    "force",
    is_flag=True,
    help="Overwrite into existing output directory without prompting.",
)
@click.option(
    "--user-agent",
    default="WebScraper/2.0",
    help="User agent string (default: WebScraper/2.0)",
)
@click.option(
    "--use-browser",
    is_flag=True,
    help="Fetch each page with a headless browser (for JS-rendered content like cursor.com/docs).",
)
@click.option(
    "--agent/--no-agent",
    default=True,
    help="Process pages with the Ollama agent (default: enabled).",
)
@click.option(
    "--model",
    default=None,
    help=f"Ollama model for generation (default: OLLAMA_MODEL env or {DEFAULT_OLLAMA_MODEL}).",
)
@click.option(
    "--embed-model",
    default=None,
    help=f"Ollama model for embeddings (default: OLLAMA_EMBED_MODEL or {DEFAULT_OLLAMA_EMBED_MODEL}).",
)
@click.option(
    "--similarity-threshold",
    default=None,
    type=float,
    help="Cosine similarity threshold for consolidation (default: 0.85).",
)
def scrape(
    url: str,
    output_dir: str,
    max_files: int,
    delay: float,
    timeout: int,
    include_external: bool,
    subdomain: Optional[str],
    path_prefix: Optional[str],
    force: bool,
    user_agent: str,
    use_browser: bool,
    agent: bool,
    model: Optional[str],
    embed_model: Optional[str],
    similarity_threshold: Optional[float],
) -> None:
    """
    Scrape a website and extract text content.
    
    URL: The starting URL to scrape
    """
    # Validate URL
    if not validate_url(url):
        click.echo(f"Error: Invalid URL: {url}", err=True)
        raise click.Abort()

    # Create output directory
    output_path = Path(output_dir)
    if output_path.exists() and any(output_path.iterdir()) and not force:
        if not click.confirm(
            f"Output directory '{output_dir}' exists and is not empty. Continue?"
        ):
            raise click.Abort()

    # Initialize scraper
    scraper = WebScraper(
        max_files=max_files,
        delay=delay,
        timeout=timeout,
        user_agent=user_agent,
        use_browser=use_browser,
    )

    content_agent: Optional[ContentAgent] = None
    if agent:
        try:
            logging.getLogger(__name__).info(
                "Initializing agent (ChromaDB connects on first document)"
            )
            ollama = OllamaClient(
                host=os.getenv("OLLAMA_HOST"),
                model=model,
                embed_model=embed_model,
            )
            ollama.ensure_models()
            content_agent = ContentAgent(
                output_dir=output_dir,
                ollama=ollama,
                memory=None,
                similarity_threshold=similarity_threshold,
            )
        except ImportError as exc:
            click.echo(
                "Error: agent mode requires chromadb and httpx. "
                "Run: pip install -r requirements.txt",
                err=True,
            )
            raise click.Abort() from exc
        except ValueError as exc:
            click.echo(
                f"Error: {exc}\n"
                "Start ChromaDB (e.g. docker compose up -d chromadb) or use --no-agent.",
                err=True,
            )
            raise click.Abort() from exc
        except Exception as exc:
            click.echo(
                f"Error: cannot initialize agent ({exc}).\n"
                "Ensure Ollama and ChromaDB are running, or use --no-agent.",
                err=True,
            )
            raise click.Abort() from exc

    try:
        # Start scraping
        click.echo(f"Starting to scrape: {url}")
        click.echo(f"Output directory: {output_path.absolute()}")
        click.echo(f"Max files: {max_files}")
        click.echo(f"Include external links: {'Yes' if include_external else 'No'}")
        click.echo(
            f"Subdomain filter: {subdomain if subdomain else '(same host as start URL)'}"
        )
        click.echo(f"Path prefix: {path_prefix if path_prefix else '(none)'}")
        click.echo(f"Use browser: {'Yes' if use_browser else 'No'}")
        click.echo(f"Agent mode: {'Yes' if agent else 'No (legacy direct save)'}")
        if agent:
            click.echo(
                f"Ollama model: {model or os.getenv('OLLAMA_MODEL', DEFAULT_OLLAMA_MODEL)}"
            )
            click.echo(
                "Embed model: "
                f"{embed_model or os.getenv('OLLAMA_EMBED_MODEL', DEFAULT_OLLAMA_EMBED_MODEL)}"
            )
            threshold = similarity_threshold or float(
                os.getenv("SIMILARITY_THRESHOLD", "0.85")
            )
            click.echo(f"Similarity threshold: {threshold}")
        click.echo("-" * 50)

        results = scraper.scrape_website(
            start_url=url,
            output_dir=output_dir,
            include_external=include_external,
            allowed_subdomain=subdomain,
            path_prefix=path_prefix,
            agent=content_agent,
        )

        # Display results
        click.echo("\n" + "=" * 50)
        click.echo("SCRAPING COMPLETED")
        click.echo("=" * 50)
        click.echo(f"Files created: {results['files_created']}")
        click.echo(f"Pages processed: {results.get('pages_processed', results['files_created'])}")
        click.echo(f"URLs scraped: {results['urls_scraped']}")
        click.echo(f"URLs failed: {results['urls_failed']}")
        click.echo(f"Output directory: {results['output_directory']}")

        if "agent_stats" in results:
            agent_stats = results["agent_stats"]
            click.echo("\nAgent decisions:")
            click.echo(f"  Saved: {agent_stats['saved']}")
            click.echo(f"  Consolidated: {agent_stats['consolidated']}")
            click.echo(f"  Skipped: {agent_stats['skipped']}")
            click.echo(f"  Errors: {agent_stats['errors']}")

        # Display statistics
        stats = scraper.get_stats()
        click.echo(f"\nSuccess rate: {stats['success_rate']:.1%}")

        if results['files_created'] == max_files:
            click.echo(f"\nNote: Reached maximum file limit ({max_files})")

    except KeyboardInterrupt:
        click.echo("\nScraping interrupted by user")
        stats = scraper.get_stats()
        if stats['content_files'] > 0:
            click.echo(f"Scraped {stats['content_files']} files before interruption")
    except Exception as e:
        click.echo(f"Error during scraping: {e}", err=True)
        raise click.Abort()


@cli.command("extract-urls")
@click.option(
    "--base",
    "-b",
    "base_url",
    required=True,
    help="Base URL to resolve relative hrefs (e.g. https://cursor.com)",
)
@click.option(
    "--path-prefix",
    "-p",
    default=None,
    help="Only output URLs whose path starts with this prefix (e.g. /docs).",
)
@click.argument(
    "html_file",
    type=click.Path(path_type=Path),
    required=False,
)
def extract_urls(
    base_url: str,
    path_prefix: Optional[str],
    html_file: Optional[Path],
) -> None:
    """
    Extract <a href> URLs from HTML (e.g. a saved sidenav snippet).
    Prints one absolute URL per line.

    Example:
      python -m web_scraper extract-urls -b https://cursor.com -p /docs sidenav.html
    """
    if not validate_url(base_url):
        click.echo(f"Error: Invalid base URL: {base_url}", err=True)
        raise click.Abort()
    if html_file:
        html = html_file.read_text(encoding="utf-8")
    else:
        click.echo("Reading HTML from stdin...", err=True)
        html = click.get_text_stream("stdin").read()
    urls = extract_links_from_html(html, base_url, path_prefix=path_prefix)
    for u in urls:
        click.echo(u)


@cli.command("discover-urls")
@click.argument("url")
@click.option(
    "--path-prefix",
    "-p",
    default=None,
    help="Only output URLs whose path starts with this prefix (e.g. /docs).",
)
@click.option(
    "--wait",
    "-w",
    default=2.0,
    type=float,
    help="Seconds to wait after load for JS to render (default: 2).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(path_type=Path),
    help="Write URLs to this file (default: print to stdout).",
)
def discover_urls(
    url: str,
    path_prefix: Optional[str],
    wait: float,
    output_file: Optional[Path],
) -> None:
    """
    Load a URL in a headless browser and extract <a href> links (for JS-rendered sites).

    Use when a site (e.g. cursor.com/docs) only shows links after JavaScript runs.
    Requires: pip install playwright && playwright install chromium.

    Example:
      python -m web_scraper discover-urls https://cursor.com/docs -p /docs -o urls.txt
    """
    if not validate_url(url):
        click.echo(f"Error: Invalid URL: {url}", err=True)
        raise click.Abort()
    try:
        from .browser import extract_links_from_page
    except ImportError as e:
        click.echo(
            "Error: Playwright is required. Run: pip install playwright && playwright install chromium",
            err=True,
        )
        raise click.Abort() from e
    click.echo(f"Loading {url} in browser (wait {wait}s for JS)...", err=True)
    urls = extract_links_from_page(url, base_url=url, path_prefix=path_prefix, wait_seconds=wait)
    click.echo(f"Found {len(urls)} link(s).", err=True)
    if output_file:
        output_file.write_text("\n".join(urls) + "\n", encoding="utf-8")
        click.echo(f"Wrote to {output_file}", err=True)
    else:
        for u in urls:
            click.echo(u)


@cli.command()
@click.argument("url")
def validate(url: str) -> None:
    """Validate a URL without scraping."""
    if validate_url(url):
        click.echo(f"✓ Valid URL: {url}")
    else:
        click.echo(f"✗ Invalid URL: {url}")
        raise click.Abort()


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def stats(directory: str) -> None:
    """Show statistics for a scraped directory."""
    dir_path = Path(directory)
    txt_files = list(dir_path.glob("*.txt"))
    
    if not txt_files:
        click.echo(f"No .txt files found in {directory}")
        return
    
    total_size = sum(f.stat().st_size for f in txt_files)
    
    click.echo(f"Directory: {dir_path.absolute()}")
    click.echo(f"Text files: {len(txt_files)}")
    click.echo(f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
    
    # Show largest files
    if txt_files:
        largest_files = sorted(txt_files, key=lambda f: f.stat().st_size, reverse=True)[:5]
        click.echo("\nLargest files:")
        for i, file in enumerate(largest_files, 1):
            size = file.stat().st_size
            click.echo(f"  {i}. {file.name} ({size:,} bytes)")


if __name__ == "__main__":
    cli()
