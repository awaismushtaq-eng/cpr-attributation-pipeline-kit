{{ config(materialized='table') }}

select
    revenue_id,
    user_id,
    company_id,
    revenue_month,
    revenue_amount,
    is_recurring,
    signup_date,
    signup_month,
    months_since_signup,

    attr_channel_first_touch,
    attr_channel_last_touch,
    has_touch_conflict,
    has_referral_utm_conflict,
    attribution_confidence,

    campaign_id,
    campaign_name,
    campaign_budget_usd,
    campaign_channel,

    content_id_first_touch,
    content_id_last_touch,
    -- Default content pointer for last-touch reporting
    content_id_last_touch as content_id

from {{ ref('int_user_revenue') }}
