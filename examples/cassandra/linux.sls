{% set settings = salt['pillar.get']('cassandra:sysctls', {}) %}
{% for key, value in settings.items() %}
cassandra_sysctl_{{ loop.index }}:
  sysctl.present:
    - name: {{ key | yaml_dquote }}
    - value: {{ value | yaml_encode }}
{% endfor %}
