-- 02. Campaign ROI: spend vs attributed revenue, ranked by efficiency (last-touch)
select
    campaign_id,
    campaign_name,
    channel,
    budget_usd,
    attributed_signups,
    round(attributed_revenue_last_touch, 2) as attributed_revenue_last_touch,
    round(attributed_revenue_first_touch, 2) as attributed_revenue_first_touch,
    round(roi_last_touch, 3) as roi_last_touch,
    round(roi_first_touch, 3) as roi_first_touch,
    round(cac_last_touch, 2) as cost_per_signup,
    rank() over (order by roi_last_touch desc nulls last) as efficiency_rank_last_touch,
    rank() over (order by roi_first_touch desc nulls last) as efficiency_rank_first_touch
from marts.fct_campaign_roi
order by roi_last_touch desc nulls last;
