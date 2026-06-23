from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

_TEST_TEMP_DIR = Path(__file__).resolve().parents[1] / ".tmp" / "pytest-temp"
_TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_TEST_TEMP_DIR)


class _WorkspaceTemporaryDirectory:
    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        ignore_cleanup_errors: bool = False,
        *,
        delete: bool = True,
    ) -> None:
        del ignore_cleanup_errors, delete
        base_dir = Path(dir) if dir is not None else _TEST_TEMP_DIR
        directory_name = f"{prefix or 'tmp'}{uuid.uuid4().hex}{suffix or ''}"
        self.name = str(base_dir / directory_name)
        Path(self.name).mkdir(parents=True, exist_ok=False)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        return None


tempfile.TemporaryDirectory = _WorkspaceTemporaryDirectory
