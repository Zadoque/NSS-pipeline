#!/bin/bash
set -e

# Roda automaticamente apenas na PRIMEIRA inicialização do volume pgdata
# (imagem oficial do Postgres só executa scripts em
# /docker-entrypoint-initdb.d quando o data directory está vazio).
#
# Se você já tem um volume pgdata existente (de antes deste arquivo
# existir), rode manualmente uma vez:
#   docker compose exec db psql -U <POSTGRES_USER> -d <POSTGRES_DB> \
#     -c "CREATE DATABASE situacao_saude_test;"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE situacao_saude_test'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'situacao_saude_test')\gexec
EOSQL
