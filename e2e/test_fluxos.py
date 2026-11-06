"""Fluxos reais em navegador. Cada teste cita o item do requisito 9 que cobre."""
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import expect

PASSWORD = "Demo@2026"
PREMIUM = "Rotina mensal de acompanhamento do contrato"
INTRO = "Documentos que não podem faltar"


def login(page, email, password=PASSWORD):
    page.goto("/entrar")
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    page.wait_for_url("**/minha-aprendizagem**")


def logout(page):
    page.get_by_role("button", name="Sair").click()
    expect(page.get_by_role("link", name="Entrar")).to_be_visible()


def register(page, query=""):
    email = f"pessoa-{uuid.uuid4().hex[:8]}@exemplo.test"
    page.goto(f"/entrar?modo=cadastro{query}")
    page.get_by_label("Nome").fill("Pessoa de Teste")
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha").fill("Senha1234")
    page.get_by_role("button", name="Criar conta", exact=True).last.click()
    return email


def open_video(page, title):
    page.goto("/catalogo")
    page.get_by_test_id("video-card").filter(has_text=title).first.click()
    page.wait_for_url("**/assistir/*")


def play_for(page, seconds):
    """Toca de verdade e devolve o tempo atual do vídeo."""
    player = page.get_by_test_id("player")
    expect(player).to_be_visible()
    player.evaluate("v => new Promise((ok, no) => { if (v.readyState >= 1) ok(); else { v.onloadedmetadata = ok; v.onerror = no; } })")
    start = player.evaluate("v => v.currentTime")
    player.evaluate("v => { v.muted = true; return v.play(); }")
    page.wait_for_function(
        "([s, t]) => { const v = document.querySelector('video'); return v.currentTime >= s + t; }",
        arg=[start, seconds], timeout=(seconds + 8) * 1000,
    )
    player.evaluate("v => v.pause()")
    return start, player.evaluate("v => v.currentTime")


def test_01_cadastro_de_novo_usuario(page):
    email = register(page)
    page.wait_for_url("**/minha-aprendizagem")
    expect(page.get_by_role("heading", name="Minha aprendizagem")).to_be_visible()
    expect(page.get_by_text("Básico, teste de 14 dias")).to_be_visible()
    assert email


def test_01b_cadastro_mostra_erros_de_validacao(page):
    page.goto("/entrar?modo=cadastro")
    page.get_by_label("Nome").fill("A")
    page.get_by_label("E-mail").fill("invalido")
    page.get_by_label("Senha").fill("123")
    page.get_by_role("button", name="Criar conta", exact=True).last.click()
    expect(page.get_by_text("Informe um e-mail válido.")).to_be_visible()
    expect(page.get_by_text("Use ao menos 8 caracteres, com letras e números.")).to_be_visible()


