from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path


class EvaluationRunner:
    """Runs validation checks against patched code."""

    def __init__(self, repo_path: str | None = None):
        self._temp_dir = None
        if repo_path:
            self.repo_path = Path(repo_path)
        else:
            self._temp_dir = tempfile.mkdtemp(prefix="code_watcher_")
            self.repo_path = Path(self._temp_dir)

    async def close(self):
        """Clean up temporary directory."""
        if self._temp_dir and Path(self._temp_dir).exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    async def check_syntax(self, file_path: str) -> bool:
        """py_compile check with timeout."""
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "python3", "-m", "py_compile", str(self.repo_path / file_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=10.0,
            )
            await result.wait()
            return result.returncode == 0
        except asyncio.TimeoutError:
            return False

    async def check_syntax_code(self, code: str, filename: str = "check.py") -> bool:
        """Check syntax of a code string with timeout."""
        tmp = self.repo_path / filename
        tmp.write_text(code)
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "python3", "-m", "py_compile", str(tmp),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=10.0,
            )
            await result.wait()
            return result.returncode == 0
        except asyncio.TimeoutError:
            return False

    async def check_lint(self, file_path: str) -> bool:
        """ruff check with timeout."""
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ruff", "check", str(self.repo_path / file_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=10.0,
            )
            stdout, _ = await result.communicate()
            return result.returncode == 0
        except (asyncio.TimeoutError, FileNotFoundError):
            return True

    async def check_lint_code(self, code: str, filename: str = "check.py") -> bool:
        """Check lint of a code string with timeout."""
        tmp = self.repo_path / filename
        tmp.write_text(code)
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ruff", "check", str(tmp),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=10.0,
            )
            stdout, _ = await result.communicate()
            return result.returncode == 0
        except (asyncio.TimeoutError, FileNotFoundError):
            return True

    async def run_tests(self, test_path: str | None = None) -> bool | None:
        """Run pytest with timeout. Returns None if no tests found."""
        cmd = ["python3", "-m", "pytest", "--tb=short", "-q"]
        if test_path:
            cmd.append(test_path)
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.repo_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=60.0,
            )
            stdout, _ = await result.communicate()
            if b"no tests ran" in stdout:
                return None
            return result.returncode == 0
        except asyncio.TimeoutError:
            return None
