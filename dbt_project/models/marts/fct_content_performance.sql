{{ config(materialized='table') }}

with content as (
    select * from {{ ref('stg_content_performance') }}
)

select
    content_id,
    channel,
    date_trunc('month', publish_date)::date as content_month,
    publish_date,
    views,
    clicks,
    utm_source,
    utm_campaign,
    case when views > 0 then clicks::double / views else null end as ctr
from content
