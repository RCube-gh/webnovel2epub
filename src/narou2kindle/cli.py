from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .epub import safe_filename, write_epub
from .extractors import ExtractionError, get_extractor
from .models import EpisodeRef


def _output_path(output: Path | None, title: str) -> Path:
    target = output or Path(safe_filename(title))
    if target.suffix.lower() != ".epub":
        return target.with_name(f"{target.name}.epub")
    return target


def main() -> int:
    # Some embedded terminals expose a Western code page.  Do not let a
    # Japanese title turn a successful conversion into a console error.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Convert a Narou novel to EPUB.")
    parser.add_argument("url", help="Novel top-page URL")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="Output EPUB file path (for example, .\\books\\my-novel.epub)",
    )
    parser.add_argument(
        "--paragraph-length",
        type=int,
        default=220,
        metavar="CHARS",
        help="Maximum length of a reflowed prose paragraph (default: 220)",
    )
    parser.add_argument(
        "--section-length",
        type=int,
        default=1000,
        metavar="CHARS",
        help="Insert a blank line after this many characters (default: 1000; 0 disables it)",
    )
    parser.add_argument(
        "--cover",
        type=Path,
        metavar="IMAGE",
        help="Image file to use as the cover (JPG, PNG, GIF, or WebP)",
    )
    parser.add_argument(
        "--writing-mode",
        choices=("vertical", "horizontal"),
        default="vertical",
        help="Text direction and page progression (default: vertical)",
    )
    args = parser.parse_args()
    if args.paragraph_length < 1:
        parser.error("--paragraph-length must be positive")
    if args.section_length < 0:
        parser.error("--section-length must not be negative")
    if args.cover and not args.cover.is_file():
        parser.error("--cover must point to an existing image file")
    try:
        extractor = get_extractor(args.url, args.paragraph_length, args.section_length)
        print(f"Inspecting {extractor.identifier(args.url)}...")

        def show_metadata(title: str, author: str, _synopsis: str, refs: list[EpisodeRef]) -> None:
            print(f"Title: {title}")
            print(f"Author: {author or 'Unknown'}")
            print(f"Episodes found: {len(refs)}")
            print("Downloading and formatting episodes...")

        def show_episode(stage: str, index: int, total: int, ref: EpisodeRef) -> None:
            if stage == "Downloading":
                print(f"  [{index:>3}/{total}] {ref.title} ...", end="", flush=True)
            else:
                print(" done")

        novel = extractor.download(args.url, on_metadata=show_metadata, on_episode=show_episode)
        target = _output_path(args.output, novel.title)
        print("Writing EPUB...")
        write_epub(novel, target, args.cover, args.writing_mode)
    except (ExtractionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created: {target} ({len(novel.episodes)} episodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
