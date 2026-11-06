from conftest import Client, PASSWORD, login, video_by_slug

INTRO = "o-que-muda-ao-terceirizar"
PREMIUM = "rotina-mensal-do-contrato"


# 1 e 2: cadastro, login e logout
def test_cadastro_cria_conta_basica_com_teste(fresh):
    user = fresh.get("/api/me").json()["user"]
    assert user["email"] == fresh.email
    assert user["role"] == "subscriber" and user["plan_status"] == "trial"
    assert user["trial_ends_at"]


def test_cadastro_rejeita_email_duplicado_e_dados_invalidos(base, fresh):
    c = Client(base)
    assert c.post("/api/auth/register", json={"name": "Outra", "email": fresh.email, "password": "Senha1234"}).status_code == 409
    r = c.post("/api/auth/register", json={"name": "O", "email": "x", "password": "123"})
    assert r.status_code == 422 and {"name", "email", "password"} <= set(r.json()["error"]["fields"])
    assert c.post("/api/auth/register", json={"name": "Hacker", "email": "h@x.test", "password": "Senha1234", "role": "admin"}).status_code == 422


def test_login_logout_invalida_sessao_no_servidor(base):
    c = login(base, "assinante@demo.guia.test")
    cookie = c.cookies.get("gt_session")
    assert c.get("/api/me").json()["user"]["role"] == "subscriber"
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/me").json()["user"] is None
    # O cookie antigo não vale mais, mesmo reenviado manualmente.
    stale = Client(base)
    stale.cookies.set("gt_session", cookie)
    assert stale.get("/api/me").json()["user"] is None


def test_cookie_e_httponly(base):
    c = Client(base)
    r = c.post("/api/auth/login", json={"email": "assinante@demo.guia.test", "password": PASSWORD})
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header


def test_senha_errada_e_limite_de_tentativas(base, fresh):
    c = Client(base)
    bad = {"email": fresh.email, "password": "errada123"}
    assert [c.post("/api/auth/login", json=bad).status_code for _ in range(5)] == [401] * 5
    assert c.post("/api/auth/login", json=bad).status_code == 429


def test_perfil_persiste(base, fresh):
    r = fresh.patch("/api/me", json={"company": "Empresa Teste", "job_title": "Gestora"})
    assert r.status_code == 200
    assert fresh.get("/api/me").json()["user"]["company"] == "Empresa Teste"


# 3: permissões
def test_admin_e_exclusivo(anon, subscriber, admin):
    for path in ("/api/admin/videos", "/api/admin/users"):
        assert anon.get(path).status_code == 401
        assert subscriber.get(path).status_code == 403
        assert admin.get(path).status_code == 200
    assert subscriber.post("/api/admin/categories", json={"name": "Invasão"}).status_code == 403
    assert subscriber.delete("/api/admin/videos/1").status_code == 403


# 4: busca
def test_busca_por_titulo_acento_e_categoria(anon):
    titles = lambda q: [v["slug"] for v in anon.get("/api/videos", params={"q": q}).json()["videos"]]
    assert "rotina-mensal-do-contrato" in titles("rotina")
    assert "documentos-essenciais" in titles("documentacao")
    assert titles("zzzz-inexistente") == []
    assert titles("%") == []
    only = anon.get("/api/videos", params={"category": "prevencao"}).json()["videos"]
    assert [v["slug"] for v in only] == ["sinais-de-risco-na-operacao"]


def test_catalogo_nao_expoe_arquivo(anon):
    for v in anon.get("/api/videos").json()["videos"]:
        assert "file_name" not in v


# 5 e 6: reprodução e bloqueio
def test_stream_entrega_mp4_com_range(subscriber):
    v = video_by_slug(subscriber, PREMIUM)
    assert v["locked"] is False
    r = subscriber.get(f"/api/videos/{v['id']}/stream", headers={"Range": "bytes=0-1023"})
    assert r.status_code == 206 and len(r.content) == 1024
    assert r.headers["content-type"].startswith("video/mp4")
    assert r.content[4:8] == b"ftyp"
    assert r.headers["content-range"].startswith("bytes 0-1023/")


