import shutil
import tempfile
import uuid
from pathlib import Path


def new_session_dir() -> Path:
    """Creates a fresh scratch directory for one bot conversation's media files."""
    base = Path(tempfile.gettempdir()) / "yozar_ai" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base


def cleanup_session_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
