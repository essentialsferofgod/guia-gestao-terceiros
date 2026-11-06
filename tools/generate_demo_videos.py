"""Gera vídeos e miniaturas demonstrativos, de autoria da equipe, a partir de slides.

Requer ffmpeg e Playwright. Uso: python tools/generate_demo_videos.py
Nenhum vídeo de terceiros é usado. O resultado é identificado como sintético no catálogo.
"""
import html
import json
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "media" / "videos"
THUMB_DIR = ROOT / "media" / "thumbs"
SECONDS_PER_SLIDE = 8

CONTENT = {
    "o-que-muda-ao-terceirizar": {
        "category": "Contratação", "cover": "Terceirizar transfere a execução. A atenção continua com você.",
        "title": "O que muda quando sua empresa terceiriza",
        "slides": [
            ("A execução muda de mãos", ["A prestadora contrata, remunera e dirige o trabalho dos seus empregados.", "A contratante recebe o serviço combinado em contrato."]),
            ("A contratante continua atenta", ["Responde de forma subsidiária por obrigações trabalhistas do período.", "Lei 6.019/1974, art. 5º-A, § 5º."]),
            ("Segurança no local de trabalho", ["Nas suas dependências ou em local combinado, garanta segurança, higiene e salubridade.", "Lei 6.019/1974, art. 5º-A, § 3º."]),
            ("Evite a subordinação direta", ["Solicitações passam pelo supervisor da prestadora.", "Ordens diretas podem gerar risco de vínculo de emprego."]),
            ("Próximo passo", ["Defina o serviço, nomeie um responsável e monte sua lista de documentos."]),
        ],
    },
    "avaliar-prestadora": {
        "category": "Contratação", "cover": "Antes de assinar, confirme se a prestadora consegue cumprir.",
        "title": "Como avaliar uma prestadora antes de assinar",
        "slides": [
            ("Comece pelos requisitos legais", ["CNPJ ativo e registro na Junta Comercial.", "Capital social compatível com o número de empregados (art. 4º-B)."]),
            ("Referência de capital social", ["Até 10 empregados: R$ 10 mil. De 11 a 20: R$ 25 mil.", "De 21 a 50: R$ 45 mil. De 51 a 100: R$ 100 mil. Acima de 100: R$ 250 mil."]),
            ("Compare com critérios iguais", ["Experiência no serviço, equipe e supervisão.", "Regularidade fiscal, trabalhista e de segurança do trabalho."]),
            ("Fique atento à quarentena", ["Quem foi empregado ou prestou serviço à contratante nos últimos 18 meses pode ter restrição.", "Lei 6.019/1974, arts. 5º-C e 5º-D."]),
            ("O contrato precisa dizer", ["Partes, serviço, prazo quando houver e valor (art. 5º-B).", "Inclua documentos, periodicidade e consequências de atraso."]),
        ],
    },
    "documentos-essenciais": {
        "category": "Documentação", "cover": "Uma lista clara evita a maior parte das surpresas.",
        "title": "Documentos que não podem faltar",
        "slides": [
            ("Regularidade da empresa", ["Contrato social, CNPJ e certidões fiscais.", "Certificado de regularidade do FGTS e certidão negativa de débitos trabalhistas."]),
            ("Trabalhadores alocados", ["Registro, folha e comprovantes de salários.", "Comprovantes de recolhimento de FGTS e INSS."]),
            ("Saúde e segurança", ["Atestados de saúde ocupacional e treinamentos obrigatórios.", "Programas exigidos para a atividade, como PGR e PCMSO."]),
            ("Controle de validade", ["Registre documento, data de emissão, validade e responsável.", "Crie um alerta 30 dias antes do vencimento."]),
            ("Adapte ao seu contrato", ["A lista varia conforme o serviço e o risco da atividade.", "Valide a lista final com seu jurídico."]),
        ],
    },
    "pendencias-documentais": {
        "category": "Documentação", "cover": "Pendência sem dono e sem prazo não se resolve sozinha.",
        "title": "Como tratar pendências documentais",
        "slides": [
            ("Registre a pendência", ["O que falta, de qual período e de qual contrato.", "Quem é o responsável e qual é o prazo."]),
            ("Notifique por escrito", ["Conversas informais não deixam evidência.", "Envie a solicitação com prazo e guarde o comprovante."]),
            ("Classifique o impacto", ["Salários, FGTS, INSS e segurança merecem prioridade.", "Combine a tratativa com o jurídico e com o financeiro."]),
            ("Use o que o contrato prevê", ["Aplique somente as medidas previstas em contrato.", "Registre cada decisão e a data em que foi tomada."]),
            ("Encerre com evidência", ["A pendência só termina quando o documento correto for conferido.", "Arquive a comprovação junto ao contrato."]),
        ],
    },
    "rotina-mensal-do-contrato": {
        "category": "Acompanhamento de contratos", "cover": "Trinta minutos por mês valem mais que uma auditoria tardia.",
        "title": "Rotina mensal de acompanhamento do contrato",
        "slides": [
            ("Defina um responsável", ["Cada contrato precisa de uma pessoa que acompanhe a execução.", "Reserve um dia fixo do mês para a conferência."]),
            ("Confira a entrega", ["O serviço foi prestado como descrito?", "Registre desvios, ocorrências e evidências."]),
            ("Confira os documentos", ["Folha, salários, FGTS, INSS e certidões do período.", "Compare os nomes da folha com quem trabalhou no local."]),
            ("Trate o que encontrou", ["Abra pendências com responsável e prazo.", "Leve os pontos críticos à reunião com a prestadora."]),
            ("Registre o mês", ["Um relatório curto cria o histórico do contrato.", "Esse histórico mostra que houve acompanhamento."]),
        ],
    },
    "sinais-de-risco-na-operacao": {
        "category": "Prevenção de riscos", "cover": "O risco costuma aparecer na operação antes de chegar ao jurídico.",
        "title": "Sinais de risco na operação",
        "slides": [
            ("Subordinação direta", ["Gestor da contratante dá ordens, controla horário ou aplica advertência.", "Isso pode caracterizar vínculo de emprego."]),
            ("Atrasos de pagamento", ["Salários ou benefícios atrasados são um alerta financeiro.", "Peça comprovantes e registre a resposta da prestadora."]),
            ("Condições inseguras", ["Falta de equipamento, de treinamento ou de sinalização.", "Interrompa a atividade insegura e acione a segurança do trabalho."]),
            ("Rotatividade e ausências", ["Trocas frequentes podem indicar dificuldades da prestadora.", "Falta de supervisor enfraquece a gestão do contrato."]),
            ("Aja cedo", ["Registre data, local e pessoas envolvidas.", "Envolva o jurídico quando houver risco trabalhista."]),
        ],
    },
}

