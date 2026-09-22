"""I4.1 - Filtro de auto-ingestao: broadcast da propria SOF nao vira memoria RAG.

O payload do /agent nao tem campo de remetente (schemas/agent.py so tem mensagem,
id_grupo, nome_revenda), entao a API nao consegue distinguir estruturalmente um
broadcast da SOF de uma mensagem de cliente. Ate o n8n passar `from_me`, o filtro
e por conteudo — e o risco dele e o FALSO POSITIVO: barrar resposta legitima de
revenda. Os testes de "deve ingerir" abaixo existem para travar isso.
"""

from app.domain.policy.broadcast_filter import deve_ingerir

# --- NAO deve ingerir: broadcast da propria SOF ---

def test_broadcast_sof_nao_e_ingerido():
    msg = (
        "Bom dia! Para organizarmos o atendimento do fim de semana, "
        "Data para o evento : Ex: 19/09/2026 "
        "Ficamos no aguardo. ~Equipe SOF"
    )
    assert deve_ingerir(msg) is False


def test_broadcast_reconhecido_so_pela_assinatura():
    assert deve_ingerir("Comunicado importante para todas as lojas. ~Equipe SOF") is False


def test_broadcast_assinatura_com_espaco_e_caixa_diferente():
    assert deve_ingerir("Segue o comunicado. ~ EQUIPE SOF") is False


def test_broadcast_template_nao_preenchido():
    """O literal 'Ex:' do template denuncia que ninguem preencheu — e a SOF falando."""
    assert deve_ingerir("Data para o evento : Ex: 19/09/2026") is False


def test_broadcast_aguardo_mais_data_do_evento():
    msg = "Precisamos da confirmacao. Data para o evento, por favor. Ficamos no aguardo."
    assert deve_ingerir(msg) is False


# --- DEVE ingerir: mensagem de cliente (protecao contra falso positivo) ---

def test_mensagem_cliente_com_data_e_ingerida():
    assert deve_ingerir("dia 19 vamos estender até as 18h") is True


def test_mensagem_comum_e_ingerida():
    assert deve_ingerir("sala quente, favor resfriar") is True


def test_cliente_respondendo_com_data_do_evento_e_ingerido():
    """Responde ao broadcast citando o termo, mas COM a data real: e cliente."""
    assert deve_ingerir("a data para o evento é 19/09, vamos até as 20h") is True


def test_cliente_mencionando_aguardo_e_ingerido():
    """'Ficamos no aguardo' sozinho nao basta — so conta junto do template."""
    assert deve_ingerir("ficamos no aguardo do tecnico entao") is True


def test_regra_operacional_legitima_e_ingerida():
    assert deve_ingerir("Todos os dias as 14:15 queremos a loja gelada") is True


# --- bordas ---

def test_mensagem_vazia_nao_e_ingerida():
    assert deve_ingerir("") is False
    assert deve_ingerir(None) is False
