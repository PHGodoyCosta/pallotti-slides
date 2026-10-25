"""Program paths and font location (ARQUITETURA §12).

The Aptos font belongs to Microsoft and cannot be redistributed: it never goes
into git or the executable, it is only located on the system.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_log_dir
from pydantic import BaseModel, ValidationError

APP_NAME = "PallottiSlides"
FONT_FAMILY = "Aptos"
FONTS_DIR_VAR = "PALLOTTI_FONTS_DIR"
DB_URL_VAR = "PALLOTTI_DB_URL"

_REGULAR_NAMES = ("Aptos.ttf", "Aptos-Regular.ttf")
_BOLD_NAMES = ("Aptos-Bold.ttf", "Aptos Bold.ttf")


@dataclass(frozen=True)
class Paths:
    """User data, config file and log folders."""

    data: Path
    config: Path
    logs: Path

    @classmethod
    def default(cls) -> "Paths":
        return cls(
            data=Path(user_data_dir(APP_NAME)),
            config=Path(user_config_dir(APP_NAME)) / "config.json",
            logs=Path(user_log_dir(APP_NAME)),
        )


class Settings(BaseModel):
    """User settings saved as JSON. API keys never go here (they live in the keyring)."""

    llm_provider: str = "openai"
    openai_model: str = "gpt-6-astra"
    anthropic_model: str = "claude-opus-5-5"


def load_settings(path: Path | None = None) -> Settings:
    """Read settings; a missing or invalid file gives the defaults."""
    file = path if path is not None else Paths.default().config
    try:
        return Settings.model_validate_json(file.read_text(encoding="utf-8"))
    except (OSError, ValidationError):
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write settings as JSON, creating the folder if needed."""
    file = path if path is not None else Paths.default().config
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


def default_db_url(paths: Paths | None = None, env: Mapping[str, str] | None = None) -> str:
    """Database URL: ``PALLOTTI_DB_URL`` or SQLite in ``Paths.data/pallotti.db``."""
    from_env = (os.environ if env is None else env).get(DB_URL_VAR)
    if from_env:
        return from_env
    data = (paths or Paths.default()).data
    return f"sqlite:///{(data / 'pallotti.db').as_posix()}"


@dataclass(frozen=True)
class TypographyConfig:
    """Song typography (SPEC F9): one size per song, from ``max_font`` down to ``min_font``."""

    min_font: int = 40
    max_font: int = 54
    max_lines: int = 6

    def __post_init__(self) -> None:
        if not 0 < self.min_font <= self.max_font:
            raise ValueError("min_font deve ser positivo e menor ou igual a max_font")
        if self.max_lines < 1:
            raise ValueError("max_lines deve ser pelo menos 1")


@dataclass(frozen=True)
class FoundFonts:
    """Aptos TTF files; ``None`` when not found."""

    regular: Path | None
    bold: Path | None

    @property
    def complete(self) -> bool:
        return self.regular is not None and self.bold is not None


FcMatchRunner = Callable[[str], str]


def _fc_match(pattern: str) -> str:
    """Run ``fc-match`` and return ``family|file`` (empty if unavailable)."""
    exe = shutil.which("fc-match")
    if exe is None:
        return ""
    try:
        res = subprocess.run(
            [exe, "-f", "%{family}|%{file}", pattern],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return res.stdout.strip()


class FontLocator:
    """Find Aptos (regular and bold) in the order defined in ARQUITETURA §12.

    1. path configured by the user (folder, or a TTF file of the font);
    2. the ``PALLOTTI_FONTS_DIR`` environment variable;
    3. system fonts (``fc-match`` on Linux; font folders on Windows);
    4. Microsoft 365 cloud fonts (``CloudFonts``).
    """

    def __init__(
        self,
        configured_path: Path | None = None,
        env: Mapping[str, str] | None = None,
        fc_match: FcMatchRunner | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._configured = configured_path
        self._env = os.environ if env is None else env
        self._fc_match = fc_match or _fc_match
        self._platform = platform_name or sys.platform

    def locate(self) -> FoundFonts:
        return FoundFonts(regular=self.locate_regular(), bold=self.locate_bold())

    def locate_regular(self) -> Path | None:
        return self._search(_REGULAR_NAMES, bold=False)

    def locate_bold(self) -> Path | None:
        return self._search(_BOLD_NAMES, bold=True)

    def _search(self, names: tuple[str, ...], *, bold: bool) -> Path | None:
        for directory in self._explicit_dirs():
            found = self._in_dir(directory, names)
            if found:
                return found
        found = self._from_system(names, bold=bold)
        if found:
            return found
        for directory in self._cloud_dirs():
            found = self._in_dir(directory, names)
            if found:
                return found
        return None

    def _explicit_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self._configured is not None:
            dirs.append(self._configured)
        from_env = self._env.get(FONTS_DIR_VAR)
        if from_env:
            dirs.append(Path(from_env))
        return dirs

    def _cloud_dirs(self) -> list[Path]:
        local = self._env.get("LOCALAPPDATA")
        if not local:
            return []
        return [Path(local) / "Microsoft" / "FontCache" / "4" / "CloudFonts" / FONT_FAMILY]

    def _windows_system_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        windir = self._env.get("WINDIR") or self._env.get("SystemRoot")
        dirs.append(Path(windir) / "Fonts" if windir else Path("C:/Windows/Fonts"))
        local = self._env.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
        return dirs

    def _from_system(self, names: tuple[str, ...], *, bold: bool) -> Path | None:
        if self._platform.startswith("win"):
            for directory in self._windows_system_dirs():
                found = self._in_dir(directory, names)
                if found:
                    return found
            return None
        pattern = f"{FONT_FAMILY}:bold" if bold else FONT_FAMILY
        family, _, file = self._fc_match(pattern).partition("|")
        # fc-match always answers (with a substitute); only Aptos counts.
        if FONT_FAMILY.lower() not in family.lower() or not file:
            return None
        path = Path(file)
        if not path.is_file():
            return None
        return path if ("bold" in path.stem.lower()) == bold else None

    @staticmethod
    def _in_dir(directory: Path, names: tuple[str, ...]) -> Path | None:
        if directory.is_file():
            directory = directory.parent
        if not directory.is_dir():
            return None
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        return None


def locate_soffice(configured: Path | None = None) -> Path | None:
    """Find the LibreOffice executable (``soffice``)."""
    if configured is not None and configured.is_file():
        return configured
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for base in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = os.environ.get(base)
        if root:
            candidate = Path(root) / "LibreOffice" / "program" / "soffice.exe"
            if candidate.is_file():
                return candidate
    return None
