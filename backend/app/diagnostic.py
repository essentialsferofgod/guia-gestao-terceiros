"""Diagnóstico adaptativo por regras explícitas, sem IA generativa.

O fluxo é uma árvore: cada alternativa aponta para a próxima pergunta (`next`) e
acrescenta sinais (`tags`). As regras em RECOMMENDATIONS e CHECKLIST convertem
esses sinais em vídeos, justificativas e orientações.
"""
from .errors import ApiError

SITUATIONS = {
    "contratar": {
        "title": "Preciso contratar uma empresa terceirizada",
        "description": "Escolher a prestadora e fechar um contrato seguro.",
        "start": "c_etapa",
    },
    "documentacao": {
        "title": "Tenho problemas com documentação",
        "description": "Resolver pendências e organizar o controle de documentos.",
        "start": "d_problema",
    },
    "acompanhar": {
        "title": "Preciso acompanhar contratos e prevenir riscos",
        "description": "Criar uma rotina e agir antes que o risco vire passivo.",
        "start": "a_foco",
    },
}


def _o(id, label, tags=(), next=None):
    return {"id": id, "label": label, "tags": list(tags), "next": next}


QUESTIONS = {
    # Contratar
    "c_etapa": {
        "text": "Em que ponto da contratação você está?",
        "options": [
            _o("definindo", "Ainda estou definindo o que terceirizar", ["escopo_indefinido"], "c_atividade"),
            _o("comparando", "Estou comparando prestadoras", ["comparando_fornecedores"], "c_documentos"),
            _o("assinando", "Já tenho uma minuta para assinar", ["minuta_pronta"], "c_clausulas"),
        ],
    },
    "c_atividade": {
        "text": "Quem vai dirigir o trabalho dos terceirizados no dia a dia?",
        "options": [
            _o("prestadora", "A prestadora, com supervisor próprio", ["gestao_prestadora"], "c_local"),
            _o("meu_gestor", "Meu gestor daria ordens diretas", ["risco_subordinacao"], "c_local"),
            _o("nao_sei", "Ainda não sei", ["risco_subordinacao"], "c_local"),
        ],
    },
    "c_documentos": {
        "text": "Você já pediu documentos às prestadoras candidatas?",
        "options": [
            _o("todos", "Sim, e analisei todos", ["due_diligence_feita"], "c_local"),
            _o("parcial", "Pedi apenas parte deles", ["due_diligence_parcial"], "c_local"),
            _o("nao", "Ainda não pedi", ["sem_due_diligence"], "c_local"),
        ],
    },
    "c_clausulas": {
        "text": "A minuta define serviço, prazo, valor e documentos que a prestadora deve entregar?",
        "options": [
            _o("completa", "Sim, todos esses pontos", ["minuta_completa"], "c_local"),
            _o("sem_docs", "Faltam as obrigações documentais", ["minuta_sem_documentos"], "c_local"),
            _o("nao_revisei", "Ainda não revisei a minuta", ["minuta_nao_revisada"], "c_local"),
        ],
    },
    "c_local": {
        "text": "Os terceirizados vão trabalhar nas suas instalações?",
        "options": [
            _o("sim", "Sim, nas minhas instalações", ["trabalho_nas_instalacoes"]),
            _o("nao", "Não, em outro local", ["trabalho_externo"]),
        ],
    },
    # Documentação
    "d_problema": {
        "text": "Qual problema descreve melhor a sua situação?",
        "options": [
            _o("pendencias", "Existem pendências documentais em aberto", ["pendencias_abertas"], "d_tipo"),
            _o("validade", "Perco o controle de vencimentos", ["sem_controle_validade"], "d_controle"),
            _o("nao_sei", "Não sei quais documentos exigir", ["nao_sabe_exigir"], "d_contratos"),
        ],
    },
    "d_tipo": {
        "text": "Que tipo de documento está pendente?",
        "options": [
            _o("trabalhista", "Folha, FGTS ou INSS", ["pendencia_trabalhista"], "d_notificacao"),
            _o("sst", "Saúde e segurança do trabalho", ["pendencia_sst"], "d_notificacao"),
            _o("fiscal", "Certidões fiscais", ["pendencia_fiscal"], "d_notificacao"),
        ],
    },
    "d_notificacao": {
        "text": "A prestadora já foi notificada formalmente?",
        "options": [
            _o("sim", "Sim, com prazo definido", ["notificada"]),
            _o("informal", "Só conversamos informalmente", ["sem_notificacao"]),
            _o("nao", "Ainda não", ["sem_notificacao"]),
        ],
    },
    "d_controle": {
        "text": "Como você controla os documentos hoje?",
        "options": [
            _o("planilha", "Em uma planilha", ["controle_planilha"]),
            _o("email", "Por e-mail e pastas", ["controle_disperso"]),
            _o("nenhum", "Não tenho controle definido", ["sem_controle"]),
        ],
    },
    "d_contratos": {
        "text": "Quantos contratos de terceirização você acompanha?",
        "options": [
            _o("um", "Um ou dois", ["poucos_contratos"]),
            _o("varios", "De três a dez", ["varios_contratos"]),
            _o("muitos", "Mais de dez", ["muitos_contratos"]),
        ],
    },
    # Acompanhamento
    "a_foco": {
        "text": "O que mais preocupa você neste momento?",
        "options": [
            _o("rotina", "Não tenho uma rotina de acompanhamento", ["sem_rotina"], "a_frequencia"),
            _o("sinais", "Percebi sinais de problema na operação", ["sinais_risco"], "a_sinal"),
            _o("renovacao", "Um contrato vai renovar ou encerrar", ["fim_contrato"], "a_pendencia_final"),
        ],
    },
    "a_frequencia": {
        "text": "Com que frequência você confere o contrato hoje?",
        "options": [
            _o("mensal", "Todo mês", ["acompanhamento_mensal"], "a_responsavel"),
            _o("eventual", "Só quando surge um problema", ["acompanhamento_reativo"], "a_responsavel"),
            _o("nunca", "Nunca conferi", ["acompanhamento_inexistente"], "a_responsavel"),
        ],
    },
    "a_responsavel": {
        "text": "Existe uma pessoa responsável por cada contrato?",
        "options": [
            _o("sim", "Sim, cada contrato tem responsável", ["com_fiscal"]),
            _o("nao", "Não, a responsabilidade é difusa", ["sem_fiscal"]),
        ],
    },
    "a_sinal": {
        "text": "Qual sinal você percebeu?",
        "options": [
            _o("pagamento", "Atraso de salários ou benefícios", ["sinal_pagamento"], "a_subordinacao"),
            _o("reclamacao", "Reclamações trabalhistas", ["sinal_reclamacao"], "a_subordinacao"),
            _o("acidente", "Acidente ou condição insegura", ["sinal_seguranca"], "a_subordinacao"),
        ],
    },
    "a_subordinacao": {
        "text": "Seus gestores dão ordens diretas aos terceirizados?",
        "options": [
            _o("sim", "Sim, com frequência", ["risco_subordinacao"]),
            _o("as_vezes", "Às vezes", ["risco_subordinacao"]),
            _o("nao", "Não, tudo passa pela prestadora", ["gestao_prestadora"]),
        ],
    },
    "a_pendencia_final": {
        "text": "Há documentos ou verbas pendentes nesse contrato?",
        "options": [
            _o("sim", "Sim, há pendências", ["pendencias_abertas"]),
            _o("nao_sei", "Não sei dizer", ["sem_controle_validade"]),
            _o("nao", "Não, está tudo em dia", ["contrato_regular"]),
        ],
    },
}

