"""Checks the import rules of ARQUITETURA §2 by AST."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "pallotti_slides"
PACKAGE = "pallotti_slides"
LAYERS = {"domain", "llm", "leaflet", "songs", "presentation", "db", "application", "ui"}


def _imported_modules(file: Path) -> set[str]:
    """Full names of imported modules (relative imports are made absolute)."""
    parts = list(file.relative_to(ROOT.parent).with_suffix("").parts)
    current_package = parts[:-1]
    found: set[str] = set()
    for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current_package[: len(current_package) - (node.level - 1)]
                name = ".".join([*base, node.module] if node.module else base)
            else:
                name = node.module or ""
            found.add(name)
            found.update(f"{name}.{alias.name}" for alias in node.names)
    return found


def _files() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def _layer(file: Path) -> str | None:
    first = file.relative_to(ROOT).parts[0]
    return first if first in LAYERS else None


def _is_under(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _internal(modules: set[str]) -> set[str]:
    return {m for m in modules if _is_under(m, PACKAGE)}


def _layer_of_module(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) > 1 and parts[0] == PACKAGE and parts[1] in LAYERS:
        return parts[1]
    return None


def test_has_files_to_check() -> None:
    assert _files()


@pytest.mark.parametrize("file", _files(), ids=lambda f: f.relative_to(ROOT).as_posix())
def test_import_rules(file: Path) -> None:
    modules = _imported_modules(file)
    name = file.relative_to(ROOT).as_posix()
    layer = _layer(file)

    # 1. domain imports nothing from the project outside domain itself
    if layer == "domain":
        foreign = {m for m in _internal(modules) if not _is_under(m, f"{PACKAGE}.domain")}
        assert not foreign, f"{name} (domain) imports the project: {foreign}"

    # 2. only ui imports PySide6 / qfluentwidgets
    if layer != "ui":
        qt = {m for m in modules if _is_under(m, "PySide6") or _is_under(m, "qfluentwidgets")}
        assert not qt, f"{name} imports Qt outside ui/: {qt}"

    # 3. ui and cli only use application and domain
    if layer == "ui" or name == "cli.py":
        for module in _internal(modules):
            target = _layer_of_module(module)
            if target is not None and target not in {"application", "domain", "ui"}:
                pytest.fail(f"{name} imports {module}; only application/domain are allowed")

    # 4. only llm/ imports LangChain, anthropic and openai
    if layer != "llm":
        sdks = {
            m
            for m in modules
            if _is_under(m, "anthropic") or _is_under(m, "openai") or m.startswith("langchain")
        }
        assert not sdks, f"{name} imports an LLM SDK outside llm/: {sdks}"

    # 5. only db imports sqlalchemy
    if layer != "db":
        assert not {m for m in modules if _is_under(m, "sqlalchemy")}, f"{name} imports sqlalchemy"


def test_import_extractor_sees_imports() -> None:
    assert "sys" in _imported_modules(ROOT / "ui" / "app.py")
    assert _is_under("PySide6.QtCore", "PySide6")
    assert not _is_under("PySide6x", "PySide6")
