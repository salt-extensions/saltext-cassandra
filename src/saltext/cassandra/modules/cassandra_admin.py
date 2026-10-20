"""Cassandra node administration through the native nodetool interface."""

import re

import salt.utils.path
from salt.exceptions import CommandExecutionError


__virtualname__ = "cassandra_admin"


def __virtual__():
    """Load when Salt's command execution function is available."""
    if "cmd.run_all" not in __salt__:
        return False, "cmd.run_all is required"
    return __virtualname__


def nodetool(
    command,
    arguments=None,
    nodetool_path=None,
    host=None,
    port=None,
    username=None,
    password_file=None,
    flags=None,
):
    """Run one Cassandra nodetool command and return its output.

    Args:
        command (str): A single nodetool command name, such as ``status`` or
            ``repair``.
        arguments (list[str]): Positional command arguments. Defaults to an empty
            list. Each argument is passed as one argv item; shell expansion is
            never used.
        nodetool_path (str): Optional path to the nodetool executable. If
            omitted, Salt searches ``PATH``.
        host (str): Optional JMX host.
        port (int): Optional JMX port.
        username (str): Optional JMX username.
        password_file (str): Optional path to a JMX password file. Passwords
            are not accepted directly, avoiding exposure in process arguments.
        flags (list[str]): Optional nodetool options placed before the command.

    Returns:
        dict: ``retcode``, ``stdout``, ``stderr``, and the executed argv.

    Raises:
        CommandExecutionError: If the executable is missing, inputs are invalid,
            or nodetool exits unsuccessfully.

    This is an imperative operation. Its effects depend on the selected
    nodetool command, and Salt test mode does not prevent execution.

    CLI Example:

    .. code-block:: bash

        salt 'cassandra-*' cassandra_admin.nodetool status
        salt 'cassandra-1' cassandra_admin.nodetool repair arguments='["my_keyspace"]'
    """
    if not isinstance(command, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", command):
        raise CommandExecutionError("command must be a nodetool command name")
    arguments = [] if arguments is None else arguments
    flags = [] if flags is None else flags
    if not isinstance(arguments, (list, tuple)) or not all(
        isinstance(item, str) for item in arguments
    ):
        raise CommandExecutionError("arguments must be a list of strings")
    if not isinstance(flags, (list, tuple)) or not all(isinstance(item, str) for item in flags):
        raise CommandExecutionError("flags must be a list of strings")

    executable = nodetool_path or salt.utils.path.which("nodetool")
    if not executable:
        raise CommandExecutionError("Could not find the nodetool executable")

    argv = [executable]
    argv.extend(flags)
    if host:
        argv.extend(["--host", str(host)])
    if port is not None:
        argv.extend(["--port", str(port)])
    if username:
        argv.extend(["--username", str(username)])
    if password_file:
        argv.extend(["--password-file", str(password_file)])
    argv.append(command)
    argv.extend(arguments)

    result = __salt__["cmd.run_all"](argv, python_shell=False)
    if result.get("retcode", 0):
        message = result.get("stderr") or result.get("stdout") or "nodetool failed"
        raise CommandExecutionError(
            f"nodetool {command} failed with exit code {result['retcode']}: {message}"
        )
    return {
        "retcode": result.get("retcode", 0),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "argv": argv,
    }


def status(keyspace=None, **kwargs):
    """Return Cassandra cluster membership from ``nodetool status``.

    Args:
        keyspace (str): Optional keyspace used to scope the status command.
        **kwargs: Connection and executable options accepted by :func:`nodetool`.

    Returns:
        list[dict]: Nodes with datacenter, status, state, address, load, tokens,
        ownership, host ID, and rack fields. If Cassandra changes the output
        format, unparsed lines are returned under ``unparsed``.

    This function is read-only. Salt test mode has no effect.

    CLI Example:

    .. code-block:: bash

        salt 'cassandra-1' cassandra_admin.status
    """
    args = [keyspace] if keyspace else None
    output = nodetool("status", arguments=args, **kwargs)["stdout"]
    nodes = []
    datacenter = None
    unparsed = []
    for line in output.splitlines():
        line = line.strip()
        if (
            not line
            or line.startswith("====")
            or line.startswith("Status=")
            or line.startswith("|/")
        ):
            continue
        if line.startswith("Datacenter:"):
            datacenter = line.split(":", 1)[1].strip()
            continue
        fields = re.match(
            r"^([UD])([NLMJ])\s+(\S+)\s+(.+?)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)$",
            line,
        )
        if fields:
            nodes.append(
                {
                    "datacenter": datacenter,
                    "status": fields.group(1),
                    "state": fields.group(2),
                    "address": fields.group(3),
                    "load": fields.group(4),
                    "tokens": fields.group(5),
                    "ownership": fields.group(6),
                    "host_id": fields.group(7),
                    "rack": fields.group(8),
                }
            )
        elif not line.startswith("--"):
            unparsed.append(line)
    if unparsed:
        nodes.append({"unparsed": unparsed})
    return nodes