# (sinal, slug do vídeo, peso, justificativa). A justificativa cita o que o usuário informou.
RECOMMENDATIONS = [
    ("escopo_indefinido", "o-que-muda-ao-terceirizar", 8, "você informou que ainda está definindo o que terceirizar"),
    ("risco_subordinacao", "sinais-de-risco-na-operacao", 9, "você indicou que ordens diretas aos terceirizados podem ocorrer ou ainda não estão definidas"),
    ("gestao_prestadora", "rotina-mensal-do-contrato", 2, "você informou que a prestadora conduz o trabalho, e isso precisa ser verificado na rotina do contrato"),
    ("comparando_fornecedores", "avaliar-prestadora", 9, "você informou que está comparando prestadoras"),
    ("sem_due_diligence", "documentos-essenciais", 8, "você ainda não pediu documentos às candidatas"),
    ("due_diligence_parcial", "documentos-essenciais", 8, "você pediu apenas parte dos documentos às candidatas"),
    ("due_diligence_feita", "o-que-muda-ao-terceirizar", 3, "mesmo com os documentos analisados, vale revisar quais responsabilidades continuam com a contratante"),
    ("minuta_pronta", "avaliar-prestadora", 7, "você informou que está prestes a assinar e precisa confirmar a capacidade da prestadora"),
    ("minuta_sem_documentos", "documentos-essenciais", 9, "você informou que a minuta não traz as obrigações documentais"),
    ("minuta_nao_revisada", "documentos-essenciais", 7, "você ainda não revisou a minuta e precisa saber quais documentos ela deve exigir"),
    ("minuta_completa", "rotina-mensal-do-contrato", 7, "sua minuta já está completa, e o próximo passo é acompanhar o que foi combinado"),
    ("trabalho_nas_instalacoes", "sinais-de-risco-na-operacao", 6, "os terceirizados vão trabalhar nas suas instalações, onde a segurança deles também envolve a sua empresa"),
    ("trabalho_externo", "rotina-mensal-do-contrato", 3, "o trabalho fora das suas instalações exige um acompanhamento planejado"),
    ("pendencias_abertas", "pendencias-documentais", 10, "você informou que existem pendências documentais"),
    ("pendencia_trabalhista", "documentos-essenciais", 7, "a pendência envolve folha, FGTS ou INSS, que estão entre os documentos essenciais"),
    ("pendencia_sst", "sinais-de-risco-na-operacao", 8, "a pendência envolve saúde e segurança do trabalho"),
    ("pendencia_fiscal", "documentos-essenciais", 7, "a pendência envolve certidões fiscais, que estão entre os documentos essenciais"),
    ("sem_notificacao", "rotina-mensal-do-contrato", 6, "a prestadora ainda não foi notificada formalmente, e a rotina do contrato define como registrar isso"),
    ("notificada", "rotina-mensal-do-contrato", 4, "com a notificação feita, é preciso acompanhar o prazo combinado"),
    ("sem_controle_validade", "documentos-essenciais", 9, "você informou que perde o controle de vencimentos"),
    ("controle_planilha", "rotina-mensal-do-contrato", 7, "você controla os documentos em planilha e precisa de uma rotina que a mantenha atualizada"),
    ("controle_disperso", "rotina-mensal-do-contrato", 8, "seus documentos estão espalhados entre e-mails e pastas"),
    ("sem_controle", "rotina-mensal-do-contrato", 9, "você informou que não tem um controle definido"),
    ("sem_controle", "pendencias-documentais", 5, "sem controle definido, pendências podem surgir sem aviso"),
    ("nao_sabe_exigir", "documentos-essenciais", 10, "você informou que não sabe quais documentos exigir"),
    ("poucos_contratos", "o-que-muda-ao-terceirizar", 6, "com poucos contratos, entender a base das responsabilidades já traz clareza"),
    ("varios_contratos", "rotina-mensal-do-contrato", 7, "você acompanha vários contratos e precisa de um método repetível"),
    ("muitos_contratos", "rotina-mensal-do-contrato", 8, "você acompanha mais de dez contratos e precisa de um método repetível"),
    ("sem_rotina", "rotina-mensal-do-contrato", 10, "você informou que não tem uma rotina de acompanhamento"),
    ("acompanhamento_reativo", "sinais-de-risco-na-operacao", 7, "hoje você só confere o contrato quando surge um problema"),
    ("acompanhamento_inexistente", "documentos-essenciais", 8, "você nunca conferiu o contrato e precisa começar pelos documentos essenciais"),
    ("acompanhamento_mensal", "sinais-de-risco-na-operacao", 5, "você já confere todo mês e pode antecipar sinais de risco"),
    ("sem_fiscal", "o-que-muda-ao-terceirizar", 7, "a responsabilidade pelos contratos está difusa na sua empresa"),
    ("sinais_risco", "sinais-de-risco-na-operacao", 10, "você informou que percebeu sinais de problema na operação"),
    ("sinal_pagamento", "pendencias-documentais", 9, "você percebeu atraso de salários ou benefícios"),
    ("sinal_reclamacao", "o-que-muda-ao-terceirizar", 7, "reclamações trabalhistas exigem entender até onde vai a responsabilidade da contratante"),
    ("sinal_seguranca", "documentos-essenciais", 7, "uma condição insegura exige conferir os documentos de saúde e segurança"),
    ("fim_contrato", "pendencias-documentais", 9, "um contrato vai renovar ou encerrar e pendências precisam ser fechadas antes disso"),
    ("contrato_regular", "rotina-mensal-do-contrato", 7, "seu contrato está em dia, e a rotina mantém esse estado até o encerramento"),
]

