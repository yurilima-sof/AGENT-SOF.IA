-- =============================================================================
-- database/init.sql - Script de Inicialização do Banco de Dados
-- =============================================================================
-- Este arquivo é executado automaticamente pelo PostgreSQL na PRIMEIRA vez
-- que o container sobe (quando o volume ainda está vazio).
--
-- IMPORTANTE: Se você precisar alterar a estrutura do banco depois que ele
-- já foi criado, NÃO edite este arquivo. Use migrations (ex: Alembic).
-- =============================================================================


-- =============================================================================
-- EXTENSÕES
-- =============================================================================

-- Habilita a geração de UUIDs diretamente pelo banco de dados.
-- Usaremos gen_random_uuid() como valor padrão nas chaves primárias.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Habilita busca vetorial (RAG) com pgvector:
CREATE EXTENSION IF NOT EXISTS "vector";


-- =============================================================================
-- TABELA 1: mapa_revendas
-- =============================================================================
-- Cada registro representa uma "Revenda" (cliente) do sistema.
-- Esta é a tabela central da nossa arquitetura multi-tenant:
-- ela mapeia um grupo de WhatsApp para uma revenda específica e
-- armazena as credenciais da API Tuya dessa revenda.
-- =============================================================================
CREATE TABLE IF NOT EXISTS mapa_revendas (

    -- Chave primária como UUID.
    -- gen_random_uuid() gera um UUID v4 automaticamente ao inserir.
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ID único do grupo de WhatsApp, formato: "XXXXXXXXXXX@g.us"
    -- É o identificador que chega do n8n para descobrirmos qual revenda é.
    -- UNIQUE garante que cada grupo pertença a apenas UMA revenda.
    id_grupo_wpp VARCHAR(100) NOT NULL UNIQUE,

    -- Nome comercial/fantasia da revenda para exibição e logs.
    nome_revenda VARCHAR(200) NOT NULL,

    -- Estado (UF) onde a revenda opera. Ex: "SP", "RJ", "MG".
    estado VARCHAR(2) NOT NULL,

    -- Credenciais da API Tuya em formato JSON flexível.
    -- JSONB = armazenamento binário de JSON, com suporte a indexação.
    -- Estrutura esperada (exemplo):
    -- {
    --   "access_key": "abc123",
    --   "secret_key": "xyz789",
    --   "region": "us",
    --   "project_code": "proj_001"
    -- }
    credenciais_tuya JSONB NOT NULL DEFAULT '{}',

    -- Home ID da Tuya vinculada diretamente à revenda pelo ID de Grupo do WhatsApp (Isolamento Multi-tenant U-07)
    tuya_home_id VARCHAR(100),

    -- Flag para desativar uma revenda sem deletá-la do banco.
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps de auditoria: criação e última atualização.
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mapa_revendas_home_id ON mapa_revendas(tuya_home_id);

-- Comentários descritivos nas colunas (boa prática para documentação do schema).
COMMENT ON TABLE mapa_revendas IS 'Tabela central multi-tenant: mapeia grupos de WhatsApp para revendas e suas credenciais Tuya.';
COMMENT ON COLUMN mapa_revendas.id_grupo_wpp IS 'ID do grupo WhatsApp no formato XXXXXXXXXXX@g.us, conforme recebido pelo n8n.';
COMMENT ON COLUMN mapa_revendas.credenciais_tuya IS 'JSON com credenciais da API Tuya (access_key, secret_key, region, etc.). Nunca exponha em logs!';

-- Índice para otimizar a busca por id_grupo_wpp (consulta mais frequente do n8n).
CREATE INDEX IF NOT EXISTS idx_mapa_revendas_grupo_wpp ON mapa_revendas(id_grupo_wpp);


-- =============================================================================
-- TABELA 2: logs_operacoes
-- =============================================================================
-- Registra TODAS as operações processadas pelo agente.
-- Serve para auditoria, debug, métricas de uso e faturamento por revenda.
-- Esta tabela pode crescer muito! Planeje uma política de retenção de dados.
-- =============================================================================
CREATE TABLE IF NOT EXISTS logs_operacoes (

    -- Chave primária UUID gerada automaticamente.
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Momento exato em que a operação foi registrada.
    -- WITH TIME ZONE é essencial para sistemas que operam em múltimos fusos.
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Referência ao grupo de WhatsApp que originou o comando.
    -- Não é FK direta para permitir logs mesmo se a revenda for deletada.
    id_grupo VARCHAR(100) NOT NULL,

    -- Nome da revenda no momento do log (desnormalizado intencionalmente).
    -- Facilita queries de relatório sem precisar de JOINs.
    nome_revenda VARCHAR(200) NOT NULL,

    -- A mensagem original que o usuário enviou pelo WhatsApp.
    mensagem_original TEXT NOT NULL,

    -- A intenção identificada pelo agente de IA.
    -- Exemplos: "ligar_dispositivo", "desligar_dispositivo", "consultar_status", "saudacao"
    intencao VARCHAR(100),

    -- O resultado da operação para controle de qualidade.
    -- Exemplos: "sucesso", "erro_tuya", "intencao_nao_identificada", "dispositivo_nao_encontrado"
    status VARCHAR(50) NOT NULL DEFAULT 'processando',

    -- Tempo total de resposta da nossa API em milissegundos.
    -- Importante para monitorar a performance e identificar gargalos.
    tempo_resposta_ms INTEGER,

    -- JSON com detalhes adicionais sobre a operação (flexível para evolução).
    -- Pode conter: dispositivo_id, parametros enviados, resposta da Tuya, etc.
    detalhes JSONB DEFAULT '{}'

);

COMMENT ON TABLE logs_operacoes IS 'Log imutável de todas as operações processadas. Usado para auditoria, debug e métricas.';
COMMENT ON COLUMN logs_operacoes.intencao IS 'Intenção identificada pelo agente de IA. Ex: ligar_dispositivo, desligar_dispositivo.';
COMMENT ON COLUMN logs_operacoes.status IS 'Resultado da operação: sucesso, erro_tuya, intencao_nao_identificada, etc.';
COMMENT ON COLUMN logs_operacoes.tempo_resposta_ms IS 'Latência total da API em milissegundos para monitoramento de performance.';

-- Índices para otimizar as queries de relatório mais comuns.
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs_operacoes(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_id_grupo ON logs_operacoes(id_grupo);
CREATE INDEX IF NOT EXISTS idx_logs_status ON logs_operacoes(status);


-- =============================================================================
-- TABELA 3: rag_documentos
-- =============================================================================
-- Armazena os blocos de conhecimento (chat, manuais, regras) e seus embeddings.
-- =============================================================================
CREATE TABLE IF NOT EXISTS rag_documentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_grupo_wpp VARCHAR(100), -- Vazio se for conhecimento geral do sistema
    conteudo TEXT NOT NULL,
    metadados JSONB DEFAULT '{}',
    embedding vector(768), -- 768 dimensões (Gemini embeddings default)
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Índice HNSW para busca vetorial rápida por similaridade de cosseno
CREATE INDEX IF NOT EXISTS idx_rag_documentos_embedding 
ON rag_documentos USING hnsw (embedding vector_cosine_ops);

-- Índice por grupo de WhatsApp para agilizar filtros multi-tenant
CREATE INDEX IF NOT EXISTS idx_rag_documentos_grupo ON rag_documentos(id_grupo_wpp);

-- =============================================================================
-- TABELA 4: tuya_clientes_homes
-- =============================================================================
-- Mapeia a sigla do cliente para o Tuya UID e Home ID
-- =============================================================================
CREATE TABLE IF NOT EXISTS tuya_clientes_homes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sigla_cliente VARCHAR(50) NOT NULL,
    tuya_uid VARCHAR(100) NOT NULL,
    home_id VARCHAR(100) NOT NULL,
    nome_home VARCHAR(200) NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tuya_homes_sigla ON tuya_clientes_homes(sigla_cliente);
CREATE INDEX IF NOT EXISTS idx_tuya_homes_nome ON tuya_clientes_homes(nome_home);

-- =============================================================================
-- TABELA 5: tuya_clientes_cenas
-- =============================================================================
-- Mapeia os ambientes e ações para os Scene IDs da Tuya
-- =============================================================================
CREATE TABLE IF NOT EXISTS tuya_clientes_cenas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sigla_cliente VARCHAR(50) NOT NULL,
    home_id VARCHAR(100) NOT NULL,
    ambiente VARCHAR(100) NOT NULL,
    scene_id VARCHAR(100) NOT NULL UNIQUE,
    nome_cena VARCHAR(200) NOT NULL,
    acao VARCHAR(50) NOT NULL, -- Ex: 'ligar', 'desligar', 'esfriar', 'esquentar'
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tuya_cenas_home ON tuya_clientes_cenas(home_id);
CREATE INDEX IF NOT EXISTS idx_tuya_cenas_ambiente ON tuya_clientes_cenas(ambiente);

-- =============================================================================
-- TABELA 6: chat_historico_recente (Memória de Curto Prazo)
-- =============================================================================
-- Armazena o histórico recente de conversas por grupo de WhatsApp para dar
-- memória de curto prazo ao agente (sliding window de 15 minutos).
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_historico_recente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_grupo_wpp VARCHAR(100) NOT NULL,
    autor VARCHAR(20) NOT NULL, -- 'usuario' ou 'sofia'
    conteudo TEXT NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_historico_grupo_tempo 
ON chat_historico_recente(id_grupo_wpp, criado_em DESC);

