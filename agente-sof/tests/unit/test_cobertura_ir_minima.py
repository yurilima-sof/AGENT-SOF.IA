"""
Cobertura mínima de transmissores IR — "1 só online = revenda offline".

Regra (decidida em 15/10/2026, ver CHANGELOG):
uma Home com no máximo UM transmissor IR online é tratada como offline — a cena
é abortada igual ao offline total.

Vale SEM exceção por tamanho da Home, inclusive quando só há 1 IR cadastrado:
um dispositivo solitário online não caracteriza revenda operante, porque na
prática ele costuma nem estar na loja (cadastro residual, aparelho de bancada).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.tuya_service import tuya_service


def _ir(nome: str, online: bool) -> dict:
    """Device que o detector classifica como transmissor IR (categoria 'wnykq')."""
    return {"id": nome, "name": nome, "category": "wnykq", "online": online}


def _sensor(nome: str, online: bool) -> dict:
    """Device que NÃO é IR — não deve contar para o limiar de cobertura."""
    return {"id": nome, "name": nome, "category": "cz", "online": online}


async def _checar(devices: list) -> dict:
    with patch(
        "app.services.tuya_service.tuya_service.get_devices_by_home",
        new_callable=AsyncMock,
        return_value=devices,
    ):
        return await tuya_service.check_home_devices_online("home-teste")


# ---------------------------------------------------------------------------
# O caso novo: cobertura degradada vira offline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ir_total", [1, 2, 3, 4, 8])
async def test_um_unico_ir_online_e_tratado_como_offline(ir_total):
    devices = [_ir("IR-1", True)] + [_ir(f"IR-{i}", False) for i in range(2, ir_total + 1)]

    resultado = await _checar(devices)

    assert resultado["ir_online"] == 1
    assert resultado["ir_total"] == ir_total
    assert resultado["all_offline"] is True, (
        f"{ir_total} IRs cadastrados e só 1 online deveria abortar o comando"
    )
    assert resultado["cobertura_degradada"] is True


async def test_sensor_online_nao_mascara_cobertura_ir_degradada():
    """Devices não-IR online não podem salvar uma Home cujos IRs caíram."""
    devices = [_ir("IR-1", True), _ir("IR-2", False), _sensor("Sensor Sala", True)]

    resultado = await _checar(devices)

    assert resultado["online_count"] == 2  # o sensor conta no geral...
    assert resultado["all_offline"] is True  # ...mas não no limiar de IR


# ---------------------------------------------------------------------------
# Sem isenção: nem a Home com um único IR cadastrado escapa do limiar
# ---------------------------------------------------------------------------

async def test_home_com_um_unico_ir_cadastrado_tambem_e_offline():
    """
    ir_total == 1 e esse IR online: ainda assim OFFLINE.

    Decisão explícita do responsável (15/10/2026): um dispositivo solitário não é da
    revenda — é cadastro residual ou equipamento fora da loja. Não existe comando
    seguro nesse estado, então nenhum é enviado.
    """
    resultado = await _checar([_ir("IR-unico", True)])

    assert resultado["ir_online"] == 1
    assert resultado["ir_total"] == 1
    assert resultado["all_offline"] is True
    assert resultado["cobertura_degradada"] is True


async def test_revenda_com_um_unico_ir_offline_continua_sendo_offline():
    """Regra antiga preservada: o único IR caiu, logo a revenda está offline."""
    resultado = await _checar([_ir("IR-unico", False)])

    assert resultado["all_offline"] is True


# ---------------------------------------------------------------------------
# Não-regressão: o que já funcionava continua funcionando
# ---------------------------------------------------------------------------

async def test_dois_ou_mais_ir_online_opera_normalmente():
    devices = [_ir("IR-1", True), _ir("IR-2", True), _ir("IR-3", False)]

    resultado = await _checar(devices)

    assert resultado["ir_online"] == 2
    assert resultado["all_offline"] is False
    assert resultado["cobertura_degradada"] is False


async def test_todos_os_ir_offline_continua_offline():
    resultado = await _checar([_ir("IR-1", False), _ir("IR-2", False)])

    assert resultado["ir_online"] == 0
    assert resultado["all_offline"] is True


async def test_home_sem_dispositivos_mantem_fail_safe_permissivo():
    """Fail-safe de produto: sem lista de devices, não trava o usuário."""
    resultado = await _checar([])

    assert resultado["all_offline"] is False
    assert resultado["checked"] is False


async def test_erro_na_consulta_mantem_fallback_permissivo():
    with patch(
        "app.services.tuya_service.tuya_service.get_devices_by_home",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Tuya fora do ar"),
    ):
        resultado = await tuya_service.check_home_devices_online("home-teste")

    assert resultado["all_offline"] is False
    assert resultado["checked"] is False
