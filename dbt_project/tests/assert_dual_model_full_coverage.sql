-- First and last touch channel totals must each equal full revenue
-- (every row is attributed under both models).
with totals as (
    select
        sum(revenue_amount) as total_rev,
        sum(case when attr_channel_last_touch is not null then revenue_amount end) as last_rev,
        sum(case when attr_channel_first_touch is not null then revenue_amount end) as first_rev
    from {{ ref('fct_attributed_revenue') }}
)
select *
from totals
where round(total_rev, 2) != round(last_rev, 2)
   or round(total_rev, 2) != round(first_rev, 2)
