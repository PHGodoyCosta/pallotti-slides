"""Theme (light/dark/system) and liturgical accent color."""

from typing import Final

from qfluentwidgets import Theme, setTheme, setThemeColor

DEFAULT_ACCENT: Final = "#7A1F2B"
THEME_MODES: Final = ("light", "dark", "system")

_THEMES = {"light": Theme.LIGHT, "dark": Theme.DARK, "system": Theme.AUTO}


def apply_theme(mode: str = "system", accent: str = DEFAULT_ACCENT) -> None:
    """Apply ``mode`` (``light``, ``dark`` or ``system``) and the accent color."""
    if mode not in _THEMES:
        raise ValueError(f"Tema desconhecido: {mode!r}")
    setTheme(_THEMES[mode])
    setThemeColor(accent)
