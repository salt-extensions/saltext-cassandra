{% set repositories = salt['pillar.get']('cassandra:repositories', []) %}
{% for repository in repositories %}
{% set params = {'name': repository['name']} %}
{% set _ = params.update(repository.get('options', {})) %}
cassandra_repository_{{ loop.index }}:
  pkgrepo.managed:
    {{ params | dict_to_sls_yaml_params | indent(4) }}
{% endfor %}
