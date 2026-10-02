"""
Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

Adiciona cd_sexo, ano_nascimento e semana_notificacao à fato_casos,
e atualiza o UNIQUE constraint para refletir a nova granularidade.
"""
from typing import Sequence, Union

# pyrefly: ignore [missing-import]
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE _cname text;
        BEGIN
            SELECT tc.constraint_name INTO _cname
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema    = 'analytics'
              AND tc.table_name      = 'fato_casos'
              AND tc.constraint_type = 'UNIQUE'
            LIMIT 1;
            IF _cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE analytics.fato_casos DROP CONSTRAINT ' || quote_ident(_cname);
            END IF;
        END $$;
    """)

    op.execute("""
        ALTER TABLE analytics.fato_casos
            ADD COLUMN cd_sexo        VARCHAR(1) NOT NULL DEFAULT 'I',
            ADD COLUMN semana_notif   SMALLINT   NOT NULL DEFAULT 0,
            ADD COLUMN ano_nascimento SMALLINT   NOT NULL DEFAULT 0
    """)

    op.execute("""
        ALTER TABLE analytics.fato_casos
            ADD CONSTRAINT fato_casos_unique UNIQUE (
                disease_codigo,
                ano,
                mes,
                cd_mun,
                cd_unidade,
                cd_classificacao,
                cd_evolucao,
                cd_sexo,
                semana_notif,
                ano_nascimento
            )
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE analytics.fato_casos DROP CONSTRAINT fato_casos_unique"
    )
    op.execute("""
        ALTER TABLE analytics.fato_casos
            DROP COLUMN cd_sexo,
            DROP COLUMN semana_notif,
            DROP COLUMN ano_nascimento
    """)
    op.execute("""
        ALTER TABLE analytics.fato_casos
            ADD CONSTRAINT fato_casos_unique UNIQUE (
                disease_codigo, ano, mes, cd_mun,
                cd_unidade, cd_classificacao, cd_evolucao
            )
    """)
