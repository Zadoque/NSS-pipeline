"""Preserva o território da unidade notificadora e a faixa etária."""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.fato_casos
            ADD COLUMN age_band VARCHAR(8) NOT NULL DEFAULT 'NI',
            ADD COLUMN notification_district_id VARCHAR(80),
            ADD COLUMN notification_neighborhood_id VARCHAR(100),
            ADD COLUMN notification_territory_status VARCHAR(40) NOT NULL DEFAULT 'UNMAPPED_NOTIFICATION_UNIT'
    """)
    op.execute("ALTER TABLE analytics.fato_casos DROP CONSTRAINT fato_casos_unique")
    op.execute("""
        ALTER TABLE analytics.fato_casos ADD CONSTRAINT fato_casos_unique UNIQUE (
            disease_codigo, ano, mes, cd_mun, cd_unidade, cd_classificacao,
            cd_evolucao, cd_sexo, semana_notif, ano_nascimento, age_band,
            notification_district_id, notification_neighborhood_id,
            notification_territory_status
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE analytics.fato_casos DROP CONSTRAINT fato_casos_unique")
    op.execute("""
        ALTER TABLE analytics.fato_casos ADD CONSTRAINT fato_casos_unique UNIQUE (
            disease_codigo, ano, mes, cd_mun, cd_unidade, cd_classificacao,
            cd_evolucao, cd_sexo, semana_notif, ano_nascimento
        )
    """)
    op.execute("""
        ALTER TABLE analytics.fato_casos
            DROP COLUMN age_band,
            DROP COLUMN notification_district_id,
            DROP COLUMN notification_neighborhood_id,
            DROP COLUMN notification_territory_status
    """)
