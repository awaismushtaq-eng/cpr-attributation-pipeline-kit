{% macro normalize_channel(column_name) -%}
  lower(trim({{ column_name }}))
{%- endmacro %}

{% macro is_known_channel(expr) -%}
  {{ expr }} in (
    'youtube', 'twitter', 'instagram', 'newsletter',
    'podcast', 'blog', 'organic', 'referral'
  )
{%- endmacro %}

{# Prefer explicit touch → utm_source → channel-like referral → unknown #}
{% macro resolve_channel(touch_col, utm_col, referral_col) -%}
  coalesce(
    case when {{ is_known_channel(touch_col) }} then {{ touch_col }} end,
    case when {{ is_known_channel(utm_col) }} then {{ utm_col }} end,
    case
      when {{ referral_col }} in (
        'youtube', 'twitter', 'instagram', 'newsletter',
        'podcast', 'blog', 'organic', 'referral'
      ) then {{ referral_col }}
    end,
    'unknown'
  )
{%- endmacro %}