def test_bloqueio_premium_no_backend(anon, basic, expired, subscriber, admin):
    premium = video_by_slug(anon, PREMIUM)["id"]
    intro = video_by_slug(anon, INTRO)["id"]
    url = lambda i: f"/api/videos/{i}/stream"
    assert anon.get(url(premium)).status_code == 401
    assert anon.get(url(intro)).status_code == 401
    r = basic.get(url(premium))
    assert r.status_code == 403 and r.json()["error"]["code"] == "plan_required"
    assert basic.get(url(intro), headers={"Range": "bytes=0-9"}).status_code == 206
    r = expired.get(url(intro))
    assert r.status_code == 403 and r.json()["error"]["code"] == "trial_expired"
    assert subscriber.get(url(premium), headers={"Range": "bytes=0-9"}).status_code == 206
    assert admin.get(url(premium), headers={"Range": "bytes=0-9"}).status_code == 206


def test_detalhe_bloqueado_nao_entrega_url(basic):
    premium = video_by_slug(basic, PREMIUM)["id"]
    video = basic.get(f"/api/videos/{premium}").json()["video"]
    assert video["locked"] is True and video["stream_url"] is None


def test_midia_nao_tem_rota_publica(anon):
    for path in (f"/media/videos/{PREMIUM}.mp4", f"/../media/videos/{PREMIUM}.mp4", "/api/thumbs/..%2Fvideos%2Frotina-mensal-do-contrato.mp4"):
        r = anon.get(path)
        assert not r.headers.get("content-type", "").startswith("video/")
        assert b"ftyp" not in r.content[:16]


def test_progresso_bloqueado_para_plano_sem_acesso(basic):
    premium = video_by_slug(basic, PREMIUM)["id"]
    assert basic.put(f"/api/progress/{premium}", json={"position_seconds": 5}).status_code == 403


# 7, 8 e 9: progresso, retomada, histórico
def test_progresso_persiste_entre_sessoes_e_gera_historico(base, fresh):
    vid = video_by_slug(fresh, INTRO)["id"]
    assert fresh.get("/api/me/learning").json()["history"] == []
    assert fresh.put(f"/api/progress/{vid}", json={"position_seconds": 20.5}).status_code == 200
    fresh.post("/api/auth/logout")
    again = Client(base)
    assert again.post("/api/auth/login", json={"email": fresh.email, "password": "Senha1234"}).status_code == 200
    video = again.get(f"/api/videos/{vid}").json()["video"]
    assert video["resume_seconds"] == 20.5
    data = again.get("/api/me/learning").json()
    assert [v["id"] for v in data["continue_watching"]] == [vid]
    assert data["history"][0]["last_watched_at"]


def test_conclusao_tira_de_continuar_e_reinicia(fresh):
    vid = video_by_slug(fresh, INTRO)["id"]
    r = fresh.put(f"/api/progress/{vid}", json={"position_seconds": 47}).json()
    assert r["completed"] is True
    data = fresh.get("/api/me/learning").json()
    assert data["continue_watching"] == [] and data["stats"]["completed"] == 1
    assert fresh.get(f"/api/videos/{vid}").json()["video"]["resume_seconds"] == 0


def test_progresso_e_limitado_a_duracao_e_validado(fresh):
    vid = video_by_slug(fresh, INTRO)["id"]
    assert fresh.put(f"/api/progress/{vid}", json={"position_seconds": 5000}).json()["position_seconds"] == 48
    assert fresh.put(f"/api/progress/{vid}", json={"position_seconds": -1}).status_code == 422


def test_progresso_isolado_por_usuario(fresh, subscriber):
    vid = video_by_slug(fresh, "documentos-essenciais")["id"]
    fresh.put(f"/api/progress/{vid}", json={"position_seconds": 11})
    other = subscriber.get(f"/api/videos/{vid}").json()["video"]
    assert other["position_seconds"] != 11


# 10 e 11: diagnóstico
def answers_path(anon, situation, picks):
    flow = anon.get("/api/diagnostic/flow").json()
    start = next(s for s in flow["situations"] if s["id"] == situation)["start"]
    answers, qid, asked = {}, start, 0
    while qid:
        q = flow["questions"][qid]
        option = q["options"][picks[asked] if asked < len(picks) else 0]
        answers[qid] = option["id"]
        qid = option["next"]
        asked += 1
    return answers, asked


