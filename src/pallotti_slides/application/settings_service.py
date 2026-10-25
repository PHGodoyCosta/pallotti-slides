"""Settings use cases: load/save, API keys in the keyring and the diagnostic (SPEC F14)."""

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pallotti_slides.config import (
    FontLocator,
    Settings,
    load_settings,
    locate_soffice,
    save_settings,
)
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.llm.client import (
    API_KEY_VARS,
    KEYRING_SERVICE,
    KEYRING_USERS,
    PROVIDER_NAMES,
    PROVIDERS,
)
from pallotti_slides.presentation.template import MassTemplate

__all__ = ["PROVIDERS", "PROVIDER_NAMES", "DiagnosticItem", "SettingsService"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiagnosticItem:
    """State of one requirement of the program, with guidance when it is not ok."""

    name: str
    ok: bool
    detail: str
    hint: str = ""


def _keyring_get(service: str, user: str) -> str | None:
    import keyring

    return keyring.get_password(service, user)


def _keyring_set(service: str, user: str, value: str) -> None:
    import keyring

    keyring.set_password(service, user, value)


def _keyring_delete(service: str, user: str) -> None:
    import keyring

    keyring.delete_password(service, user)


class SettingsService:
    """Settings file, API keys and diagnostic. Key values never leave this class."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        env: Mapping[str, str] | None = None,
        keyring_get: Callable[[str, str], str | None] = _keyring_get,
        keyring_set: Callable[[str, str, str], None] = _keyring_set,
        keyring_delete: Callable[[str, str], None] = _keyring_delete,
    ) -> None:
        self._path = config_path
        self._env = os.environ if env is None else env
        self._get = keyring_get
        self._set = keyring_set
        self._delete = keyring_delete

    def load(self) -> Settings:
        return load_settings(self._path)

    def save(self, settings: Settings) -> None:
        save_settings(settings, self._path)

    def has_key(self, provider: str) -> bool:
        """``True`` when a key exists for ``provider`` (keyring or development env var)."""
        self._check(provider)
        try:
            if (self._get(KEYRING_SERVICE, KEYRING_USERS[provider]) or "").strip():
                return True
        except Exception:  # keyring backends fail in many ways (no backend, locked...)
            _log.warning("Cofre de chaves indisponível ao consultar %s.", provider)
        return bool(self._env.get(API_KEY_VARS[provider], "").strip())

    def save_key(self, provider: str, value: str) -> None:
        """Store the key in the keyring; ``PallottiError`` if blank or the keyring fails."""
        self._check(provider)
        value = value.strip()
        if not value:
            raise PallottiError("Informe a chave da API antes de salvar.")
        try:
            self._set(KEYRING_SERVICE, KEYRING_USERS[provider], value)
        except Exception as error:
            raise PallottiError(
                f"Não foi possível guardar a chave no cofre do sistema ({type(error).__name__})."
            ) from None
        _log.info("Chave da API (%s) guardada no cofre.", provider)

    def remove_key(self, provider: str) -> None:
        """Delete the key from the keyring (no error if there was none)."""
        self._check(provider)
        try:
            self._delete(KEYRING_SERVICE, KEYRING_USERS[provider])
        except Exception:
            _log.info("Nenhuma chave de %s para remover.", provider)
        else:
            _log.info("Chave da API (%s) removida do cofre.", provider)

    def detected_soffice(self) -> Path | None:
        """LibreOffice found automatically (ignores the configured path)."""
        return locate_soffice()

    def diagnose(self, settings: Settings) -> list[DiagnosticItem]:
        """Key of the active provider, LibreOffice, Aptos font and template (same as doctor)."""
        provider = settings.llm_provider
        name = PROVIDER_NAMES.get(provider, provider)
        if provider not in PROVIDERS:
            key = DiagnosticItem(
                "Chave da API",
                False,
                f"Provedor desconhecido: {provider}",
                "Escolha OpenAI ou Anthropic.",
            )
        elif self.has_key(provider):
            key = DiagnosticItem(f"Chave da API ({name})", True, "Configurada.")
        else:
            key = DiagnosticItem(
                f"Chave da API ({name})",
                False,
                "Não configurada.",
                f"Informe a chave da {name} nesta tela (ou defina {API_KEY_VARS[provider]}).",
            )

        soffice = locate_soffice(settings.soffice_path)
        office = (
            DiagnosticItem("LibreOffice", True, str(soffice))
            if soffice
            else DiagnosticItem(
                "LibreOffice",
                False,
                "Não encontrado.",
                "Instale o LibreOffice (gratuito) para gerar o PDF ou informe o soffice.",
            )
        )

        fonts = FontLocator(settings.fonts_dir).locate()
        if fonts.complete:
            font = DiagnosticItem("Fonte Aptos", True, str(fonts.regular))
        else:
            font = DiagnosticItem(
                "Fonte Aptos",
                False,
                "Regular e negrito não encontrados."
                if not fonts.regular
                else "Negrito não encontrado.",
                "Instale a Aptos (download gratuito da Microsoft) ou informe a pasta das fontes.",
            )

        return [key, office, font, self._template_item(settings.template_path)]

    @staticmethod
    def _template_item(path: Path | None) -> DiagnosticItem:
        try:
            template = MassTemplate.load(path)
            errors = [n.message for n in template.validate() if n.level == "error"]
        except PallottiError as error:
            return DiagnosticItem(
                "Modelo PowerPoint", False, str(error), "Escolha um modelo .pptx válido."
            )
        if errors:
            return DiagnosticItem(
                "Modelo PowerPoint",
                False,
                errors[0],
                "Corrija o modelo (veja `pallotti template inspect`).",
            )
        return DiagnosticItem("Modelo PowerPoint", True, "Válido.")

    @staticmethod
    def _check(provider: str) -> None:
        if provider not in PROVIDERS:
            raise PallottiError(f"Provedor de IA desconhecido: {provider}.")
