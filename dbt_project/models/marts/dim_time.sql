{{ config(materialized='table') }}

with bounds as (
    select
        min(d) as start_date,
        max(d) as end_date
    from (
        select min(publish_date) as d from {{ ref('stg_content_performance') }}
        union all
        select min(signup_date) from {{ ref('stg_user_signups') }}
        union all
        select min(revenue_month) from {{ ref('stg_portfolio_revenue') }}
        union all
        select max(publish_date) from {{ ref('stg_content_performance') }}
        union all
        select max(signup_date) from {{ ref('stg_user_signups') }}
        union all
        select max(revenue_month) from {{ ref('stg_portfolio_revenue') }}
    ) x
),

spine as (
    select
        unnest(generate_series(start_date, end_date, interval 1 day))::date as date_day
    from bounds
)

select
    date_day,
    date_trunc('week', date_day)::date as date_week,
    date_trunc('month', date_day)::date as date_month,
    date_trunc('quarter', date_day)::date as date_quarter,
    year(date_day) as year_num,
    month(date_day) as month_num,
    strftime(date_day, '%Y-%m') as year_month,
    dayofweek(date_day) as day_of_week
from spine
