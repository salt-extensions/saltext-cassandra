"""Cassandra health checks and declarative resource states."""

import time

from salt.exceptions import CommandExecutionError

__virtualname__ = "cassandra"


def __virtual__():
    """Load when the Cassandra CQL execution functions are available."""
    required = (
        "cassandra_cql.cql_query",
        "cassandra_cql.keyspace_exists",
        "cassandra_admin.status",
    )
    missing = [name for name in required if name not in __salt__]
    if missing:
        return False, "Missing execution functions: " + ", ".join(missing)
    return __virtualname__


def _ret(name, result, comment, changes=None):
    return {
        "name": name,
        "result": result,
        "comment": comment,
        "changes": changes or {},
    }


def _literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _identifier(value):
    if not isinstance(value, str) or not value:
        raise CommandExecutionError("Cassandra identifiers must be non-empty strings")
    return '"' + value.replace('"', '""') + '"'


def _query(statement):
    return __salt__["cassandra_cql.cql_query"](statement)


def cluster_healthy(name, max_unhealthy_nodes=0, polls=1, interval=30, **connection_args):
    """Check Cassandra membership and wait briefly for nodes to stabilize.

    Args:
        name (str): State identifier used in the return data.
        max_unhealthy_nodes (int): Maximum number of nodes that may be down or
            outside the Up/Normal state. Defaults to ``0``.
        polls (int): Maximum number of status checks. Must be at least ``1``.
            Defaults to ``1``.
        interval (int): Seconds between checks when the cluster is unhealthy.
            Defaults to ``30``.
        **connection_args: Connection options passed to
            :func:`cassandra_admin.status`.

    Returns:
        dict: Standard Salt state return data with no changes. This is a
        read-only check; test mode does not change its behavior.

    Invalid limits return ``result: False``. Status command failures raise
    ``CommandExecutionError`` from the execution module.

    CLI Example:

    .. code-block:: yaml

        cassandra_cluster_ready:
          cassandra.cluster_healthy:
            - max_unhealthy_nodes: 1
            - polls: 3
            - interval: 20
    """
    for key, value, minimum in (
        ("max_unhealthy_nodes", max_unhealthy_nodes, 0),
        ("polls", polls, 1),
        ("interval", interval, 0),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            return _ret(name, False, f"{key} must be an integer greater than or equal to {minimum}")

    nodes = []
    unhealthy = []
    for attempt in range(polls):
        nodes = __salt__["cassandra_admin.status"](**connection_args)
        if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
            return _ret(name, False, "Cassandra status returned invalid node data")
        if any("unparsed" in node for node in nodes):
            return _ret(name, False, "Could not parse all nodetool status output")
        if not nodes:
            return _ret(name, False, "Cassandra status returned no nodes")
        unhealthy = [
            node for node in nodes if node.get("status") != "U" or node.get("state") != "N"
        ]
        if len(unhealthy) <= max_unhealthy_nodes:
            return _ret(name, True, f"Cluster has {len(unhealthy)} unhealthy node(s)")
        if attempt < polls - 1 and interval:
            time.sleep(interval)

    addresses = [node.get("address", "unknown") for node in unhealthy]
    return _ret(
        name,
        False,
        f"Cluster has {len(unhealthy)} unhealthy node(s), limit is {max_unhealthy_nodes}: "
        + ", ".join(addresses),
    )


def keyspace_present(name, replication, durable_writes=True):
    """Ensure a Cassandra keyspace exists with the requested options.

    Args:
        name (str): Keyspace name.
        replication (dict): Replication strategy map, for example
            ``{'class': 'SimpleStrategy', 'replication_factor': 3}``.
        durable_writes (bool): Whether writes use the commit log. Defaults to
            ``True``.

    Returns:
        dict: Standard Salt state return data. Existing keyspaces with matching
        options are unchanged; option differences are reconciled with
        ``ALTER KEYSPACE``. In test mode, reports the required action without
        applying it.

    Invalid arguments return ``result: False``. Cassandra query failures raise
    ``CommandExecutionError`` from the execution module.

    CLI Example:

    .. code-block:: yaml

        app_keyspace:
          cassandra.keyspace_present:
            - replication:
                class: NetworkTopologyStrategy
                dc1: 3
    """
    if not isinstance(durable_writes, bool):
        return _ret(name, False, "durable_writes must be a boolean")
    if not isinstance(replication, dict) or not replication or "class" not in replication:
        return _ret(name, False, "replication must be a non-empty map containing 'class'")
    if not all(isinstance(value, (str, int, bool)) for value in replication.values()):
        return _ret(name, False, "replication values must be strings, integers, or booleans")
    identifier = _identifier(name)
    rows = _query(
        "SELECT keyspace_name, replication, durable_writes FROM system_schema.keyspaces "
        f"WHERE keyspace_name = {_literal(name)}"
    )
    expected = {str(key): str(value) for key, value in replication.items()}
    if rows:
        current = rows[0]
        current_replication = {
            str(key): str(value) for key, value in current["replication"].items()
        }
        needs_change = current_replication != expected or bool(current["durable_writes"]) != bool(
            durable_writes
        )
        if not needs_change:
            return _ret(name, True, "Keyspace is already configured")
        changes = {
            "old": {
                "replication": current_replication,
                "durable_writes": bool(current["durable_writes"]),
            },
            "new": {"replication": expected, "durable_writes": bool(durable_writes)},
        }
        if __opts__.get("test"):
            return _ret(name, None, "Keyspace options would be updated", changes)
        pairs = ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in replication.items())
        _query(
            f"ALTER KEYSPACE {identifier} WITH replication = {{{pairs}}} "
            f"AND durable_writes = {str(bool(durable_writes)).lower()}"
        )
        return _ret(name, True, "Updated keyspace options", changes)

    changes = {"new": {"replication": expected, "durable_writes": bool(durable_writes)}}
    if __opts__.get("test"):
        return _ret(name, None, "Keyspace would be created", changes)
    pairs = ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in replication.items())
    _query(
        f"CREATE KEYSPACE {identifier} WITH replication = {{{pairs}}} "
        f"AND durable_writes = {str(bool(durable_writes)).lower()}"
    )
    return _ret(name, True, "Created keyspace", changes)


