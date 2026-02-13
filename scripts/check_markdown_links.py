#!/usr/bin/env python3
"""Validate local markdown links in README and docs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
IGNORED_PREFIXES = ("http://", "https://", "mailto:", "#")


@dataclass(frozen=True)
class BrokenLink:
    source: Path
    target: str


def _candidate_markdown_files(repo_root: Path) -> list[Path]:
    files = [repo_root / "README.md"]
    files.extend((repo_root / "docs").rglob("*.md"))
    return [file for file in files if file.exists()]


def _resolve_target(source: Path, target: str, repo_root: Path) -> Path:
    cleaned = target.split("#", maxsplit=1)[0]
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    if cleaned.startswith("/"):
        return (repo_root / cleaned.lstrip("/")).resolve()
    return (source.parent / cleaned).resolve()


def find_broken_links(repo_root: Path) -> list[BrokenLink]:
    broken: list[BrokenLink] = []
    for markdown_file in _candidate_markdown_files(repo_root):
        content = markdown_file.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = match.group(1).strip()
            if not target or target.startswith(IGNORED_PREFIXES):
                continue

            resolved = _resolve_target(markdown_file, target, repo_root)
            if not resolved.exists():
                broken.append(BrokenLink(source=markdown_file, target=target))
    return broken


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    broken_links = find_broken_links(repo_root)

    if not broken_links:
        print("OK: no broken local markdown links")
        return 0

    print("Broken markdown links detected:")
    for broken in broken_links:
        relative_source = broken.source.relative_to(repo_root)
        print(f"- {relative_source}: {broken.target}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
