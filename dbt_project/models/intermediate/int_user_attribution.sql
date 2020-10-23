{{
  config(
    materialized='view'
  )
}}

with signups as (
    select * from {{ ref('stg_user_signups') }}
),

campaigns as (
    select * from {{ ref('stg_campaign_metadata') }}
),

content as (
    select * from {{ ref('stg_content_performance') }}
),

resolved as (
    select
        s.user_id,
        s.signup_date,
        s.signup_month,
        s.company_id,
        s.referral_source,
        s.utm_source,
        s.utm_medium,
        s.utm_campaign,
        s.first_touch_channel,
        s.last_touch_channel,

        {{ resolve_channel('s.first_touch_channel', 's.utm_source', 's.referral_source') }}
            as attr_channel_first_touch,
        {{ resolve_channel('s.last_touch_channel', 's.utm_source', 's.referral_source') }}
            as attr_channel_last_touch,

        case
            when s.first_touch_channel is not null
             and s.last_touch_channel is not null
             and s.first_touch_channel != s.last_touch_channel
            then true
            else false
        end as has_touch_conflict,

        case
            when s.referral_source is not null
             and s.utm_source is not null
             and (
                (
                    s.referral_source in ('direct', 'word_of_mouth', 'organic')
                    and s.utm_source in (
                        'youtube', 'twitter', 'instagram',
                        'newsletter', 'podcast', 'blog'
                    )
                )
                or (
                    s.referral_source in (
                        'youtube', 'twitter', 'instagram',
                        'newsletter', 'podcast', 'blog', 'organic', 'referral'
                    )
                    and s.referral_source != s.utm_source
                )
             )
            then true
            else false
        end as has_referral_utm_conflict,

        c.campaign_id,
        c.campaign_name,
        c.budget_usd as campaign_budget_usd,
        c.channel as campaign_channel,
        c.target_company_id as campaign_target_company_id

    from signups s
    left join campaigns c
        on s.utm_campaign = c.campaign_slug
),

content_candidates as (
    select
        r.user_id,
        r.attr_channel_first_touch,
        r.attr_channel_last_touch,
        r.signup_date,
        r.utm_campaign,
        c.content_id,
        c.channel as content_channel,
        c.publish_date,
        c.utm_campaign as content_utm_campaign,
        case
            when c.utm_campaign is not null
             and r.utm_campaign is not null
             and c.utm_campaign = r.utm_campaign then 0
            else 1
        end as campaign_match_rank
    from resolved r
    inner join content c
        on c.publish_date <= r.signup_date
       and c.publish_date >= r.signup_date - interval 30 day
),

content_first as (
    select *
    from (
        select
            user_id,
            content_id as content_id_first_touch,
            row_number() over (
                partition by user_id
                order by
                    case when content_channel = attr_channel_first_touch then 0 else 1 end,
                    campaign_match_rank,
                    publish_date desc
            ) as rn
        from content_candidates
        where content_channel = attr_channel_first_touch
           or campaign_match_rank = 0
    ) x
    where rn = 1
),

content_last as (
    select *
    from (
        select
            user_id,
            content_id as content_id_last_touch,
            row_number() over (
                partition by user_id
                order by
                    case when content_channel = attr_channel_last_touch then 0 else 1 end,
                    campaign_match_rank,
                    publish_date desc
            ) as rn
        from content_candidates
        where content_channel = attr_channel_last_touch
           or campaign_match_rank = 0
    ) x
    where rn = 1
),

final as (
    select
        r.user_id,
        r.signup_date,
        r.signup_month,
        r.company_id,
        r.referral_source,
        r.utm_source,
        r.utm_medium,
        r.utm_campaign,
        r.first_touch_channel,
        r.last_touch_channel,
        r.attr_channel_first_touch,
        r.attr_channel_last_touch,
        r.has_touch_conflict,
        r.has_referral_utm_conflict,
        r.campaign_id,
        r.campaign_name,
        r.campaign_budget_usd,
        r.campaign_channel,
        r.campaign_target_company_id,
        cf.content_id_first_touch,
        cl.content_id_last_touch,

        case
            when r.attr_channel_first_touch = 'unknown'
              or r.attr_channel_last_touch = 'unknown'
            then 'low'
            when r.first_touch_channel is not null
             and r.last_touch_channel is not null
             and r.utm_source is not null
             and not r.has_touch_conflict
             and not r.has_referral_utm_conflict
            then 'high'
            when r.first_touch_channel is not null
              or r.last_touch_channel is not null
            then 'medium'
            else 'low'
        end as attribution_confidence

    from resolved r
    left join content_first cf on r.user_id = cf.user_id
    left join content_last cl on r.user_id = cl.user_id
)

select * from final
