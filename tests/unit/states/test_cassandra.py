"""Tests for Cassandra resource states."""

from unittest.mock import MagicMock

import pytest

import saltext.cassandra.states.cassandra as cassandra_state


@pytest.fixture
def configure_loader_modules():
    return {
        cassandra_state: {
            "__opts__": {"test": False},
            "__salt__": {
                "cassandra_cql.cql_query": MagicMock(return_value=[]),
                "cassandra_cql.list_keyspaces": MagicMock(return_value=[]),
                "cassandra_cql.keyspace_exists": MagicMock(return_value=False),
                "cassandra_admin.status": MagicMock(return_value=[]),
            },
        }
    }


pytestmark = pytest.mark.usefixtures("configure_loader_modules")


def _salt():
    return cassandra_state.__salt__


def test_keyspace_present_creates_if_missing():
    result = cassandra_state.keyspace_present(
        "app", {"class": "SimpleStrategy", "replication_factor": 2}
    )
    assert result["result"] is True
    assert result["changes"]["new"]["replication"]["replication_factor"] == "2"
    assert "CREATE KEYSPACE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_keyspace_present_test_mode_does_not_write():
    cassandra_state.__opts__["test"] = True
    result = cassandra_state.keyspace_present("app", {"class": "SimpleStrategy"})
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


def test_keyspace_present_is_unchanged_when_options_match():
    _salt()["cassandra_cql.cql_query"].return_value = [
        {
            "keyspace_name": "app",
            "replication": {"class": "SimpleStrategy", "replication_factor": "2"},
            "durable_writes": True,
        }
    ]
    result = cassandra_state.keyspace_present(
        "app", {"class": "SimpleStrategy", "replication_factor": 2}
    )
    assert result["changes"] == {}


def test_keyspace_present_updates_options():
    _salt()["cassandra_cql.cql_query"].return_value = [
        {
            "keyspace_name": "app",
            "replication": {"class": "SimpleStrategy", "replication_factor": "1"},
            "durable_writes": True,
        }
    ]
    result = cassandra_state.keyspace_present(
        "app",
        {"class": "SimpleStrategy", "replication_factor": 2},
        durable_writes=False,
    )
    assert result["result"] is True
    assert "ALTER KEYSPACE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_keyspace_present_update_test_mode():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.cql_query"].return_value = [
        {
            "keyspace_name": "app",
            "replication": {"class": "SimpleStrategy", "replication_factor": "1"},
            "durable_writes": True,
        }
    ]
    result = cassandra_state.keyspace_present("app", {"class": "SimpleStrategy"})
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


@pytest.mark.parametrize(
    "replication,durable_writes",
    [
        ({}, True),
        ({"replication_factor": 2}, True),
        ({"class": object()}, True),
        ({"class": "x"}, 1),
    ],
)
def test_keyspace_present_rejects_invalid_options(replication, durable_writes):
    result = cassandra_state.keyspace_present("app", replication, durable_writes)
    assert result["result"] is False


def test_keyspace_absent_is_noop_when_missing():
    result = cassandra_state.keyspace_absent("app")
    assert result["result"] is True
    assert _salt()["cassandra_cql.cql_query"].call_count == 0


def test_keyspace_absent_test_mode_does_not_drop():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.keyspace_exists"].return_value = True
    result = cassandra_state.keyspace_absent("app")
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 0


def test_keyspace_absent_drops_existing_keyspace():
    _salt()["cassandra_cql.keyspace_exists"].return_value = True
    result = cassandra_state.keyspace_absent("app")
    assert result["result"] is True
    assert "DROP KEYSPACE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_table_present_creates_and_test_mode():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.keyspace_exists"].return_value = True
    result = cassandra_state.table_present(
        "events", "app", "CREATE TABLE app.events (id uuid PRIMARY KEY)"
    )
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


def test_table_present_rejects_non_create_statement():
    result = cassandra_state.table_present("events", "app", "DROP TABLE app.events")
    assert result["result"] is False
    assert _salt()["cassandra_cql.cql_query"].call_count == 0


def test_table_present_rejects_missing_keyspace():
    result = cassandra_state.table_present("events", "missing", "CREATE TABLE events (id int)")
    assert result["result"] is False


def test_table_present_is_unchanged_when_table_exists():
    _salt()["cassandra_cql.keyspace_exists"].return_value = True
    _salt()["cassandra_cql.cql_query"].return_value = [{"table_name": "events"}]
    result = cassandra_state.table_present("events", "app", "CREATE TABLE events (id int)")
    assert result["result"] is True
    assert result["changes"] == {}


def test_table_present_creates_missing_table():
    _salt()["cassandra_cql.keyspace_exists"].return_value = True
    result = cassandra_state.table_present("events", "app", "CREATE TABLE events (id int)")
    assert result["result"] is True
    assert _salt()["cassandra_cql.cql_query"].call_count == 2


