{% set zones = salt['pillar.get']('cassandra:firewall_zones', []) %}
{% for zone in zones %}
{% set params = {'name': zone.get('name', 'public')} %}
{% for option in ('ports', 'services', 'sources', 'interfaces', 'rich_rules') %}
{% if zone.get(option) %}
{% set _ = params.update({option: zone[option]}) %}
{% endif %}
{% endfor %}
cassandra_firewall_zone_{{ loop.index }}:
  firewalld.present:
    {{ params | dict_to_sls_yaml_params | indent(4) }}
{% endfor %}
