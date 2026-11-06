"""Identidade Streamy: cores do :root, contraste e entrega do logo."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "styles.css"


def variaveis() -> dict:
    root = re.search(r":root\{(.*?)\}", CSS.read_text(encoding="utf-8"), re.S).group(1)
    return dict(re.findall(r"--([a-z0-9-]+):(#[0-9A-Fa-f]{6})", root))


def luminancia(cor: str) -> float:
    canais = [int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    claro, escuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def test_cores_pedidas_estao_no_root():
    v = variaveis()
    assert v["blue"].upper() == "#022AD5"
    assert v["amber"].upper() == "#5473FF"  # Variável usada pelo foco e pelos destaques sobre fundo escuro.
    assert v["white"].upper() == "#F7F7F7"
    assert luminancia(v["navy"]) < 0.01


def test_contrastes_principais():
    v = variaveis()
    assert contraste("#FFFFFF", v["blue"]) >= 4.5       # texto dos botões
    assert contraste(v["amber"], v["navy"]) >= 3        # foco e destaque sobre a base escura
    assert contraste(v["amber"], v["gray"]) >= 3        # foco sobre o fundo claro
    assert contraste(v["navy"], v["amber"]) >= 4.5      # selo "Assinantes"
    assert contraste(v["on-navy"], v["navy"]) >= 4.5    # texto secundário no escuro
    assert contraste(v["muted"], v["gray"]) >= 4.5      # texto secundário no claro
    assert contraste(v["text"], v["gray"]) >= 4.5
    assert contraste(v["blue-dark"], v["gray"]) >= 4.5  # links


def test_logo_e_entregue_como_png(anon):
    r = anon.get("/streamy-logo.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
