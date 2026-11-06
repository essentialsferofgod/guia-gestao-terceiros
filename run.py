"""Inicia a aplicação: python run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

import uvicorn  # noqa: E402

from app import config  # noqa: E402

def reset_database() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{config.DATABASE_PATH}{suffix}").unlink(missing_ok=True)
    print("Banco apagado. Os dados demonstrativos serão recriados.")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_database()
    print(f"Guia para a Gestão de Terceiros em http://{config.HOST}:{config.PORT}")
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, app_dir=str(Path(__file__).parent / "backend"))