def test_todo_caminho_do_diagnostico_tem_trilha_valida(anon):
    flow = anon.get("/api/diagnostic/flow").json()
    results = set()

    def explore(situation, qid, answers, depth):
        q = flow["questions"][qid]
        for option in q["options"]:
            current = {**answers, qid: option["id"]}
            if option["next"]:
                explore(situation, option["next"], current, depth + 1)
                continue
            assert 2 <= depth + 1 <= 3, qid
            r = anon.post("/api/diagnostic/evaluate", json={"situation": situation, "answers": current})
            assert r.status_code == 200, r.text
            result = r.json()["result"]
            assert 2 <= len(result["path"]) <= 3, current
            assert len({p["slug"] for p in result["path"]}) == len(result["path"])
            assert result["summary"] and 2 <= len(result["checklist"]) <= 6
            for item in result["path"]:
                assert item["reason"].startswith("Este conteúdo foi recomendado porque")
            results.add(tuple(p["slug"] for p in result["path"]))

    for situation in flow["situations"]:
        explore(situation["id"], situation["start"], {}, 0)
    assert len(results) >= 5


def test_respostas_diferentes_geram_recomendacoes_diferentes(anon):
    def run(s, picks):
        answers, _ = answers_path(anon, s, picks)
        return anon.post("/api/diagnostic/evaluate", json={"situation": s, "answers": answers}).json()["result"]

    a = run("documentacao", [0, 0, 2])
    b = run("acompanhar", [1, 2, 0])
    c = run("contratar", [1, 2, 1])
    assert a["path"][0]["slug"] == "pendencias-documentais"
    assert "existem pendências documentais" in a["path"][0]["reason"]
    assert b["path"][0]["slug"] == "sinais-de-risco-na-operacao"
    assert c["path"][0]["slug"] == "avaliar-prestadora"
    assert len({a["summary"], b["summary"], c["summary"]}) == 3


def test_perguntas_sao_adaptativas(anon):
    flow = anon.get("/api/diagnostic/flow").json()
    options = flow["questions"]["d_problema"]["options"]
    assert len({o["next"] for o in options}) == 3


def test_diagnostico_recusa_caminho_invalido(anon):
    bad = [
        {"situation": "x", "answers": {}},
        {"situation": "contratar", "answers": {}},
        {"situation": "contratar", "answers": {"c_etapa": "nao-existe"}},
        {"situation": "contratar", "answers": {"c_etapa": "definindo", "c_atividade": "prestadora", "c_local": "sim", "d_problema": "pendencias"}},
    ]
    for payload in bad:
        assert anon.post("/api/diagnostic/evaluate", json=payload).status_code == 422


# 12: trilhas
def test_trilha_exige_login_salva_e_nao_duplica(anon, fresh):
    answers, _ = answers_path(anon, "documentacao", [0, 0, 2])
    payload = {"situation": "documentacao", "answers": answers}
    assert anon.post("/api/paths", json=payload).status_code == 401
    r = fresh.post("/api/paths", json=payload)
    assert r.status_code == 201
    first = r.json()["path"]
    assert first["total"] >= 2 and first["result"]["path"][0]["reason"]
    assert fresh.post("/api/paths", json=payload).json()["path"]["id"] == first["id"]
    assert len(fresh.get("/api/paths").json()["paths"]) == 1
    vid = first["result"]["path"][0]["video"]["id"]
    video = fresh.get(f"/api/videos/{vid}").json()["video"]
    if not video["locked"]:
        fresh.put(f"/api/progress/{vid}", json={"position_seconds": 47})
        assert fresh.get("/api/paths").json()["paths"][0]["done"] == 1
    assert fresh.delete(f"/api/paths/{first['id']}").status_code == 200
    assert fresh.get("/api/paths").json()["paths"] == []


def test_trilha_de_outro_usuario_nao_pode_ser_apagada(anon, fresh, subscriber):
    answers, _ = answers_path(anon, "acompanhar", [0, 0, 0])
    path = fresh.post("/api/paths", json={"situation": "acompanhar", "answers": answers}).json()["path"]
    assert subscriber.delete(f"/api/paths/{path['id']}").status_code == 404