CSS = """
*{box-sizing:border-box;margin:0}body{width:1280px;height:720px;overflow:hidden;font-family:Inter,sans-serif;
background:#0B1730;color:#fff;position:relative}
.tab{position:absolute;left:72px;top:0;height:64px;padding:22px 26px 0;background:#3563F6;font-size:21px;font-weight:600;
border-radius:0 0 10px 10px}
.foot{position:absolute;right:72px;top:22px;display:flex;gap:28px;color:#A9B6D3;font-size:20px}
.main{position:absolute;left:72px;right:110px;top:140px}
h1{font-size:62px;line-height:1.1;letter-spacing:-.022em;font-weight:700;max-width:1040px}
ul{list-style:none;padding:0;margin-top:44px}li{font-size:34px;line-height:1.32;margin-top:24px;color:#E6ECF8;max-width:1040px;
padding-left:30px;border-left:5px solid #3563F6}
.cover h1{font-size:74px;max-width:1080px}.cover p{margin-top:32px;font-size:32px;color:#C5D0E8;line-height:1.3;max-width:980px}
.thumb{background:#0B1730}.thumb .tab{height:88px;padding-top:32px;font-size:30px}
.thumb h1{font-size:76px;line-height:1.1}.thumb .main{top:160px;right:70px}
.mark{position:absolute;right:0;bottom:0;width:430px;height:430px;background:#3563F6;opacity:.16;clip-path:polygon(100% 0,100% 100%,0 100%)}
"""


def page(body: str, klass: str = "") -> str:
    return f"<!doctype html><meta charset=utf-8><style>{CSS}</style><body class='{klass}'><div class=mark></div>{body}"


def foot(n: int, total: int) -> str:
    return f"<div class=foot><span>Vídeo demonstrativo sintético. Conteúdo educativo.</span><span>{n} de {total}</span></div>"


def slides_for(item: dict) -> list[str]:
    e = html.escape
    tab = f"<div class=tab>{e(item['category'])}</div>"
    total = len(item["slides"]) + 1
    out = [page(f"{tab}<div class=main><h1>{e(item['title'])}</h1><p>{e(item['cover'])}</p></div>{foot(1, total)}", "cover")]
    for n, (heading, bullets) in enumerate(item["slides"], 2):
        lis = "".join(f"<li>{e(b)}</li>" for b in bullets)
        out.append(page(f"{tab}<div class=main><h1>{e(heading)}</h1><ul>{lis}</ul></div>{foot(n, total)}"))
    return out


def main() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1280, "height": 720})
        for slug, item in CONTENT.items():
            folder = Path(tmp) / slug
            folder.mkdir()
            lines = []
            for i, markup in enumerate(slides_for(item)):
                pg.set_content(markup)
                pg.evaluate("document.fonts.ready")
                image = folder / f"{i}.png"
                pg.screenshot(path=str(image))
                lines += [f"file '{image}'", f"duration {SECONDS_PER_SLIDE}"]
            lines.append(f"file '{image}'")
            (folder / "list.txt").write_text("\n".join(lines))
            out = VIDEO_DIR / f"{slug}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(folder / "list.txt"),
                 "-vf", "fps=15,format=yuv420p", "-c:v", "libx264", "-profile:v", "main", "-crf", "24",
                 "-preset", "medium", "-g", "30", "-movflags", "+faststart", "-an", str(out)],
                check=True,
            )
            pg.set_content(page(f"<div class=tab>{html.escape(item['category'])}</div><div class=main><h1>{html.escape(item['cover'])}</h1></div>", "thumb"))
            pg.evaluate("document.fonts.ready")
            png = folder / "thumb.png"
            pg.screenshot(path=str(png))
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(png), "-vf", "scale=640:360", "-q:v", "4",
                 str(THUMB_DIR / f"{slug}.jpg")],
                check=True,
            )
            meta[slug] = {"duration": SECONDS_PER_SLIDE * (len(item["slides"]) + 1)}
            print(slug, out.stat().st_size // 1024, "KB")
        browser.close()
    (ROOT / "media" / "catalog-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
