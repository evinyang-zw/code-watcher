from __future__ import annotations

from src.github.diff_parser import (
    detect_language,
    extract_segments,
    parse_unified_diff,
)


def test_detect_language():
    assert detect_language("src/app.py") == "python"
    assert detect_language("src/index.ts") == "typescript"
    assert detect_language("src/main.go") == "go"
    assert detect_language("README.md") == "markdown"
    assert detect_language("unknown.xyz") == "unknown"


def test_parse_unified_diff_single_file(sample_diff):
    files = parse_unified_diff(sample_diff)
    assert len(files) == 1
    assert files[0]["path"] == "src/app.py"
    assert files[0]["old_path"] == "src/app.py"


def test_parse_unified_diff_multiple_files():
    diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-old
+new
"""
    files = parse_unified_diff(diff)
    assert len(files) == 2
    assert files[0]["path"] == "a.py"
    assert files[1]["path"] == "b.py"


def test_extract_segments(sample_diff):
    segments = extract_segments(sample_diff)
    assert len(segments) == 1
    seg = segments[0]
    assert seg.file_path == "src/app.py"
    assert seg.language == "python"
    assert seg.segment_index == 0
    assert "hello" in seg.new_content
    assert "os.environ" in seg.new_content


def test_extract_segments_empty_diff():
    segments = extract_segments("")
    assert segments == []


def test_extract_segments_large_hunk_splits():
    # Create a hunk with >200 lines to trigger splitting
    old_lines = ["old"] * 150
    new_lines = ["new"] * 150
    diff_lines = ["diff --git a/big.py b/big.py", "--- a/big.py", "+++ b/big.py"]
    diff_lines.append("@@ -1,150 +1,150 @@")

    for line in old_lines:
        diff_lines.append(f"-{line}")
    for line in new_lines:
        diff_lines.append(f"+{line}")

    diff = "\n".join(diff_lines)
    segments = extract_segments(diff, max_lines_per_segment=50)
    assert len(segments) > 1
    assert all(s.file_path == "big.py" for s in segments)
