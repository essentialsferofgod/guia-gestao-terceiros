"""Catálogo inicial. Vídeos gerados por tools/generate_demo_videos.py, de autoria da equipe."""

LICENSE = "Vídeo demonstrativo sintético criado pela equipe, sem narração."

CATEGORIES = [
    ("Contratação", "contratacao", "Como decidir, avaliar e contratar uma prestadora."),
    ("Documentação", "documentacao", "O que exigir, conferir e guardar."),
    ("Acompanhamento de contratos", "acompanhamento", "A rotina que mantém o contrato em dia."),
    ("Prevenção de riscos", "prevencao", "Como reconhecer sinais antes que virem passivo."),
]

VIDEOS = [
    {
        "slug": "o-que-muda-ao-terceirizar",
        "title": "O que muda quando sua empresa terceiriza",
        "description": "Entenda o que passa para a prestadora e o que continua sob responsabilidade da contratante.",
        "category": "contratacao",
        "access_level": "intro",
    },
    {
        "slug": "avaliar-prestadora",
        "title": "Como avaliar uma prestadora antes de assinar",
        "description": "Critérios objetivos para comparar empresas e confirmar a capacidade de cada uma.",
        "category": "contratacao",
        "access_level": "premium",
    },
    {
        "slug": "documentos-essenciais",
        "title": "Documentos que não podem faltar",
        "description": "A lista básica para conferir a regularidade da prestadora e dos trabalhadores.",
        "category": "documentacao",
        "access_level": "intro",
    },
    {
        "slug": "pendencias-documentais",
        "title": "Como tratar pendências documentais",
        "description": "Um método para registrar, cobrar e encerrar pendências sem perder o histórico.",
        "category": "documentacao",
        "access_level": "premium",
    },
    {
        "slug": "rotina-mensal-do-contrato",
        "title": "Rotina mensal de acompanhamento do contrato",
        "description": "O que conferir todo mês para manter o contrato sob controle.",
        "category": "acompanhamento",
        "access_level": "premium",
    },
    {
        "slug": "sinais-de-risco-na-operacao",
        "title": "Sinais de risco na operação",
        "description": "Como reconhecer subordinação direta, atrasos e condições inseguras.",
        "category": "prevencao",
        "access_level": "premium",
    },
]
