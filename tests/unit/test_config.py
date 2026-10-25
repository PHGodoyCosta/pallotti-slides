from pathlib import Path

from pallotti_slides.config import FontLocator, Paths


def _make_fonts(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Aptos.ttf").write_bytes(b"")
    (directory / "Aptos-Bold.ttf").write_bytes(b"")


def _no_fc(_: str) -> str:
    return ""


def test_configured_path_has_priority(tmp_path: Path) -> None:
    conf = tmp_path / "conf"
    env = tmp_path / "env"
    _make_fonts(conf)
    _make_fonts(env)
    locator = FontLocator(conf, {"PALLOTTI_FONTS_DIR": str(env)}, _no_fc, "linux")
    found = locator.locate()
    assert found.regular == conf / "Aptos.ttf"
    assert found.bold == conf / "Aptos-Bold.ttf"
    assert found.complete


def test_environment_variable(tmp_path: Path) -> None:
    _make_fonts(tmp_path)
    locator = FontLocator(None, {"PALLOTTI_FONTS_DIR": str(tmp_path)}, _no_fc, "linux")
    assert locator.locate_regular() == tmp_path / "Aptos.ttf"
    assert locator.locate_bold() == tmp_path / "Aptos-Bold.ttf"


def test_fc_match_accepts_only_aptos(tmp_path: Path) -> None:
    _make_fonts(tmp_path)

    def fc(pattern: str) -> str:
        file = "Aptos-Bold.ttf" if "bold" in pattern else "Aptos.ttf"
        return f"Aptos|{tmp_path / file}"

    locator = FontLocator(None, {}, fc, "linux")
    assert locator.locate_regular() == tmp_path / "Aptos.ttf"
    assert locator.locate_bold() == tmp_path / "Aptos-Bold.ttf"


def test_fc_match_substitute_is_ignored(tmp_path: Path) -> None:
    other = tmp_path / "DejaVuSans.ttf"
    other.write_bytes(b"")
    locator = FontLocator(None, {}, lambda _: f"DejaVu Sans|{other}", "linux")
    assert locator.locate_regular() is None
    assert locator.locate_bold() is None


def test_cloud_fonts(tmp_path: Path) -> None:
    cloud = tmp_path / "Microsoft" / "FontCache" / "4" / "CloudFonts" / "Aptos"
    _make_fonts(cloud)
    locator = FontLocator(None, {"LOCALAPPDATA": str(tmp_path)}, _no_fc, "linux")
    assert locator.locate_regular() == cloud / "Aptos.ttf"


def test_windows_fonts(tmp_path: Path) -> None:
    _make_fonts(tmp_path / "Fonts")
    locator = FontLocator(None, {"WINDIR": str(tmp_path)}, _no_fc, "win32")
    assert locator.locate_bold() == tmp_path / "Fonts" / "Aptos-Bold.ttf"


def test_nothing_found(tmp_path: Path) -> None:
    locator = FontLocator(tmp_path / "missing", {}, _no_fc, "linux")
    found = locator.locate()
    assert found.regular is None
    assert found.bold is None
    assert not found.complete


def test_default_paths() -> None:
    paths = Paths.default()
    assert "PallottiSlides" in str(paths.data)
    assert paths.config.name == "config.json"
