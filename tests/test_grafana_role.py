from app.pipeline.observability.grafana_role import provision_grafana_role


class _Result:
    def __init__(self, scalar=None, row=None):
        self._scalar = scalar
        self._row = row

    def scalar_one(self):
        return self._scalar

    def first(self):
        return self._row


class _Connection:
    def __init__(self, *, role_exists=False):
        self.role_exists = role_exists
        self.statements = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.statements.append((sql, parameters))
        if "current_database" in sql:
            return _Result(scalar="situacao_saude")
        if "quote_literal" in sql:
            return _Result(scalar="'a''b\\c$$d'")
        if "FROM pg_roles" in sql:
            return _Result(row=(1,) if self.role_exists else None)
        return _Result()


def test_provisionamento_nao_interpela_senha_em_bloco_do_postgres():
    connection = _Connection()

    provision_grafana_role(connection, "grafana_ro", "a'b\\c$$d")

    role_sql = connection.statements[3][0]
    assert "CREATE ROLE \"grafana_ro\"" in role_sql
    assert "PASSWORD 'a''b\\c$$d'" in role_sql
    assert "DO $$" not in role_sql
    assert connection.statements[1][1] == {"password": "a'b\\c$$d"}


def test_provisionamento_reconcilia_role_existente():
    connection = _Connection(role_exists=True)

    provision_grafana_role(connection, "grafana_ro", "strong-secret")

    assert "ALTER ROLE \"grafana_ro\"" in connection.statements[3][0]
