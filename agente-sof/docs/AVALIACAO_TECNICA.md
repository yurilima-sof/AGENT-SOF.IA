# Avaliação Técnica — Agente SOF (sof-ia-v1)

**Data:** 13/08/2026
**Escopo:** `agente-sof/` — ~3.000 linhas Python, 49 commits, branch `dev`
**Repositório:** `github.com/yurilima-sof/AGENT-SOF.IA`

---

## 1. Resumo executivo

O projeto entrega o que promete no caminho felizardo: uma ponte FastAPI que traduz linguagem
natural do WhatsApp em cenas Tuya, com RAG em pgvector, memória de curto prazo, escalonamento
de temperatura e pausa de automações. A estrutura de pastas é limpa, o README é
excepcionalmente bom (melhor que a média de projetos internos) e as escolhas de stack são
adequadas ao problema.

O que impede considerá-lo production-ready não é a arquitetura — é **corretude, isolamento
multi-tenant e ausência de rede de segurança**. Há bugs que só não aparecem porque o caminho
alternativo raramente é exercitado, um vazamento de credencial no histórico do Git, e a suíte
de testes está literalmente fora do controle de versão.

### Nota por dimensão

| Dimensão | Nota | Comentário |
| :--- | :---: | :--- |
| Arquitetura e organização | 8,0 | Separação clara services/crud/schemas; escala bem |
| Documentação | 8,0 | README exemplar, mas desalinhado do código atual |
| Corretude | 4,5 | 3 bugs latentes + contradições de regra de negócio |
| Segurança | 4,0 | Segredo no histórico do Git, senha de 4 chars, sem `.dockerignore` |
| Testes | 2,5 | Não versionados, sem mocks, sem CI |
| Infraestrutura / deploy | 6,5 | Docker + Caddy corretos; falta hardening |
| Observabilidade | 3,0 | ~15 `except Exception` silenciosos, zero alerta |
| **Global** | **6,0** | Protótipo maduro e bem documentado, não endurecido |

**Veredito:** aprovado para piloto controlado (poucas revendas, monitoramento manual).
Não recomendo escalar para múltiplos clientes antes de resolver os itens 🔴 da seção 8.

---

## 2. Pontos fortes (o que manter)

1. **Camadas bem definidas.** `services/` (regra + integração), `crud/` (SQL), `schemas/`
   (contrato). Poucos projetos nesse estágio já têm isso.
2. **Estratégia de degradação em cascata pensada.** Tuya nativa → IFTTT → keywords. A
   intenção arquitetural está certa (a execução tem furos, ver §4).
3. **Multi-tenant desde o dia 1.** `mapa_revendas` + `tuya_clientes_homes` foi decisão certa;
   retrofitar isolamento depois é caríssimo.
4. **Assinatura HMAC da Tuya implementada à mão e corretamente** (`tuya_service.py:31-58`) —
   incluindo o hash de corpo vazio e a ordem `client_id + token + t + stringToSign`. É a parte
   mais difícil de acertar da OpenAPI Tuya.
5. **Cache de token e de status de dispositivos** com TTL (`tuya_service.py:24-26, 67`) —
   evita estourar quota da Tuya.
6. **Verificação de dispositivo offline antes de comandar** (`main.py:376`), com fail-safe
   permissivo. Boa decisão de produto: melhor comandar do que travar por falso negativo.
7. **`secrets.compare_digest`** na validação de API Key (`main.py:69`) — timing-safe, detalhe
   que quase todo mundo erra.
8. **`/docs` desabilitado em produção** (`main.py:164`).
9. **Postgres exposto só em `127.0.0.1`** (`docker-compose.yml:18`) e API atrás do Caddy — o
   último commit não-versionado corrigiu justamente isso.
10. **Índice HNSW com `vector_cosine_ops`** (`init.sql:148`) — escolha correta para o volume
    esperado.

---

## 3. 🔴 Bugs (defeitos de corretude)

### B1 — `NameError` derruba todo o caminho de fallback puro
`app/main.py:453`

`credenciais` só é atribuída **dentro** do bloco `if settings.gemini_api_key:`
(`main.py:314`) ou no `except` dele (`main.py:351`). Se `GEMINI_API_KEY` estiver ausente, o
fluxo cai no fallback de keywords (`main.py:354`), identifica a ação, e então executa
`buscar_link_ifttt(credenciais, ...)` com a variável nunca ligada.

