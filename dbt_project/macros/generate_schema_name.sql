{% macro generate_schema_name(custom_schema_name, node) -%}
  {#- Use custom schemas as-is (staging / intermediate / marts) -#}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
