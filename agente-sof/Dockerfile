# Imagem base oficial do Python slim (leve e segura)
FROM python:3.11-slim

# Evita que o Python grave arquivos .pyc e bufferize o stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências do sistema necessárias para compilar pacotes Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# SEGURANÇA: Cria e usa um usuário não-root para limitar privilégios.
# Se o container for comprometido, o atacante NÃO terá acesso root.
RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

# Expõe a porta que o Uvicorn irá rodar
EXPOSE 8000

# Comando para iniciar o servidor Uvicorn em produção
#
# NÃO adicione --workers aqui sem antes mudar o scheduler.
# O agendamento de pausa/reativação (app/services/scheduler_service.py) guarda
# as tasks em memória do processo. Com N workers, cada um carrega TODOS os
# agendamentos pendentes do banco e executa cada um: a automação é reativada N
# vezes e a cena de desligamento dispara N vezes. A reconciliação noturna é
# idempotente e sobreviveria, mas o tick não.
# Pré-requisito para escalar: mover o "quem executa" para o banco
# (SELECT ... FOR UPDATE SKIP LOCKED) em vez do dicionário em memória.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