def keyspace_absent(name):
    """Ensure a Cassandra keyspace is absent.

    Args:
        name (str): Keyspace name to drop.

    Returns:
        dict: Standard Salt state return data. Dropping a keyspace deletes its
        tables and data. Test mode reports the drop without performing it.

    CLI Example:

    .. code-block:: yaml

        retired_keyspace:
          cassandra.keyspace_absent: []
    """
    _identifier(name)
    rows = __salt__["cassandra_cql.keyspace_exists"](name)
    if not rows:
        return _ret(name, True, "Keyspace is already absent")
    changes = {"old": name, "new": ""}
    if __opts__.get("test"):
        return _ret(name, None, "Keyspace would be dropped", changes)
    _query(f"DROP KEYSPACE {_identifier(name)}")
    return _ret(name, True, "Dropped keyspace", changes)


def table_present(name, keyspace, create_statement):
    """Ensure a table exists, creating it from a CQL definition when absent.

    Args:
        name (str): Table name.
        keyspace (str): Owning keyspace.
        create_statement (str): CQL ``CREATE TABLE`` statement. The statement
            is used only when the table does not exist.

    Returns:
        dict: Standard Salt state return data. This state ensures table
        existence; it does not compare or alter the schema of an existing
        table. Test mode does not execute the create statement.

    CLI Example:

    .. code-block:: yaml

        events_table:
          cassandra.table_present:
            - keyspace: app
            - create_statement: >-
                CREATE TABLE app.events (id uuid PRIMARY KEY, body text)
    """
    _identifier(name)
    _identifier(keyspace)
    if not __salt__["cassandra_cql.keyspace_exists"](keyspace):
        return _ret(name, False, f"Keyspace {keyspace!r} does not exist")
    if not isinstance(create_statement, str) or not create_statement.strip().upper().startswith(
        "CREATE TABLE"
    ):
        return _ret(name, False, "create_statement must be a CREATE TABLE statement")
    rows = _query(
        "SELECT table_name FROM system_schema.tables "
        f"WHERE keyspace_name = {_literal(keyspace)} AND table_name = {_literal(name)}"
    )
    if rows:
        return _ret(name, True, "Table already exists")
    changes = {"new": {"keyspace": keyspace, "table": name}}
    if __opts__.get("test"):
        return _ret(name, None, "Table would be created", changes)
    _query(create_statement)
    return _ret(name, True, "Created table", changes)