# (sinal, orientação, ordem). Só entram as orientações ligadas às respostas.
CHECKLIST = [
    ("escopo_indefinido", "Descreva o serviço por escrito, com entregas e limites claros.", 1),
    ("risco_subordinacao", "Defina um supervisor da prestadora para receber todas as solicitações.", 1),
    ("gestao_prestadora", "Registre no contrato quem é o supervisor da prestadora.", 3),
    ("comparando_fornecedores", "Compare as prestadoras com os mesmos critérios e guarde a análise.", 1),
    ("sem_due_diligence", "Peça CNPJ, contrato social e certidões antes de negociar valores.", 1),
    ("due_diligence_parcial", "Liste os documentos que faltam e defina uma data para recebê-los.", 1),
    ("due_diligence_feita", "Arquive a análise com a data de cada documento conferido.", 3),
    ("minuta_pronta", "Confira se o capital social é compatível com o número de empregados.", 2),
    ("minuta_sem_documentos", "Inclua na minuta a lista de documentos e a periodicidade de entrega.", 1),
    ("minuta_nao_revisada", "Revise a minuta com seu jurídico antes de assinar.", 1),
    ("minuta_completa", "Nomeie quem vai acompanhar o contrato desde o primeiro mês.", 2),
    ("trabalho_nas_instalacoes", "Garanta condições de segurança, higiene e salubridade no local de trabalho.", 2),
    ("trabalho_externo", "Combine como e quando as evidências do serviço serão enviadas.", 3),
    ("pendencias_abertas", "Liste cada pendência com responsável, prazo e evidência de solução.", 1),
    ("pendencia_trabalhista", "Solicite comprovantes de salários, FGTS e INSS do período pendente.", 2),
    ("pendencia_sst", "Solicite os documentos de saúde e segurança e confira os trabalhadores alocados.", 2),
    ("pendencia_fiscal", "Reemita as certidões nos sites oficiais e confira as datas de validade.", 2),
    ("sem_notificacao", "Envie uma notificação escrita com prazo para regularização.", 1),
    ("notificada", "Registre o vencimento do prazo e o próximo passo previsto no contrato.", 2),
    ("sem_controle_validade", "Crie um controle com documento, validade e responsável.", 1),
    ("controle_planilha", "Inclua na planilha um alerta 30 dias antes de cada vencimento.", 2),
    ("controle_disperso", "Reúna os documentos em um único repositório por contrato.", 1),
    ("sem_controle", "Comece com um controle simples por contrato ainda esta semana.", 1),
    ("nao_sabe_exigir", "Monte uma lista padrão de documentos para cada tipo de serviço.", 1),
    ("poucos_contratos", "Use a mesma lista de documentos em todos os contratos.", 2),
    ("varios_contratos", "Defina um dia fixo do mês para conferir todos os contratos.", 2),
    ("muitos_contratos", "Priorize os contratos por criticidade e número de trabalhadores.", 2),
    ("sem_rotina", "Marque na agenda uma conferência mensal de cada contrato.", 1),
    ("acompanhamento_reativo", "Troque a conferência por demanda por um calendário mensal.", 2),
    ("acompanhamento_inexistente", "Faça hoje uma primeira conferência dos documentos do último mês.", 1),
    ("acompanhamento_mensal", "Inclua um registro dos sinais de risco na sua conferência mensal.", 3),
    ("sem_fiscal", "Nomeie uma pessoa responsável por cada contrato.", 1),
    ("com_fiscal", "Dê ao responsável um roteiro único de conferência.", 3),
    ("sinais_risco", "Registre o sinal percebido com data, local e pessoas envolvidas.", 1),
    ("sinal_pagamento", "Peça à prestadora os comprovantes de pagamento do mês.", 1),
    ("sinal_reclamacao", "Envie as informações ao jurídico e preserve os documentos do contrato.", 1),
    ("sinal_seguranca", "Interrompa a atividade insegura e acione a segurança do trabalho.", 1),
    ("fim_contrato", "Confira verbas e documentos antes de renovar ou encerrar.", 1),
    ("contrato_regular", "Guarde a comprovação final de que o contrato estava em dia.", 3),
]

