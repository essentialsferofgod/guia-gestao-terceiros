# Relatório de testes

Executado em 06/11/2026, com Python 3.12.10, Chromium 153 e Playwright 1.63, em Windows 10 Pro. O ambiente anterior era Linux.

| Bateria | Testes | Aprovados | Falhas |
|---|---|---|---|
| API contra servidor real (`backend/tests`) | 78 | 78 | 0 |
| Navegador real (`e2e`) | 45 | 45 | 0 |

As saídas completas desta execução estão em [saida-testes-api.txt](saida-testes-api.txt) e [saida-testes-navegador.txt](saida-testes-navegador.txt). As capturas geradas pelos testes estão em [capturas](capturas).

## Linha de base

Antes das alterações: 31 de 32 na API e 24 de 26 no navegador. As três falhas vinham da falta do `ffprobe` nesta máquina: dois testes esperavam a duração de 48 s no envio, e o terceiro falhava em cascata, porque o anterior deixava um 7º vídeo no banco. A aplicação agora lê a duração do cabeçalho do MP4 quando o `ffprobe` não existe, e os testes não foram alterados para isso. Todos os resultados acima foram obtidos sem `ffprobe` instalado.

## Cobertura dos itens obrigatórios

| Item | Requisito | API | Navegador | Resultado |
|---|---|---|---|---|
| 1 | Cadastro de novo usuário | Sim | Sim | Passou |
| 2 | Login e logout | Sim | Sim | Passou, inclusive invalidação do cookie antigo |
| 3 | Permissões de administrador e assinante | Sim | Sim | Passou |
| 4 | Busca por vídeos | Sim | Sim | Passou, inclusive sem acentos |
| 5 | Reprodução de vídeo real | Sim | Sim | Passou no Chromium: tempo avançou e quadros foram decodificados |
| 6 | Bloqueio de conteúdo exclusivo | Sim | Sim | Passou, inclusive em acesso direto ao arquivo |
| 7 | Salvamento do progresso | Sim | Sim | Passou |
| 8 | Retomada de vídeo | Sim | Sim | Passou após sair e entrar de novo |
| 9 | Histórico de reprodução | Sim | Sim | Passou |
| 10 | Diagnóstico com caminhos diferentes | Sim | Sim | Passou. A API percorreu todos os caminhos da árvore |
| 11 | Recomendações com justificativas | Sim | Sim | Passou |
| 12 | Salvamento da trilha após autenticação | Sim | Sim | Passou com conta nova e existente |
| 13 | Responsividade mobile e desktop | Não se aplica | Sim | Sem rolagem horizontal de 320 a 1440 px nas rotas testadas |
| 14 | Vários perfis por conta | Sim | Sim | Passou |
| 15 | Oferta de fim de teste | Sim | Sim | Passou |
| 16 | Identidade visual Streamy | Sim | Sim | Passou |

## Perfis

- De 1 a 3 perfis, inclusive com 8 pedidos simultâneos. Nome validado e sem repetição na conta. O último perfil não pode ser excluído.
- Perfil de outra conta responde 403 ao selecionar, renomear e excluir, inclusive para administrador. Sem sessão, 401. Id inexistente, 404.
- Isolamento entre perfis da mesma conta: progresso, retomada, conclusão, histórico, continuar assistindo, trilhas salvas e exclusão de trilha.
- Duas sessões da mesma conta assistindo em perfis diferentes ao mesmo tempo.
- Login com vários perfis não presume ninguém: as rotas de perfil respondem 409, e nenhum progresso aparece até a escolha.
- Excluir um perfil apaga só os dados dele. A sessão que estava nele volta para a escolha.
- O plano vale para todos os perfis da conta, e os dados da conta não mudam ao trocar de perfil.
- Na interface: tela "Quem está assistindo?", pulo direto com um só perfil, troca de perfil, limite, renomear, excluir com confirmação e trilha pendente salva depois da escolha.
- Migração: banco antigo mantém progresso, trilhas e sessões. Migrar duas vezes não duplica nada, e uma falha no meio desfaz tudo.

## Oferta

- Sem oferta durante o teste, para assinantes e para administradores.
- Prazo de 72 horas contadas do fim do teste. Recarregar, sair e entrar não reiniciam a contagem.
- Contagem regressiva real no navegador, e troca para "Oferta encerrada" com a tela aberta.
- Os três preços e o aviso "Demonstração, nenhuma cobrança" aparecem antes e depois da ativação, em 1440, 390 e 320 px. O painel não corta o conteúdo em tela baixa de 900 x 500.
- Ativação libera o vídeo sem recarregar. Repetir o pedido não altera a data.
- Oferta vencida ou já usada não ativa. Administrador continua ativando, inclusive depois do prazo.
- A mensagem "fale com o administrador" saiu do bloqueio e da página Minha aprendizagem.

