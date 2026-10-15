# Changelog — Agente SOF

Formato: entradas mais recentes primeiro. Decisões que mudam **comportamento físico**
(ligar/desligar/pausar equipamento em loja real) ficam registradas aqui com data,
responsável e o trade-off aceito — não apenas no código.

---

## 2026-10-15

### Alterado — Cobertura mínima de transmissores IR: "1 só online = revenda offline"

`app/services/tuya_service.py`

`check_home_devices_online` passou a considerar a revenda **offline** sempre que houver
**no máximo 1 transmissor IR online**, qualquer que seja o total cadastrado. Antes, só o
zero absoluto (`ir_online == 0`) abortava o comando.

**Por que:** um dispositivo solitário online **não caracteriza revenda operante**. Na
prática ele costuma nem estar na loja — é cadastro residual, aparelho de bancada ou
equipamento que ficou noutro endereço. Disparar a cena nesse estado comanda algo que não
é da revenda e responde "pronto, liguei" para um salão que continua quente. Não existe
comando seguro nesse estado, então nenhum é enviado.

**Sem isenção por tamanho da Home.** A primeira versão desta entrada isentava
`ir_total == 1`, sob o argumento de que existiriam revendas legitimamente com um único
transmissor, que ficariam presas em offline permanente. O responsável corrigiu a premissa
no mesmo dia: não existe esse caso — um IR sozinho é justamente o sinal de que o
dispositivo não é da revenda. A isenção foi removida antes de qualquer deploy; o limiar
vale para toda Home com pelo menos 1 IR cadastrado.

**Trade-off aceito:** uma revenda com 2 IRs em que um esteja cronicamente offline deixa
de aceitar comandos até alguém religar o transmissor. Preferimos isso — visível, com
mensagem explícita no WhatsApp e `status_op=dispositivo_offline` no log — a climatizar
meia loja e reportar sucesso.

**Escopo:** só o caminho de **cena física**. Pausa/reativação de automação continua não
dependendo de IR online (é operação de nuvem) e não passa por esta checagem —
`tuya_dispatch_service.py` já faz essa distinção antes do bloco de verificação.

O limiar ficou nomeado e ajustável no topo de `tuya_service.py`: `IR_COBERTURA_MINIMA = 1`.
Pôr 0 restaura exatamente o comportamento anterior, útil como chave de desligamento se o
deploy revelar mais lojas afetadas do que o esperado.

O retorno ganhou a chave `cobertura_degradada: bool`, que distingue nos logs e na auditoria
"tudo offline" de "cobertura insuficiente". O painel admin não precisou mudar: já lia
`all_offline` + `ir_online/ir_total`, e agora mostra 🔴 Offline (1/4 IR) nesse caso.

Coberto por `tests/unit/test_cobertura_ir_minima.py` (12 casos), incluindo a Home de IR
único, a não-regressão do offline total e a prova de que um sensor online não mascara IRs
caídos. Verificado por mutação: revertendo o `elif` da cobertura, 7 testes ficam vermelhos.

---

## 2026-09-21

### Corrigido — C1: TimeParser ignorava o conector "ás"

`app/domain/policy/time_parser.py`

Mensagens como `"Hoje vamos ficar de plantão até ás 20hrs"` (com `á` no lugar da crase
`à`) não tinham o horário extraído. O conector aceito passou de `as|às|a` para
`[aá]s|às|[aá]`.

Impacto real: sem o horário, a pausa de automação era disparada **sem horário de
resume** — a loja ficava ligada a noite toda. Foi o incidente de 21/09.

Coberto por `tests/unit/test_time_parser.py`, verificado por mutação (revertendo o
regex, 2 testes ficam vermelhos).

### Adicionado — C2: salvaguarda de pausa sem horário

`app/main.py`, `app/services/tuya_dispatch_service.py`

Pausa/desativação de automação de OFF **sem horário de término confiável** agora é
abortada antes de qualquer chamada à Tuya, e o agente pede o horário ao usuário.
Duas camadas: no `main.py` (antes de chamar o dispatch) e no próprio
`tuya_dispatch_service.disparar_acao_fisica` (defesa em profundidade).

Removido junto: o fallback inseguro que assumia +2h quando o horário não era extraído.
Pausar sem consentimento explícito sobre o horário de retorno não é mais possível.

### Alterado (DECISÃO SUBSTITUÍDA) — C5: pausa sem escopo no caminho degradado

**Decisão anterior (C5):** no caminho degradado (Gemini fora do ar, `escopo_temporal`
nulo), uma pausa **não podia** ser bloqueada — o argumento era que bloquear faria a
automação desligar a loja no horário normal.

**Decisão nova (21/09/2026):** no degradado, pausa **sem horário** não desativa
automação nenhuma. O agente responde pedindo o horário.

**Trade-off aceito conscientemente pelo responsável:** é preferível a loja desligar no
horário normal durante uma reunião — visível na hora e recuperável com um comando — do
que ficar ligada a noite toda sem controle. O comportamento antigo (desativar às cegas)
produzia exatamente o pior caso sempre que o horário não era extraído, que foi o
incidente real de 21/09.

**Escopo da substituição:** vale só para **pausa/desativação**. Ação imediata e
reversível (resfriar/ligar) **continua sendo executada normalmente** pelo fallback de
keyword no degradado — isso é regressão travada por
`tests/test_gemini_fallback.py::test_degradado_resfriar_continua_funcionando`.

Teste substituído:
`test_pausa_sem_escopo_nao_e_bloqueada` → `test_pausa_sem_escopo_nao_desativa_no_degradado`
(`tests/test_zz_auditoria_lacuna.py`). A mensagem de entrada do teste foi mantida na
forma original de propósito; a mudança é de comportamento e está documentada, não
contornada.

### Notas de auditoria (riscos conhecidos, não corrigidos nesta entrega)

- **Negação invisível ao classificador de keywords.** `classificar_familia("não desliga
  as máquinas")` retorna `DESLIGAR` — a negação é ignorada. Hoje isso **não** chega à
  produção porque `llm_service.processar_mensagem` tem um override determinístico
  (`palavras_pausa`) que fixa `intencao="pausar_automacao"` antes, e o fallback de
  keyword só roda quando `not intencao`. É um ponto único de falha: removendo o
  override, a frase passa a executar a cena de **OFF**. Verificado por mutação e travado
  por `test_degradado_pausa_sem_horario_nao_dispara_nada_fisico`.
