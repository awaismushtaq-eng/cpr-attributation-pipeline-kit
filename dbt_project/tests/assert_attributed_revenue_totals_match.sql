-- Dual-model consistency: total attributed revenue must match raw revenue
-- regardless of which channel model is used for grouping.
select 'mismatch' as issue
from (
    select
        (select round(sum(revenue_amount), 2) from {{ ref('fct_attributed_revenue') }}) as fct_total,
        (select round(sum(revenue_amount), 2) from {{ ref('stg_portfolio_revenue') }}) as stg_total
) t
where fct_total != stg_total
