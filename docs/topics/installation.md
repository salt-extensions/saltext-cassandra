# Installation

Generally, extensions need to be installed into the same Python environment Salt uses.

:::{tab} State
```yaml
Install Salt Cassandra extension:
  pip.installed:
    - name: saltext-cassandra
```
:::

:::{tab} Onedir installation
```bash
salt-pip install saltext-cassandra
```
:::

:::{tab} Regular installation
```bash
pip install saltext-cassandra
```
:::

For Cassandra CQL access and the resource states, install the DataStax Python
driver in the same environment as Salt:

```bash
salt-pip install 'saltext-cassandra[cassandra]'
```

:::{hint}
Saltexts are not distributed automatically via the fileserver like custom modules, they need to be installed
on each node you want them to be available on.
:::
