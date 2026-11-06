import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path(os.environ.get("SHOTS_DIR", ROOT / "docs" / "capturas"))


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    return tmp_path_factory.mktemp("guia-e2e-db") / "e2e.db"


@pytest.fixture(scope="session")
def base(tmp_path_factory, database):
    tmp = tmp_path_factory.mktemp("guia-e2e")
    shutil.copytree(ROOT / "media", tmp / "media")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "DATABASE_PATH": str(database), "MEDIA_DIR": str(tmp / "media"),
           "DEMO_PASSWORD": "Demo@2026", "PYTHONPATH": str(ROOT / "backend")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if requests.get(f"{url}/api/health", timeout=1).ok:
                break
        except requests.RequestException:
            time.sleep(0.1)
    yield url
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser, base):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, base_url=base)
    pg = context.new_page()
    pg.problems = []
    pg.on("pageerror", lambda e: pg.problems.append(f"pageerror: {e}"))
    pg.on("console", lambda m: pg.problems.append(f"console: {m.text}")
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    yield pg
    context.close()
    assert pg.problems == []


@pytest.fixture
def phone(browser, base):
    context = browser.new_context(viewport={"width": 390, "height": 844}, base_url=base, is_mobile=True, has_touch=True, device_scale_factor=2)
    pg = context.new_page()
    yield pg
    context.close()


@pytest.fixture(scope="session")
def shot():
    SHOTS.mkdir(parents=True, exist_ok=True)
    def take(page, name, full=True):
        page.wait_for_timeout(250)
        page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)
    return take