**Falha concreta:** sem chave Gemini, `POST /agent {"mensagem": "tá quente"}` → `NameError`
→ capturado pelo `except` global (`main.py:522`) → HTTP 500. O modo de operação anunciado
como "fallback" está 100% quebrado.

**Correção:** `credenciais = None` antes da linha 305.

---

### B2 — Auto-migração nunca executa (falha silenciosa)
`app/main.py:219`

```python
from app.database import AsyncSessionLocal   # ← este símbolo não existe
```

`app/database.py:17` define `async_session_maker`. O `ImportError` é engolido pelo
`except Exception` da linha 224, que só emite um `logger.warning`.

**Falha concreta:** em qualquer banco cujo volume tenha sido criado antes de
`chat_historico_recente` entrar no `init.sql`, a tabela nunca é criada. E como
`app/crud/chat_history.py` captura exceção em **todas** as funções (linhas 26, 57, 100),
a memória de curto prazo simplesmente para de funcionar sem erro visível — o escalonamento
progressivo (§4/L2) degrada para "sempre 1º chamado" e ninguém percebe.

**Correção:** trocar por `async_session_maker` e mover para o `lifespan`.

---

### B3 — Handler de rate limit retorna o objeto errado
`app/main.py:175`

```python
return HTTPException(status_code=429, ...)
```

Um exception handler do Starlette deve **retornar uma `Response`** (ou fazer `raise`).
Retornar a instância de `HTTPException` faz o ASGI quebrar.

**Falha concreta:** ao estourar o limite, em vez de 429 o cliente recebe erro de servidor /
conexão abortada. Só não apareceu ainda porque o limite é generoso (600/min).

**Correção:** `return JSONResponse(status_code=429, content={...})`.

---

### B4 — Ambiente virtual local corrompido
`agente-sof/venv/`

**2.801 de 3.818** arquivos `.py` em `site-packages` têm **0 bytes**.
`import fastapi` falha com `cannot import name 'Depends'`; `python -m pip` não roda.

O "Método A: Execução Nativa" do README não funciona nesta máquina. Provável sincronização
de nuvem (OneDrive) ou cópia interrompida.

**Correção:** `Remove-Item -Recurse -Force venv; python -m venv venv; .\venv\Scripts\pip install -r requirements.txt`

---

### B5 — README aponta para arquivos inexistentes
- `.env.example` **não existe** — README linhas 243 e 316 instruem `cp .env.example .env`.
- `database/seed_teste.sql` **não existe** — README linhas 81, 250 e 268 o usam para seeding.

Onboarding de qualquer pessoa nova falha no passo 4.

---

### B6 — `lifespan` e `@app.on_event` coexistem
`app/main.py:166` e `app/main.py:213`. Deprecado no FastAPI atual; consolidar no `lifespan`.

---

## 4. 🟠 Lógica de negócio (o comportamento não é o especificado)

### L1 — Fallback contradiz o escalonamento
`app/services/fallback_service.py:9-16` mapeia `"quente"`, `"calor"`, `"abafado"` →
**`freezer`** (resfriamento máximo). O prompt do LLM (`llm_service.py:102`) exige
**`medio`** no primeiro chamado.

**Falha concreta:** quando o Gemini oscila, a mesma mensagem "loja quente" deixa de ligar em
temperatura média e passa a ligar no máximo. O cliente sente o sistema como imprevisível — e
essa inconsistência é invisível nos logs, porque ambos gravam `status: "sucesso"`.

### L2 — O escalonamento de 3 níveis é, na prática, de 2
`app/services/llm_service.py:103-104`

2º chamado → `ifttt_action: "freezer"`. 3º chamado → `ifttt_action: "freezer"`.
**A mesma cena Tuya dispara**, mas a mensagem ao usuário diz "T-Low" no 2º e
"resfriamento máximo T-Freezer" no 3º.

**Falha concreta:** o bot afirma ter intensificado o resfriamento sem ter feito nada
diferente. Se T-Low e T-Freezer são cenas distintas na Tuya, falta uma ação `freezer_max`;
se são a mesma, o texto precisa parar de prometer três níveis.

### L3 — A contagem de chamados é frágil por construção
`app/main.py:292` — `limite=6` mensagens, e a tabela grava **usuário e Sofia**
(`main.py:295` e `main.py:477`). Janela real: ~3 turnos.

