"""Text measurement (M3 adds ``TextMeasurer``; M2 only needs the ``Box`` type)."""

from dataclasses import dataclass

EMU_PER_POINT = 12700


@dataclass(frozen=True)
class Box:
    """Frame of a text shape on the slide, in EMU (1 pt = 12700 EMU)."""

    left: int
    top: int
    width: int
    height: int

    @property
    def width_pt(self) -> float:
        return self.width / EMU_PER_POINT

    @property
    def height_pt(self) -> float:
        return self.height / EMU_PER_POINT
