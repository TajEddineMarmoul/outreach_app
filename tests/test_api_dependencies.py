from __future__ import annotations

from unittest.mock import MagicMock

from api import deps


def test_request_connection_does_not_run_schema_setup(monkeypatch):
    connection = MagicMock()
    connect = MagicMock(return_value=connection)
    init_db = MagicMock()
    monkeypatch.setattr(deps.db, "connect", connect)
    monkeypatch.setattr(deps.db, "init_db", init_db)

    dependency = deps.get_db()
    assert next(dependency) is connection
    dependency.close()

    connect.assert_called_once_with()
    init_db.assert_not_called()
    connection.close.assert_called_once_with()
