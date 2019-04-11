-- Channel revenue ranking under last-touch vs first-touch attribution
with last_touch as (
    select
        attr_channel_last_touch as channel,
        sum(revenue_amount) as attributed_revenue,
        count(distinct user_id) as users,
        count(*) as revenue_rows
    from marts.fct_attributed_revenue
    group by 1
),
first_touch as (
    select
        attr_channel_first_touch as channel,
        sum(revenue_amount) as attributed_revenue,
        count(distinct user_id) as users,
        count(*) as revenue_rows
    from marts.fct_attributed_revenue
    group by 1
)
select
    coalesce(l.channel, f.channel) as channel,
    round(l.attributed_revenue, 2) as revenue_last_touch,
    round(f.attributed_revenue, 2) as revenue_first_touch,
    round(coalesce(l.attributed_revenue, 0) - coalesce(f.attributed_revenue, 0), 2) as last_minus_first,
    l.users as users_last_touch,
    f.users as users_first_touch,
    rank() over (order by l.attributed_revenue desc nulls last) as rank_last_touch,
    rank() over (order by f.attributed_revenue desc nulls last) as rank_first_touch
from last_touch l
full outer join first_touch f using (channel)
order by revenue_last_touch desc nulls last;
