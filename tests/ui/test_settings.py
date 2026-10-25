import logging
from pathlib import Path

from qfluentwidgets import isDarkTheme

from pallotti_slides.config import Settings, load_settings
from pallotti_slides.ui.pages.settings import SettingsPage
from pallotti_slides.ui.theme import apply_theme

from .conftest import FakeKeyring, make_service

SECRET = "sk-super-secret-123"


def _page(qtbot, tmp_path: Path, keyring: FakeKeyring | None = None) -> SettingsPage:  # type: ignore[no-untyped-def]
    page = SettingsPage(make_service(tmp_path / "config.json", keyring))
    qtbot.addWidget(page)
    return page


def test_save_and_reload_settings(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    page = _page(qtbot, tmp_path)
    page.provider_combo.setCurrentIndex(page.provider_combo.findData("anthropic"))
    page.anthropic_model.setText("modelo-x")
    page.output_dir.edit.setText(str(tmp_path / "saida"))
    page.min_font.setValue(30)
    page.max_font.setValue(50)
    page.max_lines.setValue(5)
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("light"))
    page.save()

    loaded = load_settings(tmp_path / "config.json")
    assert loaded.llm_provider == "anthropic"
    assert loaded.anthropic_model == "modelo-x"
    assert loaded.output_dir == tmp_path / "saida"
    assert (loaded.typography.min_font, loaded.typography.max_font) == (30, 50)
    assert loaded.typography.max_lines == 5
    assert loaded.theme == "light"
    again = _page(qtbot, tmp_path)
    assert again.max_font.value() == 50
    assert again.provider_combo.currentData() == "anthropic"


def test_invalid_typography_is_not_saved(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    page = _page(qtbot, tmp_path)
    page.min_font.setValue(60)
    page.max_font.setValue(40)
    page.save()
    assert not (tmp_path / "config.json").exists()


def test_theme_applies_immediately(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    apply_theme("light")
    page = _page(qtbot, tmp_path)
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("dark"))
    assert isDarkTheme()
    apply_theme("light")


def test_key_never_shown_nor_in_json_nor_log(qtbot, tmp_path: Path, caplog) -> None:  # type: ignore[no-untyped-def]
    keyring = FakeKeyring()
    page = _page(qtbot, tmp_path, keyring)
    caplog.set_level(logging.DEBUG)
    assert page.openai_key.status.text() == "Chave: não configurada"
    page.openai_key.field.setText(SECRET)
    page.openai_key.save_button.click()
    page.save()

    assert list(keyring.store.values()) == [SECRET]
    assert page.openai_key.status.text() == "Chave: configurada"
    assert page.openai_key.field.text() == ""
    texts = [w.text() for w in page.findChildren(object) if hasattr(w, "text")]
    assert all(SECRET not in str(t) for t in texts)
    assert SECRET not in (tmp_path / "config.json").read_text()
    assert SECRET not in caplog.text
    assert SECRET not in Settings().model_dump_json()

    page.openai_key.remove_button.click()
    assert keyring.store == {}
    assert page.openai_key.status.text() == "Chave: não configurada"


def test_diagnostic_shows_four_items(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    page = _page(qtbot, tmp_path)
    names = [item.name for item, _ in page.diagnostic_rows]
    assert len(names) == 4
    assert names[0].startswith("Chave da API")
    assert names[1:] == ["LibreOffice", "Fonte Aptos", "Modelo PowerPoint"]
    assert not page.diagnostic_rows[0][0].ok  # no key in the fake keyring
    assert page.diagnostic_rows[0][0].hint
