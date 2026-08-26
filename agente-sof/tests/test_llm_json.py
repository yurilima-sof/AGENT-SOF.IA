import pytest

from app.services.llm_service import _parse_and_repair_json


def test_parse_and_repair_json_valid():
    """JSON bem formado deve ser interpretado direto, sem nenhum reparo."""
    bruto = (
        '{"intencao": "ligar_temperatura_media", "ifttt_action": "medio", '
        '"ambiente": null, "mensagem_wpp": "Pronto!", "salvar_memoria": false}'
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado == {
        "intencao": "ligar_temperatura_media",
        "ifttt_action": "medio",
        "ambiente": None,
        "mensagem_wpp": "Pronto!",
        "salvar_memoria": False,
    }


def test_parse_and_repair_json_markdown():
    """JSON envolto em cerca de código markdown (```json ... ```) deve ter a cerca removida."""
    bruto = (
        "```json\n"
        '{"intencao": "sem_acao", "ifttt_action": null, "ambiente": null, '
        '"mensagem_wpp": "Oi! Como posso ajudar?", "salvar_memoria": false}\n'
        "```"
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado["intencao"] == "sem_acao"
    assert resultado["mensagem_wpp"] == "Oi! Como posso ajudar?"


def test_parse_and_repair_json_unescaped_quotes():
    """Aspas soltas dentro de um valor de string (não escapadas pelo Gemini) devem ser reparadas."""
    bruto = (
        '{"intencao": "sem_acao", "ifttt_action": null, "ambiente": null, '
        '"mensagem_wpp": "O cliente disse "tá quente" ontem", "salvar_memoria": true}'
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado["intencao"] == "sem_acao"
    assert "quente" in resultado["mensagem_wpp"]
    assert resultado["salvar_memoria"] is True


def test_parse_and_repair_json_raw_newlines():
    """Quebras de linha literais dentro de um valor de string devem virar '\\n' escapado."""
    bruto = (
        '{"intencao": "sem_acao", "ifttt_action": null, "ambiente": null, '
        '"mensagem_wpp": "Primeira linha.\nSegunda linha.", "salvar_memoria": false}'
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado["mensagem_wpp"] == "Primeira linha.\nSegunda linha."


def test_parse_and_repair_json_truncated():
    """
    JSON cortado no meio de uma string (reproduz o padrão real observado em produção:
    resposta do Gemini truncada por max_output_tokens, gerando 'Unterminated string').
    """
    bruto = (
        '{"intencao": "ligar_dispositivos", "ifttt_action": "ligar", "ambiente": null, '
        '"mensagem_wpp": "Prontinho, ativando as automaçõ'
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado["intencao"] == "ligar_dispositivos"
    assert resultado["ifttt_action"] == "ligar"
    assert resultado["mensagem_wpp"].startswith("Prontinho")


def test_parse_and_repair_json_truncated_apos_virgula():
    """
    Corte logo após uma vírgula (sem nenhuma string aberta) — variação real observada:
    fechar chaves sozinho não basta, é preciso remover a vírgula pendurada no final.
    """
    bruto = (
        '{\n  "intencao": "ligar_dispositivos",\n  "ifttt_action": "ligar",\n  "ambiente": null,'
    )
    resultado = _parse_and_repair_json(bruto)
    assert resultado["intencao"] == "ligar_dispositivos"
    assert resultado["ifttt_action"] == "ligar"
    assert resultado["ambiente"] is None


def test_parse_and_repair_json_irrecuperavel_levanta_erro():
    """Texto que não é (e não pode virar) JSON válido deve propagar JSONDecodeError."""
    import json

    with pytest.raises(json.JSONDecodeError):
        _parse_and_repair_json("isso não é json de jeito nenhum }{[")
