"""Duração lida do cabeçalho do MP4, sem depender do ffprobe."""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I4s", len(body) + 8, kind) + body


def mvhd(version: int, timescale: int, duration: int) -> bytes:
    times = struct.pack(">QQIQ", 0, 0, timescale, duration) if version else struct.pack(">IIII", 0, 0, timescale, duration)
    return box(b"mvhd", bytes([version, 0, 0, 0]) + times + bytes(80))


def test_le_os_videos_reais_do_projeto():
    from app.seed import mp4_duration
    for video in (ROOT / "media" / "videos").glob("*.mp4"):
        assert mp4_duration(video) == 48, video.name


def test_cabecalho_no_fim_do_arquivo_e_versao_64_bits(tmp_path):
    from app.seed import mp4_duration
    path = tmp_path / "v.mp4"
    path.write_bytes(box(b"ftyp", b"isom") + box(b"mdat", bytes(500)) + box(b"moov", mvhd(1, 1000, 90500)))
    assert mp4_duration(path) == 90


def test_arquivo_invalido_nao_quebra_o_envio(tmp_path):
    from app.seed import mp4_duration
    casos = {
        "vazio.mp4": b"",
        "lixo.mp4": b"nao e video" * 50,
        "sem-duracao.mp4": box(b"ftyp", b"isom"),
        "cortado.mp4": box(b"moov", box(b"mvhd", b"\x00")),
        "escala-zero.mp4": box(b"moov", mvhd(0, 0, 100)),
        "webm.mp4": b"\x1a\x45\xdf\xa3" + bytes(64),
    }
    for name, content in casos.items():
        path = tmp_path / name
        path.write_bytes(content)
        assert mp4_duration(path) == 0, name
    assert mp4_duration(tmp_path / "nao-existe.mp4") == 0