def test_table_absent_executes_only_when_present():
    _salt()["cassandra_cql.cql_query"].return_value = [{"table_name": "events"}]
    result = cassandra_state.table_absent("events", "app")
    assert result["result"] is True
    assert "DROP TABLE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_table_absent_test_mode_does_not_drop():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.cql_query"].return_value = [{"table_name": "events"}]
    result = cassandra_state.table_absent("events", "app")
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


def test_table_absent_is_noop_when_missing():
    result = cassandra_state.table_absent("events", "app")
    assert result["result"] is True
    assert result["changes"] == {}


def test_role_present_does_not_include_password_in_changes():
    result = cassandra_state.role_present("app_reader", "secret")
    assert result["result"] is True
    assert "secret" not in repr(result)
    assert "secret" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_role_present_existing_flags_are_updated():
    _salt()["cassandra_cql.cql_query"].return_value = [
        {"role": "reader", "can_login": False, "is_superuser": False}
    ]
    result = cassandra_state.role_present("reader", login=True)
    assert result["result"] is True
    assert "ALTER ROLE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_role_present_existing_flags_test_mode():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.cql_query"].return_value = [
        {"role": "reader", "can_login": False, "is_superuser": False}
    ]
    result = cassandra_state.role_present("reader", login=True)
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


@pytest.mark.parametrize(
    "password,login,superuser",
    [(None, "yes", False), (1, True, False), (None, True, 1)],
)
def test_role_present_rejects_invalid_options(password, login, superuser):
    result = cassandra_state.role_present("reader", password, login, superuser)
    assert result["result"] is False


def test_role_present_test_mode_reports_creation():
    cassandra_state.__opts__["test"] = True
    result = cassandra_state.role_present("reader", "secret")
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


def test_role_present_requires_password_for_new_login_role():
    result = cassandra_state.role_present("reader")
    assert result["result"] is False


def test_role_present_can_create_non_login_role_without_password():
    result = cassandra_state.role_present("reader_group", login=False)
    assert result["result"] is True
    assert "CREATE ROLE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]
    assert "PASSWORD" not in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_role_absent_drops_existing_role():
    _salt()["cassandra_cql.cql_query"].return_value = [{"role": "old"}]
    result = cassandra_state.role_absent("old")
    assert result["result"] is True
    assert "DROP ROLE" in _salt()["cassandra_cql.cql_query"].call_args.args[0]


def test_role_absent_test_mode_does_not_drop():
    cassandra_state.__opts__["test"] = True
    _salt()["cassandra_cql.cql_query"].return_value = [{"role": "old"}]
    result = cassandra_state.role_absent("old")
    assert result["result"] is None
    assert _salt()["cassandra_cql.cql_query"].call_count == 1


def test_role_absent_is_noop_when_missing():
    result = cassandra_state.role_absent("old")
    assert result["result"] is True
    assert result["changes"] == {}


def test_cluster_healthy_accepts_up_normal_nodes():
    _salt()["cassandra_admin.status"].return_value = [
        {"status": "U", "state": "N", "address": "10.0.0.1"}
    ]
    result = cassandra_state.cluster_healthy("cluster")
    assert result["result"] is True
    assert result["changes"] == {}


def test_cluster_healthy_allows_configured_unhealthy_count():
    _salt()["cassandra_admin.status"].return_value = [
        {"status": "D", "state": "N", "address": "10.0.0.2"}
    ]
    result = cassandra_state.cluster_healthy("cluster", max_unhealthy_nodes=1)
    assert result["result"] is True


def test_cluster_healthy_retries_then_succeeds(monkeypatch):
    status = _salt()["cassandra_admin.status"]
    status.side_effect = [
        [{"status": "U", "state": "J", "address": "10.0.0.1"}],
        [{"status": "U", "state": "N", "address": "10.0.0.1"}],
    ]
    sleep = MagicMock()
    monkeypatch.setattr(cassandra_state.time, "sleep", sleep)
    result = cassandra_state.cluster_healthy("cluster", polls=2, interval=5)
    assert result["result"] is True
    sleep.assert_called_once_with(5)


def test_cluster_healthy_fails_after_poll_limit(monkeypatch):
    _salt()["cassandra_admin.status"].return_value = [
        {"status": "D", "state": "N", "address": "10.0.0.2"}
    ]
    monkeypatch.setattr(cassandra_state.time, "sleep", lambda _: None)
    result = cassandra_state.cluster_healthy("cluster", polls=2, interval=0)
    assert result["result"] is False
    assert "10.0.0.2" in result["comment"]


def test_cluster_healthy_rejects_invalid_limits():
    result = cassandra_state.cluster_healthy("cluster", polls=0)
    assert result["result"] is False


@pytest.mark.parametrize(
    "status_result",
    [None, ["not a node"], [{"unparsed": ["unexpected output"]}], []],
)
def test_cluster_healthy_rejects_invalid_status_data(status_result):
    _salt()["cassandra_admin.status"].return_value = status_result
    result = cassandra_state.cluster_healthy("cluster")
    assert result["result"] is False