def table_absent(name, keyspace):
    """Ensure a Cassandra table is absent.

    Args:
        name (str): Table name to drop.
        keyspace (str): Owning keyspace.

    Returns:
        dict: Standard Salt state return data. Dropping a table deletes its
        data. Test mode reports the drop without performing it.

    CLI Example:

    .. code-block:: yaml

        old_events:
          cassandra.table_absent:
            - keyspace: app
    """
    identifier = f"{_identifier(keyspace)}.{_identifier(name)}"
    rows = _query(
        "SELECT table_name FROM system_schema.tables "
        f"WHERE keyspace_name = {_literal(keyspace)} AND table_name = {_literal(name)}"
    )
    if not rows:
        return _ret(name, True, "Table is already absent")
    changes = {"old": {"keyspace": keyspace, "table": name}, "new": ""}
    if __opts__.get("test"):
        return _ret(name, None, "Table would be dropped", changes)
    _query(f"DROP TABLE {identifier}")
    return _ret(name, True, "Dropped table", changes)


def role_present(name, password=None, login=True, superuser=False):
    """Ensure a Cassandra role exists with the requested login privileges.

    Args:
        name (str): Role name.
        password (str): Password used only when creating the role. Cassandra
            does not expose the stored password for comparison, so this state
            never changes an existing role's password.
        login (bool): Whether the role may authenticate. Defaults to ``True``.
        superuser (bool): Whether the role is a Cassandra superuser. Defaults to
            ``False``.

    Returns:
        dict: Standard Salt state return data. Existing role flags are
        reconciled. Password changes for existing roles are intentionally not
        inferred; use an explicit CQL operation to rotate a password.

    CLI Example:

    .. code-block:: yaml

        app_reader:
          cassandra.role_present:
            - password: {{ pillar['app_reader_password'] | yaml_dquote }}
            - login: true
            - superuser: false
    """
    if not isinstance(login, bool) or not isinstance(superuser, bool):
        return _ret(name, False, "login and superuser must be booleans")
    if password is not None and not isinstance(password, str):
        return _ret(name, False, "password must be a string")
    identifier = _identifier(name)
    rows = _query(
        "SELECT role, can_login, is_superuser FROM system_auth.roles "
        f"WHERE role = {_literal(name)}"
    )
    if rows:
        current = rows[0]
        if bool(current["can_login"]) == bool(login) and bool(current["is_superuser"]) == bool(
            superuser
        ):
            return _ret(name, True, "Role is already configured")
        changes = {
            "old": {
                "login": bool(current["can_login"]),
                "superuser": bool(current["is_superuser"]),
            },
            "new": {"login": bool(login), "superuser": bool(superuser)},
        }
        if __opts__.get("test"):
            return _ret(name, None, "Role flags would be updated", changes)
        _query(
            f"ALTER ROLE {identifier} WITH LOGIN = {str(bool(login)).lower()} "
            f"AND SUPERUSER = {str(bool(superuser)).lower()}"
        )
        return _ret(name, True, "Updated role flags", changes)

    if login and password is None:
        return _ret(name, False, "password is required when creating a role")
    changes = {"new": {"login": bool(login), "superuser": bool(superuser)}}
    if __opts__.get("test"):
        return _ret(name, None, "Role would be created", changes)
    role_options = []
    if password is not None:
        role_options.append(f"PASSWORD = {_literal(password)}")
    role_options.extend(
        [f"LOGIN = {str(bool(login)).lower()}", f"SUPERUSER = {str(bool(superuser)).lower()}"]
    )
    _query(f"CREATE ROLE {identifier} WITH " + " AND ".join(role_options))
    return _ret(name, True, "Created role", changes)


def role_absent(name):
    """Ensure a Cassandra role is absent.

    Args:
        name (str): Role name to drop.

    Returns:
        dict: Standard Salt state return data. Test mode reports the drop
        without performing it.

    CLI Example:

    .. code-block:: yaml

        retired_role:
          cassandra.role_absent: []
    """
    identifier = _identifier(name)
    rows = _query("SELECT role FROM system_auth.roles " f"WHERE role = {_literal(name)}")
    if not rows:
        return _ret(name, True, "Role is already absent")
    changes = {"old": name, "new": ""}
    if __opts__.get("test"):
        return _ret(name, None, "Role would be dropped", changes)
    _query(f"DROP ROLE {identifier}")
    return _ret(name, True, "Dropped role", changes)
