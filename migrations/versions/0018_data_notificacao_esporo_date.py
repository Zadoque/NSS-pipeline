"""Armazena a data de notificação da esporotricose sem horário."""

from alembic import op


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN data_notificacao TYPE DATE
        USING data_notificacao::date
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN data_notificacao DROP NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN data_notificacao TYPE TIMESTAMP WITHOUT TIME ZONE
        USING data_notificacao::timestamp
        """
    )
    op.execute(
        """
        ALTER TABLE analytics_animal.fato_esporo
        ALTER COLUMN data_notificacao SET NOT NULL
        """
    )
