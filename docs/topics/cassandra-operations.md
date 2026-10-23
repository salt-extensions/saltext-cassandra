# Cassandra operations with Salt

This extension exposes Cassandra operations through Salt's CQL execution
module, Cassandra resource states, and the native `nodetool` command line.

## Resource states

The `cassandra` state module checks cluster health and can ensure keyspaces,
tables, and roles are present or absent. The execution module must be installed
on a minion that can connect to Cassandra, and the DataStax Python driver must
be installed there. Connection settings can be supplied through the existing
`cassandra` minion configuration or pillar options documented by
`cassandra_cql`.

```text
application_keyspace:
  cassandra.keyspace_present:
    - replication:
        class: NetworkTopologyStrategy
        dc1: 3
    - durable_writes: true

events_table:
  cassandra.table_present:
    - keyspace: application
    - create_statement: >-
        CREATE TABLE application.events (
          id uuid PRIMARY KEY,
          payload text
        )

application_reader:
  cassandra.role_present:
    - password: {{ pillar['application_reader_password'] | yaml_dquote }}
    - login: true
    - superuser: false
```

Keyspace options are compared and changed with `ALTER KEYSPACE`. Table states
ensure existence and use the CQL statement only when creating a missing table;
they do not compare an existing table's complete schema. Cassandra does not
return stored role passwords, so a role state cannot detect password drift. It
does not change an existing password; use an explicit secret rotation action
for that. Dropping keyspaces and tables deletes their contained data.

All seven state functions honor Salt test mode. They perform read queries to
determine current state but do not execute a write query in test mode.

## Node administration

`cassandra_admin.nodetool` runs an installed Cassandra nodetool command using
an argument vector with shell execution disabled. This covers operational
commands such as repair, drain, flush, compaction, decommission, status,
streaming, and configuration toggles. The operation is imperative; Salt test
mode does not suppress it. JMX passwords are accepted only through a password
file path so the secret is not placed in process arguments.

`cassandra_admin.status` parses cluster membership into node records. For
commands not covered by the structured status helper, call `nodetool` with the
Cassandra command and its arguments:

```yaml
check_cassandra_status:
  module.run:
    - name: cassandra_admin.status

repair_application_keyspace:
  module.run:
    - name: cassandra_admin.nodetool
    - command: repair
    - arguments:
      - application
```

The `cassandra_cql.cql_query` function is the general CQL execution interface.
Use it for schema checks and CQL operations that need a specific query. CQL is
sent through the DataStax driver; `cqlsh` itself is not required.

## Server configuration

Salt's existing state modules can manage the operating system and Cassandra
service around these Cassandra-specific APIs:

| Concern | Salt state modules |
| --- | --- |
| Cassandra package installation | `pkg.installed` |
| Cassandra package repository | `pkgrepo.managed`, where supported by the platform |
| Cassandra configuration files | `file.managed` |
| Cassandra service lifecycle | `service.running` and `service.dead` |
| Kernel and OS tuning | `sysctl.present`, `file.managed`, and platform-specific states |
| Firewall rules | A provider-specific state such as `firewalld.present` or `nftables` |

Package names, repository URLs, configuration paths, service names, and
firewall providers vary by operating system and Cassandra distribution. A
configurable Salt formula example is in the repository's
`examples/cassandra/` directory; copy it into a fileserver state tree and
provide the documented Pillar values.

The `cassandra.cluster_healthy` state checks for Up/Normal nodes and retries
within the specified poll limit. It counts every node outside Up/Normal as
unhealthy. Schema-version validation remains an operator decision based on
Cassandra's reported schema information. Role permissions can be queried and
granted with `cassandra_cql.list_permissions` and
`cassandra_cql.grant_permission`; there is no declarative permission state or
permission revocation function in this API.