**Falha concreta:** no 3º pedido de resfriamento, o 1º já pode ter saído da janela, e o LLM
— que conta ocorrências lendo texto livre — volta para "medio". Contar por texto no prompt
é o mecanismo errado.

**Correção:** `SELECT COUNT(*) FROM logs_operacoes WHERE id_grupo = :g AND intencao LIKE 'ligar_%' AND timestamp >= NOW() - INTERVAL '15 minutes'`
e passar o número pronto ao prompt.

### L4 — Falso positivo em "reunião" desliga automações de verdade
`app/services/llm_service.py:42-51` — regra determinística por substring, **antes** de
qualquer análise semântica.

**Falha concreta:** `"a sala de reunião está quente"` → `pausar_automacao`. O
`main.py:409-422` então **efetivamente desativa todas as automações Tuya da revenda** e
agenda reativação, enquanto o pedido real (esfriar) é ignorado. A revenda perde as rotinas
de desligamento automático por causa de uma reclamação de calor.

**Correção:** exigir co-ocorrência de intenção temporal (`até`, `mais tarde`, `hoje à noite`,
horário) além da palavra-chave.

### L5 — Extração de horário pega qualquer número da frase
`app/services/scheduler_service.py:32`

```python
re.search(r'(\d{1,2})(?:[:h](\d{2}))?\s*(?:h|horas)?', mensagem.lower())
```

Sem âncora em "até", sem exigir sufixo de hora, e pega a **primeira** ocorrência.

**Falhas concretas:**
- `"reunião na sala 3"` → agenda 03:00 do dia seguinte (`data_alvo < agora` → +1 dia).
- `"reunião dia 30 até 21h"` → captura `30` → reprovado em `0 <= hora <= 23` → cai no
  fallback de +2h, ignorando o 21h explícito.
- `"reunião até as 8"` → 08:00 do dia seguinte, não 20:00.

**Correção:** regex ancorada (`(?:até|ate)\s*(?:as|às)?\s*(\d{1,2})(?::(\d{2}))?\s*(?:h|hs|horas)?`)
+ heurística comercial (hora < 7 → +12).

### L6 — Sinônimo de ambiente casa com quase tudo
`app/crud/tuya.py:98` — `"terreo": [..., "%t%"]`.

`LOWER(nome_cena) LIKE '%t%'` casa com praticamente qualquer nome de cena em português.
Um pedido para o térreo pode selecionar a cena de outro andar.

### L7 — 🔴 Risco de vazamento entre revendas (cross-tenant)
`app/crud/tuya.py:16-68`

`get_home_by_nome` tenta, em cascata: (1) `ILIKE` exato, (2) qualquer dígito do nome com
`JOIN` em cenas, (3) `AND` de palavras ≥3 chars, (4) **substring solta**. Nenhum passo
verifica que a home encontrada pertence ao `id_grupo` que fez a requisição — o `id_grupo`
autenticado do payload nunca entra nessa query.

Agrava: `nome_revenda` vai **cru** para o `ILIKE` (linha 26), então `%` e `_` enviados pelo
n8n viram wildcards.

**Falha concreta:** duas revendas com nomes parecidos ("Revenda 019" e "Revenda 0190", ou
duas cujo nome compartilhe as palavras ≥3 chars) podem resolver para a mesma `home_id`. O
resultado é **ligar o ar-condicionado do cliente errado** — exatamente a garantia que o
README §1 item 2 vende como central. É o risco mais sério do projeto.

**Correção:** derivar `home_id` de `id_grupo_wpp` (chave `UNIQUE`, já indexada) via
`mapa_revendas`, não de string livre. Manter a busca difusa apenas como diagnóstico
administrativo, nunca no caminho de comando.

### L8 — Agendamentos evaporam no restart
`app/services/scheduler_service.py:22, 111` — `asyncio.create_task` + `dict` em memória.

**Falha concreta:** `docker compose restart` (ou deploy, ou crash) durante uma reunião →
automações ficam desativadas **permanentemente** e a cena T-OFF nunca dispara. O
ar-condicionado da revenda passa a noite ligado, e no dia seguinte as rotinas normais não
voltam. Custo real em energia e desgaste.

Também impede rodar mais de um worker uvicorn.

