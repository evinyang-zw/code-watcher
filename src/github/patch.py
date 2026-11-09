"""Apply unified-diff patches to source text using the `unidiff` parser.

The previous implementation hand-parsed ``+``/``-``/`` ` `` lines and ignored
``@@`` hunk headers, which silently produced wrong files for any patch with
more than one hunk. This module keeps the parsing (and validation) honest:
hunks are applied at their declared source line numbers and context lines are
verified before they are consumed.
"""

from __future__ import annotations

import re

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*?)```$", re.DOTALL)


class PatchApplyError(Exception):
    """Raised when a patch cannot be applied to the given source text."""


def strip_code_fences(text: str) -> str:
    """Remove a surrounding markdown code fence (```` ```diff ... ``` ````)."""
    text = text.strip()
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip("\n")
    return text


def apply_patch(original: str, patch_text: str) -> str:
    """Apply a single-file unified diff to ``original`` and return the result.

    Raises :class:`PatchApplyError` when the patch is malformed, targets more
    than one file, overlaps, or does not match the source text.
    """
    if not patch_text.strip():
        raise PatchApplyError("empty patch")

    try:
        patch = PatchSet(strip_code_fences(patch_text))
    except (UnidiffParseError, ValueError) as exc:  # pragma: no cover - defensive
        raise PatchApplyError(f"cannot parse patch: {exc}") from exc

    if len(patch) != 1:
        raise PatchApplyError(f"expected a single-file patch, got {len(patch)} files")

    patched_file = patch[0]

    if patched_file.is_added_file:
        lines = []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    lines.append(line.value.rstrip("\r\n"))
        return "\n".join(lines) + "\n"

    had_trailing_newline = original.endswith("\n")
    source_lines = original.splitlines()

    result: list[str] = []
    cursor = 0  # 0-based index into source_lines

    for hunk in patched_file:
        start = hunk.source_start - 1
        if start < cursor:
            raise PatchApplyError("overlapping or out-of-order hunks")
        if start > len(source_lines):
            raise PatchApplyError(f"hunk starts past end of file (line {hunk.source_start})")
        result.extend(source_lines[cursor:start])
        cursor = start

        for line in hunk:
            value = line.value.rstrip("\r\n")
            if line.is_removed:
                _expect_context(source_lines, cursor, value)
                cursor += 1
            elif line.is_added:
                result.append(value)
            else:
                _expect_context(source_lines, cursor, value)
                result.append(source_lines[cursor])
                cursor += 1

    result.extend(source_lines[cursor:])
    patched = "\n".join(result)
    return patched + "\n" if had_trailing_newline else patched


def _expect_context(source_lines: list[str], cursor: int, expected: str) -> None:
    if cursor >= len(source_lines):
        raise PatchApplyError("patch expects more lines than the file has")
    actual = source_lines[cursor]
    if actual.rstrip() != expected.rstrip():
        raise PatchApplyError(
            f"context mismatch at line {cursor + 1}: expected {expected!r}, found {actual!r}"
        )
