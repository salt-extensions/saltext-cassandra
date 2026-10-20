"""Unit tests for Cassandra node administration functions."""

from unittest.mock import MagicMock

import pytest
from salt.exceptions import CommandExecutionError

import saltext.cassandra.modules.cassandra_admin as cassandra_admin


@pytest.fixture
def configure_loader_modules():
    return {
        cassandra_admin: {
            "__salt__": {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": "ok"})}
        }
    }


def test_nodetool_uses_argv_without_shell(configure_loader_modules):
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


def test_nodetool_reports_nonzero_exit(configure_loader_modules):
    cassandra_admin.__salt__["cmd.run_all"].return_value = {
        "retcode": 2,
        "stderr": "repair failed",
    }
    with pytest.raises(CommandExecutionError, match="repair failed"):
        cassandra_admin.nodetool("repair", nodetool_path="/usr/bin/nodetool")


def test_status_parses_cluster_output(configure_loader_modules):
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
