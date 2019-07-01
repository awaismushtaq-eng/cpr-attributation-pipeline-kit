-- Flag months where a channel's last-touch revenue |z-score| > 2 vs trailing history
with monthly as (
    select
        revenue_month,
        attr_channel_last_touch as channel,
        sum(revenue_amount) as revenue
    from marts.fct_attributed_revenue
    group by 1, 2
),
stats as (
    select
        revenue_month,
        channel,
        revenue,
        avg(revenue) over (
            partition by channel
            order by revenue_month
            rows between 5 preceding and 1 preceding
        ) as trailing_mean,
        stddev_samp(revenue) over (
            partition by channel
            order by revenue_month
            rows between 5 preceding and 1 preceding
        ) as trailing_stddev,
        count(revenue) over (
            partition by channel
            order by revenue_month
            rows between 5 preceding and 1 preceding
        ) as trailing_n
    from monthly
)
select
    revenue_month,
    channel,
    round(revenue, 2) as revenue,
    round(trailing_mean, 2) as trailing_mean,
    round(trailing_stddev, 2) as trailing_stddev,
    round(
        case
            when trailing_stddev is null or trailing_stddev = 0 then null
            else (revenue - trailing_mean) / trailing_stddev
        end,
        3
    ) as z_score,
    case
        when trailing_n >= 3
         and trailing_stddev is not null
         and trailing_stddev > 0
         and abs((revenue - trailing_mean) / trailing_stddev) > 2
        then true
        else false
    end as is_anomaly
from stats
where trailing_n >= 3
order by abs(
    case
        when trailing_stddev is null or trailing_stddev = 0 then 0
        else (revenue - trailing_mean) / trailing_stddev
    end
) desc, revenue_month;
