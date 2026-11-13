"""Garante o sentinela da dimensão de unidades após instalações legadas."""

from alembic import op


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO analytics.dim_unidade_saude (cd_unidade, nm_unidade)
        VALUES ('0000000', 'Não identificado')
        ON CONFLICT (cd_unidade) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM analytics.dim_unidade_saude WHERE cd_unidade = '0000000'")
