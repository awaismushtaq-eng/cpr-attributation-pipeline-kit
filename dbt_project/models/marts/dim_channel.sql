{{ config(materialized='table') }}

with channels as (
    select distinct attr_channel_last_touch as channel_name from {{ ref('int_user_attribution') }}
    union
    select distinct attr_channel_first_touch from {{ ref('int_user_attribution') }}
    union
    select distinct channel from {{ ref('stg_content_performance') }}
    union
    select distinct channel from {{ ref('stg_campaign_metadata') }}
)

select
    channel_name as channel_id,
    channel_name,
    case
        when channel_name in ('organic', 'referral') then 'earned'
        when channel_name = 'unknown' then 'unattributed'
        else 'owned_media'
    end as channel_type
from channels
where channel_name is not null
