# =============================================================================
# tests/test_grupo_thiago.py - Testes do Grupo de Teste (120363422455765261-group)
# =============================================================================
# Este script simula exatamente o que o n8n vai enviar para nossa API,
# usando o payload real que a Z-API entrega (extraído do pinData do n8n).
#
# COMO RODAR:
#   1. Certifique-se que a API está rodando: uvicorn app.main:app --reload
#   2. Execute: python tests/test_grupo_thiago.py
#
# NÃO precisa do pytest ainda — é um script simples para validar rapidamente.
# =============================================================================

import json
import sys
import urllib.request
import urllib.error
from typing import Any

# Configura a saída do terminal para UTF-8 (corrige erro de encoding com emojis no Windows)
sys.stdout.reconfigure(encoding='utf-8')

# Configurações
API_URL = "http://127.0.0.1:8000"
ID_GRUPO_TESTE = "120363422455765261-group"
NOME_REVENDA_TESTE = "Grupo Thiago (Teste)"


def chamar_api(mensagem: str) -> dict[str, Any]:
    """
    Faz um POST para /agent simulando o que o n8n enviaria.

    Args:
        mensagem: Texto da mensagem do WhatsApp.

    Returns:
        Dicionário com a resposta da API.
    """
    payload = {
        "mensagem": mensagem,
        "id_grupo": ID_GRUPO_TESTE,
        "nome_revenda": NOME_REVENDA_TESTE,
    }
    dados = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/agent",
        data=dados,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def imprimir_resultado(mensagem: str, resposta: dict[str, Any]) -> None:
    """Formata e imprime o resultado de forma legível."""
    acao = resposta.get("ifttt_action")
    emoji = {"freezer": "❄️ ", "esquentar": "🔆", "off": "❌", None: "💬"}
    print(f"\n{'─' * 55}")
    print(f"  📩 Mensagem   : \"{mensagem}\"")
    print(f"  🎯 Intenção   : {resposta.get('intencao')}")
    print(f"  {emoji.get(acao, '?')} IFTTT Action : {acao or 'Nenhuma (só conversa)'}")
    print(f"  📱 Resp. WPP  : {resposta.get('mensagem_wpp', '')[:60]}...")
    print(f"{'─' * 55}")


# =============================================================================
# Casos de Teste — baseados nos comandos reais do grupo
# =============================================================================
CASOS_DE_TESTE = [
    # --- Deve acionar FREEZER (esfriar) ---
    ("tá muito quente aqui",           "freezer"),
    ("opção 1",                        "freezer"),
    ("🔥",                             "freezer"),
    ("calor demais",                   "freezer"),
    ("esfriar por favor",              "freezer"),

    # --- Deve acionar ESQUENTAR (aquecer) ---
    ("tá muito frio aqui",             "esquentar"),
    ("opção 2",                        "esquentar"),
    ("🥶",                             "esquentar"),
    ("muito frio",                     "esquentar"),

    # --- Deve acionar OFF (desligar) ---
    ("opção 3",                        "off"),
    ("❌",                             "off"),
    ("desligar maquinas",              "off"),
    ("podem desligar todas",           "off"),

    # --- Deve acionar LIGAR (ligar) ---
    ("ligar",                          "ligar"),
    ("ligar arcondicionado",           "ligar"),
    ("ligar maquina",                  "ligar"),

    # --- NÃO deve acionar nada (conversa) ---
    ("boa tarde",                      None),
    ("obrigado",                       None),
    ("tudo bem?",                      None),
    ("Joia, já foi ajustado ;)",       None),  # Mensagem real do pinData do n8n
]



def main() -> None:
    print("\n" + "═" * 55)
    print("  🧪 TESTE DA API — Grupo Thiago (120363422455765261)")
    print("═" * 55)

    # Verifica se a API está no ar
    try:
        req = urllib.request.urlopen(f"{API_URL}/health")
        health = json.loads(req.read().decode("utf-8"))
        print(f"\n  ✅ API no ar | v{health.get('version')} | {health.get('mode')}")
    except urllib.error.URLError:
        print(f"\n  ❌ API não está respondendo em {API_URL}")
        print("     Execute: uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    print(f"\n  🔍 Rodando {len(CASOS_DE_TESTE)} casos de teste...\n")

    erros = 0
    for mensagem, acao_esperada in CASOS_DE_TESTE:
        try:
            resposta = chamar_api(mensagem)
            acao_recebida = resposta.get("ifttt_action")

            imprimir_resultado(mensagem, resposta)

            # Verifica se o resultado bate com o esperado
            if acao_recebida == acao_esperada:
                print(f"  ✅ PASSOU — ação: {acao_recebida}")
            else:
                print(f"  ❌ FALHOU — esperado: {acao_esperada}, recebido: {acao_recebida}")
                erros += 1

        except Exception as e:
            print(f"\n  ❌ ERRO na mensagem '{mensagem}': {e}")
            erros += 1

    # Resultado final
    total = len(CASOS_DE_TESTE)
    passou = total - erros
    print(f"\n{'═' * 55}")
    print(f"  📊 Resultado: {passou}/{total} testes passaram")
    if erros == 0:
        print("  🎉 Tudo certo! API pronta para integração com o n8n.")
    else:
        print(f"  ⚠️  {erros} teste(s) falharam. Verifique a lógica de palavras-chave.")
    print("═" * 55 + "\n")
    sys.exit(0 if erros == 0 else 1)


if __name__ == "__main__":
    main()
