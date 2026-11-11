"""Codifica a faixa etária animal em valores inteiros."""

from alembic import op


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN idade_animal TO idade_faixa_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN idade_faixa_codigo TYPE SMALLINT
        USING CASE lower(trim(idade_faixa_codigo))
            WHEN 'i' THEN 0
            WHEN 'nao informado' THEN 0
            WHEN 'não informado' THEN 0
            WHEN '< 1 ano' THEN 1
            WHEN '<1 ano' THEN 1
            WHEN '1 - 3 anos' THEN 2
            WHEN '1-3 anos' THEN 2
            WHEN '4 - 6 anos' THEN 3
            WHEN '4-6 anos' THEN 3
            WHEN '7 - 10 anos' THEN 4
            WHEN '7-10 anos' THEN 4
            WHEN '> 10 anos' THEN 5
            WHEN '>10 anos' THEN 5
            ELSE NULL
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ADD CONSTRAINT ck_fato_esporo_idade_faixa_codigo
        CHECK (idade_faixa_codigo BETWEEN 0 AND 5)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        DROP CONSTRAINT ck_fato_esporo_idade_faixa_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN idade_faixa_codigo TYPE VARCHAR(20)
        USING CASE idade_faixa_codigo
            WHEN 0 THEN 'i'
            WHEN 1 THEN '< 1 ano'
            WHEN 2 THEN '1 - 3 anos'
            WHEN 3 THEN '4 - 6 anos'
            WHEN 4 THEN '7 - 10 anos'
            WHEN 5 THEN '> 10 anos'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN idade_faixa_codigo TO idade_animal
        """
    )
