# Guia para a Gestão de Terceiros

Plataforma de streaming educativo para gestores de empresas que contratam serviços terceirizados.
O streaming é o produto principal. O diferencial é um diagnóstico guiado por regras, que recomenda uma trilha de vídeos e explica cada recomendação.

Projeto do Hack Garanhuns Tech 2026, Desafio 2: Streaming Platform Engineering.

## Como executar

Requisito: Python 3.10 ou superior. O frontend já vem compilado, então Node.js não é necessário para rodar.

No Windows, dê dois cliques em `iniciar.bat`, ou use os comandos abaixo:

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux e macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Abra <http://127.0.0.1:8000>. O banco SQLite e os dados demonstrativos são criados no primeiro início.

Para voltar ao estado inicial antes de uma demonstração, pare o servidor e execute `python run.py --reset`.

## Contas demonstrativas

Todas são sintéticas e usam a senha `Demo@2026`.

| Conta | Papel e plano | O que demonstra |
|---|---|---|
| `admin@demo.guia.test` | Administrador | Gerencia vídeos, categorias e assinaturas |
| `assinante@demo.guia.test` | Assinante | Acesso completo, com progresso já iniciado |
| `basico@demo.guia.test` | Básico, teste de 14 dias | Vê o catálogo e assiste só ao conteúdo introdutório |
| `expirado@demo.guia.test` | Teste encerrado | Vê o catálogo, sem reprodução, e recebe a oferta de fim de teste |

Cada conta nasce com um perfil. Para ver a tela "Quem está assistindo?", abra "Trocar de perfil" em Minha aprendizagem, crie um segundo perfil, saia e entre de novo.

A oferta da conta `expirado` vale por 48 horas depois do `python run.py --reset`, porque o teste dela termina um dia antes da criação do banco. Faça o reset perto da demonstração.

## Testes

```bash
pip install -r requirements-dev.txt
playwright install chromium
python -m pytest backend/tests     # API contra servidor real
python -m pytest e2e               # navegador real, gera docs/capturas
```

Os testes usam banco e mídia temporários. Rode cada pasta em um comando separado, porque as duas têm um `conftest.py`. Os resultados registrados estão em [docs/RELATORIO-TESTES.md](docs/RELATORIO-TESTES.md).

## Como alterar o frontend

Requer Node.js 18 ou superior.

```bash
cd frontend
npm install
npm run build
```

## Configuração

Copie `.env.example` para `.env` somente se precisar alterar algum valor. Todas as opções estão descritas nesse arquivo.

## Estrutura

```
backend/app      API, regras de acesso, diagnóstico e banco
backend/tests    testes de API
frontend/src     aplicação React
frontend/dist    frontend compilado, servido pelo backend
media            vídeos e miniaturas demonstrativos
tools            gerador dos vídeos demonstrativos
e2e              testes em navegador real
docs             documentação da entrega
```

## Documentação

- [Arquitetura](docs/ARQUITETURA.md)
- [Endpoints](docs/API.md)
- [Relatório de testes](docs/RELATORIO-TESTES.md)
- [Premissas, limitações, riscos e próximos passos](docs/PREMISSAS-LIMITACOES-RISCOS.md)
- [Roteiro do pitch de 8 minutos](docs/ROTEIRO-PITCH.md)

## Publicar no GitHub

Crie um repositório vazio no GitHub e execute na pasta do projeto:

```bash
git init -b main
git add .
git commit -m "Entrega do MVP Guia para a Gestão de Terceiros"
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
git push -u origin main
```

## Conteúdo

Os vídeos foram criados para este projeto, são demonstrativos e não têm narração. O conteúdo é educativo e não substitui a avaliação jurídica de cada caso. A fonte Inter é distribuída sob a licença SIL Open Font License, incluída em `frontend/public/fonts`.
