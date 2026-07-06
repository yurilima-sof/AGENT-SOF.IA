# =============================================================================
# app/scripts/ingest_chat_mock.py - Ingestão Simulada (Mock) de Conversas
# =============================================================================

import os
import re
import sys
import json
import random
import math
from datetime import datetime
from sqlalchemy import text

# Configura a saída do terminal para UTF-8 (corrige erro de encoding com emojis no Windows)
sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o diretório raiz ao PYTHONPATH para permitir imports da pasta app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import get_settings
from app.database import get_sync_engine

settings = get_settings()

# ID do grupo de teste fixo para esta ingestão
TEST_GROUP_ID = "120363422455765261-group"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_CHAT_PATH = os.path.join(_PROJECT_ROOT, "_chat.txt")
CHAT_FILE_PATH = (
    sys.argv[1] if len(sys.argv) > 1
    else os.getenv("CHAT_FILE_PATH", _DEFAULT_CHAT_PATH)
)

MSG_REGEX = re.compile(r"^\[(\d{2}/\d{2}/\d{4}),\s+(\d{2}:\d{2}:\d{2})\]\s+([^:]+):\s*(.*)$")


def parse_chat_file(file_path: str) -> list[dict]:
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
                if current_msg:
                    messages.append(current_msg)

                date_str, time_str, sender, content = match.groups()
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
                if current_msg:
                    current_msg["content"] += "\n" + line_str

        if current_msg:
            messages.append(current_msg)

    print(f"✅ Total de {len(messages)} mensagens extraídas com sucesso.")
    return messages


def chunk_messages(messages: list[dict], max_gap_minutes: int = 30, max_messages_per_chunk: int = 15) -> list[str]:
    if not messages:
        return []

    print(f"🧩 Agrupando conversas (intervalo máximo: {max_gap_minutes} min, limite: {max_messages_per_chunk} mensagens)...")
    chunks = []
    current_chunk = []
    last_timestamp = None

    for msg in messages:
        ts = msg["timestamp"]

        tempo_excedido = last_timestamp and (ts - last_timestamp).total_seconds() / 60 > max_gap_minutes
        tamanho_excedido = len(current_chunk) >= max_messages_per_chunk

        if tempo_excedido or tamanho_excedido:
            if current_chunk:
                chunks.append(format_chunk(current_chunk))
                current_chunk = []

        current_chunk.append(msg)
        last_timestamp = ts

    if current_chunk:
        chunks.append(format_chunk(current_chunk))

    print(f"✅ Total de {len(chunks)} blocos de conversa gerados.")
    return chunks


def format_chunk(msg_list: list[dict]) -> str:
    formatted_lines = []
    for msg in msg_list:
        time_str = msg["timestamp"].strftime("%d/%m/%Y %H:%M")
        formatted_lines.append(f"[{time_str}] {msg['sender']}: {msg['content']}")
    return "\n".join(formatted_lines)


def generate_mock_embedding(dim: int = 768) -> list[float]:
    """Gera um vetor aleatório unitário (normalizado L2) de tamanho `dim`."""
    vec = [random.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        vec[0] = 1.0
        norm = 1.0
    return [x / norm for x in vec]


def main():
    messages = parse_chat_file(CHAT_FILE_PATH)
    if not messages:
        print("⚠️ Nenhuma mensagem encontrada para processamento.")
        return

    chunks = chunk_messages(messages)

    # Inicializa conexão síncrona com o banco de dados
    print("🔌 Conectando ao banco de dados...")
    engine = get_sync_engine()

    print("🚀 Iniciando vetorização SIMULADA e inserção no banco...")
    inserted_count = 0

    with engine.begin() as conn:
        # Limpa dados anteriores do RAG para o grupo de testes para evitar duplicidade
        conn.execute(
            text("DELETE FROM rag_documentos WHERE id_grupo_wpp = :group_id"),
            {"group_id": TEST_GROUP_ID}
        )

        for i, chunk_text in enumerate(chunks):
            if (i + 1) % 50 == 0 or i == 0 or i == len(chunks) - 1:
                print(f"   Processando bloco {i + 1}/{len(chunks)}...")

            try:
                # Gera um embedding artificial
                embedding = generate_mock_embedding(768)

                # Insere no banco
                conn.execute(
                    text("""
                        INSERT INTO rag_documentos (id_grupo_wpp, conteudo, embedding, metadados)
                        VALUES (:group_id, :content, :embedding, :metadata)
                    """),
                    {
                        "group_id": TEST_GROUP_ID,
                        "content": chunk_text,
                        "embedding": str(embedding),
                        "metadata": json.dumps({"source": "whatsapp_chat_export_mock"})
                    }
                )
                inserted_count += 1
            except Exception as e:
                print(f"❌ Erro ao processar o bloco {i + 1}: {e}")

    print(f"🎉 Ingestão SIMULADA finalizada! {inserted_count} blocos inseridos no banco com embeddings mockados.")


if __name__ == "__main__":
    main()
