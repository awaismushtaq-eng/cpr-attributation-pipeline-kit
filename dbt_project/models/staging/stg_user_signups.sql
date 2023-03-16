with source as (
    select * from {{ source('raw', 'user_signups') }}
)

select
    user_id,
    signup_date,
    company_id,
    nullif({{ normalize_channel('referral_source') }}, '') as referral_source,
    nullif({{ normalize_channel('utm_source') }}, '') as utm_source,
    nullif(lower(trim(utm_medium)), '') as utm_medium,
    nullif(lower(trim(utm_campaign)), '') as utm_campaign,
    nullif({{ normalize_channel('first_touch_channel') }}, '') as first_touch_channel,
    nullif({{ normalize_channel('last_touch_channel') }}, '') as last_touch_channel,
    date_trunc('month', signup_date)::date as signup_month
from source
where user_id is not null
