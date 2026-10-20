# Cassandra operations with Salt

This extension exposes Cassandra operations through Salt's CQL execution
module, Cassandra resource states, and the native `nodetool` command line. The
API is designed around Cassandra resources and tools. It does not aim to
preserve Ansible task contracts.

## Resource states

The `cassandra` state module checks cluster health and can ensure keyspaces,
tables, and roles are present or absent. The execution module must be installed on a minion that can
connect to Cassandra, and the DataStax Python driver must be installed there.
Connection settings can be supplied through the existing `cassandra` minion
configuration or pillar options documented by `cassandra_cql`.

```yaml
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

`cassandra_admin.nodetool` runs any installed Cassandra nodetool command using
an argument vector with shell execution disabled. This covers operational
commands such as repair, drain, flush, compaction, decommission, status,
streaming, and configuration toggles without binding the extension to one
Cassandra release's full nodetool command list. The operation is imperative;
Salt test mode does not suppress it. JMX passwords are accepted only through a
password file path so the secret is not placed in process arguments.

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

The existing `cassandra_cql.cql_query` function remains the general CQL
execution interface. Use it for schema checks and CQL operations that need a
specific query. CQL is sent through the DataStax driver; `cqlsh` itself is not
required.

## Translating server setup

The collection's server setup tasks map to existing Salt state modules, keeping
package and OS policy in the formula that owns the target platform:

| Server setup concern | Salt building blocks |
| --- | --- |
| Cassandra package installation | `pkg.installed` |
| Cassandra package repository | `pkgrepo.managed`, where supported by the platform |
| Cassandra configuration files | `file.managed` |
| Cassandra service lifecycle | `service.running` and `service.dead` |
| Kernel and OS tuning | `sysctl.present`, `file.managed`, and platform-specific states |
| Firewall rules | A provider-specific Salt state such as `firewalld.present` or `nftables` |

These are deployment choices rather than extension-specific Cassandra states.
Package names, repository URLs, configuration paths, service names, and
firewall providers vary by operating system and Cassandra distribution.
This guide does not supply a single distro-independent replacement for the
`cassandra_install`, `cassandra_repository`, `cassandra_linux`, or
`cassandra_firewall` roles; those role defaults and platform branches must be
encoded in the target formula. A configurable Salt formula example is in
[`examples/cassandra/`](../../examples/cassandra/README.md); copy it into a
fileserver state tree and provide the documented Pillar values.

## Operation mapping

Node-local operational modules map to their Cassandra `nodetool` commands.
The node operation modules `cassandra_assassinate`, `cassandra_autocompaction`,
`cassandra_backup`, `cassandra_batchlogreplaythrottle`, `cassandra_binary`,
`cassandra_cleanup`, `cassandra_concurrency`, `cassandra_compact`,
`cassandra_compactionthreshold`, `cassandra_compactionthroughput`,
`cassandra_decommission`, `cassandra_drain`, `cassandra_flush`,
`cassandra_fullquerylog`, `cassandra_garbagecollect`, `cassandra_gossip`,
`cassandra_handoff`, `cassandra_interdcstreamthroughput`,
`cassandra_invalidatecache`, `cassandra_maxhintwindow`, `cassandra_netstats`,
`cassandra_reload`, `cassandra_removenode`, `cassandra_schema`,
`cassandra_streamthroughput`,
`cassandra_thrift`, `cassandra_timeout`, `cassandra_traceprobability`,
`cassandra_truncatehints`, `cassandra_upgradesstables`, and `cassandra_verify`
map to their matching Cassandra `nodetool` commands through
`cassandra_admin.nodetool`. For example, `cassandra_assassinate` maps to
`assassinate`, `cassandra_decommission` to `decommission`, and
`cassandra_flush` to `flush`. `cassandra_stopdaemon` maps to Salt's
`service.dead`. `cassandra_status` maps to the structured
`cassandra_admin.status` query. `cassandra_cqlsh` maps to the existing
`cassandra_cql.cql_query` function. CQL resource operations map to
`cassandra.keyspace_present`/`keyspace_absent`,
`cassandra.table_present`/`table_absent`, and
`cassandra.role_present`/`role_absent`. The exact supported command arguments
remain those of the Cassandra version installed on the minion; consult
`nodetool help <command>` on that node.

The status operation's polling interval and tolerated-down-node threshold map
to `cassandra.cluster_healthy`, which checks for Up/Normal nodes and retries
within the specified poll limit. This state counts every node outside Up/Normal
as unhealthy. Schema-version
validation likewise remains an operator decision based on Cassandra's reported
schema information. Role permissions can be queried and granted with the
existing `cassandra_cql.list_permissions` and
`cassandra_cql.grant_permission` execution functions, but there is no
declarative permission state or permission revocation function in this API.
