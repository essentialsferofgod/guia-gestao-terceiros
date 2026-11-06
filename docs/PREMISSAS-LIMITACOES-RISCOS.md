# Premissas, limitações, riscos e próximos passos

## Premissas

- O PDF oficial do evento foi tratado como fonte prioritária. Ele pede catálogo, reprodução, perfis, papéis, histórico e continuar assistindo, além de repositório com instruções, pitch e este registro.
- "Perfis" foi implementado como vários perfis por conta, de 1 a 3. Progresso, histórico, continuar assistindo e trilhas são do perfil. Plano, e-mail, empresa e cargo são da conta.
- O perfil não tem senha nem PIN. Quem entra na conta pode abrir qualquer perfil dela.
- Uma conta nova nasce no plano Básico, com 14 dias de teste.
- Contas do plano Básico também podem salvar trilhas, porque o diagnóstico convida quem acabou de se cadastrar a salvar o resultado. O prompt lista trilhas salvas no plano Assinante, então esta é uma decisão a confirmar.
- Quando o teste termina, a pessoa continua vendo o catálogo, mas não reproduz vídeos, e recebe a oferta de fim de teste.
- As 72 horas da oferta contam a partir do fim do teste, e não da primeira visita. Quem volta depois desse prazo já não encontra a oferta. A decisão deve ser confirmada pela equipe.
- A oferta pode ser ativada uma única vez por conta. Depois das 72 horas, resta a ativação pelo administrador, e a interface diz isso.
- Sem pagamento, a ativação da oferta é simulada e identificada como "Demonstração, nenhuma cobrança". O administrador continua podendo ativar e encerrar a assinatura pelo painel.

## Limitações conhecidas

- Os seis vídeos são demonstrativos: slides sem narração, com 48 segundos cada. Devem ser trocados pelos vídeos finais da equipe no painel administrativo.
- O conteúdo jurídico é um resumo educativo e não passou por revisão de advogado.
- O repositório e o frontend da equipe não estavam acessíveis, então esta entrega não integra esse código.
- A equipe havia escolhido FastAPI, mas esta versão usa Starlette. O motivo está em [ARQUITETURA.md](ARQUITETURA.md).
- Não há recuperação de senha nem troca de senha.
- Vídeos criados no painel não têm envio de miniatura. A interface mostra uma capa gerada com título e categoria.
- O player usa os controles nativos do navegador, sem legendas ou troca de qualidade.
- A oferta não cobra nada e não muda de preço com o tempo: os valores são exibidos, mas nenhum mês é contado depois da ativação.
- Durante o teste, quem tenta abrir um vídeo exclusivo ainda vê que a assinatura é ativada pelo administrador. A oferta só aparece quando o teste termina.
- O perfil ativo é da sessão, não da aba. Se duas abas da mesma sessão estiverem abertas e uma trocar de perfil, o progresso da outra passa a ser gravado no novo perfil.
- Se o perfil ativo for excluído em outro aparelho, a tela aberta só leva à escolha ao recarregar. Até lá, salvar progresso falha com aviso no player.
- Na tela de resultado do diagnóstico, quem está com o teste encerrado vê "Entre para assistir" nos vídeos, mesmo já tendo entrado. O comportamento é anterior a esta entrega.
- A identidade Streamy trocou as variáveis do `:root` e o componente `Logo`, além de duas regras aprovadas pela equipe para usar #5473FF no sublinhado da navegação e na barra de progresso das miniaturas. Ficaram de fora o título da aba, o favicon, a `theme-color`, as miniaturas e vídeos (com fundo azul-marinho) e algumas bordas de tom azulado escritas direto no CSS. Diagnóstico, resultado, Minha aprendizagem e Administração continuam com fundo claro.
- O destaque #5473FF usa a variável `--amber`, que manteve o nome antigo para não alterar as regras que dependem dela.
- O logo veio de `streamy-frontend.zip`, porque não estava em `frontend/public`. É branco, para fundo escuro, e não deve ser usado sobre fundo claro.
- A duração automática no envio usa o `ffprobe` e, sem ele, lê o cabeçalho do arquivo MP4. Um WebM enviado sem `ffprobe` tem a duração preenchida na primeira reprodução.

## Riscos

| Risco | Impacto | Como reduzir |
|---|---|---|
| Rede instável no Demo Day | Alto | Rodar localmente. Fontes, vídeos e frontend estão no projeto |
| Python ausente ou antigo na máquina da demo | Alto | Testar `iniciar.bat` antes do code freeze |
| Dados alterados nos ensaios | Médio | Executar `python run.py --reset` antes da banca |
| Oferta da conta `expirado` vencida no Demo Day | Médio | Ela vale 48 horas depois do reset. Executar `python run.py --reset` no dia |
| Orientação jurídica mal interpretada | Médio | Manter os avisos e validar o conteúdo com especialistas |
| Hipótese de dor ainda não validada | Médio | Validar com mentores no checkpoint |

## Próximos passos

1. Validar o problema e o diagnóstico com os mentores.
2. Revisar o conteúdo jurídico com um especialista.
3. Gravar e publicar os vídeos finais, com narração e legendas.
4. Integrar pagamento real à oferta e recuperação de senha.
5. Migrar para PostgreSQL, armazenamento de objetos e HLS.
6. Adicionar painel para empresas com várias pessoas e relatórios de equipe.
