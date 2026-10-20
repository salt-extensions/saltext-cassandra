{% set config = salt['pillar.get']('cassandra', {}) %}
{% set repositories = salt['pillar.get']('cassandra:repositories', []) %}
cassandra_package:
  pkg.installed:
    - name: {{ config.get('package', 'cassandra') | yaml_dquote }}
{% if repositories %}
    - require:
{% for repository in repositories %}
      - pkgrepo: cassandra_repository_{{ loop.index }}
{% endfor %}
{% endif %}

{% if config.get('config_path') and config.get('config_source') %}
cassandra_configuration:
  file.managed:
    - name: {{ config['config_path'] | yaml_dquote }}
    - source: {{ config['config_source'] | yaml_dquote }}
    - require:
      - pkg: cassandra_package
{% endif %}

cassandra_service:
  service.running:
    - name: {{ config.get('service', 'cassandra') | yaml_dquote }}
    - enable: true
    - require:
      - pkg: cassandra_package
{% if config.get('config_path') and config.get('config_source') %}
      - file: cassandra_configuration
{% endif %}
