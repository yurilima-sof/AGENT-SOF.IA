# Plano de Ação Técnico — Agente SOF

**Autor:** Engenharia de Software / Sistemas IA-IoT
**Data:** 13/08/2026
**Base:** `docs/AVALIACAO_TECNICA.md` (34 achados)
**Status:** PLANO — nenhuma alteração aplicada ao código ainda

---

## Sumário

- [Princípios de execução](#princípios-de-execução)
- [Portões de decisão (preciso de resposta)](#portões-de-decisão)
- [Arquitetura-alvo](#arquitetura-alvo)
- [ETAPA 0 — Recuperação do ambiente e baseline](#etapa-0)
- [ETAPA 1 — Bloco 1: 9 itens urgentes](#etapa-1)
- [ETAPA 2 — Bloco 2: regressão semântica + 13 itens](#etapa-2)
- [ETAPA 3 — Bloco 3: backlog e refatoração](#etapa-3)
- [Matriz de rastreabilidade](#matriz-de-rastreabilidade)
- [Riscos do próprio plano](#riscos-do-próprio-plano)

---

## Princípios de execução

Cinco regras que valem para todas as etapas:

1. **Um problema por commit.** Cada item vira um commit atômico com mensagem
   `fix(escopo): descrição [ref]`, onde `ref` é o ID do achado (`L7`, `S3`…). Isso permite
   `git revert` cirúrgico se algo regredir em produção.
2. **Teste antes da correção (red-green).** Para cada bug, primeiro escrevo o teste que
   *falha* reproduzindo o defeito, depois corrijo. Sem isso, não há prova de que o bug
   existia nem garantia de que não volta.
3. **Etapa 0 não muda comportamento.** Só ambiente e arnês de teste. Qualquer tentação de
   "já que estou aqui, corrijo isso" vai para a Etapa 1.
4. **Degradação é decisão explícita, nunca acidente.** O padrão `except Exception +
   logger.warning` some. Cada capacidade recebe uma classificação escrita:
   *degradável* (com métrica) ou *fatal* (aborta e informa). Ver §[Etapa 1 / U-01](#u-01).
5. **Isolamento multi-tenant é invariante, não feature.** Nenhum caminho de código pode
   resolver `home_id` a partir de string livre. Isso vira teste de arquitetura
   (grep-test que falha o build se `get_home_by_nome` for importado em `services/`).

---

## Portões de decisão

Itens que **não posso decidir sozinho** — a resposta muda o desenho. Segue minha
recomendação para cada um; se você concordar, sigo sem esperar.

| # | Pergunta | Impacto | Minha recomendação |
| :---: | :--- | :--- | :--- |
| **D1** | `T-Low` e `T-Freezer` são **cenas distintas** na Tuya, ou o mesmo cenário? | Define se o escalonamento é de 3 ou 2 níveis (achado L2) | Rodar a query abaixo. Se houver cenas distintas → 3 níveis reais com nova ação `low`. Se não → colapsar para 2 e **corrigir o texto** que hoje promete três |
| **D2** | Ao pausar para reunião, devo desativar **todas** as automações ou só as de desligamento? | Hoje o código desativa **todas** as automações habilitadas da home (`main.py:414-421`), apesar do log dizer "regras de desligamento/timer" | Restringir por padrão de nome (`desliga`, `off`, `timer`, `noturn`) **e** registrar em auditoria o que foi desativado. Desativar tudo é destrutivo e não foi pedido pelo usuário |
| **D3** | Quando não der para extrair o horário, o bot deve **perguntar** ou manter o default de +2h? | Hoje inventa +2h em silêncio (`scheduler_service.py:45`) | **Perguntar.** Prometer reativação num horário que o usuário não pediu é pior que pedir confirmação |
| **D4** | Quem rotaciona a chave do IFTTT? O repo `AGENT-SOF.IA` é público? | Achado S1 — chave real no histórico do Git | Rotacionar **hoje**, antes de qualquer código. Se o repo for privado, o risco cai, mas a chave continua em todo clone existente |
| **D5** | `utils/` contém dados reais de cliente (`tuya_inserts.sql` tem 100 KB, `home_ids_revendas.md`)? | Define se desmarco `utils/` do `.gitignore` junto com `tests/` | Manter `utils/` ignorado; mover só os scripts reutilizáveis para `scripts/` e versionar esses |
| **D6** | Posso mover o `venv` para fora de `Desktop/` (ex.: `C:\venvs\agente-sof`)? | É a **causa raiz** da corrupção (§Etapa 0). Recriar no mesmo lugar provavelmente corrompe de novo | Sim, mover — ou excluir a pasta do OneDrive |
| **D7** | Existe um Postgres de teste/staging disponível? | Define se os testes de integração rodam em CI ou só localmente | Usar Docker efêmero no CI (`services: postgres` no GitHub Actions com imagem `pgvector/pgvector:pg16`) |
| **D8** | Qual o SLA de latência aceitável para `POST /agent`? | Define se a chamada Tuya fica no caminho síncrono ou vira fila | Manter síncrono por ora (usuário espera confirmação), mas instrumentar p95 |

**Query do portão D1:**
```sql
SELECT h.nome_home, c.ambiente, c.acao, c.nome_cena
FROM tuya_clientes_cenas c
JOIN tuya_clientes_homes h ON h.home_id = c.home_id
ORDER BY h.nome_home, c.ambiente, c.acao;
```

---

## Arquitetura-alvo

O `main.py` de 613 linhas com uma função de 280 vira isto. A mudança não é estética: **é o
que torna as regras testáveis sem LLM e sem banco.**

```
agente-sof/
├── app/
│   ├── api/
│   │   ├── deps.py                 # verify_api_key, get_db, get_tenant
│   │   ├── errors.py               # handlers (rate limit, domínio → HTTP)
│   │   └── routes/
│   │       ├── agent.py            # rota fina: valida → orquestra → responde
│   │       ├── health.py           # liveness + readiness
│   │       ├── rag.py
│   │       └── proactive.py
│   ├── core/
│   │   ├── config.py               # + validadores de boot (S4)
│   │   ├── exceptions.py           # hierarquia de domínio (U-01)
│   │   ├── logging.py              # structured logs + correlation_id
│   │   └── metrics.py              # contadores de degradação
│   ├── domain/
│   │   ├── intents.py              # Enums Intencao / AcaoIoT — fonte da verdade
│   │   └── policy/                 # ← REGRAS DETERMINÍSTICAS, 100% testáveis
│   │       ├── time_parser.py      # U-06 (L5)
│   │       ├── pause_rules.py      # U-05 (L4)
│   │       ├── escalation.py       # C-03 (L2/L3)
│   │       └── keyword_fallback.py # U-04 (L1)
│   ├── services/
│   │   ├── orchestrator.py         # o miolo do ex-process_agent_command
│   │   ├── llm/
│   │   │   ├── client.py           # Protocol LLMClient (porta)
│   │   │   ├── gemini.py           # adapter real (async-safe)
│   │   │   ├── fake.py             # adapter determinístico para testes
│   │   │   └── prompt.py           # carrega prompts/sistema_vN.md
│   │   ├── rag/                    # embeddings (porta) + repositório vetorial
│   │   ├── tuya/                   # client httpx compartilhado + cenas
│   │   └── scheduler/
│   │       ├── repository.py       # tabela agendamentos (C-01)
│   │       └── worker.py           # loop idempotente
│   ├── repositories/               # ex-crud/, sem lógica de negócio
│   └── schemas/
├── prompts/
│   └── sistema_v1.md               # prompt versionado (B-02)
├── migrations/                     # Alembic (B-04)
├── scripts/
│   └── backfill_home_ids.py        # ex-get_home_by_nome, FORA do request path
└── tests/
    ├── unit/                       # puro, sem I/O, <1s total
    ├── integration/                # -m integration, precisa de Postgres
    └── llm_eval/                   # -m llm_eval, precisa de rede + quota
```

### A decisão central: tirar regra do prompt e colocar em código

Hoje ~90 linhas do prompt (`llm_service.py:66-154`) carregam regras de negócio duras:
contagem de chamados, detecção de reunião, prioridades absolutas. Isso é **intestável** —
é a razão pela qual existem 12 commits de "Correção da llm".

Divisão nova:

| Responsabilidade | Onde vive | Por quê |
| :--- | :--- | :--- |
| Contar chamados de calor na janela | SQL em `escalation.py` | Determinístico. LLM contando texto livre é frágil e não auditável |
| Detectar pedido de pausa/reunião | `pause_rules.py` | Ação destrutiva. Precisa de decisão explicável em auditoria |
| Extrair horário de término | `time_parser.py` | Regex é testável em 20 casos; LLM não dá garantia |
| Resolver ambiente quando o usuário especifica | `policy` + banco | Só o banco sabe quais ambientes existem |
| **Entender paráfrase e gíria** | **LLM** | É o que só o LLM faz bem |
| **Gerar texto amigável em pt-BR** | **LLM** | Idem |
| Desambiguar caso genuinamente ambíguo | LLM, com a política passando `INDETERMINADO` | Política não deve chutar |

O prompt encolhe de ~90 para ~25 linhas e passa a receber **fatos já computados**
(`nivel_escalonamento: 2`, `pausa_detectada: false`, `ambientes: [...]`) em vez de pedir
que o modelo os deduza.

---

## ETAPA 0

### Recuperação do ambiente e estabelecimento da baseline

**Objetivo:** conseguir rodar `pytest` de forma estável e repetível, **sem alterar uma
linha de lógica de produção**. Sem baseline não há como provar que a Etapa 1 corrigiu algo.

### 0.1 — Causa raiz da corrupção do venv

**O que observei:** 2.801 de 3.818 arquivos `.py` em `venv/Lib/site-packages` têm **0
bytes**. `fastapi/__init__.py` está vazio, `import fastapi` falha com
`cannot import name 'Depends'`, e `python -m pip` não produz saída.

**Por que aconteceu (hipótese principal):** o projeto está em
`C:\Users\SOF - Jaylson\Desktop\`, e há um `desktop.ini` oculto em `sof-ia-v1/` — assinatura
de pasta especial do Windows sob sincronização de nuvem. OneDrive com *Files On-Demand*
transforma arquivos em ponteiros de 0 byte quando libera espaço. Um `venv` tem ~4.000
arquivos pequenos: é exatamente o padrão que a sincronização quebra. Um `git status` ou uma
cópia interrompida produzem o mesmo sintoma.

**Por que isso importa mais que o sintoma:** recriar o `venv` no mesmo caminho apenas
reinicia o relógio até a próxima corrupção. Um `venv` **nunca** deve morar em pasta
sincronizada.

**Correção:**
1. Confirmar se `Desktop` é redirecionado para OneDrive (`$env:OneDrive`, `Get-Item Desktop`
   procurando reparse point).
2. Criar o venv **fora** do caminho sincronizado — `C:\venvs\agente-sof` (portão **D6**).
3. Se mover não for possível: excluir `venv/` da sincronização e adicionar `venv/` ao
   `.dockerignore` (que ainda não existe) e confirmar que já está no `.gitignore:8` — está.

**Risco da operação:** zero. O `venv` não está no Git (confirmado: 37 arquivos rastreados,
nenhum sob `venv/`) e é 100% reconstruível a partir do `requirements.txt`. Não há nada a
preservar.

### 0.2 — Reconstrução e travamento de dependências

Sequência:
```powershell
# 1. Descartar o venv corrompido
Remove-Item -Recurse -Force ".\venv"

# 2. Criar fora da árvore sincronizada (D6)
python -m venv C:\venvs\agente-sof
C:\venvs\agente-sof\Scripts\python.exe -m pip install --upgrade pip setuptools wheel

# 3. Instalar
C:\venvs\agente-sof\Scripts\pip.exe install -r requirements.txt

# 4. Travar o que de fato resolveu
C:\venvs\agente-sof\Scripts\pip.exe freeze > requirements.lock.txt
```

**Pontos de atenção no `requirements.txt` atual** — versões que preciso validar na
instalação, porque não confirmei que existem/são compatíveis:

| Linha | Pin | Risco |
| :--- | :--- | :--- |
| `requirements.txt:37` | `asyncpg==0.31.0` | Verificar se a versão existe no PyPI; asyncpg tem ciclo lento e pins inventados quebram o build |
| `requirements.txt:40` | `psycopg2-binary==2.9.12` | Idem |
| `requirements.txt:16` + `:54` | `fastapi==0.111.0` + `httpx==0.28.1` | FastAPI 0.111 fixa `starlette>=0.37.2,<0.38`. O `TestClient` do Starlette usa httpx; httpx 0.28 removeu o argumento `app=` depreciado. Se o `TestClient` dessa faixa ainda usar `app=`, **toda a suíte quebra na importação** — é o primeiro item a validar |
| `requirements.txt:26` | `pydantic>=2.13.0,<3.0.0` | Faixa aberta: build de hoje ≠ build de amanhã. Motivo pelo qual `requirements.lock.txt` é obrigatório |
| `requirements.txt:44` | `alembic==1.13.1` | Instalado mas **não usado** — não há `alembic.ini` nem `migrations/`. Fica até a Etapa 3 (B-04) |

Faltando (adicionar em `requirements-dev.txt`, separado do de produção):
`pytest`, `pytest-asyncio`, `pytest-cov`, `respx` (mock de httpx), `ruff`, `mypy`.

**Decisão de separar dev de prod:** hoje não há `requirements-dev.txt`, então instalar
pytest na imagem Docker seria a saída fácil. Não vamos fazer isso — inflaria a imagem e
aumentaria a superfície de ataque.

### 0.3 — Por que a suíte atual não roda, e o que corrigir (só arnês)

Três problemas independentes, todos de **arnês**, não de produção:

#### (a) Chave de API fixa no teste
`tests/test_api.py:45` usa `Bearer dev-api-key-insegura`. O `.env` real tem `API_KEY` de 64
caracteres. Resultado: **401**, e o `assert response.status_code == 200` falha.

**Correção:** o teste não pode conhecer a chave. Ela vem do mesmo `Settings` que a app usa:
```python
# tests/conftest.py
@pytest.fixture
def auth_headers(settings):
    return {"Authorization": f"Bearer {settings.api_key}"}
```

#### (b) Os testes leem o `.env` de produção
Todos os módulos (`main`, `database`, `llm_service`, `rag_service`, `tuya_service`) chamam
`get_settings()` **no momento da importação**, e `get_settings` é `@lru_cache`
(`config.py:113`). Consequência: quando o primeiro `import app.main` acontece, as
configurações reais já estão congeladas — inclusive `GEMINI_API_KEY` e
`TUYA_CLIENT_SECRET`. Rodar a suíte hoje **gasta quota do Gemini e fala com a Tuya real**.

**Correção em duas velocidades:**
- *Etapa 0 (pragmática):* `tests/conftest.py` popula `os.environ` no escopo de módulo,
  antes de qualquer import de `app.*`. Em pydantic-settings, variável de ambiente tem
  precedência sobre o arquivo `.env`, então isso vence. `conftest.py` é importado antes dos
  módulos de teste, o que garante a ordem.
- *Etapa 3 (correta):* parar de chamar `get_settings()` em tempo de import. Serviços
  recebem `Settings` por injeção. Isso elimina o singleton global e é o que permite testar
  dois cenários de configuração no mesmo processo.

#### (c) O teste "de unidade" é um teste de integração disfarçado
`test_agent_valid_keyword_fallback` (`tests/test_api.py:38`) atravessa banco, Gemini, RAG e
Tuya. É lento, custa dinheiro, não é determinístico e falha offline.

**Correção:** dividir. `dependency_overrides[get_db]` com sessão falsa; `FakeLLMClient`;
`respx` interceptando httpx para a Tuya. O teste de ponta a ponta real vira
`tests/integration/`, marcado e fora do laço rápido.

### 0.4 — Baseline prevista (a confirmar na execução)

Minha previsão, para ser comparada com o resultado real:

| Teste | Previsão | Motivo |
| :--- | :---: | :--- |
| `test_health_check` | ✅ passa | Sem I/O |
| `test_agent_unauthorized_missing_token` | ✅ passa | `HTTPBearer` retorna 403 antes de qualquer I/O |
| `test_agent_unauthorized_invalid_token` | ✅ passa | 401 antes de I/O |
| `test_agent_valid_keyword_fallback` | ❌ **falha (401)** | Chave fixa ≠ `.env` real |
| `test_rag_aprender_unauthorized` | ✅ passa | 403 |
| `test_proactive_fechamento_unauthorized` | ✅ passa | 403 |

**Baseline esperada: 5 passed, 1 failed.**

Detalhe importante: nenhum desses testes executa o `@app.on_event("startup")`, porque
`TestClient` só dispara o ciclo de vida quando usado como context manager, e
`tests/test_api.py:5` o instancia solto. **É por isso que o bug B2 (`AsyncSessionLocal`
inexistente) nunca apareceu em teste** — a suíte, do jeito que está, não consegue vê-lo.
Um dos primeiros testes novos usa `with TestClient(app):` justamente para expô-lo.

### 0.5 — O achado mais delicado da Etapa 0

Depois de corrigir a chave (item *a*), `test_agent_valid_keyword_fallback` vai passar de 401
para **200 com o corpo errado**:

```python
assert data["intencao"] == "ligar_resfriamento"   # o teste espera isto
assert data["ifttt_action"] == "freezer"
```

Mas o prompt vigente (`llm_service.py:102`) manda **`ligar_temperatura_media` / `medio`** no
primeiro chamado de calor. O teste codifica o comportamento *antigo*; o prompt implementa o
*novo*. Eles se contradizem — é a prova executável do achado **L1/L2**.

**A tentação errada:** trocar a asserção para casar com o comportamento atual. Isso apagaria
a evidência.

**O que farei:** converter em `xfail` estrito, com o motivo documentado:
```python
@pytest.mark.xfail(
    strict=True,
    reason="L1/L2: o fallback de keywords retorna 'freezer' mas o prompt do LLM "
           "exige 'medio' no 1º chamado. Contradição resolvida em U-04/C-03; "
           "este xfail deve virar PASS lá (strict=True força a revisão)."
)
```
Com `strict=True`, no dia em que a Etapa 1 corrigir a contradição o teste passa a *falhar
por passar inesperadamente* — o que me obriga a voltar e remover o marcador. É um lembrete
que não dá para ignorar.

### 0.6 — Entregáveis da Etapa 0

| Arquivo | Conteúdo |
| :--- | :--- |
| `requirements.lock.txt` | Saída de `pip freeze` do ambiente que funcionou |
| `requirements-dev.txt` | pytest, pytest-asyncio, pytest-cov, respx, ruff, mypy |
| `pyproject.toml` | `[tool.pytest.ini_options]`: `asyncio_mode`, `markers` (`integration`, `llm_eval`), `testpaths`, `addopts = -q --strict-markers` |
| `tests/conftest.py` | Env de teste antes dos imports, `get_settings.cache_clear()`, fixtures `settings` / `client` / `auth_headers` / `fake_db` |
| `docs/baseline_testes.md` | Saída bruta do primeiro `pytest`, com data e hash do commit |
| `.env.example` | Corrige o achado B5 (README linhas 243 e 316 referenciam arquivo inexistente) |

**Critério de saída da Etapa 0:** `pytest` roda em <5 s, offline, sem tocar em Postgres,
Gemini ou Tuya, com resultado idêntico em duas execuções seguidas.

---

## ETAPA 1

### Bloco 1 — 9 itens urgentes

Ordem deliberada: **segredos primeiro** (não dependem de código e o risco é contínuo),
depois **isolamento de tenant** (maior risco de produto), depois os bugs de corretude.

---

<a name="u-01"></a>
### U-01 — Exceções silenciosas: de `except Exception` para política explícita

**Onde:** `chat_history.py` (26, 57, 100, 118), `revendas.py:33`, `logs.py:51`,
`llm_service.py:229`, `rag_service.py` (41, 78, 93, 111), `crud/tuya.py`, `main.py`
(224, 448). ~15 pontos.

**Causa raiz.** O padrão é sempre o mesmo: `except Exception` → `logger.warning` → retorna
vazio/None. Não é um descuido pontual, é um *estilo* adotado no projeto, provavelmente para
evitar 500 em produção. O efeito colateral é que o sistema opera degradado por tempo
indeterminado e ninguém sabe: RAG mudo, memória morta, log de auditoria faltando — e tudo
gravado como `status: "sucesso"` em `logs_operacoes`.

**A prova:** o bug B2 (`AsyncSessionLocal` inexistente, `main.py:219`) é um `ImportError`
capturado pelo `except Exception` da linha 224. A auto-migração **nunca rodou** desde que
foi escrita, e o único vestígio é uma linha de `warning` no meio do log de startup.

**Reestruturação.**

Passo 1 — hierarquia de domínio (`app/core/exceptions.py`):
```python
class AgenteSofError(Exception):
    """Raiz. Toda exceção nossa herda daqui."""

class ConfigError(AgenteSofError):
    """Configuração inválida. Só no boot, sempre fatal."""

class DegradableError(AgenteSofError):
    """Capacidade opcional indisponível. Loga, emite métrica, segue."""
    capability: str

class RagUnavailable(DegradableError):            capability = "rag"
class ShortTermMemoryUnavailable(DegradableError): capability = "chat_history"
class LlmUnavailable(DegradableError):            capability = "llm"

class FatalError(AgenteSofError):
    """Aborta a requisição. Degradar aqui produziria ação errada."""

class TenantResolutionError(FatalError): ...   # L7 — jamais degradar
class SchedulePersistError(FatalError): ...    # C-01 — não prometer o que não gravou
class AuditLogWriteFailed(FatalError): ...     # ver nota abaixo

class TuyaError(AgenteSofError): ...
class TuyaAuthError(TuyaError): ...            # credencial ruim → alerta
class TuyaTransientError(TuyaError): ...       # 5xx/timeout → retry
class TuyaDeviceOffline(TuyaError): ...        # esperado, informa o usuário
```

Passo 2 — **a tabela de política**. Este é o entregável conceitual do item; sem ela, o
próximo desenvolvedor recria o problema:

| Capacidade | Falha → | Justificativa |
| :--- | :--- | :--- |
| RAG / contexto longo prazo | **degrada** (sem contexto) | Melhora qualidade, não corretude |
| Memória curto prazo — leitura | **degrada + força nível 1** | Perder a contagem só pode errar para o lado conservador (nunca ligar mais forte que o pedido) |
| Memória curto prazo — escrita | **degrada + métrica** | Próxima mensagem perde contexto, não há dano físico |
| Contagem de escalonamento | **degrada → nível 1** | Idem. Nunca escalar por falta de informação |
| **Resolução de tenant** | **FATAL** | Degradar = comandar o ar do cliente errado |
| **Persistência de agendamento** | **FATAL** | Se não gravou, o bot **não pode** prometer reativação |
| Execução de cena Tuya | **fatal para a resposta** | Usuário tem de saber que não ligou |
| Checagem de dispositivo online | **degrada permissiva** | Fail-safe atual está correto: melhor comandar que travar |
| Log de auditoria | **degrada + ALERTA sev-2** | Não bloqueia o comando, mas cega a operação |
| Gemini | **degrada → fallback determinístico** | É o desenho pretendido; agora com fallback coerente (U-04) |
| Config no boot | **FATAL** | Fail fast |

Passo 3 — reescrever cada `except`. Exemplo (`chat_history.py:100`):
```python
# ANTES — engole tudo, inclusive bug de código
except Exception as e:
    await db.rollback()
    logger.warning(f"⚠️ Erro ao buscar histórico recente de chat: {e}")
    return ""

# DEPOIS — captura só falha de infraestrutura; bug de código sobe
except (DBAPIError, OSError) as e:
    await db.rollback()
    metrics.degraded("chat_history.read")
    raise ShortTermMemoryUnavailable("leitura de histórico recente") from e
```
`ProgrammingError` (tabela inexistente, SQL inválido) **não** é degradável: é bug nosso,
tem de aparecer. O orquestrador captura `DegradableError`, registra e segue com nível 1.

Passo 4 — Sentry + `metrics.degraded(capability)` (contador simples via log estruturado
`event=degraded capability=...`, consumível por qualquer agregador).

**Testes.**
- Unitário, para cada capacidade: injetar repositório que levanta `OperationalError` →
  asserir que sobe a `DegradableError` correta e que `metrics.degraded` foi chamada com a
  label certa.
- Unitário: repositório levanta `ProgrammingError` → asserir que **propaga** (não é
  engolido). Este teste é o antídoto direto contra B2.
- Contrato: memória indisponível → resposta ainda é 200 **e** nível de escalonamento = 1.
- Contrato: `TenantResolutionError` → 200 com mensagem honesta, e **zero** chamadas ao
  cliente Tuya (`respx` asserindo `call_count == 0`). Esse é o teste que impede o vazamento
  cross-tenant de voltar por um caminho novo.
- Teste de arquitetura: `grep` falha o build se `except Exception:` aparecer sem
  `# noqa: BLE001` justificado.

**Edge cases.** Exceção *dentro* do handler de exceção (rollback falhando com a conexão
morta); `asyncio.CancelledError` — que herda de `BaseException` no Python 3.8+ e **não deve**
ser capturada por `except Exception`, mas hoje o `_run_task` do scheduler
(`scheduler_service.py:105`) a captura explicitamente, o que está correto e deve ser
preservado; `TimeoutError` do httpx classificado como transiente, não como falha permanente.

---

### U-02 — Rotacionar a chave IFTTT e limpar exposição (S1)

**Causa raiz.** `database/seed_grupos.sql` foi sanitizado no commit `32929e9`
("docs: sanitiza seed do banco"), substituindo as chaves por `SUA_CHAVE_IFTTT_AQUI`. Mas
Git é imutável: `git show 32929e9^:agente-sof/database/seed_grupos.sql` devolve a chave real
(`boVO_…`, 22 caracteres), e ela também está em `41442ac` e `27fb7d3`. Sanitizar o arquivo
no HEAD **não remove nada** do histórico. Além disso `README.md:144` ainda exibe o prefixo
real no exemplo de response.

**Por que a ordem importa:** reescrever o histórico *antes* de rotacionar não protege nada —
quem já clonou tem a chave. Rotacionar primeiro torna o histórico inofensivo.

**Correção.**
1. **Rotacionar a chave no IFTTT** (portão D4). Nada mais acontece antes disso.
2. Atualizar as 26 URLs no banco de produção — via `UPDATE mapa_revendas SET
   credenciais_tuya = ...`, **não** por re-seed (o seed só roda na criação do volume).
3. Mascarar `README.md:144`.
4. Varredura completa: `git log -p --all` procurando `with/key/`, `AIza` (Gemini),
   `TUYA_CLIENT_SECRET` com valor. Confirmei que `.env` **nunca** foi commitado (bom), mas a
   varredura tem de ser exaustiva antes de declarar limpo.
5. Instalar `gitleaks` como pre-commit hook — é o controle que impede a próxima ocorrência.
6. *Opcional, depois da rotação:* `git filter-repo` + force-push. Só com o time avisado,
   porque invalida todos os clones.

**Testes.** Não é código, mas é verificável e deve ser automatizado:
- `gitleaks detect --no-git` no working tree, e `gitleaks detect` no histórico, como job de
  CI que falha o build.
- Teste unitário garantindo que `credenciais_tuya` nunca apareça em log: asserir que o
  formatter redige chaves cujo nome casa `(key|secret|token|senha|password)`.

---

### U-03 — `.dockerignore`: parar de assar segredos na imagem (S3)

**Causa raiz.** `Dockerfile:21` faz `COPY . .` e **não existe `.dockerignore`**. Entram na
imagem: `.env` (com `GEMINI_API_KEY`, `API_KEY` de 64 chars, `TUYA_CLIENT_SECRET`), os
200 MB de `venv/` Windows corrompido, `.git/`, `__pycache__/`, `.pytest_cache/`.

O ponto sutil: `docker-compose.yml:38` usa `env_file: .env`, o que dá a *impressão* de que
os segredos entram só em runtime. Mas o `COPY . .` os gravou numa **layer**, e layer é
recuperável de qualquer registry, tarball ou `docker history` — independente do `env_file`.
E o `venv/` corrompido explica boa parte do tempo de build.

**Correção.** Criar `.dockerignore`:
```
venv/
.venv/
.env
.env.*
!.env.example
.git/
.gitignore
__pycache__/
*.py[cod]
.pytest_cache/
docs/
utils/
tests/
*.exe
*.md
!README.md
```
E como defesa em profundidade: mudar `COPY . .` para copiar só o necessário
(`COPY app/ ./app/`, `COPY prompts/ ./prompts/`), invertendo a lógica de "tudo menos o
excluído" para "só o que é preciso".

**Testes.**
- Teste de build em CI: `docker build` e então `docker run --rm img sh -c 'test ! -f /app/.env'`
  → falha o build se o `.env` aparecer.
- Asserir que a imagem final não contém `venv/` nem `.git/`.
- Registrar o tamanho da imagem antes/depois como métrica de regressão.

---

### U-04 — Alinhar fallback de keywords com o escalonamento (L1)

**Causa raiz.** `fallback_service.py:9-16` mapeia `"quente"`, `"calor"`, `"abafado"` →
`freezer` (resfriamento máximo). O prompt (`llm_service.py:102`) exige `medio` no primeiro
chamado. As duas trilhas de decisão divergiram porque foram escritas em momentos diferentes
e ninguém as compara — e ambas gravam `status: "sucesso"`, então a divergência é invisível
no banco.

**Impacto real.** Quando o Gemini oscila (o que `llm_service.py:229` trata como rotina), a
mesma frase deixa de ligar em temperatura média e passa a ligar no máximo. O cliente
percebe o sistema como imprevisível, e o log não explica por quê.

**Reestruturação.** A causa mais profunda é que existem **duas fontes de verdade** para a
mesma decisão. A correção não é editar a lista de keywords — é fazer as duas trilhas
consultarem a *mesma* política:

```python
# domain/policy/keyword_fallback.py
def classificar(mensagem: str) -> ClassificacaoFallback | None:
    """Só identifica a FAMÍLIA da intenção. Nunca escolhe o nível."""
    # "quente"/"calor"/"abafado" → FAMILIA_RESFRIAMENTO (sem nível)

# domain/policy/escalation.py
def nivel_para(familia, chamados_recentes: int) -> AcaoIoT:
    """Única função no sistema autorizada a escolher medio/low/freezer."""
```
Assim, LLM e fallback produzem `FAMILIA_RESFRIAMENTO`, e `escalation.nivel_para()` decide o
nível nos dois caminhos. A divergência deixa de ser possível por construção.

Correções adicionais na tabela de keywords:
- `"baixo"` e `"low"` em `freezer` (`fallback_service.py:13`) casam com frases sem relação
  com temperatura ("volume baixo", "estoque baixo").
- Faixas de temperatura em graus (linhas 14-15, 22-23, 28-29) deveriam ser uma comparação
  numérica, não 40 strings literais; `"18,5°"` e `"18.5"` não casam com nada hoje.

**Testes.**
- Teste de equivalência — o coração do item:
  ```python
  @pytest.mark.parametrize("frase", CORPUS_FRASES_REAIS)
  def test_fallback_e_llm_concordam_na_familia(frase, fake_llm):
      assert familia(fallback.classificar(frase)) == familia(fake_llm.classificar(frase))
  ```
- Parametrizado: `("loja quente", 0 chamados) → medio`; `(…, 1) → low`; `(…, 2) → freezer`.
- Regressão do achado L1: mesma frase, com LLM disponível e indisponível → **mesma ação**.
- Edge cases: `"volume baixo"` → nenhuma ação; `"estoque baixo"` → nenhuma; `"18,5 graus"`
  → resfriamento; `"tá quente mas não liga o ar"` → negação, sem ação (hoje ligaria);
  `"🔥"` sozinho → resfriamento; `"não tá quente"` → sem ação.
- Preservar o teste que já existe para a inversão frio/quente (commit `e9a7a19` corrigiu
  isso uma vez; sem teste, pode voltar).

---

### U-05 — Gatilho de pausa: exigir marcador temporal e restringir o escopo (L4)

**Causa raiz.** `llm_service.py:42-51` faz `any(p in mensagem_lower for p in
palavras_pausa)` — substring simples, **antes** de qualquer análise semântica, com retorno
imediato. Não há contexto, não há negação, não há checagem de intenção temporal.

**Impacto real.** `"a sala de reunião está quente"` → `pausar_automacao`. E isso não é só
uma etiqueta errada: `main.py:409-422` então **desativa automações Tuya de verdade** e
agenda reativação, enquanto o pedido real (esfriar) é descartado. A revenda perde as rotinas
de desligamento automático por causa de uma reclamação de calor.

**Segundo defeito, no mesmo caminho (L4b).** `main.py:414-421` itera **todas** as automações
da home e desativa **cada uma que estiver habilitada** — apesar de o log da linha 411 dizer
"regras de desligamento/timer". Se a revenda tem automação de iluminação, alarme ou
irrigação, tudo é desativado. É destrutivo além do escopo pedido (portão **D2**).

**Reestruturação.**
```python
# domain/policy/pause_rules.py
class DecisaoPausa(Enum):
    PAUSAR = auto()
    NAO_PAUSAR = auto()
    INDETERMINADO = auto()   # deixa o LLM decidir — política não chuta

def avaliar(mensagem: str) -> DecisaoPausa:
    tem_gatilho   = _casa(GATILHOS)              # reunião, fechamento de mês, não desliga
    tem_temporal  = _casa(MARCADORES_TEMPORAIS)  # até, mais tarde, hoje à noite, \d{1,2}h
    tem_termico   = _casa(PEDIDOS_TERMICOS)      # quente, calor, abafado, frio, esfria
    tem_negacao   = _casa(NEGACOES)              # não precisa, cancela, esquece

    if tem_negacao:                      return NAO_PAUSAR
    if tem_gatilho and tem_termico and not tem_temporal:
        return NAO_PAUSAR                # "a sala de reunião está quente"
    if tem_gatilho and tem_temporal:     return PAUSAR
    if tem_gatilho:                      return INDETERMINADO
    return NAO_PAUSAR
```
Três mudanças de comportamento:
1. Exigir **gatilho + marcador temporal**. Palavra solta não basta.
2. Presença de pedido térmico sem marcador temporal **vence** o gatilho.
3. `INDETERMINADO` vai para o LLM em vez de a política chutar.

E no lado da execução: filtrar as automações por padrão de nome (`desliga|off|timer|noturn|
encerr`) — portão D2 — e gravar em `logs_operacoes.detalhes` a lista exata de IDs
desativados, com horário previsto de reativação. Sem esse registro, um incidente de "as
automações sumiram" é indebugável.

**Testes.**
- Parametrizado exaustivo em `avaliar()`:
  | Mensagem | Esperado |
  | :--- | :--- |
  | `"vamos ter reunião até 20h"` | PAUSAR |
  | `"a sala de reunião está quente"` | NAO_PAUSAR ← **regressão L4** |
  | `"reunião na sala de testes"` | INDETERMINADO |
  | `"fechamento de mês hoje, ficamos até 22h"` | PAUSAR |
  | `"não desliga o ar até as 21h"` | PAUSAR |
  | `"não precisa pausar mais, cancela"` | NAO_PAUSAR |
  | `"a reunião acabou"` | NAO_PAUSAR |
  | `"tá quente na sala de reunião, esfria aí"` | NAO_PAUSAR |
  | `"reunião amanhã até 20h"` | INDETERMINADO (é regra futura, não comando) |
- Contrato: `NAO_PAUSAR` → `set_automation_status` **nunca** chamado (`respx`,
  `call_count == 0`).
- Contrato: `PAUSAR` → só automações com nome casando o padrão são desativadas; a de
  iluminação permanece habilitada.
- Auditoria: após pausar, `logs_operacoes.detalhes` contém os IDs e o horário de reativação.

---

### U-06 — `extrair_horario_termino`: regex ancorada e sem default silencioso (L5)

**Causa raiz.** `scheduler_service.py:32`:
```python
re.search(r'(\d{1,2})(?:[:h](\d{2}))?\s*(?:h|horas)?', mensagem.lower())
```
Três defeitos independentes:
1. **Sem âncora** — não exige "até"/"às". Casa com qualquer número da frase.
2. **Sufixo opcional** — `(?:h|horas)?` é opcional, então um número nu qualifica.
3. **Primeira ocorrência** — `re.search` para no primeiro match.

E um quarto, de desenho: a linha 45 **inventa** `agora + 2h` quando não encontra nada. O bot
promete reativar num horário que o usuário nunca pediu.

**Falhas concretas:**
| Entrada | Hoje | Correto |
| :--- | :--- | :--- |
| `"reunião na sala 3"` | 03:00 de amanhã | Sem horário → perguntar |
| `"reunião dia 30 até 21h"` | pega `30` → inválido → +2h | 21:00 |
| `"reunião até as 8"` | 08:00 de amanhã | 20:00 (hora comercial) |
| `"reunião de 14h até 16h"` | 14:00 | 16:00 |

**Reestruturação.** Além da regex, uma mudança de testabilidade: **injetar `agora` como
parâmetro** em vez de chamar `datetime.now()` dentro da função. Isso torna a função pura e
elimina a necessidade de `freezegun`.

```python
# domain/policy/time_parser.py
_ANCORA = r"(?:at[eé]|ate|por\s+volta\s+d[ae]s?|no\s+m[aá]ximo\s+at[eé])"
_HORA   = r"(?P<h>[01]?\d|2[0-3])(?:\s*[:h.]\s*(?P<m>[0-5]\d))?"
_SUFIXO = r"(?:\s*(?:h|hs|hrs|horas?))?"
_RE = re.compile(rf"{_ANCORA}\s*(?:as|às|a)?\s*{_HORA}{_SUFIXO}\b", re.I | re.X)

_ANTI = re.compile(r"\b(?:dia|sala|andar|piso|n[ºo°]|numero|número)\s*\d", re.I)

def extrair_horario(mensagem: str, agora: datetime) -> ResultadoHorario:
    """Retorna NAO_ENCONTRADO em vez de inventar um default."""
```
Regras adicionais:
- `re.finditer` + **último** match (em "de 14h até 16h", o relevante é o último).
- Descartar candidatos precedidos por `dia|sala|andar|piso|nº`.
- Heurística comercial: `h < 7` e sem "da manhã"/"am" → `h + 12`.
- Alvo no passado → +1 dia; mas se o atraso resultante passar de 18 h, devolver
  `AMBIGUO` em vez de agendar.
- **Nunca** default silencioso: `NAO_ENCONTRADO` → o orquestrador pergunta (portão D3).

**Testes.** Tabela parametrizada com `agora` fixo (`2026-08-13 14:00 America/Recife`):

| Entrada | Esperado |
| :--- | :--- |
| `"reunião até as 20h"` | 20:00 hoje |
| `"reunião até 21:30"` | 21:30 hoje |
| `"fechamento até 22 horas"` | 22:00 hoje |
| `"vamos até 19h30"` | 19:30 hoje |
| `"reunião até as 8"` | 20:00 hoje (comercial) |
| `"reunião até as 8 da manhã"` | 08:00 **amanhã** |
| `"reunião na sala 3"` | NAO_ENCONTRADO ← **regressão L5** |
| `"reunião dia 30 até 21h"` | 21:00 hoje ← **regressão L5** |
| `"reunião de 14h até 16h"` | 16:00 hoje ← **regressão L5** |
| `"reunião até as 25h"` | NAO_ENCONTRADO (hora inválida) |
| `"não desliga até mais tarde"` | NAO_ENCONTRADO → pergunta |
| `"reunião até 20h"` com `agora = 23:50` | AMBIGUO (atraso > 18 h) |
| `"até 00:30"` com `agora = 23:50` | 00:30 de amanhã |
| `"reunião até as 12"` | 12:00 hoje (meio-dia, não 00:00) |

Edge cases de fuso: `America/Recife` não tem horário de verão, o que simplifica — mas o teste
deve fixar o tz explicitamente para não passar por acidente na máquina do dev.
Propriedade (Hypothesis): para toda saída não-nula, `agora < resultado <= agora + 24h`.

---

### U-07 — 🔴 Isolamento multi-tenant: `home_id` deriva de `id_grupo`, nunca de string livre (L7)

**Causa raiz.** `crud/tuya.py:16-68`. `get_home_by_nome` recebe `payload.nome_revenda` —
texto livre vindo do n8n — e tenta quatro estratégias em cascata: `ILIKE` exato → qualquer
dígito com `JOIN` em cenas → `AND` de palavras ≥3 chars → **substring solta**. Em nenhum
momento o `id_grupo` autenticado entra na query.

Isso inverte a relação de confiança: o sistema autentica por `id_grupo` (chave `UNIQUE`,
indexada, confiável) e depois **descarta** essa informação para adivinhar o tenant por
semelhança de nome.

Agrava: `nome_revenda` vai cru para o `ILIKE` na linha 26, então `%` e `_` enviados no
payload viram wildcards. `nome_revenda = "%"` casa com a primeira home da tabela.

**Impacto real.** Duas revendas com nomes próximos ("Revenda 019" / "Revenda 0190", ou que
compartilhem as palavras ≥3 chars) podem resolver para a mesma `home_id`. O resultado é
**acionar o ar-condicionado do cliente errado** — exatamente a garantia que o README §1
item 2 vende como central. É o risco mais sério do projeto.

**Reestruturação.**

Passo 1 — migração:
```sql
ALTER TABLE mapa_revendas ADD COLUMN tuya_home_id VARCHAR(100);
CREATE INDEX idx_mapa_revendas_home ON mapa_revendas(tuya_home_id);
```
Passo 2 — backfill **único, revisado à mão**, em `scripts/backfill_home_ids.py`, usando a
busca difusa atual para *propor* e exigindo aprovação humana. Um relatório
`docs/backfill_home_ids.md` lista cada par (revenda → home) para conferência antes do
commit. É a única vez em que a busca difusa é aceitável, e mesmo assim com revisão.

Passo 3 — resolução única no caminho de request:
```python
# repositories/tenants.py
async def resolver_tenant(db, id_grupo: str) -> Tenant:
    row = await db.execute(text("""
        SELECT id_grupo_wpp, nome_revenda, tuya_home_id, credenciais_tuya
        FROM mapa_revendas WHERE id_grupo_wpp = :g AND ativo = TRUE
    """), {"g": id_grupo})
    if not row: raise TenantResolutionError(f"grupo não cadastrado: {id_grupo}")
    if not tenant.tuya_home_id: raise TenantResolutionError("revenda sem home_id Tuya")
    return tenant
```
Passo 4 — `payload.nome_revenda` passa a ser **exclusivamente de exibição**. O
`nome_revenda` gravado em log vem do banco, não do payload (senão o n8n pode falsear a
auditoria).

Passo 5 — `get_home_by_nome` e `get_ambientes_by_cliente(nome_revenda)` saem de
`app/crud/` e vão para `scripts/`, com `DeprecationWarning`. `get_ambientes_by_cliente`
passa a receber `home_id`.

Passo 6 — teste de arquitetura que falha o build se `scripts.backfill_home_ids` for
importado de dentro de `app/`.

**Testes.**
- Cenário de vazamento — o teste mais importante da suíte:
  ```python
  async def test_nome_revenda_do_payload_nao_influencia_home_id(db):
      # grupo A cadastrado com home_A; payload mente dizendo ser a revenda B
      resp = await post_agent(id_grupo=GRUPO_A, nome_revenda="Revenda B", mensagem="tá quente")
      assert cenas_executadas_em() == [HOME_A]   # jamais HOME_B
  ```
- Nomes ambíguos: seed com "Revenda 019" e "Revenda 0190" → cada grupo resolve para a sua
  home, determinístico, em 100 execuções.
- Wildcard: `nome_revenda = "%"`, `"_"`, `"[SOF]%"` → não altera a resolução.
- `tuya_home_id` NULL → `TenantResolutionError`, resposta honesta, **zero** chamadas Tuya.
- Grupo inexistente → mesma coisa.
- Grupo com `ativo = FALSE` → recusa (hoje `buscar_credenciais_revenda` filtra `ativo`, mas
  `get_home_by_nome` **não** — uma revenda desativada ainda consegue comandar).
- Escalonamento não atravessa grupos: chamados do grupo A não contam para o grupo B.

---

### U-08 — Boot seguro: falhar se as credenciais estiverem no default (S4) e trocar a senha do Postgres (S2)

**Causa raiz (S4).** `config.py:64` define `api_key` com default
`"dev-api-key-insegura"` — valor público, está no repositório e no README. Se o `.env` não
for lido (path errado no container, typo em `env_file`, volume não montado), a aplicação
**sobe normalmente** com uma chave que qualquer um conhece, e passa a aceitar comandos IoT.
Falha silenciosa com consequência física.

Mesma classe de problema em `secret_key` (`config.py:59`).

**Causa raiz (S2).** `POSTGRES_PASSWORD` no `.env` tem **4 caracteres**, e a mesma senha
compõe a `DATABASE_URL`. Mitigado por `docker-compose.yml:18` expor o Postgres só em
`127.0.0.1`, mas isso é uma camada, não a correção.

**Reestruturação.**
```python
DEFAULTS_INSEGUROS = {"dev-api-key-insegura", "chave-insegura-apenas-para-desenvolvimento"}

@model_validator(mode="after")
def _proibir_defaults_em_producao(self):
    if self.app_env != "production":
        return self
    problemas = []
    if self.api_key in DEFAULTS_INSEGUROS or len(self.api_key) < 32:
        problemas.append("API_KEY")
    if self.secret_key in DEFAULTS_INSEGUROS or len(self.secret_key) < 32:
        problemas.append("SECRET_KEY")
    if not self.gemini_api_key:
        problemas.append("GEMINI_API_KEY")   # sem ela, o fallback é o único caminho
    if problemas:
        raise ConfigError(f"produção com credenciais inseguras/ausentes: {problemas}")
    return self
```
Fail fast é deliberado: um container que não sobe é um incidente visível em 30 segundos; um
container aberto ao mundo pode passar meses sem ser notado.

Para S2: gerar senha de 32+ chars, atualizar `.env` e `DATABASE_URL`, rotacionar no
Postgres (`ALTER USER`), documentar em `.env.example` com aviso.

**Testes.**
- `Settings(app_env="production", api_key="dev-api-key-insegura")` → `ConfigError`.
- `app_env="development"` com os mesmos defaults → sobe (não travar o dev local).
- `api_key` com 31 chars em produção → `ConfigError`; com 32 → ok.
- Produção sem `GEMINI_API_KEY` → `ConfigError`.
- Integração: `docker compose up` sem `.env` → container termina com código ≠ 0 e a
  mensagem nomeia a variável faltante.

---

### U-09 — Corrigir B1 (NameError), B2 (auto-migração) e B6 (lifespan duplicado)

Três bugs de corretude, agrupados porque vivem no mesmo arquivo e desaparecem juntos na
extração do orquestrador.

#### B1 — `credenciais` possivelmente não ligada (`main.py:453`)

**Causa raiz.** `credenciais` só é atribuída dentro de `if settings.gemini_api_key:`
(`main.py:314`) ou no `except` correspondente (`main.py:351`). Sem chave Gemini, o fluxo cai
no fallback de keywords (`main.py:354`), identifica a ação, e chega em
`buscar_link_ifttt(credenciais, ...)` com a variável nunca criada → `NameError` → capturado
pelo `except` global (`main.py:522`) → **HTTP 500**.

Ou seja: o modo anunciado como "fallback resiliente" está 100% quebrado. Só não apareceu
porque a chave Gemini está presente em todos os ambientes reais.

A causa mais profunda é o escopo de função de 280 linhas, onde o fluxo de dados não é
óbvio. A extração do orquestrador (B-01) elimina a classe inteira desse bug, porque cada
passo passa a receber e devolver valores explícitos em vez de mutar locais compartilhados.

**Correção imediata:** inicializar `credenciais = None` antes da linha 305 e habilitar
`ruff` com a regra `F821`/`possibly-unbound` no CI.

**Testes.** Teste de contrato com `GEMINI_API_KEY = ""`: `POST /agent {"mensagem": "tá
quente"}` → **200** com ação do fallback (hoje: 500). Executar essa asserção contra todos os
ramos de saída (`acao` presente, `acao` ausente, dispositivo offline).

#### B2 — `AsyncSessionLocal` não existe (`main.py:219`)

**Causa raiz.** `from app.database import AsyncSessionLocal` — o símbolo real é
`async_session_maker` (`database.py:17`). Provável renomeação sem atualizar o chamador. O
`ImportError` é engolido pelo `except Exception` da linha 224 (achado U-01) e reduzido a um
`warning`.

Efeito em cascata: a tabela `chat_historico_recente` nunca é criada pela auto-migração; e
como `chat_history.py` também engole tudo, a memória de curto prazo falha em silêncio, o
LLM nunca vê histórico, e o escalonamento degrada para "sempre 1º chamado". Três achados
(B2 → U-01 → L3) são o mesmo defeito visto de ângulos diferentes.

**Por que a suíte não pegou:** `tests/test_api.py:5` instancia `TestClient(app)` solto, e
`TestClient` só dispara o ciclo de vida quando usado como context manager. O evento de
startup nunca roda em teste.

**Correção.** Duas fases:
- Curto prazo: corrigir o nome e mover para o `lifespan`.
- Etapa 3 (B-04): eliminar a auto-migração. Schema é responsabilidade do Alembic, não da
  aplicação. `CREATE TABLE IF NOT EXISTS` no boot esconde deriva de schema em vez de
  denunciá-la.

**Testes.**
- `with TestClient(app) as c:` → asseriar que o startup completou sem `warning` de
  degradação. Este é o teste que faltava.
- Unitário: `import app.database; assert hasattr(..., "async_session_maker")` — trivial, mas
  pega renomeações futuras.
- Integração: banco sem a tabela → readiness probe reprova (em vez de "ok" com memória
  morta).

#### B6 — `lifespan` e `@app.on_event` coexistem

`main.py:166` registra `lifespan=lifespan` e `main.py:213` usa
`@app.on_event("startup")`. Depreciado, e pior: divide a inicialização em dois lugares, o
que foi como B2 passou desapercebido. Consolidar tudo no `lifespan` — que é também onde
entram o `httpx.AsyncClient` compartilhado (P2) e o worker do scheduler (C-01).

#### Bônus do mesmo arquivo — B3 (rate limit)

`main.py:175` faz `return HTTPException(...)`. Um handler do Starlette precisa **retornar
uma `Response`**. Ao estourar o limite, em vez de 429 o cliente recebe erro de servidor.
Correção: `JSONResponse(status_code=429, ...)`. Teste: `limiter` configurado com
`2/minute`, três chamadas → a terceira devolve **429** com corpo JSON válido. (Hoje o limite
de 600/min torna isso inalcançável em teste; o teste sobrescreve o limite via fixture.)

---

### Critério de saída da Etapa 1

- Todos os itens U-01…U-09 com teste vermelho→verde documentado.
- Chave IFTTT rotacionada e `gitleaks` no CI.
- Imagem Docker sem `.env` (verificado por teste de build).
- Nenhum `except Exception` sem justificativa explícita.
- `pytest` verde, offline, <10 s.
- O `xfail(strict=True)` de 0.5 convertido em teste normal.

---

## ETAPA 2

### Bloco 2 — Regressão semântica e 13 itens de curto prazo

### 2.1 — A suíte de regressão semântica

**O problema a resolver.** O histórico do Git tem 12 commits de "Correção da llm" /
"fix: ..." sobre semântica: `e9a7a19` (inversão frio/quente), `563b6f5`, `72b9e0b`,
`7e95e89` (reunião/pausa, três tentativas), `0d4997d`, `77f20cd`, `8ec4675` (T-Medium no 1º
chamado, três tentativas). O padrão é inequívoco: cada ajuste de prompt corrige um caso e
tem chance de quebrar outro, e não há como saber.

**Por que não basta "escrever testes para o LLM".** Um LLM não é determinístico nem com
`temperature=0.0`; depende de rede e quota; muda de comportamento quando o provedor atualiza
o modelo (e `gemini_model` é `"gemini-flash-latest"` — um alias **móvel**, o que significa
que o comportamento pode mudar sem nenhum commit nosso). Um teste que chama a API real em
cada `git push` é lento, caro e instável — e seria desligado em duas semanas.

**A arquitetura de três camadas.**

#### Camada 1 — Testes de política (determinísticos, ~200 casos, <1 s)
Testam as funções puras extraídas do prompt na Etapa 1: `time_parser`, `pause_rules`,
`escalation`, `keyword_fallback`. **É aqui que vive a garantia de "nunca mais".** Rodam em
todo commit. Zero rede, zero banco, zero custo.

Isso só é possível porque a Etapa 1 tirou a regra do prompt. Enquanto a regra vive numa
string de 90 linhas, nenhuma garantia é possível — é o argumento central do plano.

#### Camada 2 — Testes de contrato com LLM falso (~60 casos, <5 s)
`FakeLLMClient` devolve respostas roteirizadas. Testam o **orquestrador**: dado que o LLM
retornou X e o banco está no estado Y, qual cena disparou, qual resposta foi ao usuário,
qual linha entrou em `logs_operacoes`. Cobrem tudo que não é o LLM: offline, tenant
irresolvido, RAG caído, memória morta, falha de persistência do agendamento, JSON malformado
do modelo.

#### Camada 3 — Avaliação do LLM real (opt-in, ~60 casos × 3 execuções)
`tests/llm_eval/`, marcada `@pytest.mark.llm_eval`, **desativada por padrão** (roda com
`RUN_LLM_EVAL=1`). Dataset em `tests/llm_eval/casos.yaml`:

```yaml
- id: calor_generico_primeiro_chamado
  critico: false
  mensagem: "loja quente"
  contexto: { historico: [], ambientes: [], chamados_recentes: 0 }
  espera: { intencao: ligar_temperatura_media, acao: medio }

- id: reuniao_com_reclamacao_de_calor
  critico: true          # falha aqui bloqueia a promoção do prompt
  mensagem: "a sala de reunião está quente"
  espera_nao: { intencao: pausar_automacao }

- id: ambiente_ambiguo_multiplos
  critico: true
  mensagem: "tá quente"
  contexto: { ambientes: [terreo, primeiro_andar] }
  espera: { acao: null }   # deve PERGUNTAR, não agir
```

Regras do harness:
- Cada caso roda **3×** (temperature 0 não garante determinismo).
- **Casos `critico: true`: tolerância zero.** São os de impacto físico ou de segurança —
  nunca pausar automações por reclamação de calor, nunca agir sem saber o ambiente, nunca
  comandar tenant não resolvido.
- Casos normais: acurácia agregada **≥ 95%**.
- Saída: `docs/eval/prompt_v1_YYYYMMDD.md` com matriz de confusão por intenção.
- **Portão de promoção:** editar o prompt significa criar `prompts/sistema_v2.md` e provar
  que ele iguala ou supera `v1` no dataset antes de virar default. Fim do ajuste no escuro.
- Custo: ~60 casos × 3 × ~2 k tokens ≈ centavos por execução. Nightly + antes de cada
  alteração de prompt.

**Alimentação do dataset.** Modo de captura que grava `(mensagem, intenção decidida, ação
executada, feedback)` anonimizado a partir de `logs_operacoes` — que já tem tudo. Toda
divergência relatada por revenda entra como caso novo. O dataset cresce com a operação, não
com imaginação. Anonimização é requisito (achado S6).

**Alerta sobre `gemini-flash-latest`.** Alias móvel: o Google pode trocar o modelo sob os
pés. Recomendo **fixar uma versão explícita** em produção e usar o alias apenas em avaliação
— assim o harness detecta a mudança antes dos clientes.

### 2.2 — Cobertura das ramificações de decisão

Inventário das ramificações e o que ainda não tem teste:

| Ramificação | Origem | Camada |
| :--- | :--- | :--- |
| Pausa: PAUSAR / NAO_PAUSAR / INDETERMINADO | U-05 | 1 |
| Escalonamento: nível 1 / 2 / 3 | C-03 | 1 |
| Horário: encontrado / ausente / ambíguo / inválido | U-06 | 1 |
| Ambiente: único / múltiplo especificado / múltiplo ambíguo | prompt §Múltiplos Ambientes | 1 + 3 |
| Regra futura vs comando imediato | prompt §Execução Imediata | 3 |
| `salvar_memoria`: true / false | prompt §Memória Orgânica | 3 |
| Origem da decisão: LLM ok / LLM falhou / sem chave | U-04, B1 | 2 |
| Tenant: resolvido / sem home_id / inativo / inexistente | U-07 | 2 |
| Dispositivos: online / todos offline / consulta falhou | `tuya_service.py:245` | 2 |
| Cena: encontrada / não encontrada / Tuya recusou | `crud/tuya.py:105` | 2 |
| Agendamento: persistiu / falhou | C-01 | 2 |
| Degradação: RAG / memória / log de auditoria | U-01 | 2 |

**Edge cases de sistema que nenhum teste cobre hoje:**

1. **Concorrência no escalonamento.** Duas mensagens do mesmo grupo em paralelo leem a mesma
   contagem e ambas decidem "nível 1". Teste com `asyncio.gather`. Correção: advisory lock
   do Postgres por grupo (`pg_advisory_xact_lock(hashtext(id_grupo))`). **Bug real, ainda
   não catalogado.**
2. **Corrida no token da Tuya.** `get_access_token` (`tuya_service.py:60-102`) não tem lock:
   N requisições concorrentes com token expirado disparam N renovações, e a Tuya tem quota.
   Correção: `asyncio.Lock` + dupla checagem. **Também novo.**
3. **Fronteira da janela de 15 min:** 14 min 59 s conta, 15 min 01 s não.
4. **Truncamento do LLM.** `max_output_tokens=1000` (`llm_service.py:190`) com
   `response_mime_type="application/json"`: se truncar, o JSON fica inválido e
   `json.loads` falha (`llm_service.py:222`) → cai na mensagem genérica de "instabilidade",
   sem tentar o fallback de keywords. Recomendação: usar `response_schema` (saída
   estruturada) em vez de só `response_mime_type`, e cair no fallback em vez de dar mensagem
   morta.
5. **LLM devolve ação fora do enum** (`"gelar_tudo"`) → validar contra `AcaoIoT` e recusar,
   nunca repassar para a Tuya.
6. Payload de 4096 chars (limite) e 4097 (422). Só emoji. Só espaços.
7. `mensagem` com `%`, `_`, `'`, `--` → confirmar parametrização e escape de wildcards.
8. Reinício do processo com agendamento pendente (C-01).
9. Duas pausas para o mesmo grupo → dedupe e união dos IDs de automação.
10. Requisição às 23:50 com "até 00:30" → cruza a meia-noite.

### 2.3 — Os 13 itens de curto prazo

| ID | Item | Ref. | Causa raiz resumida | Correção | Testes |
| :---: | :--- | :---: | :--- | :--- | :--- |
| C-01 | Persistir agendamentos | L8 | `asyncio.create_task` + dict em memória (`scheduler_service.py:22,111`). Restart = automações desativadas para sempre e T-OFF nunca dispara: o ar passa a noite ligado | Tabela `agendamentos` (`status`, `executar_em`, `home_id`, `automacao_ids`, `tentativas`) + worker no `lifespan` varrendo a cada 60 s, idempotente (`UPDATE ... WHERE status='pendente' RETURNING`). Se a persistência falhar, **`SchedulePersistError` e o bot não promete** | Grava → "restart" (novo worker, mesma tabela) → reativação ocorre. Dois workers concorrentes → executa 1×. Falha ao gravar → resposta não promete reativação |
| C-02 | Contar chamados via SQL | L3 | Janela de 6 mensagens com usuário+Sofia = ~3 turnos; e o LLM conta lendo texto livre | `SELECT COUNT(*) FROM logs_operacoes WHERE id_grupo=:g AND intencao LIKE 'ligar_%' AND timestamp >= NOW() - INTERVAL '15 min'` + advisory lock; nível vai **pronto** ao prompt | Fronteira 14:59/15:01. Isolamento entre grupos. Falha da query → nível 1 (conservador) |
| C-03 | Resolver T-Low vs T-Freezer | L2 | 2º e 3º chamado retornam ambos `freezer`; o texto promete "T-Low" e "T-Freezer" | Portão **D1**. Se cenas distintas → `AcaoIoT.LOW` + sinônimos + prompt. Se não → 2 níveis e corrigir o texto | Nível 2 → cena de low; nível 3 → cena de freezer; asserir `scene_id` **diferente**. Texto coerente com a ação |
| C-04 | `embed_content` fora do event loop | P1 | `genai.embed_content` é síncrono dentro de `async def` (`rag_service.py:34,86`): bloqueia o loop e congela a API sob concorrência | `await asyncio.to_thread(...)` atrás de uma porta `EmbeddingClient` | 10 requisições concorrentes: p95 não cresce linearmente. Fake mede que não houve bloqueio |
| C-05 | Boot seguro | S4 | (feito em U-08) | — | — |
| C-06 | `registrar_log` com sessão própria | S7 | Chamado no `except` global (`main.py:526`) reusando sessão possivelmente abortada; `logs.py:51` não faz rollback. Perde-se o log dos piores incidentes — contradizendo o README:158 | Sessão nova + rollback + retry. Falha → `AuditLogWriteFailed` com alerta sev-2 | Sessão em estado abortado → log ainda grava. Banco fora → alerta emitido, requisição não quebra |
| C-07 | Remover CORS | S5 | `allow_origins=["*"]` (`main.py:184-190`) num serviço server-to-server (n8n). Não há navegador no fluxo | Remover o middleware | Requisição com `Origin` → sem `Access-Control-Allow-Origin` |
| C-08 | Handler de rate limit | B3 | (feito em U-09) | — | 3 chamadas com limite 2/min → 429 JSON |
| C-09 | `.env.example` e `seed_teste.sql` | B5 | README:243,316 pedem `.env.example`; README:81,250,268 usam `seed_teste.sql`. Nenhum dos dois existe: onboarding falha no passo 4 | Criar ambos | Teste de docs: todo caminho de arquivo citado no README existe |
| C-10 | `httpx.AsyncClient` compartilhado | P2 | Novo client por requisição (`tuya_service.py:84,129`): zero reuso de conexão/TLS | Client único no `lifespan`, injetado | `respx` conta conexões; timeouts explícitos configurados |
| C-11 | Lock no token da Tuya | novo | `get_access_token` sem lock: N requisições concorrentes = N renovações e risco de quota | `asyncio.Lock` + dupla checagem | 20 chamadas concorrentes com token expirado → exatamente 1 requisição de token |
| C-12 | Limiar na busca vetorial | P4 | Sem limiar (`rag_service.py:54`): sempre injeta 3 documentos, relevantes ou não. Ruído no prompt e custo de token | `WHERE embedding <=> :q < :limiar` (calibrar ~0.35 com dados reais) | Consulta sem vizinho relevante → contexto vazio; com vizinho → retorna. Documentar a calibração |
| C-13 | `"%t%"` em `AMBIENTE_SYNONYMS` | L6 | `crud/tuya.py:98`: `LIKE '%t%'` casa com quase todo nome de cena em português → pode escolher a cena do andar errado | Remover; usar mapa explícito ambiente→cena, validado contra o banco | Ambiente "terreo" não casa cena de "primeiro andar". Ambiente desconhecido → erro, não chute |

### Critério de saída da Etapa 2

- Camada 1 com ≥95% de cobertura em `domain/policy/`.
- Camada 2 cobrindo as 12 ramificações da tabela.
- Camada 3 rodando, com scorecard versionado e o portão de promoção documentado.
- Os 13 itens fechados com teste.
- CI: camadas 1 e 2 em todo push; camada 3 nightly.

---

## ETAPA 3

### Bloco 3 — Backlog e refatoração

| ID | Item | Ref. | Escopo |
| :---: | :--- | :---: | :--- |
| B-01 | Extrair `orchestrator.py` | Q5 | `process_agent_command` tem ~280 linhas misturando HTTP, orquestração, negócio, log e persistência. Vira: rota fina → `AgentOrchestrator.processar(comando) -> Decisao`. Elimina a classe de bug do B1 por construção. Consolidar imports (`main.py:90-99,310,426,579`) no topo |
| B-02 | Prompt versionado | Q6 | `prompts/sistema_v1.md`, deduplicando as regras sobrepostas ("PRIORIDADE MÁXIMA" ≡ "SOBREPOSIÇÃO ABSOLUTA"; escalonamento repetido em 99-105 e 120-124). Encolhe de ~90 para ~25 linhas porque as regras duras foram para código na Etapa 1. Fixar versão explícita do modelo em produção |
| B-03 | Injeção de `Settings` | Q5 / 0.3 | Parar de chamar `get_settings()` em tempo de import. Remove o singleton `lru_cache` e permite testar múltiplas configurações no mesmo processo |
| B-04 | Alembic de verdade | I2 | `alembic init`, revisão baseline do schema atual, migrações para `tuya_home_id` (U-07), `agendamentos` (C-01), `chat_historico_recente`. **Remover** o `CREATE TABLE IF NOT EXISTS` da aplicação — schema não é responsabilidade do app |
| B-05 | Logs estruturados | Q e §3 | JSON em produção, legível em dev. `correlation_id` (de `X-Request-Id` ou gerado), `id_grupo` com hash, mensagem truncada — formalizar o instinto que já existe em `main.py:281-288`. Emoji só no formatter de dev (quebra ingestores) |
| B-06 | Sentry + métricas | Q4 | `metrics.degraded(capability)` alimentando alerta. Sem isso, a política do U-01 não tem consumidor |
| B-07 | Retenção de dados | S6 | `limpar_historico_antigo` (`chat_history.py:105`) existe e **nunca é chamada** — código morto. Ligar ao worker (histórico 24 h) + purga/particionamento de `logs_operacoes` (90 dias). Revisão LGPD do armazenamento de mensagens de WhatsApp |
| B-08 | Hardening de infra | I1,I3,I5,I6 | Remover `version:` obsoleto; `HEALTHCHECK` no Dockerfile e no serviço `api`; `depends_on: condition` no Caddy; multi-stage build (hoje `build-essential` + `libpq-dev` ficam na imagem final); headers de segurança e `log` no Caddyfile |
| B-09 | Readiness vs liveness | I3 | `/health` (`main.py:232`) devolve `ok` sem checar banco. Separar: `/health` (processo vivo) e `/ready` (banco + Tuya acessíveis). É o que teria denunciado o B2 |
| B-10 | Limpar código morto | Q8 | `main.py:515` (`'ambiente' in locals()` — sempre definida em 302); TODOs de "Fase 2" já feitos (`main.py:140-141`); `database.py:35` `get_sync_engine` sem uso; `extracao_tuya_completa.md` duplicado (60 KB na raiz e em `utils/`); `app/scripts/` misturado ao pacote da aplicação |
| B-11 | Documentação | Q7 | Ver detalhe abaixo |
| B-12 | CI no GitHub Actions | Q1 | Só faz sentido depois de versionar `tests/`. Jobs: `ruff` + `mypy`; camadas 1 e 2; `gitleaks`; teste de build da imagem; nightly da camada 3 |
| B-13 | Documentar restrição de worker único | I4 | `Dockerfile:32` roda 1 worker, sem `--workers`. Hoje é **obrigatório** (scheduler e cache de token em memória). Depois de C-01 e C-11, multi-worker fica viável — registrar o antes/depois para ninguém "otimizar" e quebrar os agendamentos |

### B-11 em detalhe

**`CLAUDE.md` (criar).** Não existe. Conteúdo: mapa da arquitetura, como rodar os testes
(as três camadas e quando cada uma roda), **invariantes que não podem ser violadas**
(`home_id` nunca deriva de string livre; nenhum `except Exception` sem justificativa;
prompt só muda passando pelo portão de eval), convenções de commit, portões de decisão em
aberto.

**`README.md`** — corrigir as divergências catalogadas:

| Onde | Divergência |
| :--- | :--- |
| `main.py:238` vs `:137` | `/health` diz `mode: "ifttt_bridge"`; o log de startup diz "Tuya API Direta + IFTTT Fallback" |
| `schemas/agent.py:104-108` | Descrição de `intencao` lista valores **inexistentes** (`ligar_dispositivo`, `ajustar_temperatura`, `consultar_status`) — o Swagger publica contrato errado |
| README §3 | Não documenta `ambiente`, `tuya_success`, `POST /rag/aprender`, `POST /proactive/fechamento`, nem `ligar_temperatura_media` / `pausar_automacao` |
| `main.py:83` vs `:86` | Comentário diz "60 requisições por minuto"; código usa `600/minute` |
| README §2 | Lista `cloudflared.exe`, mas `*.exe` está no `.gitignore:64` |
| README:158 | Promete log automático de todo 500 — não é garantido (C-06) |
| README:144 | Prefixo real de chave IFTTT no exemplo (U-02) |
| README §6 | Passos 4 e 6 referenciam arquivos inexistentes (C-09) |

Adicionar: **teste de documentação** que falha se um caminho citado no README não existir.

---

## Matriz de rastreabilidade

Os 34 achados da avaliação → itens deste plano. Nenhum órfão.

| Achado | Item | Etapa |
| :--- | :--- | :---: |
| B1 NameError | U-09 | 1 |
| B2 AsyncSessionLocal | U-09 | 1 |
| B3 rate limit handler | U-09 / C-08 | 1 |
| B4 venv corrompido | 0.1–0.2 | 0 |
| B5 arquivos ausentes | C-09 | 2 |
| B6 lifespan duplicado | U-09 | 1 |
| L1 fallback × escalonamento | U-04 | 1 |
| L2 T-Low ≡ T-Freezer | C-03 (portão D1) | 2 |
| L3 janela de contagem | C-02 | 2 |
| L4 falso positivo de pausa | U-05 | 1 |
| L4b desativa todas as automações | U-05 (portão D2) | 1 |
| L5 regex de horário | U-06 | 1 |
| L6 `"%t%"` | C-13 | 2 |
| **L7 cross-tenant** | **U-07** | **1** |
| L8 agendamento em memória | C-01 | 2 |
| P1 embedding bloqueante | C-04 | 2 |
| P2 client httpx por requisição | C-10 | 2 |
| P3 sessão própria do RAG | B-01 | 3 |
| P4 sem limiar vetorial | C-12 | 2 |
| P5 múltiplos commits | B-01 | 3 |
| S1 chave IFTTT no Git | U-02 | 1 |
| S2 senha de 4 chars | U-08 | 1 |
| S3 sem `.dockerignore` | U-03 | 1 |
| S4 default inseguro | U-08 | 1 |
| S5 CORS aberto | C-07 | 2 |
| S6 PII sem retenção | B-07 | 3 |
| S7 log de erro perdido | C-06 | 2 |
| Q1 testes fora do Git | 0.6 + B-12 | 0/3 |
| Q2 testes não isolados | 0.3 | 0 |
| Q3 sem cobertura crítica | 2.1–2.2 | 2 |
| Q4 excepts silenciosos | U-01 | 1 |
| Q5 `main.py` monolítico | B-01, B-03 | 3 |
| Q6 prompt remendado | B-02 | 3 |
| Q7 docs desalinhados | B-11 | 3 |
| Q8 código morto | B-10 | 3 |
| I1–I7 infra | B-08, B-13, U-03 | 1/3 |
| **Novos** — corrida no escalonamento | C-02 | 2 |
| **Novos** — corrida no token Tuya | C-11 | 2 |
| **Novos** — truncamento do LLM | 2.2 §4 | 2 |
| **Novos** — revenda inativa comanda | U-07 | 1 |
| **Novos** — `gemini-flash-latest` móvel | B-02 | 3 |

---

## Riscos do próprio plano

Honestidade sobre onde este plano pode dar errado:

| Risco | Probabilidade | Mitigação |
| :--- | :---: | :--- |
| **Backfill de `tuya_home_id` mapeia revenda errada** e institucionaliza o bug L7 | Média | Revisão humana obrigatória do relatório antes do commit; conferir contra `utils/home_ids_revendas.md` |
| Rotação da chave IFTTT derruba automações em produção | Média | Atualizar o banco na mesma janela; testar numa revenda antes de propagar |
| Encolher o prompt regride comportamento que ninguém documentou | **Alta** | É exatamente por isso que a camada 3 vem **antes** do B-02. Nunca editar o prompt sem baseline de eval |
| Alembic baseline divergir do schema real em produção | Média | `alembic check` contra dump de produção antes de aplicar |
| Etapa 1 tocar U-07 e U-05 juntos e ficar difícil de reverter | Média | Um commit por item; U-07 atrás de flag até o backfill ser validado |
| Testes de integração exigirem infra indisponível | Baixa | Postgres efêmero no CI (portão D7); camadas 1 e 2 não precisam de infra |
| `requirements.txt` com pins inexistentes travar a Etapa 0 | Média | Resolver na hora e registrar em `requirements.lock.txt`; é o primeiro sinal a observar |

### Sequenciamento e paralelismo

```
D4 (rotação IFTTT) ──────────────────────► pode começar AGORA, sem código
Etapa 0 ──► U-02,U-03,U-08 (segredos) ──┐
            U-01 (exceções) ────────────┤
            U-07 (tenant) ──────────────┼──► Etapa 2 ──► Etapa 3
            U-04,U-05,U-06 (política) ──┤
            U-09 (bugs) ────────────────┘
```
U-01 deve vir **antes** de U-04/U-05/U-06: sem a hierarquia de exceções, cada correção de
política recria um `except Exception` para "não quebrar produção". A ordem não é negociável.

**Estimativa:** Etapa 0 ~meio dia · Etapa 1 ~4-5 dias · Etapa 2 ~5-7 dias ·
Etapa 3 ~5 dias. Total ~3-4 semanas de trabalho focado, com valor entregue de forma
incremental (segredos no dia 1, isolamento de tenant na semana 1).
