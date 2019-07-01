-- 03. CAC by channel per company (last-touch and first-touch)
-- CAC ≈ channel campaign spend allocated to company / new signups
with channel_spend as (
    -- Allocate each campaign's budget to its channel; portfolio-wide campaigns
    -- split evenly across companies that received signups on that channel.
    select
        c.channel,
        c.budget_usd,
        c.target_company_id,
        c.campaign_id
    from staging.stg_campaign_metadata c
),
signups_last as (
    select
        company_id,
        attr_channel_last_touch as channel,
        count(*) as signups
    from intermediate.int_user_attribution
    group by 1, 2
),
signups_first as (
    select
        company_id,
        attr_channel_first_touch as channel,
        count(*) as signups
    from intermediate.int_user_attribution
    group by 1, 2
),
-- Targeted campaign spend by channel × company
targeted_spend as (
    select
        channel,
        target_company_id as company_id,
        sum(budget_usd) as spend
    from channel_spend
    where target_company_id is not null
    group by 1, 2
),
-- Untargeted spend by channel, split by signup share within channel
untargeted as (
    select channel, sum(budget_usd) as spend
    from channel_spend
    where target_company_id is null
    group by 1
),
channel_signup_share as (
    select
        channel,
        company_id,
        signups,
        signups::double / nullif(sum(signups) over (partition by channel), 0) as share
    from signups_last
),
allocated_spend as (
    select
        s.company_id,
        s.channel,
        coalesce(t.spend, 0)
          + coalesce(u.spend, 0) * coalesce(s.share, 0) as allocated_spend,
        s.signups
    from channel_signup_share s
    left join targeted_spend t
        on s.channel = t.channel and s.company_id = t.company_id
    left join untargeted u on s.channel = u.channel
)
select
    a.company_id,
    d.company_name,
    a.channel,
    a.signups as signups_last_touch,
    round(a.allocated_spend, 2) as allocated_spend_usd,
    round(a.allocated_spend / nullif(a.signups, 0), 2) as cac_last_touch,
    f.signups as signups_first_touch,
    round(a.allocated_spend / nullif(f.signups, 0), 2) as cac_first_touch
from allocated_spend a
left join signups_first f
    on a.company_id = f.company_id and a.channel = f.channel
left join marts.dim_company d on a.company_id = d.company_id
order by a.company_id, cac_last_touch nulls last;