# Completa a trilha quando as respostas apontam para menos de dois vídeos.
SITUATION_DEFAULTS = {
    "contratar": (["o-que-muda-ao-terceirizar", "avaliar-prestadora"], "Compare as propostas pelos mesmos critérios."),
    "documentacao": (["documentos-essenciais", "pendencias-documentais"], "Revise sua lista de documentos a cada novo contrato."),
    "acompanhar": (["rotina-mensal-do-contrato", "sinais-de-risco-na-operacao"], "Registre cada conferência para formar o histórico do contrato."),
}

SUMMARIES = [
    ("sinal_seguranca", "Há um sinal de segurança na operação. Ele pede ação imediata e registro do que foi feito."),
    ("sinal_pagamento", "Há sinais de atraso em pagamentos da prestadora. Esse risco pode alcançar a sua empresa e precisa de comprovação rápida."),
    ("sinal_reclamacao", "Há reclamações trabalhistas ligadas ao contrato. O momento é de reunir documentos e entender a responsabilidade envolvida."),
    ("fim_contrato", "Seu contrato está perto de uma decisão de renovação ou encerramento. Fechar pendências agora evita surpresas depois."),
    ("sem_rotina", "Falta uma rotina de acompanhamento. Sem ela, os problemas só aparecem quando já estão maiores."),
    ("pendencias_abertas", "Existem pendências documentais em aberto. A prioridade é tratá-las com responsável, prazo e registro."),
    ("sem_controle_validade", "O controle de vencimentos é o ponto frágil. Um documento vencido pode passar despercebido por meses."),
    ("nao_sabe_exigir", "Falta uma lista clara de documentos. Com ela, cada contrato passa a seguir o mesmo padrão de conferência."),
    ("escopo_indefinido", "Você está na fase de definição. Decidir bem o escopo agora reduz os riscos do contrato inteiro."),
    ("comparando_fornecedores", "Você está escolhendo a prestadora. Critérios iguais e documentos conferidos dão segurança à decisão."),
    ("minuta_pronta", "Você está perto de assinar. Esta é a última chance de corrigir o contrato sem custo de renegociação."),
]


