"""Unit tests for Cassandra node administration functions."""

from unittest.mock import MagicMock

import pytest
from salt.exceptions import CommandExecutionError

from saltext.cassandra.modules import cassandra_admin


@pytest.fixture
def configure_loader_modules():
    return {
        cassandra_admin: {
            "__salt__": {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": "ok"})}
        }
    }


pytestmark = pytest.mark.usefixtures("configure_loader_modules")


def test_nodetool_uses_argv_without_shell():
    run_all = cassandra_admin.__salt__["cmd.run_all"]
    result = cassandra_admin.nodetool(
        "repair",
        ["app", "table;touch /tmp/no"],
        nodetool_path="/usr/bin/nodetool",
        host="db1",
        port=7199,
    )

    assert result["retcode"] == 0
    argv = run_all.call_args.args[0]
    assert argv[-2:] == ["app", "table;touch /tmp/no"]
    assert run_all.call_args.kwargs["python_shell"] is False


def test_nodetool_rejects_invalid_command():
    with pytest.raises(CommandExecutionError):
        cassandra_admin.nodetool("repair;touch /tmp/no", nodetool_path="/usr/bin/nodetool")


def test_nodetool_rejects_non_string_arguments():
    with pytest.raises(CommandExecutionError):
        cassandra_admin.nodetool("repair", ["app", 4], nodetool_path="/usr/bin/nodetool")


@pytest.mark.parametrize("arguments", ["app", [1]])
def test_nodetool_rejects_invalid_arguments(arguments):
    with pytest.raises(CommandExecutionError, match="arguments must be a list"):
        cassandra_admin.nodetool("repair", arguments, nodetool_path="/usr/bin/nodetool")


@pytest.mark.parametrize("flags", ["--verbose", [1]])
def test_nodetool_rejects_invalid_flags(flags):
    with pytest.raises(CommandExecutionError, match="flags must be a list"):
        cassandra_admin.nodetool("repair", flags=flags, nodetool_path="/usr/bin/nodetool")


def test_nodetool_requires_executable(monkeypatch):
    monkeypatch.setattr(cassandra_admin.salt.utils.path, "which", lambda _: None)
    with pytest.raises(CommandExecutionError, match="Could not find"):
        cassandra_admin.nodetool("repair")


def test_nodetool_builds_optional_connection_arguments():
    result = cassandra_admin.nodetool(
        "repair",
        nodetool_path="/usr/bin/nodetool",
        flags=["-Dfoo=bar"],
        host="db1",
        port=7199,
        username="admin",
        password_file="/tmp/jmx.password",
    )
    assert result["argv"] == [
        "/usr/bin/nodetool",
        "-Dfoo=bar",
        "--host",
        "db1",
        "--port",
        "7199",
        "--username",
        "admin",
        "--password-file",
        "/tmp/jmx.password",
        "repair",
    ]


def test_nodetool_reports_nonzero_exit():
    cassandra_admin.__salt__["cmd.run_all"].return_value = {
        "retcode": 2,
        "stderr": "repair failed",
    }
    with pytest.raises(CommandExecutionError, match="repair failed"):
        cassandra_admin.nodetool("repair", nodetool_path="/usr/bin/nodetool")


@pytest.mark.parametrize(
    "result",
    [{"retcode": 1, "stdout": "failure"}, {"retcode": 1}, {"retcode": 0}],
)
def test_nodetool_error_fallbacks_and_empty_output(result):
    cassandra_admin.__salt__["cmd.run_all"].return_value = result
    if result.get("retcode"):
        expected = result.get("stderr") or result.get("stdout") or "nodetool failed"
        with pytest.raises(CommandExecutionError, match=expected):
            cassandra_admin.nodetool("repair", nodetool_path="/usr/bin/nodetool")
    else:
        response = cassandra_admin.nodetool("repair", nodetool_path="/usr/bin/nodetool")
        assert response["stdout"] == ""
        assert response["stderr"] == ""


def test_status_parses_cluster_output():
    cassandra_admin.__salt__["cmd.run_all"].return_value = {
        "retcode": 0,
        "stdout": (
            "Datacenter: dc1\n"
            "=======================\n"
            "Status=Up/Down\n"
            "|/ State=Normal/Leaving/Joining/Moving\n"
            "-- Address Load Tokens Owns Host ID Rack\n"
            "UN 10.0.0.1 1.0 GiB 16 100% host-id rack1\n"
        ),
    }
    assert cassandra_admin.status(nodetool_path="/usr/bin/nodetool") == [
        {
            "datacenter": "dc1",
            "status": "U",
            "state": "N",
            "address": "10.0.0.1",
            "load": "1.0 GiB",
            "tokens": "16",
            "ownership": "100%",
            "host_id": "host-id",
            "rack": "rack1",
        }
    ]


def test_status_returns_unparsed_lines_and_skips_headers():
    cassandra_admin.__salt__["cmd.run_all"].return_value = {
        "retcode": 0,
        "stdout": "\n-- heading\nDatacenter: dc1\nnew-format node data\n",
    }
    assert cassandra_admin.status(nodetool_path="/usr/bin/nodetool") == [
        {"unparsed": ["new-format node data"]}
    ]


def test_status_passes_optional_keyspace():
    cassandra_admin.status("app", nodetool_path="/usr/bin/nodetool")
    assert cassandra_admin.__salt__["cmd.run_all"].call_args.args[0][-2:] == ["status", "app"]
