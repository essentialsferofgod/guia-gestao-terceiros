"""Sobe um servidor real, com banco e mídia temporários, e testa pela rede."""
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Demo@2026"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    return tmp_path_factory.mktemp("guia-db") / "test.db"


@pytest.fixture(scope="session")
def base(tmp_path_factory, database):
    tmp = tmp_path_factory.mktemp("guia")
    shutil.copytree(ROOT / "media", tmp / "media")
    port = free_port()
    env = {**os.environ, "DATABASE_PATH": str(database), "MEDIA_DIR": str(tmp / "media"),
           "DEMO_PASSWORD": PASSWORD, "APP_PORT": str(port), "PYTHONPATH": str(ROOT / "backend")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if requests.get(f"{url}/api/health", timeout=1).ok:
                break
        except requests.RequestException:
            time.sleep(0.1)
    else:
        proc.kill()
        raise RuntimeError(proc.stderr.read().decode())
    yield url
    proc.terminate()
    proc.wait(timeout=5)


class Client(requests.Session):
    def __init__(self, base):
        super().__init__()
        self.base = base

    def request(self, method, url, *args, **kwargs):
        return super().request(method, self.base + url, *args, timeout=15, **kwargs)


def login(base, email):
    client = Client(base)
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def anon(base):
    return Client(base)


@pytest.fixture
def admin(base):
    return login(base, "admin@demo.guia.test")


@pytest.fixture
def subscriber(base):
    return login(base, "assinante@demo.guia.test")


@pytest.fixture
def basic(base):
    return login(base, "basico@demo.guia.test")


@pytest.fixture
def expired(base):
    return login(base, "expirado@demo.guia.test")


@pytest.fixture
def fresh(base):
    client = Client(base)
    client.email = f"novo-{uuid.uuid4().hex[:8]}@exemplo.test"
    response = client.post("/api/auth/register", json={"name": "Pessoa Nova", "email": client.email, "password": "Senha1234"})
    assert response.status_code == 201, response.text
    return client


def video_by_slug(client, slug):
    return next(v for v in client.get("/api/videos").json()["videos"] if v["slug"] == slug)
