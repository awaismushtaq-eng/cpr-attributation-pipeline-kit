with source as (
    select * from {{ source('raw', 'campaign_metadata') }}
)

select
    campaign_id,
    campaign_name,
    {{ normalize_channel('channel') }} as channel,
    budget_usd,
    start_date,
    end_date,
    nullif(trim(target_company_id), '') as target_company_id,
    campaign_slug
from source
where campaign_id is not null
