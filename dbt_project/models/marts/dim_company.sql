{{ config(materialized='table') }}

select *
from (
    values
        ('CTC-001', 'GreenLeaf Landscaping', 'Home Services', 120.0),
        ('CTC-002', 'BrightPath Education', 'Education', 85.0),
        ('CTC-003', 'QuickFix Auto Repair', 'Automotive', 210.0),
        ('CTC-004', 'Summit Dental Group', 'Healthcare', 165.0)
) as t(company_id, company_name, industry, avg_revenue_per_user)