## Identidade visual

- Cores aplicadas conferidas no navegador: botão #022AD5 com texto branco, cabeçalho na base quase preta e foco #5473FF.
- Sobre fundo escuro, o sublinhado da navegação e a barra de progresso das miniaturas usam #5473FF. Sobre fundo claro, a barra continua em #022AD5.
- Contraste calculado para texto de botão, texto secundário, links e foco, em fundo claro e escuro.
- Logo entregue como `image/png`, carregado no navegador e alinhado ao botão Menu em 320 e 390 px.

## Também verificado

- `iniciar.bat` executado no Windows, com `.venv` já existente: o servidor subiu e os fluxos de oferta e perfis responderam por HTTP.
- `npm install` e `npm run build` a partir da internet, com Node 24.
- `pip install -r requirements-dev.txt` e `playwright install chromium` a partir da internet.
- Painel administrativo pela interface: criação, envio de arquivo, publicação, reprodução e exclusão de vídeo, além de categorias e ativação de assinatura.
- Rejeição de arquivo falso, entrada inválida, escalonamento de papel no cadastro e injeção SQL na busca.
- Limite de tentativas de login e isolamento de dados entre usuários.
- Ausência de erros de JavaScript no console nos testes com a fixture `page`.

## Problemas encontrados e corrigidos

| Problema | Como foi encontrado | Correção |
|---|---|---|
| Criar o 2º perfil tirava a sessão do perfil em uso, e o progresso passava a dar 409 | Revisão da captura `perfis-desktop` | Sessão grava o perfil ativo desde o login, com teste de regressão |
| Trilha pendente falharia ao entrar em conta com vários perfis | Revisão de código, antes de implementar | Trilha só é salva depois da escolha do perfil |
| Sublinhado da navegação e barra das miniaturas com contraste de cerca de 2,1:1 no escuro | Cálculo de contraste | Duas regras passaram a usar #5473FF |
| Envio de vídeo ficava com duração 0:00 em máquina sem `ffprobe` | Linha de base no Windows | Leitura da duração no cabeçalho do MP4, com testes para arquivo inválido |
| Logo 3,4 px fora do centro do botão Menu |
| Nome do perfil no cabeçalho não parecia link | Revisão das capturas | Seletor corrigido |
| Caminhos do diagnóstico com só um vídeo | Teste de todos os caminhos | Trilha mínima por situação |
| Tabela do admin alargava a página no celular | Revisão das capturas | Layout empilhado e posicionamento corrigido |
| Teste de responsividade não detectava esse problema | Revisão das capturas | Teste passou a medir contra a largura esperada |
| Selos "Bloqueado" em vídeos introdutórios e sobre a miniatura | Revisão das capturas | Selos por nível de acesso, no canto inferior |
| Rodapé do vídeo atrás dos controles do player | Revisão das capturas | Vídeos regenerados com o aviso no topo |
| Excluir vídeo demonstrativo apagaria o arquivo do projeto | Revisão de código | Arquivos demonstrativos preservados |
| Possível tipo de arquivo incorreto no Windows | Revisão de código | Tipos definidos no servidor, agora também para `.png` |

## O que não pôde ser verificado

- **`ffprobe` real:** esta máquina não tem `ffprobe`, então nesta rodada só a leitura pelo cabeçalho do MP4 foi exercitada. A chamada ao `ffprobe` não mudou.
- **Primeira execução do `iniciar.bat`:** o trecho que cria a `.venv` não rodou, porque ela já existia. Os comandos equivalentes foram executados à mão. O arquivo usa finais de linha LF e funcionou assim.
- **Migração com banco real da equipe:** o teste usa um banco antigo reconstruído a partir do esquema anterior. Nenhum banco real existia nesta pasta.
- **PDF oficial:** não estava na pasta do projeto e não foi consultado. O requisito de perfis foi seguido conforme o pedido da equipe.
- **Outros navegadores:** Firefox, Safari, Edge e Chrome em celular real não foram testados. O teste móvel emula um celular no Chromium.
- **Linux:** esta rodada foi só em Windows.
- **Áudio:** os vídeos não têm som.
- **Carga e concorrência:** não houve teste de desempenho, além dos pedidos simultâneos de criação de perfil.
- **Acessibilidade:** há foco visível, rótulos e movimento reduzido, mas não houve auditoria com leitor de tela.
- **Revisão jurídica:** nenhum especialista revisou o conteúdo, nem as condições da oferta.