def test_02_login_logout_e_sessao_persistente(page):
    login(page, "assinante@demo.guia.test")
    expect(page.get_by_text("Sara", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_text("Sara", exact=True)).to_be_visible()
    logout(page)
    page.goto("/minha-aprendizagem")
    page.wait_for_url("**/entrar?next=*")


def test_02b_login_incorreto(page):
    page.goto("/entrar")
    page.get_by_label("E-mail").fill("assinante@demo.guia.test")
    page.get_by_label("Senha").fill("errada123")
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    expect(page.get_by_role("alert")).to_contain_text("E-mail ou senha incorretos.")


def test_03_permissoes_de_administrador_e_assinante(page):
    login(page, "assinante@demo.guia.test")
    expect(page.get_by_role("link", name="Administração")).to_have_count(0)
    page.goto("/admin")
    expect(page.get_by_text("Esta área é exclusiva para administradores.")).to_be_visible()
    assert page.request.get("/api/admin/videos").status == 403
    logout(page)
    login(page, "admin@demo.guia.test")
    page.get_by_role("link", name="Administração").click()
    expect(page.get_by_test_id("admin-video-row")).to_have_count(6)


def test_04_busca(page, shot):
    page.goto("/catalogo")
    expect(page.get_by_test_id("video-card")).to_have_count(6)
    page.get_by_label("Buscar vídeos").fill("documentacao")
    expect(page.get_by_text("2 vídeos encontrados")).to_be_visible()
    expect(page).to_have_url(re.compile(r"q=documentacao"))
    page.get_by_label("Buscar vídeos").fill("nada-por-aqui")
    expect(page.get_by_text("Nenhum vídeo encontrado")).to_be_visible()
    page.get_by_role("button", name="Limpar filtros").click()
    expect(page.get_by_test_id("video-card")).to_have_count(6)
    page.get_by_role("button", name="Prevenção de riscos").click()
    expect(page.get_by_test_id("video-card")).to_have_count(1)


def test_05_reproducao_real_de_video(page, shot):
    login(page, "assinante@demo.guia.test")
    open_video(page, INTRO)
    start, end = play_for(page, 3)
    assert end - start >= 3
    player = page.get_by_test_id("player")
    assert player.evaluate("v => v.videoWidth") == 1280
    assert player.evaluate("v => v.error") is None
    # Prova de decodificação real: quadros foram apresentados pelo navegador.
    assert player.evaluate("v => v.getVideoPlaybackQuality().totalVideoFrames") > 10
    shot(page, "player-desktop")


def test_05b_avancar_no_video_usa_range(page):
    login(page, "assinante@demo.guia.test")
    open_video(page, INTRO)
    player = page.get_by_test_id("player")
    play_for(page, 1)
    player.evaluate("v => { v.currentTime = 40; }")
    page.wait_for_function("() => { const v = document.querySelector('video'); return v.readyState >= 2 && v.currentTime >= 40; }")


def test_06_bloqueio_de_conteudo_exclusivo(page, shot):
    login(page, "basico@demo.guia.test")
    page.goto("/catalogo")
    expect(page.get_by_test_id("video-card").filter(has_text=PREMIUM).get_by_text("Assinantes")).to_be_visible()
    open_video(page, PREMIUM)
    expect(page.get_by_test_id("lock-panel")).to_contain_text("exclusivo para assinantes")
    expect(page.get_by_test_id("player")).to_have_count(0)
    shot(page, "bloqueio-desktop")
    video_id = page.url.rsplit("/", 1)[1]
    # Mesmo chamando o endereço direto, o backend recusa.
    assert page.request.get(f"/api/videos/{video_id}/stream").status == 403
    open_video(page, INTRO)
    play_for(page, 1)


def test_06b_visitante_precisa_entrar(page):
    open_video(page, INTRO)
    expect(page.get_by_test_id("lock-panel")).to_contain_text("Entre ou crie uma conta")


def test_06c_teste_expirado(page):
    login(page, "expirado@demo.guia.test")
    open_video(page, INTRO)
    panel = page.get_by_test_id("lock-panel")
    expect(panel).to_contain_text("teste de 14 dias terminou")
    expect(panel).not_to_contain_text("administrador")


def test_07_08_09_progresso_retomada_e_historico(page, shot):
    register(page)
    page.wait_for_url("**/minha-aprendizagem")
    email = page.evaluate("fetch('/api/me').then(r => r.json()).then(d => d.user.email)")
    open_video(page, INTRO)
    player = page.get_by_test_id("player")
    play_for(page, 1)
    player.evaluate("v => { v.currentTime = 20; }")
    page.wait_for_function("() => document.querySelector('video').currentTime >= 20")
    with page.expect_response(lambda r: "/api/progress/" in r.url and r.status == 200):
        play_for(page, 2)
    saved = player.evaluate("v => v.currentTime")
    assert saved >= 20

    logout(page)
    login(page, email, "Senha1234")
    expect(page.get_by_test_id("video-card").filter(has_text=INTRO)).to_be_visible()
    expect(page.get_by_test_id("history-item").filter(has_text=INTRO)).to_contain_text("Parou em")
    shot(page, "minha-aprendizagem-desktop")

    page.get_by_test_id("video-card").filter(has_text=INTRO).click()
    expect(page.get_by_test_id("resume-note")).to_contain_text("Continuando de")
    resumed = page.get_by_test_id("player").evaluate("v => v.currentTime")
    assert abs(resumed - saved) < 1.5


def test_07b_saida_da_pagina_salva_progresso(page):
    register(page)
    page.wait_for_url("**/minha-aprendizagem")
    open_video(page, INTRO)
    play_for(page, 1)
    # Avança menos que o intervalo periódico: só a gravação ao sair pode salvar esta posição.
    player = page.get_by_test_id("player")
    player.evaluate("v => { v.currentTime = v.currentTime + 3; }")
    page.wait_for_timeout(300)
    position = player.evaluate("v => v.currentTime")
    with page.expect_response(lambda r: "/api/progress/" in r.url and r.status == 200):
        page.get_by_role("link", name="Catálogo").click()
    page.get_by_role("link", name="Minha aprendizagem").click()
    item = page.get_by_test_id("history-item").filter(has_text=INTRO)
    minutes = int(round(position))
    expect(item).to_contain_text(f"Parou em 0:{minutes:02d}")


def diagnose(page, picks):
    page.goto("/diagnostico")
    for label in picks:
        page.get_by_role("button", name=label).click()
    page.wait_for_url("**/diagnostico/resultado")


DOC = ["Tenho problemas com documentação", "Existem pendências documentais em aberto", "Folha, FGTS ou INSS", "Ainda não"]
RISK = ["Preciso acompanhar contratos", "Percebi sinais de problema", "Acidente ou condição insegura", "Sim, com frequência"]
HIRE = ["Preciso contratar", "Estou comparando prestadoras", "Ainda não pedi", "Não, em outro local"]


def test_10_11_diagnostico_sem_login_com_caminhos_diferentes(page, shot):
    tops = {}
    for name, picks in (("doc", DOC), ("risk", RISK), ("hire", HIRE)):
        diagnose(page, picks)
        items = page.get_by_test_id("path-item")
        count = items.count()
        assert 2 <= count <= 3
        for i in range(count):
            expect(items.nth(i).locator(".reason")).to_contain_text("Este conteúdo foi recomendado porque")
        assert page.locator(".checklist li").count() >= 2
        tops[name] = items.first.locator(".path-title").inner_text()
        if name == "doc":
            expect(items.first).to_contain_text("você informou que existem pendências documentais")
            shot(page, "resultado-desktop")
    assert len(set(tops.values())) == 3, tops


def test_10b_voltar_no_diagnostico_muda_a_pergunta(page):
    page.goto("/diagnostico?situacao=documentacao")
    page.get_by_role("button", name="Existem pendências documentais em aberto").click()
    expect(page.get_by_role("heading", name="Que tipo de documento está pendente?")).to_be_visible()
    page.get_by_role("button", name="Voltar").click()
    page.get_by_role("button", name="Perco o controle de vencimentos").click()
    expect(page.get_by_role("heading", name="Como você controla os documentos hoje?")).to_be_visible()


def test_12_salvar_trilha_apos_criar_conta(page, shot):
    diagnose(page, DOC)
    page.get_by_role("link", name="Criar conta e salvar trilha").click()
    page.get_by_label("Nome").fill("Pessoa da Trilha")
    page.get_by_label("E-mail").fill(f"trilha-{uuid.uuid4().hex[:8]}@exemplo.test")
    page.get_by_label("Senha").fill("Senha1234")
    page.get_by_role("button", name="Criar conta", exact=True).last.click()
    page.wait_for_url("**/minha-aprendizagem?trilha=salva")
    saved = page.get_by_test_id("saved-path")
    expect(saved).to_have_count(1)
    expect(saved).to_contain_text("Este conteúdo foi recomendado porque")
    page.reload()
    expect(page.get_by_test_id("saved-path")).to_have_count(1)


def test_12b_salvar_trilha_com_conta_existente(page):
    diagnose(page, RISK)
    page.get_by_role("link", name="Já tenho conta").click()
    page.get_by_label("E-mail").fill("assinante@demo.guia.test")
    page.get_by_label("Senha").fill(PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    page.wait_for_url("**/minha-aprendizagem?trilha=salva")
    expect(page.get_by_test_id("saved-path").filter(has_text="Preciso acompanhar contratos")).to_be_visible()


def test_admin_gerencia_conteudo_pela_interface(page, tmp_path, shot):
    login(page, "admin@demo.guia.test")
    page.goto("/admin")
    page.get_by_role("button", name="Novo vídeo").click()
    title = f"Encerramento seguro {uuid.uuid4().hex[:5]}"
    form = page.get_by_test_id("video-form")
    form.get_by_label("Título").fill(title)
    form.get_by_label("Licença ou autoria").fill("Criado pela equipe")
    form.get_by_role("button", name="Criar vídeo").click()
    row = page.get_by_test_id("admin-video-row").filter(has_text=title)
    expect(row).to_contain_text("Rascunho")
    expect(row).to_contain_text("Sem arquivo")
    shot(page, "admin-desktop")

    row.get_by_role("button", name="Publicar").click()
    expect(page.get_by_role("alert")).to_contain_text("Envie o arquivo")

    source = __import__("pathlib").Path(__file__).resolve().parents[1] / "media/videos/documentos-essenciais.mp4"
    row.get_by_label(f"Enviar arquivo de {title}").set_input_files(str(source))
    expect(row).to_contain_text("0:48")
    row.get_by_role("button", name="Publicar").click()
    expect(row).to_contain_text("Publicado")

    page.goto(f"/catalogo?q={title.split()[-1]}")
    expect(page.get_by_test_id("video-card")).to_have_count(1)
    page.get_by_test_id("video-card").click()
    play_for(page, 1)

    page.goto("/admin")
    row = page.get_by_test_id("admin-video-row").filter(has_text=title)
    row.get_by_role("button", name="Excluir").click()
    page.get_by_role("button", name="Confirmar exclusão").click()
    expect(page.get_by_test_id("admin-video-row").filter(has_text=title)).to_have_count(0)

    page.get_by_role("tab", name="Categorias").click()
    page.get_by_label("Nome da categoria").fill("Encerramento")
    page.get_by_role("button", name="Criar categoria").click()
    row = page.get_by_test_id("admin-category-row").filter(has=page.locator("input[value='Encerramento']"))
    expect(page.get_by_test_id("admin-category-row")).to_have_count(5)
    page.get_by_test_id("admin-category-row").last.get_by_role("button", name="Excluir").click()
    expect(page.get_by_test_id("admin-category-row")).to_have_count(4)


def test_admin_ativa_assinatura_e_libera_conteudo(page, browser, base):
    context = browser.new_context(base_url=base, viewport={"width": 1280, "height": 800})
    user = context.new_page()
    register(user)
    user.wait_for_url("**/minha-aprendizagem")
    email = user.evaluate("fetch('/api/me').then(r => r.json()).then(d => d.user.email)")
    open_video(user, PREMIUM)
    expect(user.get_by_test_id("lock-panel")).to_be_visible()

    login(page, "admin@demo.guia.test")
    page.goto("/admin")
    page.get_by_role("tab", name="Assinaturas").click()
    page.get_by_test_id("admin-user-row").filter(has_text=email).get_by_role("button", name="Ativar assinatura").click()
    expect(page.get_by_test_id("admin-user-row").filter(has_text=email)).to_contain_text("Assinante")

    user.reload()
    play_for(user, 1)
    context.close()


def conta_com_dois_perfis(page):
    """Cria uma conta nova e devolve o e-mail, com um segundo perfil chamado Convidada."""
    email = register(page)
    page.wait_for_url("**/minha-aprendizagem")
    page.get_by_role("link", name="Trocar de perfil").click()
    expect(page.get_by_role("heading", name="Quem está assistindo?")).to_be_visible()
    page.get_by_role("button", name="Gerenciar perfis").click()
    page.get_by_label("Nome do novo perfil").fill("Convidada")
    page.get_by_role("button", name="Adicionar perfil").click()
    expect(page.get_by_test_id("profile-card")).to_have_count(2)
    # Criar outro perfil não tira a sessão do perfil em uso.
    expect(page.get_by_test_id("profile-card").filter(has_text="Pessoa de Teste")).to_have_attribute("aria-current", "true")
    expect(page.get_by_role("link", name="Pessoa", exact=True)).to_be_visible()
    return email


def entrar_sem_esperar(page, email, password="Senha1234"):
    page.goto("/entrar")
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Entrar", exact=True).last.click()


def test_14_quem_esta_assistindo_e_isolamento_entre_perfis(page, shot):
    email = conta_com_dois_perfis(page)
    shot(page, "perfis-desktop")
    page.get_by_test_id("profile-card").filter(has_text="Pessoa de Teste").click()
    page.wait_for_url("**/minha-aprendizagem")
    open_video(page, INTRO)
    player = page.get_by_test_id("player")
    play_for(page, 1)
    player.evaluate("v => { v.currentTime = 20; }")
    page.wait_for_function("() => document.querySelector('video').currentTime >= 20")
    with page.expect_response(lambda r: "/api/progress/" in r.url and r.status == 200):
        play_for(page, 1)

    logout(page)
    entrar_sem_esperar(page, email)
    page.wait_for_url("**/perfis**")
    expect(page.get_by_role("heading", name="Quem está assistindo?")).to_be_visible()

    # Sem escolher, nenhuma outra tela abre.
    page.goto("/minha-aprendizagem")
    page.wait_for_url("**/perfis**")

    page.get_by_test_id("profile-card").filter(has_text="Convidada").click()
    page.wait_for_url("**/minha-aprendizagem")
    expect(page.get_by_text("Assistindo como")).to_contain_text("Convidada")
    expect(page.get_by_text("Você ainda não assistiu a nenhum vídeo.")).to_be_visible()

    page.get_by_role("link", name="Trocar de perfil").click()
    page.get_by_test_id("profile-card").filter(has_text="Pessoa de Teste").click()
    page.wait_for_url("**/minha-aprendizagem")
    expect(page.get_by_test_id("history-item").filter(has_text=INTRO)).to_contain_text("Parou em")


def test_14b_um_so_perfil_pula_a_escolha(page):
    login(page, "basico@demo.guia.test")
    expect(page.get_by_text("Assistindo como")).to_contain_text("Bruno Básico")
    expect(page.get_by_role("heading", name="Quem está assistindo?")).to_have_count(0)


def test_14c_trilha_pendente_e_salva_depois_de_escolher_o_perfil(page):
    email = conta_com_dois_perfis(page)
    logout(page)
    diagnose(page, DOC)
    page.get_by_role("link", name="Já tenho conta").click()
    page.get_by_label("E-mail").fill(email)
    page.get_by_label("Senha").fill("Senha1234")
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    page.wait_for_url("**/perfis**")
    page.get_by_test_id("profile-card").filter(has_text="Convidada").click()
    page.wait_for_url("**/minha-aprendizagem?trilha=salva")
    expect(page.get_by_test_id("saved-path")).to_have_count(1)
    expect(page.get_by_text("Assistindo como")).to_contain_text("Convidada")

    page.get_by_role("link", name="Trocar de perfil").click()
    page.get_by_test_id("profile-card").filter(has_text="Pessoa de Teste").click()
    page.wait_for_url("**/minha-aprendizagem")
    expect(page.get_by_text("Faça o diagnóstico para montar sua primeira trilha.")).to_be_visible()


def test_14d_limite_renomear_e_excluir_perfil(page):
    conta_com_dois_perfis(page)
    page.get_by_label("Nome do novo perfil").fill("Terceira")
    page.get_by_role("button", name="Adicionar perfil").click()
    expect(page.get_by_test_id("profile-card")).to_have_count(3)
    expect(page.get_by_text("Esta conta já tem o limite de 3 perfis.")).to_be_visible()
    expect(page.get_by_label("Nome do novo perfil")).to_have_count(0)

    row = page.get_by_test_id("profile-manage-row").nth(2)
    row.get_by_role("textbox").fill("Renomeada")
    row.get_by_role("button", name="Salvar nome").click()
    expect(page.get_by_test_id("profile-card").filter(has_text="Renomeada")).to_be_visible()

    row = page.get_by_test_id("profile-manage-row").nth(1)
    row.get_by_role("button", name="Excluir").click()
    expect(row).to_contain_text("não pode ser desfeita")
    row.get_by_role("button", name="Confirmar exclusão").click()
    expect(page.get_by_test_id("profile-card")).to_have_count(2)
    expect(page.get_by_label("Nome do novo perfil")).to_be_visible()


def test_14e_perfis_no_celular(phone, shot):
    page = phone
    page.goto("/entrar")
    page.get_by_label("E-mail").fill("assinante@demo.guia.test")
    page.get_by_label("Senha").fill(PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    page.wait_for_url("**/minha-aprendizagem")
    page.goto("/perfis")
    expect(page.get_by_role("heading", name="Quem está assistindo?")).to_be_visible()
    page.get_by_role("button", name="Gerenciar perfis").click()
    assert_no_overflow(page)
    shot(page, "perfis-mobile")


def encerrar_teste(database, email, ago):
    stamp = (datetime.now(timezone.utc).replace(microsecond=0) - ago).isoformat()
    with sqlite3.connect(database, timeout=10) as conn:
        assert conn.execute("UPDATE users SET trial_ends_at = ? WHERE email = ?", (stamp, email)).rowcount == 1


def conta_com_teste_encerrado(page, database, ago=timedelta(hours=2)):
    email = register(page)
    page.wait_for_url("**/minha-aprendizagem")
    encerrar_teste(database, email, ago)
    return email


def precos_visiveis(area):
    prices = area.get_by_test_id("offer-prices")
    for text in ("R$ 9,90", "R$ 19,90", "R$ 29,90", "1º mês", "Meses 2 e 3", "A partir do 4º mês"):
        expect(prices.get_by_text(text, exact=True)).to_be_visible()


def test_15_oferta_com_contagem_regressiva_e_precos(page, database, shot):
    conta_com_teste_encerrado(page, database)
    page.goto("/minha-aprendizagem")
    offer = page.get_by_test_id("offer")
    precos_visiveis(offer)
    expect(offer).to_contain_text("Demonstração, nenhuma cobrança")
    expect(page.get_by_text("Peça ao administrador")).to_have_count(0)

    timer = page.get_by_test_id("offer-timer")
    expect(timer).to_contain_text(re.compile(r"^69h 5\dmin|^70h 00min"))
    first = timer.inner_text()
    expect(timer).not_to_have_text(first, timeout=3000)
    shot(page, "oferta-desktop")

    # O prazo vem do servidor: recarregar não devolve o tempo.
    deadline = timer.get_attribute("datetime")
    page.reload()
    expect(page.get_by_test_id("offer-timer")).to_have_attribute("datetime", deadline)


def test_15b_ativacao_libera_o_video_sem_recarregar(page, database, shot):
    conta_com_teste_encerrado(page, database)
    open_video(page, PREMIUM)
    panel = page.get_by_test_id("lock-panel")
    expect(panel).to_contain_text("Ative a oferta")
    precos_visiveis(panel)
    shot(page, "oferta-bloqueio-desktop")
    panel.get_by_role("button", name="Ativar oferta").click()
    play_for(page, 1)
    page.get_by_role("link", name="Minha aprendizagem").click()
    offer = page.get_by_test_id("offer")
    expect(offer).to_contain_text("Assinatura ativa")
    expect(offer).to_contain_text("Demonstração, nenhuma cobrança")
    precos_visiveis(offer)
    expect(page.get_by_text("Assinante", exact=True)).to_be_visible()


def test_15b2_sair_com_a_oferta_aberta_nao_quebra_a_tela(page, database):
    conta_com_teste_encerrado(page, database)
    open_video(page, PREMIUM)
    expect(page.get_by_role("button", name="Ativar oferta")).to_be_visible()
    logout(page)
    expect(page.get_by_role("heading", name="O terceiro é de outra empresa. O risco também é seu.")).to_be_visible()


def test_15c_oferta_termina_com_a_tela_aberta(page, database):
    email = conta_com_teste_encerrado(page, database)
    encerrar_teste(database, email, timedelta(hours=72) - timedelta(seconds=4))
    open_video(page, INTRO)
    panel = page.get_by_test_id("lock-panel")
    expect(panel.get_by_role("button", name="Ativar oferta")).to_be_visible()
    expect(panel).to_contain_text("Oferta encerrada", timeout=9000)
    expect(panel).to_contain_text("oferta não está mais disponível")
    expect(panel.get_by_role("button", name="Ativar oferta")).to_have_count(0)


def test_15d_oferta_vencida_nao_mostra_botao(page, database):
    conta_com_teste_encerrado(page, database, timedelta(hours=80))
    page.goto("/minha-aprendizagem")
    offer = page.get_by_test_id("offer")
    expect(offer).to_contain_text("Oferta encerrada")
    expect(offer.get_by_role("button", name="Ativar oferta")).to_have_count(0)


def test_15e_ativacao_recusada_mostra_o_erro(page, database):
    email = conta_com_teste_encerrado(page, database)
    page.goto("/minha-aprendizagem")
    expect(page.get_by_role("button", name="Ativar oferta")).to_be_visible()
    encerrar_teste(database, email, timedelta(hours=80))  # O prazo vence antes do clique.
    page.get_by_role("button", name="Ativar oferta").click()
    expect(page.get_by_test_id("offer")).to_contain_text("Oferta encerrada")


def test_15f_admin_ativa_conta_com_oferta_vencida(page, browser, base, database):
    context = browser.new_context(base_url=base, viewport={"width": 1280, "height": 800})
    user = context.new_page()
    email = conta_com_teste_encerrado(user, database, timedelta(hours=80))
    login(page, "admin@demo.guia.test")
    page.goto("/admin")
    page.get_by_role("tab", name="Assinaturas").click()
    row = page.get_by_test_id("admin-user-row").filter(has_text=email)
    expect(row).to_contain_text("Teste encerrado")
    row.get_by_role("button", name="Ativar assinatura").click()
    expect(row).to_contain_text("Assinante")
    open_video(user, PREMIUM)
    play_for(user, 1)
    context.close()


@pytest.mark.parametrize("width,height", [(390, 844), (320, 640)])
def test_15g_oferta_no_celular_sem_cortes(browser, base, database, shot, width, height):
    context = browser.new_context(viewport={"width": width, "height": height}, base_url=base, is_mobile=True, has_touch=True)
    page = context.new_page()
    conta_com_teste_encerrado(page, database)
    open_video(page, PREMIUM)
    panel = page.get_by_test_id("lock-panel")
    precos_visiveis(panel)
    button = panel.get_by_role("button", name="Ativar oferta")
    expect(button).to_be_visible()
    frame, box = panel.bounding_box(), button.bounding_box()
    assert box["y"] + box["height"] <= frame["y"] + frame["height"], "botão cortado pelo painel"
    assert_no_overflow(page, width)
    if width == 390:
        shot(page, "oferta-mobile")
    context.close()


def test_15h_painel_da_oferta_nao_corta_em_tela_baixa(browser, base, database):
    context = browser.new_context(viewport={"width": 900, "height": 500}, base_url=base)
    page = context.new_page()
    conta_com_teste_encerrado(page, database)
    open_video(page, PREMIUM)
    panel = page.get_by_test_id("lock-panel")
    note = panel.get_by_text("Nenhum dado de pagamento é pedido.")
    expect(note).to_be_visible()
    frame, box = panel.bounding_box(), note.bounding_box()
    assert box["y"] + box["height"] <= frame["y"] + frame["height"]
    context.close()


def test_16_identidade_visual(page):
    page.goto("/entrar")
    logo = page.get_by_role("img", name="Streamy")
    expect(logo).to_be_visible()
    assert logo.evaluate("i => i.complete && i.naturalWidth") == 1323
    button = page.get_by_role("button", name="Entrar", exact=True).last
    assert button.evaluate("b => getComputedStyle(b).backgroundColor") == "rgb(2, 42, 213)"
    assert button.evaluate("b => getComputedStyle(b).color") == "rgb(255, 255, 255)"
    assert page.locator(".header").evaluate("h => getComputedStyle(h).backgroundColor") == "rgb(10, 11, 16)"
    page.goto("/catalogo")
    expect(page.get_by_test_id("video-card").first).to_be_visible()
    page.get_by_label("Buscar vídeos").focus()
    page.keyboard.press("Tab")
    focused = page.evaluate("getComputedStyle(document.activeElement).outlineColor")
    assert focused == "rgb(84, 115, 255)"


def test_16a_destaques_sobre_fundo_escuro(page):
    destaque, botao = "rgb(84, 115, 255)", "rgb(2, 42, 213)"
    login(page, "assinante@demo.guia.test")
    current = page.get_by_role("link", name="Minha aprendizagem")
    assert current.evaluate("a => getComputedStyle(a).borderBottomColor") == destaque
    # Sara tem um vídeo em andamento: a barra fica sobre a miniatura escura.
    bar = page.get_by_test_id("video-card").first.locator(".progress span")
    assert bar.evaluate("s => getComputedStyle(s).backgroundColor") == destaque
    # Sobre o fundo claro, a barra continua no azul dos botões.
    light = page.locator(".learning-main > .progress span")
    assert light.evaluate("s => getComputedStyle(s).backgroundColor") == botao


@pytest.mark.parametrize("width", [320, 390])
def test_16b_logo_cabe_ao_lado_do_menu(browser, base, width):
    context = browser.new_context(viewport={"width": width, "height": 700}, base_url=base)
    page = context.new_page()
    page.goto("/")
    logo = page.get_by_role("img", name="Streamy").bounding_box()
    menu = page.get_by_role("button", name="Menu").bounding_box()
    assert logo["x"] + logo["width"] <= menu["x"], (logo, menu)
    assert abs((logo["y"] + logo["height"] / 2) - (menu["y"] + menu["height"] / 2)) < 2
    context.close()


ROUTES = ["/", "/catalogo", "/entrar", "/diagnostico", "/diagnostico?situacao=contratar"]


def assert_no_overflow(page, width=390):
    # A largura esperada é fixa: em modo móvel, innerWidth cresce junto com o conteúdo.
    measure = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.offsetWidth]")
    assert max(measure) <= width, measure


@pytest.mark.parametrize("width,height", [(1440, 900), (1024, 768), (768, 1024), (390, 844), (320, 640)])
def test_13_responsividade_rotas_publicas(browser, base, width, height):
    context = browser.new_context(viewport={"width": width, "height": height}, base_url=base)
    page = context.new_page()
    for route in ROUTES:
        page.goto(route)
        page.wait_for_load_state("networkidle")
        assert_no_overflow(page, width)
    context.close()


def test_13b_mobile_fluxo_autenticado_e_capturas(phone, shot):
    page = phone
    page.goto("/")
    page.wait_for_load_state("networkidle")
    shot(page, "home-mobile")
    # A homepage empilha diagnóstico e streaming no celular.
    top_diag = page.locator(".hero-diagnostic").bounding_box()
    top_stream = page.locator(".hero-stream").bounding_box()
    assert top_stream["y"] >= top_diag["y"] + top_diag["height"] - 1

    page.get_by_role("button", name="Menu").click()
    page.get_by_role("link", name="Entrar").click()
    page.get_by_label("E-mail").fill("admin@demo.guia.test")
    page.get_by_label("Senha").fill(PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).last.click()
    page.wait_for_url("**/minha-aprendizagem")
    expect(page.get_by_role("heading", name="Conta")).to_be_visible()
    assert_no_overflow(page)
    shot(page, "minha-aprendizagem-mobile")

    page.goto("/catalogo")
    page.wait_for_load_state("networkidle")
    assert_no_overflow(page)
    shot(page, "catalogo-mobile")
    page.get_by_test_id("video-card").first.click()
    page.wait_for_url("**/assistir/*")
    play_for(page, 1)
    assert_no_overflow(page)
    shot(page, "player-mobile")
    page.goto("/admin")
    expect(page.get_by_test_id("admin-video-row")).to_have_count(6)
    assert_no_overflow(page)
    shot(page, "admin-mobile")

    page.goto("/diagnostico?situacao=documentacao")
    for label in DOC[1:]:
        page.get_by_role("button", name=label).click()
    page.wait_for_url("**/diagnostico/resultado")
    assert_no_overflow(page)
    shot(page, "resultado-mobile")


def test_capturas_desktop(page, shot):
    page.goto("/")
    page.wait_for_load_state("networkidle")
    box_d = page.locator(".hero-diagnostic").bounding_box()
    box_s = page.locator(".hero-stream").bounding_box()
    assert box_s["x"] >= box_d["x"] + box_d["width"] - 1  # lado a lado no desktop
    shot(page, "home-desktop")
    page.goto("/catalogo")
    page.wait_for_load_state("networkidle")
    shot(page, "catalogo-desktop")
    page.goto("/diagnostico?situacao=acompanhar")
    page.wait_for_load_state("networkidle")
    shot(page, "diagnostico-desktop")
    page.goto("/entrar")
    shot(page, "login-desktop")
