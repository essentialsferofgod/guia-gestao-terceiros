# Endpoints

Base: `http://127.0.0.1:8000`. Requisições com corpo usam JSON, exceto o envio de vídeo.

Formato de erro:

```json
{"error": {"code": "validation_error", "message": "Revise os campos informados.", "fields": {"email": "Informe um e-mail válido."}}}
```

Acesso: **público**, **sessão** (qualquer conta), **perfil** (sessão com perfil ativo) ou **admin**.

## Autenticação e conta

| Método | Rota | Acesso | Corpo | Resultado |
|---|---|---|---|---|
| POST | `/api/auth/register` | público | `name`, `email`, `password` | 201 e cookie de sessão. 409 se o e-mail existir |
| POST | `/api/auth/login` | público | `email`, `password` | 200 e cookie. 401 ou 429 |
| POST | `/api/auth/logout` | público | | Encerra a sessão |
| GET | `/api/me` | público | | `{user}`, ou `null` sem sessão |
| PATCH | `/api/me` | sessão | `name`, `company`, `job_title` | Dados da conta atualizados |
| GET | `/api/me/learning` | perfil | | `continue_watching`, `history`, `paths`, `stats` do perfil ativo |

`register`, `login`, `GET /api/me` e `PATCH /api/me` devolvem em `user`, além dos dados da conta:

| Campo | Significado |
|---|---|
| `profiles` | Perfis da conta: `id` e `name` |
| `active_profile_id` | Perfil ativo nesta sessão, ou `null` |
| `needs_profile` | `true` quando a conta tem vários perfis e esta sessão ainda não escolheu um |
| `max_profiles` | Limite de perfis por conta |
| `offer` | Oferta de fim de teste, ou `null`. Veja [Oferta de fim de teste](#oferta-de-fim-de-teste) |

## Perfis

Cada conta tem de 1 a 3 perfis. O cadastro cria o primeiro. Progresso, histórico, continuar assistindo e trilhas salvas são do perfil. O plano é da conta.

Com um único perfil, a sessão já nasce nele. Com vários, o login não presume ninguém: rotas de acesso **perfil** respondem 409 `profile_required` até a escolha. A escolha fica na sessão, então dois aparelhos da mesma conta podem assistir em perfis diferentes, e o logout a descarta.

| Método | Rota | Acesso | Corpo | Resultado |
|---|---|---|---|---|
| GET | `/api/profiles` | sessão | | `profiles`, `active_profile_id`, `max_profiles` |
| POST | `/api/profiles` | sessão | `name` | 201. 409 `profile_limit` acima de 3 perfis, 409 `profile_name_in_use` com nome repetido na conta |
| PATCH | `/api/profiles/{id}` | sessão | `name` | Renomeia. 409 `profile_name_in_use` |
| DELETE | `/api/profiles/{id}` | sessão | | Apaga o perfil, seu progresso e suas trilhas. 409 `last_profile` se for o único |
| POST | `/api/profiles/{id}/select` | sessão | | Define o perfil ativo da sessão |

Nas rotas com `{id}`, perfil de outra conta responde **403** `profile_forbidden`, inclusive para administradores, e id inexistente responde 404 `profile_not_found`.

## Oferta de fim de teste

Ativação simulada, sem pagamento real. O campo `user.offer` traz:

| Campo | Significado |
|---|---|
| `status` | `available`, `expired`, `activated` ou `used` |
| `expires_at` | Fim das 72 horas, contadas de `trial_ends_at`. `null` em `activated` e `used` |
| `seconds_left` | Segundos restantes, calculados no servidor. A interface conta a partir deste valor |
| `prices` | `period`, `price` e `cents`: R$ 9,90 no 1º mês, R$ 19,90 nos meses 2 e 3, R$ 29,90 a partir do 4º |
| `notice` | `Demonstração, nenhuma cobrança` |
| `activated_at` | Data da ativação, ou `null` |

`offer` é `null` durante o teste, para administradores e para quem foi ativado pelo administrador. `used` indica que a oferta já foi ativada e a assinatura foi encerrada depois: ela não pode ser usada de novo.

| Método | Rota | Acesso | Resultado |
|---|---|---|---|
| POST | `/api/offer/activate` | sessão | 200 e `{user}`, com o plano da conta em `premium`. Repetir o pedido não muda nada. 409 `offer_unavailable` fora do prazo ou sem oferta |

A ativação pelo administrador continua em `PATCH /api/admin/users/{id}`.

## Catálogo e reprodução

| Método | Rota | Acesso | Observação |
|---|---|---|---|
| GET | `/api/categories` | público | Categorias e contagem de vídeos |
| GET | `/api/videos?q=&category=` | público | Busca sem diferenciar acentos. Cada item traz `locked`, `lock_reason` e `lock_message`. A posição é a do perfil ativo |
| GET | `/api/videos/{id}` | público | Detalhe, `stream_url` e `resume_seconds` do perfil ativo. Vídeo bloqueado vem sem URL |
| GET | `/api/videos/{id}/stream` | conforme plano | Aceita `Range`. 401 sem sessão, 403 sem plano |
| GET | `/api/thumbs/{arquivo}` | público | Miniaturas |
| PUT | `/api/progress/{id}` | perfil, conforme plano | `position_seconds`, `duration_seconds` opcional |

Motivos de bloqueio: `login_required`, `plan_required`, `trial_expired`. Em `trial_expired`, `lock_message` convida a ativar a oferta enquanto ela está disponível.

## Diagnóstico e trilhas

| Método | Rota | Acesso | Corpo |
|---|---|---|---|
| GET | `/api/diagnostic/flow` | público | |
| POST | `/api/diagnostic/evaluate` | público | `situation`, `answers` |
| GET | `/api/paths` | perfil | |
| POST | `/api/paths` | perfil | `situation`, `answers`. O servidor recalcula o resultado |
| DELETE | `/api/paths/{id}` | perfil | Somente trilhas do perfil ativo. Trilha de outro perfil responde 404 |

Exemplo de `evaluate`:

```json
{"situation": "documentacao", "answers": {"d_problema": "pendencias", "d_tipo": "trabalhista", "d_notificacao": "nao"}}
```

A resposta traz `summary`, `answers`, `checklist` e `path`, em que cada item tem `video` e `reason`.

## Administração

| Método | Rota | Corpo |
|---|---|---|
| GET, POST | `/api/admin/videos` | `title`, `description`, `category_id`, `access_level`, `license_note` |
| PATCH, DELETE | `/api/admin/videos/{id}` | Campos a alterar, incluindo `status` |
| PUT | `/api/admin/videos/{id}/file` | Arquivo bruto, com `Content-Type` `video/mp4` ou `video/webm` |
| POST | `/api/admin/categories` | `name`, `description` |
| PATCH, DELETE | `/api/admin/categories/{id}` | `name`, `description`. Exclusão retorna 409 se houver vídeos |
| GET | `/api/admin/users` | |
| PATCH | `/api/admin/users/{id}` | `plan`: `trial` ou `premium` |

Saúde do serviço: `GET /api/health`.
