from __future__ import annotations

import pytest

from src.github.patch import PatchApplyError, apply_patch, strip_code_fences

SINGLE_HUNK = """--- a/a.py
+++ b/a.py
@@ -1,3 +1,3 @@
 def f():
-    return 1
+    return 2
     # trailing
"""

MULTI_HUNK = """--- a/a.py
+++ b/a.py
@@ -2,3 +2,3 @@
 line2
-line3
+LINE3
 line4
@@ -10,3 +10,3 @@
 line10
-line11
+LINE11
 line12
"""


def test_apply_single_hunk():
    original = "def f():\n    return 1\n    # trailing\n"
    assert apply_patch(original, SINGLE_HUNK) == ("def f():\n    return 2\n    # trailing\n")


def test_apply_multi_hunk_uses_declared_line_numbers():
    """Regression: the old implementation ignored @@ headers and shifted lines."""
    original = "\n".join(f"line{i}" for i in range(1, 13)) + "\n"
    patched = apply_patch(original, MULTI_HUNK)
    assert (
        patched
        == "\n".join(
            ["line1", "line2", "LINE3", "line4"]
            + [f"line{i}" for i in range(5, 10)]
            + ["line10", "LINE11", "line12"]
        )
        + "\n"
    )


def test_context_mismatch_raises():
    original = "def f():\n    return 99\n    # trailing\n"
    with pytest.raises(PatchApplyError, match="context mismatch"):
        apply_patch(original, SINGLE_HUNK)


def test_added_file_patch_creates_content():
    new_file = """--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+x = 1
+y = 2
"""
    assert apply_patch("", new_file) == "x = 1\ny = 2\n"


def test_strip_code_fences():
    fenced = "```diff\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n```"
    assert strip_code_fences(fenced).startswith("--- a/a.py")


def test_apply_rejects_multi_file_patch():
    two_files = (
        SINGLE_HUNK
        + """--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-x
+y
"""
    )
    with pytest.raises(PatchApplyError, match="single-file"):
        apply_patch("def f():\n    return 1\n", two_files)