def public_flow() -> dict:
    """Devolve a árvore sem as regras internas de recomendação."""
    questions = {
        qid: {
            "id": qid,
            "text": q["text"],
            "options": [{"id": o["id"], "label": o["label"], "next": o["next"]} for o in q["options"]],
        }
        for qid, q in QUESTIONS.items()
    }
    situations = [{"id": k, "title": v["title"], "description": v["description"], "start": v["start"]} for k, v in SITUATIONS.items()]
    return {"situations": situations, "questions": questions}


def walk(situation: str, answers: dict[str, str]) -> tuple[list[str], list[dict]]:
    """Valida o caminho respondido e devolve os sinais e o resumo das respostas."""
    if situation not in SITUATIONS:
        raise ApiError(422, "invalid_situation", "Escolha uma das situações disponíveis.")
    tags: list[str] = []
    trail: list[dict] = []
    qid = SITUATIONS[situation]["start"]
    visited = set()
    while qid:
        question = QUESTIONS[qid]
        chosen = next((o for o in question["options"] if o["id"] == answers.get(qid)), None)
        if chosen is None:
            raise ApiError(422, "incomplete_answers", "Responda a todas as perguntas do diagnóstico.", {"question": qid})
        visited.add(qid)
        tags.extend(chosen["tags"])
        trail.append({"question": question["text"], "answer": chosen["label"]})
        qid = chosen["next"]
    if set(answers) - visited:
        raise ApiError(422, "invalid_answers", "As respostas não correspondem ao caminho do diagnóstico.")
    return tags, trail


def evaluate(situation: str, answers: dict[str, str], videos: list[dict]) -> dict:
    tags, trail = walk(situation, answers)
    by_slug = {v["slug"]: v for v in videos}
    scored: dict[str, dict] = {}
    for tag, slug, weight, reason in RECOMMENDATIONS:
        if tag in tags and slug in by_slug:
            item = scored.setdefault(slug, {"score": 0, "reasons": []})
            item["score"] += weight
            if reason not in item["reasons"]:
                item["reasons"].append(reason)

    ranked = sorted(scored.items(), key=lambda kv: (-kv[1]["score"], kv[0]))[:3]
    path = []
    for slug, item in ranked:
        reasons = item["reasons"][:2]
        path.append({
            "slug": slug,
            "score": item["score"],
            "reason": "Este conteúdo foi recomendado porque " + " e ".join(reasons) + ".",
        })

    default_slugs, default_tip = SITUATION_DEFAULTS[situation]
    title = SITUATIONS[situation]["title"].lower()
    for slug in default_slugs:
        if len(path) >= 2:
            break
        if slug in by_slug and all(item["slug"] != slug for item in path):
            path.append({
                "slug": slug,
                "score": 0,
                "reason": f"Este conteúdo foi recomendado porque você escolheu a situação “{title}”, e ele cobre a base desse tema.",
            })

    checklist = [text for _, text, _ in sorted(
        (entry for entry in CHECKLIST if entry[0] in tags), key=lambda entry: entry[2]
    )][:6]
    if len(checklist) < 2:
        checklist.append(default_tip)
    summary = next((text for tag, text in SUMMARIES if tag in tags),
                   "Suas respostas indicam uma boa base. O foco agora é manter o acompanhamento em dia.")
    return {
        "situation": situation,
        "situation_title": SITUATIONS[situation]["title"],
        "summary": summary,
        "answers": trail,
        "path": path,
        "checklist": checklist,
        "note": "Orientação educativa. Não substitui a avaliação jurídica do seu caso.",
    }
