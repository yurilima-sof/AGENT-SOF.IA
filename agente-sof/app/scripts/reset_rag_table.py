# =============================================================================
# app/scripts/reset_rag_table.py - Recriação da Tabela RAG (Dimensão 768)
# =============================================================================

import os
import sys
from sqlalchemy import text

# Configura a saída do terminal para UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import get_sync_engine

def main():
    print("🔌 Conectando ao banco de dados...")
    engine = get_sync_engine()
    
    print("⚠️  Removendo a tabela anterior (rag_documentos) se existir...")
    drop_query = "DROP TABLE IF EXISTS rag_documentos CASCADE;"
    
    create_query = """
    CREATE TABLE rag_documentos (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        id_grupo_wpp VARCHAR(100),
        conteudo TEXT NOT NULL,
        metadados JSONB DEFAULT '{}',
        embedding vector(768), -- Nova dimensão (Gemini text-embedding-004)
        criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """
    
    idx_embedding_query = """
    CREATE INDEX IF NOT EXISTS idx_rag_documentos_embedding 
    ON rag_documentos USING hnsw (embedding vector_cosine_ops);
    """
    
    idx_grupo_query = """
    CREATE INDEX IF NOT EXISTS idx_rag_documentos_grupo ON rag_documentos(id_grupo_wpp);
    """
    
    with engine.begin() as conn:
        conn.execute(text(drop_query))
        print("   Tabela antiga removida.")
        
        conn.execute(text(create_query))
        print("   Nova tabela rag_documentos (vector(768)) criada.")
        
        conn.execute(text(idx_embedding_query))
        conn.execute(text(idx_grupo_query))
        print("   Índices da tabela recriados com sucesso.")
        
    print("🎉 Tabela RAG resetada com sucesso!")

if __name__ == "__main__":
    main()
