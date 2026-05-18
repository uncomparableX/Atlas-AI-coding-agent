import difflib
import os
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
import structlog

logger = structlog.get_logger(__name__)


class AgentTools:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def _safe_path(self, file_path: str) -> Path:
        full = (self.repo_path / file_path).resolve()
        if not str(full).startswith(str(self.repo_path.resolve())):
            raise ValueError(f"Path traversal detected: {file_path}")
        return full

    async def read_file(self, file_path: str) -> Optional[str]:
        try:
            path = self._safe_path(file_path)
            if not path.exists() or not path.is_file():
                return None
            if path.stat().st_size > 1_000_000:
                return None
            async with aiofiles.open(path, "r", encoding="utf-8", errors="replace") as f:
                return await f.read()
        except Exception as e:
            logger.warning("Failed to read file", path=file_path, error=str(e))
            return None

    async def write_file(self, file_path: str, content: str) -> bool:
        try:
            path = self._safe_path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error("Failed to write file", path=file_path, error=str(e))
            return False

    async def delete_file(self, file_path: str) -> bool:
        try:
            path = self._safe_path(file_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete file", path=file_path, error=str(e))
            return False

    def generate_diff(self, original: str, modified: str, file_path: str) -> str:
        original_lines = original.splitlines(keepends=True) if original else []
        modified_lines = modified.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)

    async def apply_change(
        self,
        file_path: str,
        content: str,
        action: str = "modify",
        original_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        if action == "delete":
            success = await self.delete_file(file_path)
            return {
                "file_path": file_path,
                "action": "delete",
                "success": success,
                "diff": f"--- a/{file_path}\n+++ /dev/null",
            }

        if original_content is None:
            original_content = await self.read_file(file_path) or ""

        success = await self.write_file(file_path, content)
        diff = self.generate_diff(original_content, content, file_path)

        return {
            "file_path": file_path,
            "action": action,
            "success": success,
            "original": original_content,
            "modified": content,
            "diff": diff,
            "lines_added": diff.count("\n+") - diff.count("\n+++"),
            "lines_removed": diff.count("\n-") - diff.count("\n---"),
        }

    async def get_file_tree(self, max_depth: int = 5) -> Dict[str, Any]:
        SKIP = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", ".next"}

        def _walk(path: Path, depth: int) -> Dict:
            if depth == 0:
                return {}
            node = {
                "name": path.name,
                "path": str(path.relative_to(self.repo_path)),
                "type": "directory",
                "children": [],
            }
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith(".") or item.name in SKIP:
                        continue
                    if item.is_dir():
                        child = _walk(item, depth - 1)
                        if child:
                            node["children"].append(child)
                    else:
                        node["children"].append({
                            "name": item.name,
                            "path": str(item.relative_to(self.repo_path)),
                            "type": "file",
                            "size": item.stat().st_size,
                        })
            except PermissionError:
                pass
            return node

        return _walk(self.repo_path, max_depth)
