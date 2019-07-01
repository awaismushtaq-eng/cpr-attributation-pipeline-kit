-- 04. Cohort retention: revenue retention by signup-month cohort and last-touch channel
with base as (
    select
        signup_month,
        attr_channel_last_touch as channel,
        months_since_signup,
        user_id,
        revenue_amount
    from marts.fct_attributed_revenue
    where months_since_signup between 0 and 11
),
cohort_size as (
    select
        signup_month,
        attr_channel_last_touch as channel,
        count(distinct user_id) as cohort_users
    from intermediate.int_user_attribution
    group by 1, 2
),
monthly as (
    select
        signup_month,
        channel,
        months_since_signup,
        count(distinct user_id) as active_users,
        sum(revenue_amount) as revenue
    from base
    group by 1, 2, 3
),
m0 as (
    select signup_month, channel, revenue as revenue_m0
    from monthly
    where months_since_signup = 0
)
select
    m.signup_month,
    m.channel,
    c.cohort_users,
    m.months_since_signup,
    m.active_users,
    round(m.active_users::double / nullif(c.cohort_users, 0), 3) as user_retention_rate,
    round(m.revenue, 2) as revenue,
    round(m.revenue / nullif(m0.revenue_m0, 0), 3) as revenue_retention_vs_m0
from monthly m
inner join cohort_size c
    on m.signup_month = c.signup_month and m.channel = c.channel
left join m0
    on m.signup_month = m0.signup_month and m.channel = m0.channel
order by m.signup_month, m.channel, m.months_since_signup;
