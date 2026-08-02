from __future__ import annotations

import pytest

from src.graph.state import create_review_state
from src.schema.types import CodeSegment


@pytest.fixture
def sample_review_state():
    return create_review_state(
        pr_url="https://github.com/test/repo/pull/1",
        owner="test",
        repo="repo",
        pr_number=1,
        auto_fix_enabled=True,
    )


@pytest.fixture
def sample_diff() -> str:
    return """diff --git a/src/app.py b/src/app.py
index 1234567..abcdefg 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,7 @@
 import os

 def hello():
-    print("hello")
+    name = os.environ.get("NAME", "world")
+    print(f"hello {name}")
     return True
"""


@pytest.fixture
def sample_segments() -> list[CodeSegment]:
    return [
        CodeSegment(
            file_path="src/app.py",
            hunk_start=1,
            hunk_end=7,
            old_content='import os\n\ndef hello():\n    print("hello")\n    return True',
            new_content='import os\n\ndef hello():\n    name = os.environ.get("NAME", "world")\n    print(f"hello {name}")\n    return True',
            language="python",
            segment_index=0,
        )
    ]
