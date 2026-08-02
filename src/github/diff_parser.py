from __future__ import annotations

import re

from src.schema.types import CodeSegment

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    for ext, lang in LANGUAGE_MAP.items():
        if file_path.endswith(ext):
            return lang
    return "unknown"


def parse_unified_diff(raw_diff: str) -> list[dict]:
    """Parse raw unified diff text into per-file dicts."""
    files = []
    current_file = None

    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            match = re.match(r"diff --git a/(.+?) b/(.+)", line)
            if match:
                current_file = {
                    "path": match.group(2),
                    "old_path": match.group(1),
                    "hunks": [],
                    "raw_lines": [],
                }
        elif current_file is not None:
            current_file["raw_lines"].append(line)

    if current_file:
        files.append(current_file)

    return files


def _parse_hunks(raw_lines: list[str]) -> list[dict]:
    """Parse hunk headers and content from diff raw lines."""
    hunks = []
    current_hunk = None

    for line in raw_lines:
        hunk_match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "old_start": int(hunk_match.group(1)),
                "new_start": int(hunk_match.group(2)),
                "lines": [],
            }
        elif current_hunk is not None:
            current_hunk["lines"].append(line)

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def _hunk_to_segment(
    hunk: dict, file_path: str, language: str, segment_index: int
) -> CodeSegment:
    """Convert a single hunk to a CodeSegment."""
    old_lines = []
    new_lines = []
    new_line_num = hunk["new_start"]

    for line in hunk["lines"]:
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        else:
            old_lines.append(line[1:] if line.startswith(" ") else line)
            new_lines.append(line[1:] if line.startswith(" ") else line)

    return CodeSegment(
        file_path=file_path,
        hunk_start=hunk["new_start"],
        hunk_end=hunk["new_start"] + len(new_lines),
        old_content="\n".join(old_lines),
        new_content="\n".join(new_lines),
        language=language,
        segment_index=segment_index,
    )


def extract_segments(
    raw_diff: str, max_lines_per_segment: int = 200
) -> list[CodeSegment]:
    """Parse unified diff and extract CodeSegments."""
    files = parse_unified_diff(raw_diff)
    segments = []
    idx = 0

    for file_info in files:
        file_path = file_info["path"]
        language = detect_language(file_path)
        hunks = _parse_hunks(file_info["raw_lines"])

        for hunk in hunks:
            line_count = len(hunk["lines"])
            if line_count > max_lines_per_segment:
                # Split large hunk into sub-segments at function boundaries
                sub = _split_large_hunk(hunk, file_path, language, idx, max_lines_per_segment)
                segments.extend(sub)
                idx += len(sub)
            else:
                seg = _hunk_to_segment(hunk, file_path, language, idx)
                segments.append(seg)
                idx += 1

    return segments


def _split_large_hunk(
    hunk: dict,
    file_path: str,
    language: str,
    start_idx: int,
    max_lines: int,
) -> list[CodeSegment]:
    """Split a large hunk into smaller segments at blank lines or function boundaries."""
    lines = hunk["lines"]
    segments = []
    chunk_start = 0
    idx = start_idx

    while chunk_start < len(lines):
        chunk_end = min(chunk_start + max_lines, len(lines))

        # Try to find a good split point (blank line or function def)
        if chunk_end < len(lines):
            for i in range(chunk_end, max(chunk_start + max_lines // 2, chunk_start), -1):
                if i < len(lines) and lines[i].strip() == "":
                    chunk_end = i + 1
                    break

        chunk_lines = lines[chunk_start:chunk_end]
        old_lines = []
        new_lines = []

        for line in chunk_lines:
            if line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            else:
                old_lines.append(line[1:] if line.startswith(" ") else line)
                new_lines.append(line[1:] if line.startswith(" ") else line)

        new_start = hunk["new_start"] + sum(
            1 for l in lines[:chunk_start] if l.startswith("+") or l.startswith(" ")
        )

        segments.append(
            CodeSegment(
                file_path=file_path,
                hunk_start=new_start,
                hunk_end=new_start + len(new_lines),
                old_content="\n".join(old_lines),
                new_content="\n".join(new_lines),
                language=language,
                segment_index=idx,
            )
        )
        idx += 1
        chunk_start = chunk_end

    return segments
