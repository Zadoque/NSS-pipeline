"""Codifica o status de castração animal em valores inteiros."""

from alembic import op


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN castrado TO castrado_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN castrado_codigo TYPE SMALLINT
        USING CASE lower(trim(castrado_codigo))
            WHEN 'não' THEN 1
            WHEN 'nao' THEN 1
            WHEN 'n' THEN 1
            WHEN 'sim' THEN 2
            WHEN 's' THEN 2
            WHEN 'i' THEN 0
            WHEN 'não informado' THEN 0
            WHEN 'nao informado' THEN 0
            ELSE NULL
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ADD CONSTRAINT ck_fato_esporo_castrado_codigo
        CHECK (castrado_codigo BETWEEN 0 AND 2)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        DROP CONSTRAINT ck_fato_esporo_castrado_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN castrado_codigo TYPE VARCHAR(20)
        USING CASE castrado_codigo
            WHEN 0 THEN 'i'
            WHEN 1 THEN 'Não'
            WHEN 2 THEN 'Sim'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN castrado_codigo TO castrado
        """
    )
