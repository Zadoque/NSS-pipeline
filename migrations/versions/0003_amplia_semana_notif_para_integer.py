"""
Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

Amplia semana_notif para preservar o código SINAN no formato AAAASS.
Valores já corrompidos por overflow precisam ser recuperados da fonte.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.fato_casos
            ALTER COLUMN semana_notif TYPE INTEGER
            USING semana_notif::INTEGER
    """)


def downgrade() -> None:
    # O PostgreSQL aborta a conversão se houver valores fora da faixa de
    # SMALLINT, impedindo truncamento de códigos AAAASS já carregados.
    op.execute("""
        ALTER TABLE analytics.fato_casos
            ALTER COLUMN semana_notif TYPE SMALLINT
            USING semana_notif::SMALLINT
    """)
