# Roteiro do pitch de 8 minutos

Prepare antes: execute `python run.py --reset`, inicie o servidor e deixe duas janelas abertas, uma anônima e outra com a conta administradora.

| Tempo | Bloco | Fala e ação |
|---|---|---|
| 0:00 a 0:45 | Problema | "Quem contrata um terceirizado transfere a execução, mas não transfere toda a atenção. A lei prevê responsabilidade subsidiária da contratante pelas obrigações trabalhistas do período. O gestor costuma descobrir isso quando o problema já chegou." |
| 0:45 a 1:30 | Solução | "O Guia para a Gestão de Terceiros é um streaming educativo. Em vez de pedir que o gestor procure um curso, ele conta o que está acontecendo e recebe uma trilha com a razão de cada vídeo." Mostrar a homepage. |
| 1:30 a 3:15 | Diagnóstico | Janela anônima, sem login. Escolher "Tenho problemas com documentação", "Existem pendências", "Folha, FGTS ou INSS" e "Ainda não". Ler a justificativa do primeiro vídeo e o checklist. Refazer com outra situação para mostrar que a recomendação muda. |
| 3:15 a 4:00 | Conta e trilha | Criar uma conta com um e-mail novo pelo botão "Criar conta e salvar trilha". Mostrar a trilha em Minha aprendizagem. |
| 4:00 a 5:00 | Controle de acesso | Abrir um vídeo exclusivo e mostrar o bloqueio. Explicar que a validação ocorre no servidor, inclusive no arquivo. Na janela de administração, ativar a assinatura. Recarregar a outra janela e mostrar o vídeo liberado. |
| 5:00 a 5:45 | Continuar assistindo | Avançar o vídeo, sair da conta e entrar de novo. Mostrar o histórico e a retomada no ponto salvo. |
| 5:45 a 6:15 | Administração | Criar um vídeo sem arquivo e mostrar que ele não pode ser publicado. Mostrar categorias e a lista de vídeos. |
| 6:15 a 7:15 | Arquitetura | Regra única de acesso, sessão no servidor, senha com hash e testes automatizados e em navegador real. Citar gargalos e evolução: PostgreSQL, CDN e HLS. Mostrar `docs/RELATORIO-TESTES.md`. |
| 7:15 a 8:00 | Impacto e fechamento | "O modelo serve a qualquer empresa que dependa de terceiros, e a mesma estrutura pode receber outros temas de conformidade. Próximos passos: validar com especialistas, gravar os vídeos finais e integrar pagamento." |

## Como o roteiro atende aos critérios da banca

| Critério | Onde aparece |
|---|---|
| Pertinência | Catálogo, reprodução, perfis, papéis e histórico funcionando |
| Inovação | Recomendação explicável por regras |
| Impacto e abrangência | Gestores que contratam terceiros e aplicação a outros temas |
| Viabilidade | MVP executável e plano de evolução |
| Pitch | Roteiro cronometrado |
| Escalabilidade e robustez | Gargalos, tratamento de falhas e caminho para produção |

## Perguntas prováveis

- **Por que não usar IA?** Porque a regra é auditável. A pessoa vê exatamente por que cada vídeo foi recomendado.
- **E se alguém copiar o link do vídeo?** O endpoint valida a sessão e o plano a cada requisição. Quem baixa o arquivo com acesso legítimo não é bloqueado, pois não há DRM neste MVP.
- **Os vídeos são reais?** São demonstrativos, criados pela equipe, e estão identificados como sintéticos.
- **Quanto a dor custa ao gestor?** Ainda é uma hipótese. Responda com o que os mentores confirmarem no checkpoint e não cite números sem fonte.

## Plano B

Se a rede ou o projetor falhar, mostre as capturas em `docs/capturas`. Rode a demonstração sempre em `127.0.0.1`, sem depender da internet.
