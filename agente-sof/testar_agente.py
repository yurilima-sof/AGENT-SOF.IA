import asyncio
import httpx
import os
from dotenv import load_dotenv

import sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    url = "http://localhost:8000/agent"
    api_key = os.getenv("API_KEY", "dev-api-key-insegura")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "mensagem": "tlow sala teste",
        "id_grupo": "teste123@g.us",
        "nome_revenda": "[SOF] Testes"
    }
    
    print("Enviando requisição para o Agente...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            print(f"Status HTTP: {response.status_code}")
            print("Resposta JSON:")
            import json
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Erro de conexão: {e}")

if __name__ == "__main__":
    asyncio.run(main())
