-- Revenue amounts must be non-negative.
select revenue_id, revenue_amount
from {{ ref('fct_attributed_revenue') }}
where revenue_amount < 0