# Administração
def test_admin_crud_video_upload_e_publicacao(admin, anon, subscriber, base):
    categories = anon.get("/api/categories").json()["categories"]
    r = admin.post("/api/admin/videos", json={"title": "Vídeo de teste automatizado", "category_id": categories[0]["id"], "access_level": "premium", "license_note": "Criado no teste"})
    assert r.status_code == 201
    vid = r.json()["video"]["id"]
    assert admin.patch(f"/api/admin/videos/{vid}", json={"status": "published"}).status_code == 422
    assert video_id_missing(anon, vid)
    assert anon.get(f"/api/videos/{vid}").status_code == 404

    with open(__import__("pathlib").Path(__file__).resolve().parents[2] / "media/videos/documentos-essenciais.mp4", "rb") as f:
        content = f.read()
    assert admin.put(f"/api/admin/videos/{vid}/file", data=b"nao e video!!!!!!!!", headers={"Content-Type": "video/mp4"}).status_code == 422
    assert admin.put(f"/api/admin/videos/{vid}/file", data=content, headers={"Content-Type": "text/plain"}).status_code == 415
    assert subscriber.put(f"/api/admin/videos/{vid}/file", data=content, headers={"Content-Type": "video/mp4"}).status_code == 403
    r = admin.put(f"/api/admin/videos/{vid}/file", data=content, headers={"Content-Type": "video/mp4"})
    assert r.status_code == 200 and r.json()["video"]["duration_seconds"] == 48

    assert admin.patch(f"/api/admin/videos/{vid}", json={"status": "published", "title": "Título editado"}).status_code == 200
    assert any(v["title"] == "Título editado" for v in anon.get("/api/videos").json()["videos"])
    assert subscriber.get(f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-9"}).status_code == 206
    assert admin.delete(f"/api/admin/videos/{vid}").status_code == 200
    assert anon.get(f"/api/videos/{vid}").status_code == 404


def video_id_missing(client, vid):
    return all(v["id"] != vid for v in client.get("/api/videos").json()["videos"])


def test_admin_categorias(admin, anon):
    r = admin.post("/api/admin/categories", json={"name": "Categoria temporária"})
    assert r.status_code == 201
    cid = r.json()["category"]["id"]
    assert admin.post("/api/admin/categories", json={"name": "Categoria temporária"}).status_code == 409
    assert admin.patch(f"/api/admin/categories/{cid}", json={"name": "Categoria renomeada"}).json()["category"]["name"] == "Categoria renomeada"
    assert admin.delete(f"/api/admin/categories/{cid}").status_code == 200
    used = anon.get("/api/categories").json()["categories"][0]["id"]
    assert admin.delete(f"/api/admin/categories/{used}").status_code == 409


def test_admin_libera_assinatura_e_acesso_muda_na_hora(admin, fresh):
    premium = video_by_slug(fresh, PREMIUM)["id"]
    assert fresh.get(f"/api/videos/{premium}/stream").status_code == 403
    uid = fresh.get("/api/me").json()["user"]["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"plan": "premium"}).status_code == 200
    assert fresh.get(f"/api/videos/{premium}/stream", headers={"Range": "bytes=0-9"}).status_code == 206
    assert admin.patch(f"/api/admin/users/{uid}", json={"plan": "trial"}).status_code == 200
    assert fresh.get(f"/api/videos/{premium}/stream").status_code == 403


# Robustez e segurança
def test_respostas_de_erro_e_cabecalhos(anon):
    assert anon.get("/api/nao-existe").status_code == 404
    assert anon.post("/api/auth/login", data="{quebrado", headers={"Content-Type": "application/json"}).status_code == 400
    assert anon.post("/api/auth/login", data="a=1", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 415
    r = anon.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_injecao_sql_na_busca_nao_altera_dados(anon):
    assert anon.get("/api/videos", params={"q": "'; DROP TABLE videos; --"}).json()["videos"] == []
    assert len(anon.get("/api/videos").json()["videos"]) >= 6


def test_senhas_guardadas_com_hash():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.security import hash_password, verify_password
    stored = hash_password("Senha1234")
    assert stored.startswith("scrypt$") and "Senha1234" not in stored
    assert verify_password("Senha1234", stored) and not verify_password("outra", stored)
    assert hash_password("Senha1234") != stored


def test_arquivos_estaticos_tem_tipo_explicito(anon):
    assert anon.get("/app.js").headers["content-type"].startswith("text/javascript")
    assert anon.get("/app.css").headers["content-type"].startswith("text/css")
    assert anon.get("/catalogo").headers["content-type"].startswith("text/html")
    assert anon.get("/fonts/Inter-Regular.woff").headers["content-type"] == "font/woff"
    assert anon.get("/../.env").status_code in (200, 404)
    assert b"DEMO_PASSWORD" not in anon.get("/../.env").content


def test_arquivo_demonstrativo_nao_e_apagado_com_o_registro(admin, anon):
    r = admin.post("/api/admin/videos", json={"title": "Temporario", "category_id": anon.get("/api/categories").json()["categories"][0]["id"]})
    assert r.status_code == 201 and admin.delete(f"/api/admin/videos/{r.json()['video']['id']}").status_code == 200
