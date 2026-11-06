"""Oferta de fim de teste: prazo definido no servidor, preços, ativação simulada e convivência com o admin."""
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import Client, video_by_slug
from test_api import INTRO, PREMIUM

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + delta).isoformat()


@pytest.fixture
def conta(base):
    client = Client(base)
    client.email = f"oferta-{uuid.uuid4().hex[:8]}@exemplo.test"
    r = client.post("/api/auth/register", json={"name": "Pessoa Oferta", "email": client.email, "password": "Senha1234"})
    assert r.status_code == 201, r.text
    return client


@pytest.fixture
def fim_do_teste(database):
    """Define há quanto tempo o teste da conta terminou."""
    def ajustar(client, ago: timedelta):
        with sqlite3.connect(database, timeout=10) as conn:
            cur = conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (iso(-ago), client.email))
            assert cur.rowcount == 1
    return ajustar


def oferta(client):
    return client.get("/api/me").json()["user"]["offer"]


def test_sem_oferta_durante_o_teste_e_para_assinante_e_admin(conta, subscriber, admin, anon):
    assert oferta(conta) is None
    assert oferta(subscriber) is None
    assert oferta(admin) is None
    for client in (conta, subscriber, admin):
        assert client.post("/api/offer/activate").status_code == 409
    assert conta.get("/api/me").json()["user"]["plan_status"] == "trial"
    assert anon.post("/api/offer/activate").status_code == 401


def test_oferta_mostra_prazo_precos_e_aviso(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    o = oferta(conta)
    assert o["status"] == "available"
    assert 70 * 3600 < o["seconds_left"] <= 71 * 3600
    assert o["notice"] == "Demonstração, nenhuma cobrança"
    assert [(p["period"], p["price"], p["cents"]) for p in o["prices"]] == [
        ("1º mês", "R$ 9,90", 990), ("Meses 2 e 3", "R$ 19,90", 1990), ("A partir do 4º mês", "R$ 29,90", 2990)]


def test_prazo_e_de_72_horas_a_partir_do_fim_do_teste(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(seconds=5))
    o = oferta(conta)
    limite = datetime.fromisoformat(o["expires_at"]) - datetime.now(timezone.utc)
    assert timedelta(hours=71, minutes=59) < limite <= timedelta(hours=72)


def test_recarregar_ou_entrar_de_novo_nao_reinicia_a_contagem(base, conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=10))
    primeiro = oferta(conta)["expires_at"]
    assert oferta(conta)["expires_at"] == primeiro
    conta.post("/api/auth/logout")
    conta.post("/api/auth/login", json={"email": conta.email, "password": "Senha1234"})
    assert oferta(conta)["expires_at"] == primeiro


def test_mensagem_de_bloqueio_nao_manda_falar_com_administrador(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    video = video_by_slug(conta, INTRO)
    assert video["lock_reason"] == "trial_expired"
    assert "Ative a oferta" in video["lock_message"] and "administrador" not in video["lock_message"].lower()
    r = conta.get(f"/api/videos/{video['id']}/stream")
    assert r.status_code == 403 and "Ative a oferta" in r.json()["error"]["message"]


def test_ativacao_libera_conteudo_na_hora_sem_pedir_pagamento(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    premium = video_by_slug(conta, PREMIUM)["id"]
    assert conta.get(f"/api/videos/{premium}/stream").status_code == 403

    r = conta.post("/api/offer/activate")
    assert r.status_code == 200
    user = r.json()["user"]
    assert user["plan_status"] == "premium" and user["offer"]["status"] == "activated"
    assert user["offer"]["activated_at"] and user["offer"]["notice"] == "Demonstração, nenhuma cobrança"
    assert conta.get(f"/api/videos/{premium}/stream", headers={"Range": "bytes=0-9"}).status_code == 206


def test_repetir_a_ativacao_nao_altera_a_data(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    primeira = conta.post("/api/offer/activate").json()["user"]["offer"]["activated_at"]
    r = conta.post("/api/offer/activate")
    assert r.status_code == 200 and r.json()["user"]["offer"]["activated_at"] == primeira


def test_oferta_vencida_nao_ativa_e_mensagem_muda(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=72, seconds=1))
    assert oferta(conta)["status"] == "expired"
    r = conta.post("/api/offer/activate")
    assert r.status_code == 409 and r.json()["error"]["code"] == "offer_unavailable"
    video = video_by_slug(conta, INTRO)
    assert video["locked"] and "Ative a oferta" not in video["lock_message"]
    assert conta.get("/api/me").json()["user"]["plan_status"] == "trial_expired"


def test_ultimo_segundo_da_oferta_ainda_ativa(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=71, minutes=59, seconds=30))
    assert conta.post("/api/offer/activate").status_code == 200


def test_ativacao_pelo_admin_continua_funcionando(admin, conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=100))  # Oferta vencida: resta o caminho do administrador.
    uid = conta.get("/api/me").json()["user"]["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"plan": "premium"}).status_code == 200
    user = conta.get("/api/me").json()["user"]
    assert user["plan_status"] == "premium" and user["offer"] is None
    video = video_by_slug(conta, PREMIUM)
    assert conta.get(f"/api/videos/{video['id']}/stream", headers={"Range": "bytes=0-9"}).status_code == 206


def test_oferta_so_pode_ser_usada_uma_vez(admin, conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    uid = conta.get("/api/me").json()["user"]["id"]
    assert conta.post("/api/offer/activate").status_code == 200
    # O administrador encerra a assinatura ainda dentro das 72 horas.
    assert admin.patch(f"/api/admin/users/{uid}", json={"plan": "trial"}).status_code == 200
    assert oferta(conta)["status"] == "used"
    assert conta.post("/api/offer/activate").status_code == 409
    assert conta.get("/api/me").json()["user"]["plan_status"] == "trial_expired"
    assert "Ative a oferta" not in video_by_slug(conta, INTRO)["lock_message"]


def test_plano_ativado_vale_para_todos_os_perfis(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    segundo = conta.post("/api/profiles", json={"name": "Outro Perfil"}).json()["profile"]["id"]
    conta.post("/api/offer/activate")
    assert conta.post(f"/api/profiles/{segundo}/select").json()["user"]["plan_status"] == "premium"
    assert video_by_slug(conta, PREMIUM)["locked"] is False


def test_oferta_nao_aceita_preco_vindo_do_cliente(conta, fim_do_teste):
    fim_do_teste(conta, timedelta(hours=1))
    conta.post("/api/offer/activate", json={"cents": 1, "status": "activated"})
    assert [p["cents"] for p in oferta(conta)["prices"]] == [990, 1990, 2990]


def test_migracao_adiciona_coluna_da_oferta(tmp_path, monkeypatch):
    from app import config, db
    from test_perfis import LEGADO
    path = tmp_path / "antigo.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGADO)
    conn.close()
    monkeypatch.setattr(config, "DATABASE_PATH", path)
    db.init_db()
    with db.transaction() as c:
        assert c.execute("SELECT offer_activated_at FROM users WHERE id = 1").fetchone()[0] is None
