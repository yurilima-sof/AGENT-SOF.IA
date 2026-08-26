# =============================================================================
# app/scripts/ingest_chat.py - Ingestão e Vetorização do Histórico de Conversas
# =============================================================================

import os
import re
import sys
import json
import time
from datetime import datetime
from sqlalchemy import text
from google import genai
from google.genai import types

# Configura a saída do terminal para UTF-8 (corrige erro de encoding com emojis no Windows)
sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o diretório raiz ao PYTHONPATH para permitir imports da pasta app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import get_settings
from app.database import get_sync_engine

settings = get_settings()

import argparse

# Configuração de Argumentos do Terminal (CLI)
parser = argparse.ArgumentParser(description="Ingestão de Histórico do WhatsApp para o RAG")
parser.add_argument("group_id", type=str, help="ID do grupo (ex: 120363422455765261-group)")
parser.add_argument("file_path", type=str, nargs='?', default="_chat.txt", help="Caminho para o arquivo .txt (Padrão: _chat.txt na raiz)")

# Para compatibilidade com a execução antiga, verificamos se o usuário passou argumentos
if len(sys.argv) > 1:
    args = parser.parse_args()
    TARGET_GROUP_ID = args.group_id
    CHAT_FILE_PATH = args.file_path
else:
    print("❌ Erro: Faltando ID do Grupo. Uso correto: python app/scripts/ingest_chat.py <ID_DO_GRUPO> [caminho_do_arquivo.txt]")
    sys.exit(1)

# Regex para detectar mensagens no formato do WhatsApp
# Exemplo: [30/07/2025, 14:09:22] ~ Eduardo Dos Anjos: Recepção muito quente...
MSG_REGEX = re.compile(r"^\[(\d{2}/\d{2}/\d{4}),\s+(\d{2}:\d{2}:\d{2})\]\s+([^:]+):\s*(.*)$")


def parse_chat_file(file_path: str) -> list[dict]:
    """
    Lê o arquivo de chat e extrai uma lista de mensagens estruturadas.
    Une mensagens de múltiplas linhas corretamente.
    """
    if not os.path.exists(file_path):
        print(f"❌ Arquivo não encontrado: {file_path}")
        sys.exit(1)

    print(f"📖 Lendo o histórico de chat de: {file_path}...")
    messages = []
    current_msg = None

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue

            match = MSG_REGEX.match(line_str)
            if match:
                # Se tínhamos uma mensagem anterior sendo processada, salva ela
                if current_msg:
                    messages.append(current_msg)

                date_str, time_str, sender, content = match.groups()
                # Limpa caracteres especiais do nome (como o '~' do WhatsApp)
                sender = sender.replace("~", "").strip()

                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    dt = datetime.now()

                current_msg = {
                    "timestamp": dt,
                    "sender": sender,
                    "content": content
                }
            else:
                # Mensagem de múltiplas linhas: anexa a linha atual à mensagem anterior
                if current_msg:
                    current_msg["content"] += "\n" + line_str
                else:
                    # Linha órfã no início do arquivo, ignora
                    pass

        # Adiciona a última mensagem processada
        if current_msg:
            messages.append(current_msg)

    print(f"✅ Total de {len(messages)} mensagens extraídas com sucesso.")
    return messages


def chunk_messages(messages: list[dict], max_gap_minutes: int = 30, max_messages_per_chunk: int = 15) -> list[str]:
    """
    Agrupa mensagens em 'conversas' (blocos lógicos) baseados na diferença de tempo
    e limita o tamanho máximo de cada bloco para otimizar tokens.
    """
    if not messages:
        return []

    print(f"🧩 Agrupando conversas (intervalo máximo: {max_gap_minutes} min, limite: {max_messages_per_chunk} mensagens)...")
    chunks = []
    current_chunk = []
    last_timestamp = None

    for msg in messages:
        ts = msg["timestamp"]

        # Condição de quebra: se mudou a conversa pelo tempo OU atingiu o limite de tamanho do chunk
        tempo_excedido = last_timestamp and (ts - last_timestamp).total_seconds() / 60 > max_gap_minutes
        tamanho_excedido = len(current_chunk) >= max_messages_per_chunk

        if tempo_excedido or tamanho_excedido:
            if current_chunk:
                chunks.append(format_chunk(current_chunk))
                current_chunk = []

        current_chunk.append(msg)
        last_timestamp = ts

    # Adiciona o último bloco restante
    if current_chunk:
        chunks.append(format_chunk(current_chunk))

    print(f"✅ Total de {len(chunks)} blocos de conversa gerados.")
    return chunks


def format_chunk(msg_list: list[dict]) -> str:
    """Formata uma lista de mensagens em um diálogo textual legível para a IA."""
    formatted_lines = []
    for msg in msg_list:
        time_str = msg["timestamp"].strftime("%d/%m/%Y %H:%M")
        formatted_lines.append(f"[{time_str}] {msg['sender']}: {msg['content']}")
    return "\n".join(formatted_lines)


def main():
    if not settings.gemini_api_key:
        print("❌ Chave de API GEMINI_API_KEY não configurada no arquivo .env.")
        sys.exit(1)

    # 1. Parse do chat
    messages = parse_chat_file(CHAT_FILE_PATH)
    if not messages:
        print("⚠️ Nenhuma mensagem encontrada para processamento.")
        return

    # 2. Agrupamento em chunks (conversas)
    chunks = chunk_messages(messages)

    client = genai.Client(api_key=settings.gemini_api_key)
    engine = get_sync_engine()
    inserted_count = 0

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM rag_documentos WHERE id_grupo_wpp = :group_id"),
            {"group_id": TARGET_GROUP_ID}
        )

    for i, chunk_text in enumerate(chunks):
        if (i + 1) % 10 == 0 or i == 0 or i == len(chunks) - 1:
            print(f"   Processando bloco {i + 1}/{len(chunks)}...")

        embedding = None
        for attempt in range(3):
            try:
                result = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=chunk_text,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768,
                    ),
                )
                embedding = result.embeddings[0].values
                break
            except Exception as e:
                print(f"⚠️ Erro na tentativa {attempt + 1}: {e}. Tentando novamente em 2s...")
                time.sleep(2)
        
        if embedding:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO rag_documentos (id_grupo_wpp, conteudo, embedding, metadados)
                            VALUES (:group_id, :content, :embedding, :metadata)
                        """),
                        {
                            "group_id": TARGET_GROUP_ID,
                            "content": chunk_text,
                            "embedding": json.dumps(embedding),
                            "metadata": json.dumps({"source": "whatsapp_chat_export"})
                        }
                    )
                inserted_count += 1
            except Exception as e:
                print(f"❌ Erro ao salvar bloco {i + 1}: {e}")

    print(f"🎉 Ingestão finalizada! {inserted_count} blocos inseridos no banco com embeddings.")


if __name__ == "__main__":
    main()
