"""Permite filtrar o lote corrente diretamente no índice territorial.

Revision ID: 0016
Revises: 0015
"""

from alembic import op


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS analytics.idx_fato_casos_territorio_recorte"
    )
    op.execute(
        """
        CREATE INDEX idx_fato_casos_territorio_recorte
        ON analytics.fato_casos (
            disease_codigo,
            ano,
            cd_mun,
            notification_district_id,
            cd_sexo,
            batch_id
        )
        INCLUDE (
            notification_neighborhood_id,
            notification_territory_status,
            cases_total
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS analytics.idx_fato_casos_territorio_recorte"
    )
    op.execute(
        """
        CREATE INDEX idx_fato_casos_territorio_recorte
        ON analytics.fato_casos (
            disease_codigo,
            ano,
            cd_mun,
            notification_district_id,
            cd_sexo
        )
        INCLUDE (
            batch_id,
            notification_neighborhood_id,
            notification_territory_status,
            cases_total
        )
        """
    )
