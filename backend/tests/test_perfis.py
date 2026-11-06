"""Perfis por conta: limites, posse, isolamento de dados e migração de bancos antigos."""
import sqlite3
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from conftest import Client, video_by_slug
from test_api import INTRO, PREMIUM, answers_path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SENHA = "Senha1234"


def nova_conta(base):
    client = Client(base)
    client.email = f"perfil-{uuid.uuid4().hex[:8]}@exemplo.test"
    r = client.post("/api/auth/register", json={"name": "Titular da Conta", "email": client.email, "password": SENHA})
    assert r.status_code == 201, r.text
    return client


def entrar(base, email):
    client = Client(base)
    assert client.post("/api/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return client


def criar_perfil(client, name):
    r = client.post("/api/profiles", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["profile"]["id"]


def selecionar(client, profile_id):
    r = client.post(f"/api/profiles/{profile_id}/select")
    assert r.status_code == 200, r.text
    return r.json()["user"]


def conta_com_dois_perfis(base):
    client = nova_conta(base)
    primeiro = client.get("/api/me").json()["user"]["active_profile_id"]
    segundo = criar_perfil(client, "Segundo Perfil")
    return client, primeiro, segundo


# Criação e limites
def test_cadastro_cria_o_primeiro_perfil_e_ja_o_ativa(base):
    user = nova_conta(base).get("/api/me").json()["user"]
    assert [p["name"] for p in user["profiles"]] == ["Titular da Conta"]
    assert user["active_profile_id"] == user["profiles"][0]["id"]
    assert user["needs_profile"] is False and user["max_profiles"] == 3


def test_login_pula_a_escolha_quando_ha_um_so_perfil(base):
    conta = nova_conta(base)
    user = Client(base).post("/api/auth/login", json={"email": conta.email, "password": SENHA}).json()["user"]
    assert user["needs_profile"] is False and user["active_profile_id"] == user["profiles"][0]["id"]


def test_criar_perfil_nao_tira_a_sessao_do_perfil_atual(base):
    client = nova_conta(base)
    outra_sessao = entrar(base, client.email)
    atual = client.get("/api/me").json()["user"]["active_profile_id"]
    vid = video_by_slug(client, INTRO)["id"]

    r = client.post("/api/profiles", json={"name": "Recém-criado"})

    assert r.json()["user"]["active_profile_id"] == atual and r.json()["user"]["needs_profile"] is False
    assert client.put(f"/api/progress/{vid}", json={"position_seconds": 9}).status_code == 200
    # A sessão aberta em outro aparelho também continua no perfil em que estava.
    assert outra_sessao.get("/api/me").json()["user"]["active_profile_id"] == atual
    assert outra_sessao.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 9


def test_limite_de_tres_perfis(base):
    client = nova_conta(base)
    criar_perfil(client, "Segundo")
    criar_perfil(client, "Terceiro")
    r = client.post("/api/profiles", json={"name": "Quarto"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "profile_limit"
    assert len(client.get("/api/profiles").json()["profiles"]) == 3


def test_limite_vale_com_pedidos_simultaneos(base):
    client = nova_conta(base)
    cookie = client.cookies.get("gt_session")

    def pedir(n):
        c = Client(base)
        c.cookies.set("gt_session", cookie)
        return c.post("/api/profiles", json={"name": f"Paralelo {n}"}).status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(pedir, range(8)))
    assert sorted(codes) == [201, 201] + [409] * 6, codes
    assert len(client.get("/api/profiles").json()["profiles"]) == 3


def test_nome_de_perfil_e_validado(base):
    client = nova_conta(base)
    assert client.post("/api/profiles", json={"name": "A"}).status_code == 422
    assert client.post("/api/profiles", json={"name": "Valido", "user_id": 1}).status_code == 422
    r = client.post("/api/profiles", json={"name": "Titular da Conta"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "profile_name_in_use"


def test_renomear_perfil(base):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    r = client.patch(f"/api/profiles/{segundo}", json={"name": "Novo Nome"})
    assert r.status_code == 200
    assert "Novo Nome" in [p["name"] for p in r.json()["user"]["profiles"]]
    assert client.patch(f"/api/profiles/{primeiro}", json={"name": "Novo Nome"}).status_code == 409


def test_conta_mantem_ao_menos_um_perfil(base):
    client = nova_conta(base)
    unico = client.get("/api/me").json()["user"]["active_profile_id"]
    r = client.delete(f"/api/profiles/{unico}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_profile"


# Posse: perfil de outra conta responde 403
def test_perfil_de_outra_conta_responde_403(base):
    dona = nova_conta(base)
    alheio = criar_perfil(dona, "Perfil Alheio")
    invasora = nova_conta(base)
    antes = invasora.get("/api/me").json()["user"]["active_profile_id"]

    r = invasora.post(f"/api/profiles/{alheio}/select")
    assert r.status_code == 403 and r.json()["error"]["code"] == "profile_forbidden"
    assert invasora.patch(f"/api/profiles/{alheio}", json={"name": "Roubado"}).status_code == 403
    assert invasora.delete(f"/api/profiles/{alheio}").status_code == 403

    assert invasora.get("/api/me").json()["user"]["active_profile_id"] == antes
    assert "Perfil Alheio" in [p["name"] for p in dona.get("/api/profiles").json()["profiles"]]


def test_administrador_tambem_recebe_403_em_perfil_alheio(base, admin):
    alheio = criar_perfil(nova_conta(base), "Perfil Privado")
    assert admin.post(f"/api/profiles/{alheio}/select").status_code == 403


def test_perfis_exigem_sessao_e_id_existente(base, anon, fresh):
    assert anon.get("/api/profiles").status_code == 401
    assert anon.post("/api/profiles", json={"name": "Visitante"}).status_code == 401
    assert anon.post("/api/profiles/1/select").status_code == 401
    assert fresh.post("/api/profiles/99999999/select").status_code == 404


def test_lista_so_mostra_perfis_da_propria_conta(base):
    dona = nova_conta(base)
    criar_perfil(dona, "Somente da Dona")
    nomes = [p["name"] for p in nova_conta(base).get("/api/profiles").json()["profiles"]]
    assert nomes == ["Titular da Conta"]


# Isolamento entre perfis da mesma conta
def test_progresso_retomada_historico_e_continuar_sao_por_perfil(base):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    vid = video_by_slug(client, INTRO)["id"]

    selecionar(client, primeiro)
    assert client.put(f"/api/progress/{vid}", json={"position_seconds": 20}).status_code == 200

    selecionar(client, segundo)
    assert client.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 0
    assert video_by_slug(client, INTRO)["position_seconds"] == 0
    vazio = client.get("/api/me/learning").json()
    assert vazio["history"] == [] and vazio["continue_watching"] == [] and vazio["stats"]["started"] == 0

    assert client.put(f"/api/progress/{vid}", json={"position_seconds": 7}).status_code == 200

    selecionar(client, primeiro)
    assert client.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 20
    assert [v["position_seconds"] for v in client.get("/api/me/learning").json()["continue_watching"]] == [20]

    selecionar(client, segundo)
    assert client.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 7


def test_conclusao_e_por_perfil(base):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    vid = video_by_slug(client, INTRO)["id"]
    selecionar(client, primeiro)
    assert client.put(f"/api/progress/{vid}", json={"position_seconds": 47}).json()["completed"] is True
    selecionar(client, segundo)
    assert video_by_slug(client, INTRO)["completed"] is False
    assert client.get("/api/me/learning").json()["stats"]["completed"] == 0


def test_trilhas_salvas_sao_por_perfil(base, anon):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    answers, _ = answers_path(anon, "documentacao", [0, 0, 2])
    payload = {"situation": "documentacao", "answers": answers}

    selecionar(client, primeiro)
    trilha = client.post("/api/paths", json=payload).json()["path"]

    selecionar(client, segundo)
    assert client.get("/api/paths").json()["paths"] == []
    assert client.get("/api/me/learning").json()["paths"] == []
    assert client.delete(f"/api/paths/{trilha['id']}").status_code == 404
    # A mesma resposta em outro perfil vira outra trilha, não a do primeiro perfil.
    outra = client.post("/api/paths", json=payload).json()["path"]
    assert outra["id"] != trilha["id"]

    selecionar(client, primeiro)
    assert [p["id"] for p in client.get("/api/paths").json()["paths"]] == [trilha["id"]]


def test_progresso_da_trilha_usa_o_perfil_ativo(base, anon):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    answers, _ = answers_path(anon, "documentacao", [0, 0, 2])
    payload = {"situation": "documentacao", "answers": answers}
    vid = video_by_slug(client, INTRO)["id"]

    selecionar(client, primeiro)
    client.put(f"/api/progress/{vid}", json={"position_seconds": 47})
    selecionar(client, segundo)
    resultado = client.post("/api/diagnostic/evaluate", json=payload).json()["result"]
    assert all(item["video"]["position_seconds"] == 0 for item in resultado["path"])


def test_duas_sessoes_da_conta_assistem_em_perfis_diferentes(base):
    sessao_a, primeiro, segundo = conta_com_dois_perfis(base)
    sessao_b = entrar(base, sessao_a.email)
    selecionar(sessao_a, primeiro)
    selecionar(sessao_b, segundo)
    vid = video_by_slug(sessao_a, INTRO)["id"]

    sessao_a.put(f"/api/progress/{vid}", json={"position_seconds": 11})
    sessao_b.put(f"/api/progress/{vid}", json={"position_seconds": 22})

    assert sessao_a.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 11
    assert sessao_b.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 22


def test_dados_do_perfil_nao_vazam_para_outra_conta(base):
    dona, primeiro, _ = conta_com_dois_perfis(base)
    vid = video_by_slug(dona, INTRO)["id"]
    selecionar(dona, primeiro)
    dona.put(f"/api/progress/{vid}", json={"position_seconds": 33})
    outra = nova_conta(base)
    assert outra.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 0
    assert outra.get("/api/me/learning").json()["history"] == []


# Sessão sem perfil escolhido
def test_com_varios_perfis_o_login_exige_escolha_e_nao_presume(base):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    vid = video_by_slug(client, INTRO)["id"]
    selecionar(client, primeiro)
    client.put(f"/api/progress/{vid}", json={"position_seconds": 15})

    nova = entrar(base, client.email)
    user = nova.get("/api/me").json()["user"]
    assert user["needs_profile"] is True and user["active_profile_id"] is None

    answers, _ = answers_path(nova, "documentacao", [0, 0, 2])
    bloqueadas = (
        nova.get("/api/me/learning"),
        nova.get("/api/paths"),
        nova.put(f"/api/progress/{vid}", json={"position_seconds": 1}),
        nova.post("/api/paths", json={"situation": "documentacao", "answers": answers}),
        nova.delete("/api/paths/1"),
    )
    for r in bloqueadas:
        assert r.status_code == 409 and r.json()["error"]["code"] == "profile_required", r.text

    # Nada do progresso de um perfil aparece enquanto ninguém foi escolhido.
    assert nova.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 0
    assert video_by_slug(nova, INTRO)["position_seconds"] == 0

    assert selecionar(nova, primeiro)["needs_profile"] is False
    assert nova.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 15


def test_logout_nao_guarda_a_escolha_do_perfil(base):
    client, _, segundo = conta_com_dois_perfis(base)
    selecionar(client, segundo)
    client.post("/api/auth/logout")
    assert entrar(base, client.email).get("/api/me").json()["user"]["needs_profile"] is True


# Exclusão
def test_excluir_perfil_apaga_apenas_os_dados_dele(base, anon):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    terceiro = criar_perfil(client, "Terceiro Perfil")
    vid = video_by_slug(client, INTRO)["id"]
    answers, _ = answers_path(anon, "documentacao", [0, 0, 2])
    payload = {"situation": "documentacao", "answers": answers}
    for profile, position in ((primeiro, 12), (segundo, 24)):
        selecionar(client, profile)
        client.put(f"/api/progress/{vid}", json={"position_seconds": position})
        client.post("/api/paths", json=payload)

    selecionar(client, primeiro)
    assert client.delete(f"/api/profiles/{segundo}").status_code == 200
    assert client.post(f"/api/profiles/{segundo}/select").status_code == 404
    dados = client.get("/api/me/learning").json()
    assert [v["position_seconds"] for v in dados["history"]] == [12] and len(dados["paths"]) == 1
    assert terceiro in [p["id"] for p in client.get("/api/profiles").json()["profiles"]]


def test_excluir_o_perfil_ativo_de_outra_sessao_volta_para_a_escolha(base):
    sessao_a, primeiro, segundo = conta_com_dois_perfis(base)
    terceiro = criar_perfil(sessao_a, "Terceiro Perfil")
    sessao_b = entrar(base, sessao_a.email)
    selecionar(sessao_a, primeiro)
    selecionar(sessao_b, segundo)
    assert sessao_a.delete(f"/api/profiles/{segundo}").status_code == 200
    user = sessao_b.get("/api/me").json()["user"]
    assert user["needs_profile"] is True and user["active_profile_id"] is None
    assert sessao_a.delete(f"/api/profiles/{terceiro}").status_code == 200
    # Sobrou um só: não há mais o que escolher.
    assert sessao_b.get("/api/me").json()["user"]["active_profile_id"] == primeiro


# O plano continua na conta
def test_plano_e_da_conta_e_vale_para_todos_os_perfis(base, admin):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    premium = video_by_slug(client, PREMIUM)["id"]
    uid = client.get("/api/me").json()["user"]["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"plan": "premium"}).status_code == 200
    for profile in (primeiro, segundo):
        assert selecionar(client, profile)["plan_status"] == "premium"
        assert client.get(f"/api/videos/{premium}/stream", headers={"Range": "bytes=0-9"}).status_code == 206


def test_dados_da_conta_nao_mudam_ao_trocar_de_perfil(base):
    client, primeiro, segundo = conta_com_dois_perfis(base)
    client.patch("/api/me", json={"company": "Empresa Única"})
    assert selecionar(client, segundo)["company"] == "Empresa Única"
    assert selecionar(client, primeiro)["email"] == client.email


# Migração de bancos criados antes dos perfis
LEGADO = """
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'subscriber', plan TEXT NOT NULL DEFAULT 'trial', trial_ends_at TEXT,
  company TEXT NOT NULL DEFAULT '', job_title TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0);
CREATE TABLE videos (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT, access_level TEXT NOT NULL DEFAULT 'premium',
  status TEXT NOT NULL DEFAULT 'draft', duration_seconds INTEGER NOT NULL DEFAULT 0, file_name TEXT, thumb_name TEXT,
  license_note TEXT NOT NULL DEFAULT '', is_synthetic INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE progress (user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE, position_seconds REAL NOT NULL DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0, first_watched_at TEXT NOT NULL, last_watched_at TEXT NOT NULL, PRIMARY KEY (user_id, video_id));
CREATE TABLE saved_paths (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  situation TEXT NOT NULL, answers_json TEXT NOT NULL, result_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE (user_id, fingerprint));
CREATE INDEX idx_progress_user ON progress(user_id, last_watched_at DESC);
INSERT INTO users (id,name,email,password_hash,created_at) VALUES (1,'Pessoa Um','um@x.test','h','2026-01-01'),(2,'Pessoa Dois','dois@x.test','h','2026-01-02');
INSERT INTO sessions VALUES ('tok',1,'2099-01-01','2026-01-01');
INSERT INTO categories (id,name,slug) VALUES (1,'Cat','cat');
INSERT INTO videos (id,slug,title,category_id,created_at,updated_at) VALUES (1,'v','V',1,'2026-01-01','2026-01-01');
INSERT INTO progress VALUES (1,1,30.5,0,'2026-01-03','2026-01-04'),(2,1,10,1,'2026-01-05','2026-01-06');
INSERT INTO saved_paths VALUES (7,2,'documentacao','{}','{"path":[]}','abc','2026-01-07');
"""


def test_migracao_preserva_dados_de_banco_antigo(tmp_path, monkeypatch):
    from app import config, db
    path = tmp_path / "antigo.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGADO)
    conn.close()
    monkeypatch.setattr(config, "DATABASE_PATH", path)

    db.init_db()
    db.init_db()  # Reiniciar o servidor não pode migrar de novo.

    with db.transaction() as c:
        profiles = {r["user_id"]: r for r in c.execute("SELECT * FROM profiles").fetchall()}
        assert {u: p["name"] for u, p in profiles.items()} == {1: "Pessoa Um", 2: "Pessoa Dois"}
        rows = c.execute("SELECT * FROM progress ORDER BY position_seconds DESC").fetchall()
        assert [(r["profile_id"], r["position_seconds"], r["completed"]) for r in rows] == [
            (profiles[1]["id"], 30.5, 0), (profiles[2]["id"], 10, 1)]
        assert rows[0]["first_watched_at"] == "2026-01-03" and rows[0]["last_watched_at"] == "2026-01-04"
        trilha = c.execute("SELECT * FROM saved_paths").fetchone()
        assert (trilha["id"], trilha["profile_id"], trilha["fingerprint"]) == (7, profiles[2]["id"], "abc")
        assert c.execute("SELECT profile_id FROM sessions").fetchone()["profile_id"] == profiles[1]["id"]
        assert c.execute("SELECT COUNT(*) AS n FROM pragma_foreign_key_check").fetchone()["n"] == 0
        assert c.execute("SELECT 1 FROM sqlite_master WHERE name = 'idx_progress_profile'").fetchone()


def test_migracao_com_falha_nao_deixa_banco_pela_metade(tmp_path, monkeypatch):
    from app import config, db
    path = tmp_path / "antigo.db"
    conn = sqlite3.connect(path)
    conn.executescript(LEGADO)
    conn.close()
    monkeypatch.setattr(config, "DATABASE_PATH", path)
    monkeypatch.setattr(db, "SAVED_PATHS_TABLE", "CREATE TABLE {name} (quebrada")

    try:
        db.init_db()
    except sqlite3.Error:
        pass
    else:
        raise AssertionError("A migração deveria ter falhado")

    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    columns = {r[1] for r in conn.execute("PRAGMA table_info(progress)")}
    conn.close()
    assert "profiles" not in tables and "progress_new" not in tables and "user_id" in columns
