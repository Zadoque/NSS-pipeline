"""Armazena sexo animal como código F, M ou i."""

from alembic import op


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN sexo_animal TO sexo_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN sexo_codigo TYPE CHAR(1)
        USING CASE lower(trim(sexo_codigo))
            WHEN 'f' THEN 'F'
            WHEN 'fêmea' THEN 'F'
            WHEN 'femea' THEN 'F'
            WHEN 'feminino' THEN 'F'
            WHEN 'm' THEN 'M'
            WHEN 'macho' THEN 'M'
            WHEN 'masculino' THEN 'M'
            WHEN 'i' THEN 'i'
            WHEN 'nao informado' THEN 'i'
            WHEN 'não informado' THEN 'i'
            ELSE NULL
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ADD CONSTRAINT ck_fato_esporo_sexo_codigo
        CHECK (sexo_codigo IN ('F', 'M', 'i'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        DROP CONSTRAINT ck_fato_esporo_sexo_codigo
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN sexo_codigo TYPE VARCHAR(20)
        USING CASE sexo_codigo
            WHEN 'F' THEN 'fêmea'
            WHEN 'M' THEN 'macho'
            WHEN 'i' THEN 'i'
        END
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        RENAME COLUMN sexo_codigo TO sexo_animal
        """
    )
