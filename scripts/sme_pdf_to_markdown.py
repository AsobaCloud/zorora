#!/usr/bin/env python3
"""Extract SME corpus PDFs to Markdown + frontmatter for smaller git footprint.

The diligence loader still reads PDFs directly, but if ``stem.md`` exists alongside
``stem.pdf``, only the Markdown is used. Typical workflow:

1. Drop PDFs under ``data/sme_orthodoxies/``.
2. Run: ``python scripts/sme_pdf_to_markdown.py``
3. Review/edit the ``.md`` files; optionally remove PDFs or ignore them in git.

Requires ``pypdf`` (see requirements.txt).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

# Repo root: scripts/ -> parent
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.research.local_sme_corpus import (  # noqa: E402
    display_title_from_path,
    extract_pdf_plain_text,
    inferred_meta_for_pdf,
)


def _dump_frontmatter(meta: Dict[str, object]) -> str:
    lines = ["---"]
    priority = [
        "title",
        "orthodoxy",
        "domains",
        "technologies",
        "countries",
        "tags",
        "weight",
        "source_pdf",
    ]
    ordered_keys: List[str] = [k for k in priority if k in meta]
    ordered_keys.extend(sorted(k for k in meta if k not in ordered_keys))
    for key in ordered_keys:
        val = meta[key]
        if isinstance(val, list):
            inner = ", ".join(str(x) for x in val)
            lines.append(f"{key}: [{inner}]")
        elif isinstance(val, bool):
            lines.append(f"{key}: {str(val).lower()}")
        elif isinstance(val, float):
            lines.append(f"{key}: {val}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            s = str(val).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}: "{s}"')
    lines.append("---")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert SME corpus PDFs to Markdown.")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=REPO_ROOT / "data" / "sme_orthodoxies",
        help="Directory containing PDFs (default: data/sme_orthodoxies)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help="Max PDF pages to extract (default: all pages)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .md files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files",
    )
    parser.add_argument(
        "--delete-pdf",
        action="store_true",
        help="Delete each PDF after a successful write (use after verifying output)",
    )
    args = parser.parse_args()

    corpus: Path = args.corpus
    if not corpus.is_absolute():
        corpus = REPO_ROOT / corpus
    if not corpus.is_dir():
        print(f"Corpus directory not found: {corpus}", file=sys.stderr)
        return 1

    pdfs = sorted(corpus.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs under {corpus}")
        return 0

    written = 0
    skipped = 0
    for pdf in pdfs:
        out_md = pdf.with_suffix(".md")
        if out_md.exists() and not args.force:
            print(f"skip (exists): {out_md.relative_to(corpus)}")
            skipped += 1
            continue

        text = extract_pdf_plain_text(pdf, max_pages=args.max_pages)
        if not text.strip():
            print(f"skip (no text): {pdf.relative_to(corpus)}", file=sys.stderr)
            skipped += 1
            continue

        rel_pdf = pdf.relative_to(corpus).as_posix()
        meta = dict(inferred_meta_for_pdf(pdf))
        meta["title"] = display_title_from_path(pdf)
        meta["orthodoxy"] = "SME reference (converted from PDF)"
        meta["source_pdf"] = rel_pdf

        body = (
            "<!-- Extracted text; edit frontmatter and body as needed. -->\n\n"
            + text.strip()
            + "\n"
        )
        content = _dump_frontmatter(meta) + "\n\n" + body

        if args.dry_run:
            print(f"would write: {out_md.relative_to(corpus)} ({len(content)} chars)")
            continue

        out_md.write_text(content, encoding="utf-8")
        print(f"wrote: {out_md.relative_to(corpus)}")
        written += 1

        if args.delete_pdf:
            pdf.unlink()
            print(f"deleted: {pdf.relative_to(corpus)}")

    print(f"Done. wrote={written} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
