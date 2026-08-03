"""Write artifact files under a run-scoped directory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from axiom.workers.tools.base import BaseTool, ToolExecutionContext, check_governance

DEFAULT_ARTIFACTS_ROOT = Path(os.environ.get("AXIOM_ARTIFACTS_ROOT", "/var/axiom/artifacts"))
MAX_FILE_BYTES = 10 * 1024 * 1024


def _validate_filename(name: str) -> None:
    if not name or "\x00" in name:
        msg = "invalid filename"
        raise ValueError(msg)
    if ".." in name or name.startswith(("/", "\\")):
        msg = "path traversal not allowed"
        raise ValueError(msg)
    if "/" in name or "\\" in name or ":" in name:
        msg = "invalid filename characters"
        raise ValueError(msg)


def artifact_path_for_run(run_id: UUID, filename: str, *, root: Path | None = None) -> Path:
    _validate_filename(filename)
    base = root if root is not None else DEFAULT_ARTIFACTS_ROOT
    return (base / str(run_id) / filename).resolve()


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write a file under the run artifact directory."
    schema: ClassVar[dict[str, object]] = {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string", "description": "File body (utf-8 text)"},
                },
                "required": ["filename", "content"],
            },
        },
    }

    async def execute(self, ctx: ToolExecutionContext, **kwargs: object) -> dict[str, object]:
        if ctx.run_id is None:
            return {"ok": False, "error": "run_id_required"}
        filename = str(kwargs.get("filename", ""))
        content = kwargs.get("content", "")
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
        if len(raw) > MAX_FILE_BYTES:
            return {"ok": False, "error": "file_too_large"}

        target = artifact_path_for_run(ctx.run_id, filename)
        rel = f"/artifacts/{ctx.run_id}/{filename}"
        await check_governance(
            ctx=ctx,
            action_type="tool.file_write",
            target=rel[:1024],
            parameters={"filename": filename, "size_bytes": len(raw)},
        )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return {
            "ok": True,
            "url": rel,
            "content_type": "application/octet-stream",
            "size_bytes": len(raw),
        }
