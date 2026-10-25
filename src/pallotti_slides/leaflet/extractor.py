"""PDF leaflet → ``LeafletData`` with a SHA-256 cache (ARQUITETURA §7)."""

import hashlib
import logging
from pathlib import Path

from pydantic import ValidationError

from pallotti_slides.domain.text import normalize_title
from pallotti_slides.leaflet.errors import LeafletError
from pallotti_slides.leaflet.prompts import LEAFLET_INSTRUCTION
from pallotti_slides.leaflet.schema import LeafletData
from pallotti_slides.llm.client import LLMClient

_log = logging.getLogger(__name__)


class LeafletExtractor:
    """Send the PDF to the LLM once per distinct file."""

    def __init__(self, llm: LLMClient, cache_dir: Path) -> None:
        self._llm = llm
        self._cache_dir = cache_dir

    def extract(self, pdf: Path) -> LeafletData:
        try:
            content = pdf.read_bytes()
        except OSError as error:
            raise LeafletError(f"Não foi possível abrir o arquivo {pdf.name}.") from error
        if not content.startswith(b"%PDF"):
            raise LeafletError(f"O arquivo {pdf.name} não é um PDF.")
        digest = hashlib.sha256(content).hexdigest()
        cached = self._read_cache(digest)
        if cached is not None:
            return cached
        data = self._llm.extract_structured(
            instruction=LEAFLET_INSTRUCTION, schema=LeafletData, pdf=content
        )
        if data.is_empty():
            raise LeafletError(
                "Este PDF não parece ser um folheto litúrgico: nenhum campo foi encontrado. "
                "Use o preenchimento manual."
            )
        if data.title:
            data = data.model_copy(update={"title": normalize_title(data.title)})
        self._write_cache(digest, data)
        return data

    def _cache_path(self, digest: str) -> Path:
        return self._cache_dir / f"{digest}.json"

    def _read_cache(self, digest: str) -> LeafletData | None:
        path = self._cache_path(digest)
        if not path.is_file():
            return None
        try:
            return LeafletData.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError):
            _log.warning("Cache do folheto inválido; será refeito.")
            return None

    def _write_cache(self, digest: str, data: LeafletData) -> None:
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(digest).write_text(data.model_dump_json(indent=2), encoding="utf-8")
        except OSError:
            _log.warning("Não foi possível gravar o cache do folheto.")
