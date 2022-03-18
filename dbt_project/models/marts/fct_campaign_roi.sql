{{ config(materialized='table') }}

with campaigns as (
    select * from {{ ref('stg_campaign_metadata') }}
),

-- Users acquired under each campaign (signup-time attribution)
attributed_users as (
    select
        campaign_id,
        user_id,
        company_id,
        attr_channel_last_touch,
        attr_channel_first_touch
    from {{ ref('int_user_attribution') }}
    where campaign_id is not null
),

revenue_last as (
    select
        a.campaign_id,
        sum(r.revenue_amount) as attributed_revenue_last_touch,
        count(distinct r.user_id) as revenue_users_last_touch
    from attributed_users a
    inner join {{ ref('stg_portfolio_revenue') }} r
        on a.user_id = r.user_id
    group by 1
),

revenue_first as (
    select
        a.campaign_id,
        sum(r.revenue_amount) as attributed_revenue_first_touch,
        count(distinct r.user_id) as revenue_users_first_touch
    from attributed_users a
    inner join {{ ref('stg_portfolio_revenue') }} r
        on a.user_id = r.user_id
    group by 1
),

signup_counts as (
    select
        campaign_id,
        count(distinct user_id) as attributed_signups
    from attributed_users
    group by 1
)

select
    c.campaign_id,
    c.campaign_name,
    c.channel,
    c.budget_usd,
    c.start_date,
    c.end_date,
    c.target_company_id,
    coalesce(s.attributed_signups, 0) as attributed_signups,
    coalesce(rl.attributed_revenue_last_touch, 0) as attributed_revenue_last_touch,
    coalesce(rf.attributed_revenue_first_touch, 0) as attributed_revenue_first_touch,
    coalesce(rl.revenue_users_last_touch, 0) as revenue_users_last_touch,
    coalesce(rf.revenue_users_first_touch, 0) as revenue_users_first_touch,
    case
        when c.budget_usd > 0
        then coalesce(rl.attributed_revenue_last_touch, 0) / c.budget_usd
    end as roi_last_touch,
    case
        when c.budget_usd > 0
        then coalesce(rf.attributed_revenue_first_touch, 0) / c.budget_usd
    end as roi_first_touch,
    case
        when coalesce(s.attributed_signups, 0) > 0
        then c.budget_usd / s.attributed_signups
    end as cac_last_touch
from campaigns c
left join signup_counts s on c.campaign_id = s.campaign_id
left join revenue_last rl on c.campaign_id = rl.campaign_id
left join revenue_first rf on c.campaign_id = rf.campaign_id