**Correção:** tabela `agendamentos` (status, `executar_em`, `home_id`, `automacao_ids`) +
loop que varre a cada minuto e é idempotente.

---

## 5. 🟡 Performance

| # | Local | Problema |
| :--- | :--- | :--- |
| P1 | `rag_service.py:34, 86` | `genai.embed_content` é **síncrono** dentro de `async def` → bloqueia o event loop. Com concorrência, toda a API congela durante cada embedding. Envolver em `asyncio.to_thread`. |
| P2 | `tuya_service.py:84, 129` | `httpx.AsyncClient()` novo por requisição — zero reuso de conexão/TLS. Instanciar um no `lifespan`. |
| P3 | `rag_service.py:47` | Abre sessão própria em vez de reusar a do request → conexão extra por chamada. |
| P4 | `rag_service.py:54` | Busca vetorial sem limiar de distância: sempre injeta 3 documentos, relevantes ou não. Ruído no prompt e custo de token. Adicionar `WHERE embedding <=> :q < 0.35`. |
| P5 | `main.py:290-295` | Dois `COMMIT` sequenciais (histórico) antes do LLM, mais 1 depois, mais 1 do log — 4 round-trips por mensagem. |

---

## 6. 🔴 Segurança

### S1 — Chave real do IFTTT no histórico do Git ⚠️ AÇÃO IMEDIATA
`database/seed_grupos.sql` foi sanitizado em `32929e9` ("docs: sanitiza seed do banco"), mas
a chave real (`boVO_…`, 22 caracteres) permanece acessível em `32929e9^`, `41442ac` e
`27fb7d3`. O remote é público-por-padrão no GitHub.

`README.md:144` também exibe o prefixo real no exemplo de response.

**Sanitizar o arquivo não remove nada do histórico.** Qualquer clone tem a chave.

**Ação:** (1) **rotacionar a chave IFTTT agora**; (2) mascarar o exemplo do README;
(3) opcionalmente `git filter-repo` + force-push, mas só depois da rotação — a rotação é o
que de fato resolve.

### S2 — Senha do Postgres com 4 caracteres
`.env` → `POSTGRES_PASSWORD` tem **4 chars**, e a mesma senha compõe `DATABASE_URL`.
Mitigado por `127.0.0.1:5432` (`docker-compose.yml:18`), mas indefensável em produção.

### S3 — Sem `.dockerignore`: segredos e 200 MB de lixo na imagem
`Dockerfile:21` faz `COPY . .` e **não existe `.dockerignore`**. Entram na imagem:
- **`.env`** — com `GEMINI_API_KEY`, `API_KEY` (64 chars), `TUYA_CLIENT_SECRET`. Gravado em
  layer, recuperável de qualquer registry/tarball, independente de `env_file`.
- **`venv/`** — 200 MB de bibliotecas Windows corrompidas, inúteis no Linux.
- `.git/`, `__pycache__/`, `.pytest_cache/`.

**Ação:** criar `.dockerignore` com `venv/`, `.env*`, `.git/`, `__pycache__/`,
`.pytest_cache/`, `*.exe`, `docs/`, `utils/`.

### S4 — API sobe aberta se o `.env` não for lido
`config.py:64` → `api_key` default `"dev-api-key-insegura"` (valor público, está no repo).
Um typo de path no container, e a API aceita comandos de qualquer um com a chave que está
no README.

**Ação:** validador Pydantic que **falha o boot** se `is_production` e
`api_key`/`secret_key` estiverem no default.

### S5 — CORS totalmente aberto
`main.py:184-190` — `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`.
O consumidor é n8n server-to-server; não há navegador no fluxo. Remover o middleware.

### S6 — PII sem retenção
`init.sql:102` (`mensagem_original TEXT NOT NULL`) e `chat_historico_recente.conteudo`
guardam mensagens de WhatsApp indefinidamente. O próprio `init.sql:82` reconhece
("planeje uma política de retenção") e ela nunca foi implementada.
`limpar_historico_antigo` (`chat_history.py:105`) existe mas **não é chamada em lugar
nenhum** — código morto.

**Ação:** job de purga (ex.: histórico 24 h, logs 90 dias) e revisão LGPD.

### S7 — O log de erro pode se perder exatamente quando importa
`main.py:526` chama `registrar_log` dentro do `except` global, reusando a **mesma sessão**
que provavelmente está em estado abortado. `logs.py:51` captura a exceção e **não faz
rollback**.

