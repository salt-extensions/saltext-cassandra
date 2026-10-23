"""Security-focused tests for Cassandra CQL diagnostics."""

from unittest.mock import MagicMock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.cassandra.modules import cassandra_cql


def test_redact_query_password_literals():
    query = "CREATE ROLE reader WITH PASSWORD = 'secret''value' AND LOGIN = true"
    assert cassandra_cql._redact_query(query) == (
        "CREATE ROLE reader WITH PASSWORD = '<redacted>' AND LOGIN = true"
    )


def test_redact_hashed_password_literals():
    query = "ALTER ROLE reader WITH HASHED PASSWORD = 'digest'"
    assert cassandra_cql._redact_query(query) == (
        "ALTER ROLE reader WITH HASHED PASSWORD = '<redacted>'"
    )


def test_redact_query_does_not_change_non_password_literals():
    query = "SELECT * FROM system.local WHERE dc = 'secret'"
    assert cassandra_cql._redact_query(query) == query


def test_failed_password_query_redacts_error_and_log(monkeypatch, caplog):
    query = "CREATE ROLE reader WITH PASSWORD = 'secret' AND LOGIN = true"
    session = MagicMock()
    session.execute.side_effect = RuntimeError(query)
    monkeypatch.setattr(cassandra_cql, "dict_factory", object(), raising=False)
    monkeypatch.setattr(cassandra_cql, "_connect", lambda **kwargs: (None, session))

    with pytest.raises(CommandExecutionError) as exc:
        cassandra_cql.cql_query(query)

    assert "secret" not in str(exc.value)
    assert "secret" not in caplog.text
    assert "<redacted>" in caplog.text
