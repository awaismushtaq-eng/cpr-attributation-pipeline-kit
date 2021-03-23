{{
  config(
    materialized='view'
  )
}}

with attribution as (
    select * from {{ ref('int_user_attribution') }}
),

revenue as (
    select * from {{ ref('stg_portfolio_revenue') }}
)

select
    r.revenue_id,
    r.user_id,
    r.company_id,
    r.revenue_month,
    r.revenue_amount,
    r.is_recurring,

    a.signup_date,
    a.signup_month,
    a.attr_channel_first_touch,
    a.attr_channel_last_touch,
    a.has_touch_conflict,
    a.has_referral_utm_conflict,
    a.attribution_confidence,
    a.campaign_id,
    a.campaign_name,
    a.campaign_budget_usd,
    a.campaign_channel,
    a.content_id_first_touch,
    a.content_id_last_touch,

    -- Convenience: months since signup (0 = signup month)
    date_diff('month', a.signup_month, r.revenue_month) as months_since_signup

from revenue r
inner join attribution a
    on r.user_id = a.user_id
