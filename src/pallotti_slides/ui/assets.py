"""Access to the images bundled with the program."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

IMAGES_DIR = Path(__file__).resolve().parents[1] / "resources" / "images"


def image_path(name: str) -> Path:
    """Absolute path of a file in ``resources/images``."""
    return IMAGES_DIR / name


def load_pixmap(name: str, *, height: int | None = None) -> QPixmap:
    """Load a bundled image, optionally scaled to ``height`` (smooth, aspect kept)."""
    pixmap = QPixmap(str(image_path(name)))
    if height is not None and not pixmap.isNull():
        pixmap = pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
    return pixmap
