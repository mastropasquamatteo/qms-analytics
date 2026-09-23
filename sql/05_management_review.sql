-- 05_management_review.sql
-- The KPI table for the management review (ISO 13485:2016, clause 5.6): 2024 vs 2025.

DROP VIEW IF EXISTS capa_median_days;
CREATE VIEW capa_median_days AS
WITH ranked AS (
    SELECT
        opened_year,
        days_to_close,
        row_number() OVER (PARTITION BY opened_year ORDER BY days_to_close) AS rn,
        count(*)     OVER (PARTITION BY opened_year)                        AS cnt
    FROM capa_status
    WHERE state = 'Closed'
)
SELECT opened_year, avg(days_to_close) AS median_days
FROM ranked
WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
GROUP BY opened_year;

DROP VIEW IF EXISTS management_review;
CREATE VIEW management_review AS
SELECT 1 AS ord, 'Nonconformities raised' AS kpi,
       sum(substr(nc_date,1,4) = '2024') AS y2024,
       sum(substr(nc_date,1,4) = '2025') AS y2025
FROM nonconformities
UNION ALL
SELECT 2, 'Cost of nonconformities (EUR)',
       round(sum(CASE WHEN substr(nc_date,1,4) = '2024' THEN cost_eur END), 0),
       round(sum(CASE WHEN substr(nc_date,1,4) = '2025' THEN cost_eur END), 0)
FROM nonconformities
UNION ALL
SELECT 3, 'Major + critical NC',
       sum(substr(nc_date,1,4) = '2024' AND severity IN ('Major','Critical')),
       sum(substr(nc_date,1,4) = '2025' AND severity IN ('Major','Critical'))
FROM nonconformities
UNION ALL
SELECT 4, 'Final test failure rate (%)',
       round(100.0 * sum(CASE WHEN substr(week_start,1,4) = '2024' THEN units_failed END)
                   / sum(CASE WHEN substr(week_start,1,4) = '2024' THEN units_tested END), 2),
       round(100.0 * sum(CASE WHEN substr(week_start,1,4) = '2025' THEN units_failed END)
                   / sum(CASE WHEN substr(week_start,1,4) = '2025' THEN units_tested END), 2)
FROM inspections
UNION ALL
SELECT 5, 'CAPA opened',
       sum(opened_year = '2024'), sum(opened_year = '2025')
FROM capa_status
UNION ALL
SELECT 6, 'CAPA closed on time (% of closed)',
       round(100.0 * sum(opened_year = '2024' AND timeliness = 'Closed on time') / sum(opened_year = '2024' AND state = 'Closed'), 1),
       round(100.0 * sum(opened_year = '2025' AND timeliness = 'Closed on time') / sum(opened_year = '2025' AND state = 'Closed'), 1)
FROM capa_status
UNION ALL
SELECT 7, 'CAPA median days to close',
       (SELECT median_days FROM capa_median_days WHERE opened_year = '2024'),
       (SELECT median_days FROM capa_median_days WHERE opened_year = '2025')
UNION ALL
SELECT 8, 'CAPA effective at 90-day check (%)',
       round(100.0 * sum(opened_year = '2024' AND effective = 'Yes') / nullif(sum(opened_year = '2024' AND effective IN ('Yes','No')), 0), 1),
       round(100.0 * sum(opened_year = '2025' AND effective = 'Yes') / nullif(sum(opened_year = '2025' AND effective IN ('Yes','No')), 0), 1)
FROM capa_status
UNION ALL
SELECT 9, 'CAPA open and overdue at year end',
       NULL, sum(timeliness = 'Open, overdue')
FROM capa_status
UNION ALL
SELECT 10, 'Audit findings (all types)',
       sum(substr(audit_date,1,4) = '2024'), sum(substr(audit_date,1,4) = '2025')
FROM audit_findings
UNION ALL
SELECT 11, 'Audit major nonconformities',
       sum(substr(audit_date,1,4) = '2024' AND finding_type = 'Major NC'),
       sum(substr(audit_date,1,4) = '2025' AND finding_type = 'Major NC')
FROM audit_findings;
