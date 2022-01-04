{{ config(materialized='table') }}

select
    user_id,
    company_id,
    signup_date,
    signup_month,
    attr_channel_first_touch as cohort_channel_first_touch,
    attr_channel_last_touch as cohort_channel_last_touch,
    attribution_confidence,
    campaign_id,
    -- Cohort key: company + signup month + last-touch channel
    company_id || '|' || strftime(signup_month, '%Y-%m') || '|' || attr_channel_last_touch
        as cohort_key
from {{ ref('int_user_attribution') }}
