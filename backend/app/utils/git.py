"""
Git Utility Helpers
Lightweight helpers for diff generation, patch manipulation,
and repository status queries — no external Git server required.
"""
import difflib
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


# ─── Diff generation ─────────────────────────────────────────────────────────

def generate_unified_diff(
    original: str,
    modified: str,
    file_path: str,
    context_lines: int = 3,
) -> str:
    """
    Generate a unified diff between two strings.
    Returns the diff as a string (empty if no changes).
    """
    orig_lines = original.splitlines(keepends=True) if original else []
    mod_lines  = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
        lineterm="",
    )
    return "".join(diff)


def diff_summary(diff_text: str) -> Dict[str, int]:
    """
    Return a summary of a unified diff.
    """
    added = removed = 0
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"lines_added": added, "lines_removed": removed, "net_change": added - removed}


def split_diff_by_file(diff_text: str) -> Dict[str, str]:
    """
    Split a multi-file unified diff into per-file diffs.
    Returns dict of filename → diff_text.
    """
    file_diffs: Dict[str, str] = {}
    current_file: Optional[str] = None
    current_lines: List[str] = []

    for line in diff_text.split("\n"):
        if line.startswith("--- "):
            if current_file and current_lines:
                file_diffs[current_file] = "\n".join(current_lines)
            current_file  = line[4:].strip()
            if current_file.startswith("a/"):
                current_file = current_file[2:]
            current_lines = [line]
        elif current_file:
            current_lines.append(line)

    if current_file and current_lines:
        file_diffs[current_file] = "\n".join(current_lines)

    return file_diffs


def apply_patch_in_memory(original: str, patch: str) -> Optional[str]:
    """
    Attempt to apply a unified diff patch to a string in memory.
    Returns the patched string or None if the patch cannot be applied.
    """
    try:
        import unidiff
        patch_set = unidiff.PatchSet.from_string(patch)
        if not patch_set:
            return original
        lines = original.splitlines(keepends=True)
        for patched_file in patch_set:
            for hunk in patched_file:
                source_start = hunk.source_start - 1
                new_lines: List[str] = []
                for line in hunk:
                    if line.line_type == " ":   # context
                        new_lines.append(line.value)
                    elif line.line_type == "+":  # addition
                        new_lines.append(line.value)
                    # line_type == "-" (removal) → skip
                source_end = source_start + hunk.source_length
                lines[source_start:source_end] = new_lines
        return "".join(lines)
    except Exception as e:
        logger.warning("In-memory patch failed", error=str(e))
        return None


# ─── Git CLI wrappers ─────────────────────────────────────────────────────────

def _git(repo_path: str, *args: str) -> Tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git", "-C", repo_path] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def get_current_branch(repo_path: str) -> str:
    _, stdout, _ = _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    return stdout.strip() or "main"


def get_repo_root(path: str) -> Optional[str]:
    """Resolve the git repository root for a given path."""
    rc, stdout, _ = _git(path, "rev-parse", "--show-toplevel")
    return stdout.strip() if rc == 0 else None


def is_git_repo(path: str) -> bool:
    rc, _, _ = _git(path, "rev-parse", "--git-dir")
    return rc == 0


def get_changed_files(repo_path: str, since_ref: str = "HEAD") -> List[str]:
    """Return a list of files changed since since_ref."""
    _, stdout, _ = _git(repo_path, "diff", "--name-only", since_ref)
    return [f.strip() for f in stdout.strip().split("\n") if f.strip()]


def get_file_at_ref(repo_path: str, file_path: str, ref: str = "HEAD") -> Optional[str]:
    """Return the content of a file at a specific git ref."""
    rc, stdout, _ = _git(repo_path, "show", f"{ref}:{file_path}")
    return stdout if rc == 0 else None


def get_commit_log(
    repo_path: str,
    n: int = 10,
    since: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Return recent commit metadata."""
    args = ["log", f"-{n}", "--pretty=format:%H%x00%s%x00%an%x00%ar"]
    if since:
        args.append(f"--since={since}")
    _, stdout, _ = _git(repo_path, *args)
    commits = []
    for line in stdout.strip().split("\n"):
        if line:
            parts = line.split("\x00")
            if len(parts) == 4:
                commits.append({
                    "hash":    parts[0][:8],
                    "subject": parts[1],
                    "author":  parts[2],
                    "when":    parts[3],
                })
    return commits


# ─── Patch parsing helpers ───────────────────────────────────────────────────

def extract_hunks(diff_text: str) -> List[Dict[str, Any]]:
    """
    Parse a unified diff into a list of hunk dicts with
    source/target line ranges and content.
    """
    hunks: List[Dict[str, Any]] = []
    hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    current: Optional[Dict[str, Any]] = None

    for line in diff_text.split("\n"):
        m = hunk_header.match(line)
        if m:
            if current:
                hunks.append(current)
            current = {
                "source_start":  int(m.group(1)),
                "source_length": int(m.group(2)) if m.group(2) else 1,
                "target_start":  int(m.group(3)),
                "target_length": int(m.group(4)) if m.group(4) else 1,
                "lines":         [line],
            }
        elif current:
            current["lines"].append(line)

    if current:
        hunks.append(current)

    return hunks


def validate_diff(diff_text: str) -> Dict[str, Any]:
    """
    Basic validation of a unified diff string.
    Returns a dict with valid (bool) and any issues found.
    """
    issues: List[str] = []

    if not diff_text.strip():
        return {"valid": True, "issues": [], "note": "Empty diff — no changes"}

    if "--- " not in diff_text or "+++ " not in diff_text:
        issues.append("Missing --- / +++ file headers")

    if "@@ " not in diff_text:
        issues.append("No hunk headers (@@ ... @@) found")

    return {
        "valid":  len(issues) == 0,
        "issues": issues,
    }
