with source as (
    select * from {{ source('raw', 'content_performance') }}
)

select
    content_id,
    {{ normalize_channel('channel') }} as channel,
    publish_date,
    views,
    clicks,
    nullif({{ normalize_channel('utm_source') }}, '') as utm_source,
    nullif(lower(trim(utm_campaign)), '') as utm_campaign
from source
where content_id is not null
