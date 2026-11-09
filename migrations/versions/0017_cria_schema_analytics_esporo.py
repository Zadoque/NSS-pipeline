"""
Revision ID: 0017
Revises: 0016

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics_animal")

    op.execute("""
        CREATE TABLE analytics_animal.fato_esporo (
            id                      BIGSERIAL       PRIMARY KEY,
            data_notificacao        TIMESTAMP       NOT NULL,
            especie                 VARCHAR(20)     NOT NULL,
            sexo_animal             VARCHAR(20)     NOT NULL,
            idade_animal            VARCHAR(20)     NOT NULL,
            castrado                VARCHAR(20)     NOT NULL,
        )
    """)