"""Garante os códigos sentinela usados pelas fatos analíticas."""

from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO analytics.dim_unidade_saude (cd_unidade, nm_unidade)
        VALUES ('0000000', 'Não identificado')
        ON CONFLICT (cd_unidade) DO NOTHING
    """)
    op.execute("""
        INSERT INTO analytics.dim_classificacao (codigo, descricao)
        VALUES ('NI', 'Não informado')
        ON CONFLICT (codigo) DO NOTHING
    """)
    op.execute("""
        INSERT INTO analytics.dim_evolucao (codigo, descricao)
        VALUES ('NI', 'Não informado')
        ON CONFLICT (codigo) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM analytics.dim_unidade_saude WHERE cd_unidade = '0000000'")
    op.execute("DELETE FROM analytics.dim_evolucao WHERE codigo = 'NI'")
    op.execute("DELETE FROM analytics.dim_classificacao WHERE codigo = 'NI'")
