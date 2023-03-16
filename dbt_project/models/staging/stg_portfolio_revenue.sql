with source as (
    select * from {{ source('raw', 'portfolio_revenue') }}
)

select
    revenue_id,
    company_id,
    user_id,
    month as revenue_month,
    revenue_amount,
    is_recurring
from source
where revenue_id is not null
  and revenue_amount is not null