**Falha concreta:** falhas causadas por erro de banco não geram registro em
`logs_operacoes` — contradizendo o aviso do README linha 158 ("Erros HTTP 500 geram um
registro automático na tabela de logs"). Você perde justamente os logs dos piores
incidentes.

**Ação:** `registrar_log` deve abrir sessão própria e fazer `rollback` no `except`.

---

## 7. 🟠 Qualidade, testes e documentação

### Q1 — 🔴 A suíte de testes não está no controle de versão
`.gitignore:67-72` ignora `utils/`, `tests/`, `testar_agente.py`, `test_grupo_thiago.py`.
Confirmado: **37 arquivos rastreados**, nenhum teste entre eles.

Consequência: ninguém além desta máquina tem os testes; não há como rodar CI; o trabalho de
`tests/test_api.py` e `tests/test_grupo_thiago.py` está a um `rm -rf` de desaparecer.
Provavelmente foi um ignore de conveniência (dados sensíveis em `utils/`) que arrastou
`tests/` junto.

**Ação:** remover `tests/` e `testar_agente.py` do `.gitignore`, commitar. Manter `utils/`
ignorado se contiver dados de cliente — mas então mover os scripts reutilizáveis para
`scripts/`.

### Q2 — Os testes existentes não são executáveis nem isolados
- `tests/test_api.py:45` usa `Bearer dev-api-key-insegura` hardcoded → falha contra o `.env`
  real (`API_KEY` de 64 chars).
- `test_agent_valid_keyword_fallback` bate no **Postgres e no Gemini de verdade**. É teste de
  integração disfarçado de unitário: lento, não determinístico, gasta quota, e falha
  offline.
- Sem `pytest.ini`, `pyproject.toml` nem `conftest.py` — nenhuma fixture, nenhum `TESTING`
  env, nenhum CI.

### Q3 — Zero cobertura no que mais quebra
Nada testa: assinatura HMAC da Tuya, `extrair_horario_termino` (§L5), `get_scene_by_ambiente`
/ `get_home_by_nome` (§L7 — o roteamento multi-tenant), matriz de keywords do fallback
(§L1), ou a classificação do LLM.

Um `pytest.mark.parametrize` com 30 frases reais → intenção esperada teria pegado L1, L2 e L4
antes da produção. É o item de melhor retorno da lista inteira.

### Q4 — `except Exception` silencioso em ~15 pontos
`chat_history.py` (26, 57, 100, 118), `revendas.py:33`, `logs.py:51`, `llm_service.py:229`,
`rag_service.py` (41, 78, 93, 111), `tuya.py`, `main.py` (224, 448).

O padrão é `logger.warning` + retornar vazio. O sistema opera degradado indefinidamente sem
que ninguém saiba: RAG mudo, memória de curto prazo morta, logs faltando — tudo com
`status: "sucesso"` no banco. Não há Sentry, alerta nem métrica.

**Ação:** para cada `except`, decidir explicitamente entre *degradar* (e emitir métrica) ou
*falhar*. Adicionar Sentry — é meia hora de trabalho.

### Q5 — `main.py` acumulou responsabilidade demais
613 linhas; `process_agent_command` sozinha tem **~280 linhas** e mistura roteamento HTTP,
orquestração Tuya, decisão de negócio, logging e persistência. Imports espalhados no meio do
módulo (`main.py:90-99, 310, 426, 579`; `crud/tuya.py:32`; `llm_service.py:225`).

**Ação:** extrair `services/agent_orchestrator.py`; deixar a rota com validar → orquestrar →
responder.

### Q6 — O prompt do sistema pede refatoração urgente
`llm_service.py:66-154` — ~90 linhas de regras em concatenação de strings, com camadas que se
sobrepõem: "PRIORIDADE MÁXIMA", "REGRA DE SOBREPOSIÇÃO ABSOLUTA (PRIORIDADE CRÍTICA)",
"REGRA MANDATÓRIA", "Hierarquia de Conhecimento". Regra 1 e a seção de sobreposição dizem a
mesma coisa duas vezes; a regra de escalonamento aparece duplicada nas linhas 99-105 e
120-124.

O histórico do Git confirma o diagnóstico: 12 commits `"Correção da llm"` / `"fix: ..."`
sobre semântica. É um prompt remendado em produção, e cada remendo aumenta a chance de
regressão no comportamento anterior.

**Ação:** mover para `prompts/sistema_v1.md` versionado, deduplicar, e criar a suíte de
regressão de classificação do Q3. Sem os testes, qualquer edição do prompt é aposta.

### Q7 — Documentação desalinhada do código
| Onde | Divergência |
| :--- | :--- |
| `main.py:238` vs `main.py:137` | `/health` responde `mode: "ifttt_bridge"`, mas o log de startup diz "Tuya API Direta + IFTTT Fallback" |
| `schemas/agent.py:104-108` | Descrição de `intencao` lista valores que **não existem** (`ligar_dispositivo`, `ajustar_temperatura`, `consultar_status`) — o Swagger publica contrato errado |
| README §3 | Não documenta `ambiente`, `tuya_success`, `POST /rag/aprender`, `POST /proactive/fechamento`, nem as intenções `ligar_temperatura_media` e `pausar_automacao` |
| `main.py:83` vs `main.py:86` | Comentário diz "Padrão: 60 requisições por minuto"; o código usa `600/minute` |
| README §2 | Lista `cloudflared.exe` na estrutura, mas `*.exe` está no `.gitignore:64` |
| README:158 | Promete log automático de todo erro 500 — ver §S7, não é garantido |

### Q8 — Códigos mortos e pequenos ruídos
- `chat_history.py:105` `limpar_historico_antigo` — nunca chamada.
- `main.py:515` `ambiente if 'ambiente' in locals() else None` — `ambiente` sempre existe
  (definida em `main.py:302`).
- `main.py:140-141` TODOs de "Fase 2" já implementados.
- `database.py:35` `get_sync_engine` — sem uso no app.
- `extracao_tuya_completa.md` duplicado na raiz e em `utils/` (60 KB cada).
- `app/scripts/ingest_chat_mock.py`, `reset_rag_table.py` — utilitários misturados ao pacote
  da aplicação.

---

## 8. Infraestrutura

| # | Item | Observação |
| :--- | :--- | :--- |
| I1 | `docker-compose.yml:1` | `version: '3.8'` obsoleto — Compose v2 emite aviso |
| I2 | `docker-compose.yml:21` | `./database` como `initdb.d` roda **só na criação do volume**, em ordem alfabética. Alembic está no `requirements.txt:44` mas **não há `alembic.ini` nem `migrations/`** — o schema evolui por `CREATE TABLE IF NOT EXISTS` no código de aplicação (§B2). Dívida técnica que vai doer no primeiro `ALTER TABLE` |
| I3 | `Dockerfile` / compose | Sem `HEALTHCHECK`; serviço `api` sem healthcheck (só `db` tem); `caddy` usa `depends_on` sem `condition` |
| I4 | `Dockerfile:32` | Worker único, sem `--workers`. Hoje é **obrigatório** — scheduler (§L8) e cache de token Tuya são in-memory. Documentar essa restrição explicitamente, senão alguém "otimiza" e quebra os agendamentos |
| I5 | `Dockerfile:11-14` | `build-essential` + `libpq-dev` permanecem na imagem final. Multi-stage build reduziria bem o tamanho |
| I6 | `Caddyfile` | Sem headers de segurança (HSTS, `X-Content-Type-Options`), sem bloco `log`, sem rate limit de borda |
| I7 | Alterações não commitadas | `Caddyfile` (domínio → `sof.app.br`) e `docker-compose.yml` (porta → `127.0.0.1:8000`) estão apenas na árvore de trabalho. **A blindagem da porta 8000 só existe nesta máquina** — um deploy a partir do Git reexpõe a API |

---

## 9. Plano de ação priorizado

### 🔴 Bloco 1 — Fazer esta semana
| # | Ação | Ref. |
| :---: | :--- | :--- |
| 1 | **Rotacionar a chave do IFTTT** (está no histórico do Git) e mascarar o exemplo do README | S1 |
| 2 | Criar `.dockerignore` (`venv/`, `.env*`, `.git/`, `__pycache__/`) e rebuildar | S3 |
| 3 | Remover `tests/` e `testar_agente.py` do `.gitignore` e commitar a suíte | Q1 |
| 4 | Commitar as mudanças pendentes de `Caddyfile` e `docker-compose.yml` | I7 |
| 5 | Corrigir `credenciais = None` (`main.py:453`) | B1 |
| 6 | Corrigir `AsyncSessionLocal` → `async_session_maker` (`main.py:219`) | B2 |
| 7 | Derivar `home_id` de `id_grupo_wpp`, não de `nome_revenda` | **L7** |
| 8 | Trocar `POSTGRES_PASSWORD` (4 → 32+ chars) | S2 |
| 9 | Recriar o `venv` local | B4 |

### 🟠 Bloco 2 — Próximas duas semanas
| # | Ação | Ref. |
| :---: | :--- | :--- |
| 10 | Persistir agendamentos em tabela (hoje o ar passa a noite ligado após qualquer restart) | **L8** |
| 11 | Suíte de regressão de classificação: 30+ frases reais → intenção esperada, com Gemini mockado | Q3 |
| 12 | Alinhar fallback ↔ escalonamento (`"quente"` → `medio`) | L1 |
| 13 | Resolver T-Low vs T-Freezer: nova ação ou parar de prometer 3 níveis | L2 |
| 14 | Contar chamados por SQL em `logs_operacoes`, não pedindo ao LLM contar texto | L3 |
| 15 | Exigir marcador temporal junto de "reunião" antes de pausar automações | L4 |
| 16 | Reescrever `extrair_horario_termino` com regex ancorada em "até" + testes | L5 |
| 17 | `embed_content` em `asyncio.to_thread` | P1 |
| 18 | Validador que falha o boot com `api_key`/`secret_key` default em produção | S4 |
| 19 | `registrar_log` com sessão própria + rollback | S7 |
| 20 | Remover o middleware de CORS | S5 |
| 21 | Corrigir o handler de rate limit | B3 |
| 22 | Criar `.env.example` e `database/seed_teste.sql` | B5 |

### 🟡 Bloco 3 — Backlog técnico
| # | Ação | Ref. |
| :---: | :--- | :--- |
| 23 | Extrair `agent_orchestrator.py` de `main.py` (280 linhas numa função) | Q5 |
| 24 | Mover o prompt para `prompts/sistema_v1.md`, deduplicar as regras sobrepostas | Q6 |
| 25 | Adotar Alembic de fato (`alembic init`) e parar de migrar via código | I2 |
| 26 | Sentry + revisão dos ~15 `except Exception` silenciosos | Q4 |
| 27 | Job de retenção (histórico 24 h, logs 90 dias) — LGPD | S6 |
| 28 | `httpx.AsyncClient` único no `lifespan` | P2 |
| 29 | Limiar de distância na busca vetorial | P4 |
| 30 | Corrigir `"%t%"` em `AMBIENTE_SYNONYMS` | L6 |
| 31 | Sincronizar README + docstrings do Swagger com o código | Q7 |
| 32 | Healthchecks, multi-stage build, headers de segurança no Caddy | I3, I5, I6 |
| 33 | Limpar código morto e arquivos duplicados | Q8 |
| 34 | CI no GitHub Actions rodando `pytest` (só faz sentido depois do item 3) | Q1 |

---

## 10. Considerações finais

O projeto tem uma base melhor do que a maioria dos protótipos que chegam a produção: a
separação em camadas é real, o multi-tenant foi pensado desde o início, e o README é um ativo
genuíno. Os problemas se concentram em três frentes bem delimitadas, e nenhuma exige
reescrita:

1. **Isolamento multi-tenant** (L7) — resolver derivando `home_id` da chave `UNIQUE` de
   grupo. É meio dia de trabalho e elimina o pior risco de produto: comandar o ar do cliente
   errado.
2. **Durabilidade de estado** (L8, B2) — tirar scheduler e migração de dentro da memória do
   processo.
3. **Rede de segurança** (Q1, Q3) — versionar os testes e criar a suíte de regressão
   semântica. Sem ela, os 12 commits de "Correção da llm" vão continuar virando 20, porque
   cada ajuste de prompt é feito no escuro.

O padrão que mais preocupa não é nenhum bug isolado, e sim o **`except Exception` +
`logger.warning`** repetido em ~15 pontos. Ele transformou pelo menos dois defeitos reais
(B2 e o RAG mudo) em silêncio operacional. Vale como princípio para a próxima fase: em cada
`except`, escolher deliberadamente entre degradar com métrica ou falhar alto — nunca
sussurrar.
