-- 05. MoM revenue by channel (last-touch) + trailing 3-month average forecast (next 3 months)
with monthly as (
    select
        revenue_month,
        attr_channel_last_touch as channel,
        sum(revenue_amount) as revenue
    from marts.fct_attributed_revenue
    group by 1, 2
),
with_mom as (
    select
        revenue_month,
        channel,
        revenue,
        lag(revenue) over (partition by channel order by revenue_month) as prev_revenue,
        avg(revenue) over (
            partition by channel
            order by revenue_month
            rows between 2 preceding and current row
        ) as trailing_3mo_avg
    from monthly
),
history as (
    select
        revenue_month,
        channel,
        round(revenue, 2) as revenue,
        round(prev_revenue, 2) as prev_revenue,
        round(
            case when prev_revenue is null or prev_revenue = 0 then null
                 else (revenue - prev_revenue) / prev_revenue
            end,
            4
        ) as mom_growth,
        round(trailing_3mo_avg, 2) as trailing_3mo_avg,
        'actual' as series_type
    from with_mom
),
-- Latest trailing average per channel → forecast next 3 months
latest as (
    select
        channel,
        max(revenue_month) as last_month,
        arg_max(trailing_3mo_avg, revenue_month) as forecast_value
    from with_mom
    group by 1
),
forecast as (
    select
        (last_month + interval (offset_n) month)::date as revenue_month,
        channel,
        round(forecast_value, 2) as revenue,
        null::double as prev_revenue,
        null::double as mom_growth,
        round(forecast_value, 2) as trailing_3mo_avg,
        'forecast' as series_type
    from latest
    cross join (select unnest([1, 2, 3]) as offset_n) o
)
select * from history
union all
select * from forecast
order by channel, revenue_month, series_type;
