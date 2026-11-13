"""Codifica espécie animal como 0 (NI), 1 (felino) ou 2 (canino)."""

from alembic import op


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN especie TO especie_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN especie_codigo TYPE SMALLINT
        USING CASE lower(trim(especie_codigo))
            WHEN 'i' THEN 0
            WHEN 'não informado' THEN 0
            WHEN 'nao informado' THEN 0
            WHEN 'felino' THEN 1
            WHEN 'canino' THEN 2
            ELSE NULL
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ADD CONSTRAINT ck_fato_esporo_especie_codigo
        CHECK (especie_codigo BETWEEN 0 AND 2)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        DROP CONSTRAINT ck_fato_esporo_especie_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN especie_codigo TYPE VARCHAR(20)
        USING CASE especie_codigo
            WHEN 0 THEN 'i'
            WHEN 1 THEN 'Felino'
            WHEN 2 THEN 'Canino'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN especie_codigo TO especie
        """
    )
