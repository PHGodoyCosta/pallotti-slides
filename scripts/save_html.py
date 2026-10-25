"""Save the real HTML of the P3 song pages as test fixtures (network only here).

Usage: ``uv run python scripts/save_html.py``. Skips files already saved.
"""

import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "html"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
CIFRA = "https://www.cifraclub.com.br"
LETRAS = "https://www.letras.mus.br"
URLS = [
    f"{CIFRA}/catolicas/eis-me-aqui-senhor/",
    f"{CIFRA}/catolicas/pelos-pecados-ato-penitencial/",
    f"{CIFRA}/catolicas/gloria-a-deus-nos-altos-ceus/",
    f"{CIFRA}/padre-zezinho/um-coracao-para-amar/",
    f"{CIFRA}/ministerio-gratia-plena/tu-es-minha-vida-outro-deus-nao-ha/",
    f"{CIFRA}/padre-zezinho/o-povo-de-deus/",
    f"{CIFRA}/chitaozinho-e-xororo/ave-maria/",
    f"{LETRAS}/padre-zezinho/um-coracao-para-amar/",
    f"{LETRAS}/padre-zezinho/o-povo-de-deus/",
]


def target(url: str) -> Path:
    parsed = urlparse(url)
    folder = "cifra_club" if "cifraclub" in parsed.netloc else "letras_mus"
    artist, song = parsed.path.strip("/").split("/")
    return ROOT / folder / f"{artist}__{song}.html"


def fetch(url: str) -> str | None:
    """Fetch with curl: the sites answer 403 to httpx (HTTP/1.1) but 200 to HTTP/2 clients."""
    result = subprocess.run(
        [
            "curl",
            "-sL",
            "--compressed",
            "-m",
            "15",
            "-w",
            "\n%{http_code}",
            "-A",
            USER_AGENT,
            "-H",
            "Accept: text/html",
            "-H",
            "Accept-Language: pt-BR,pt;q=0.9",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    body, _, status = result.stdout.rpartition("\n")
    print(status, url)
    return body if status == "200" else None


def main() -> None:
    for url in URLS:
        path = target(url)
        if path.exists():
            continue
        html = fetch(url)
        if html:
            path.write_text(html, encoding="utf-8")
        time.sleep(3)


if __name__ == "__main__":
    main()
