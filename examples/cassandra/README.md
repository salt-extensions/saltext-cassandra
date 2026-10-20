# Cassandra server formula example

Copy this directory into a Salt fileserver state tree under `cassandra/` and
configure the target platform through Pillar. Apply it with:

```bash
salt 'cassandra-*' state.apply cassandra
```

Example Pillar data:

```yaml
cassandra:
  package: cassandra
  service: cassandra
  config_path: /etc/cassandra/cassandra.yaml
  config_source: salt://cassandra/files/cassandra.yaml
  repositories:
    - name: deb https://example.invalid/cassandra stable main
      options:
        dist: stable
        file: /etc/apt/sources.list.d/cassandra.list
        key_url: https://example.invalid/cassandra-signing-key.asc
  sysctls:
    vm.max_map_count: 1048575
  firewall_zones:
    - name: public
      ports:
        - 9042/tcp
```

The repository options must match the operating system. The firewall example
uses Salt's `firewalld` state and requires firewalld; replace that SLS with the
configured provider's state on systems using another firewall. This example
separates package repository, kernel tuning, firewall, package, configuration file, and service management
into native Salt states. It does not encode Cassandra role defaults for every
distribution; review the rendered states and adapt the Pillar data to the
target environment.
