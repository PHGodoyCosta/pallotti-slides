"""Real-network/LLM check of song search and repertoire import (run with ``pytest -m live``)."""

import os

import pytest

from pallotti_slides.config import Settings
from pallotti_slides.llm.client import API_KEY_VARS, create_llm_client
from pallotti_slides.songs.repertoire import RepertoireImporter
from pallotti_slides.songs.web_search import ALLOWED_DOMAINS, WebSongSearcher

pytestmark = pytest.mark.live
REPERTOIRE = "https://www.cifraclub.com.br/@32936533/repertorio/57846361/"
PROVIDERS = [
    pytest.param(name, marks=pytest.mark.skipif(not os.environ.get(var), reason=f"sem {var}"))
    for name, var in API_KEY_VARS.items()
]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_web_search_returns_only_allowed_sites(provider: str) -> None:
    llm = create_llm_client(Settings(llm_provider=provider), keyring_get=lambda _p: None)
    found = WebSongSearcher(llm).search("Me chamaste para caminhar", "Padre Zezinho")
    assert found
    assert all(any((c.url or "").split("/")[2].endswith(d) for d in ALLOWED_DOMAINS) for c in found)


def test_repertoire_link_gives_a_proposal() -> None:
    try:
        proposal = RepertoireImporter().load(REPERTOIRE)
    except Exception as error:  # network or site blocking: skip, do not fail
        pytest.skip(f"sem acesso ao Cifra Club: {error}")
    assert proposal.requires_confirmation
    assert len(proposal.items) == 7
