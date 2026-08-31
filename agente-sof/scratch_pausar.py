import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o diretório da aplicação no path
sys.path.insert(0, os.path.abspath("."))

from app.database import async_session_maker
from app.services.tuya_dispatch_service import disparar_acao_fisica
from app.services.scheduler_service import scheduler_service

RECIFE_TZ = ZoneInfo("America/Recife")

async def main():
    print("🔍 Buscando revenda 'SOF Teste' no banco de dados...")
    horario_fim = datetime(2026, 8, 31, 11, 0, 0, tzinfo=RECIFE_TZ)
    
    async with async_session_maker() as db:
        try:
            # Busca revenda por nome aproximado ou ID de grupo
            result = await db.execute(text("""
                SELECT id_grupo_wpp, nome_revenda, tuya_home_id 
                FROM mapa_revendas 
                WHERE LOWER(nome_revenda) LIKE '%sof%' 
                   OR LOWER(nome_revenda) LIKE '%teste%'
                   OR LOWER(id_grupo_wpp) LIKE '%teste%'
            """))
            revendas = result.fetchall()
            
            if not revendas:
                print("⚠️ Nenhuma revenda encontrada com 'sof' ou 'teste' no banco. Usando fallback de teste 'teste123@g.us'...")
                id_grupo = "teste123@g.us"
                nome_revenda = "[SOF] Testes"
                home_id = "home_sof_teste"
            else:
                for r in revendas:
                    print(f"✅ Encontrada revenda: Nome='{r.nome_revenda}' | Grupo='{r.id_grupo_wpp}' | HomeID='{r.tuya_home_id}'")
                rev = revendas[0]
                id_grupo = rev.id_grupo_wpp
                nome_revenda = rev.nome_revenda
                home_id = rev.tuya_home_id or "home_sof_teste"
        except Exception as e:
            print(f"⚠️ Aviso ao consultar banco (usando modo dev/offline): {e}")
            id_grupo = "teste123@g.us"
            nome_revenda = "[SOF] Testes"
            home_id = "home_sof_teste"

        print(f"\n🚀 Executando pausa de automações de OFF para '{nome_revenda}' ({id_grupo})...")
        print(f"⏰ Horário limite configurado: {horario_fim.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        resultado = await disparar_acao_fisica(
            db=db,
            id_grupo=id_grupo,
            nome_revenda=nome_revenda,
            home_id=home_id,
            acao="desativar_automacao",
            intencao="pausar_automacao",
            horario_fim_pausa=horario_fim,
        )

        print("\n📋 Resultado da operação:")
        print(f"  - Sucesso Tuya : {resultado.get('tuya_success')}")
        print(f"  - Detalhe     : {resultado.get('detail')}")
        print(f"  - Dispositivo : {'OFFLINE' if resultado.get('device_offline') else 'ONLINE'}")

if __name__ == "__main__":
    asyncio.run(main())
