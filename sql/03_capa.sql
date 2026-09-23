-- 03_capa.sql
-- CAPA status, timeliness and effectiveness.

DROP VIEW IF EXISTS capa_status;
CREATE VIEW capa_status AS
SELECT
    c.capa_id,
    c.nc_id,
    n.severity,
    c.root_cause_category,
    c.opened_date,
    substr(c.opened_date, 1, 4)                                          AS opened_year,
    c.due_date,
    nullif(c.closed_date, '')                                            AS closed_date,
    CASE WHEN c.closed_date = '' THEN 'Open' ELSE 'Closed' END           AS state,
    CASE WHEN c.closed_date <> ''
         THEN cast(julianday(c.closed_date) - julianday(c.opened_date) AS integer) END AS days_to_close,
    CASE
        WHEN c.closed_date <> '' AND c.closed_date <= c.due_date THEN 'Closed on time'
        WHEN c.closed_date <> ''                                  THEN 'Closed late'
        WHEN c.due_date < p.report_date                           THEN 'Open, overdue'
        ELSE 'Open, not yet due'
    END                                                                  AS timeliness,
    cast(julianday(p.report_date) - julianday(c.opened_date) AS integer) AS age_days,
    c.effective
FROM capa c
JOIN nonconformities n ON n.nc_id = c.nc_id
CROSS JOIN params p;

-- Effectiveness is only known once the 90-day check has been done.
DROP VIEW IF EXISTS capa_effectiveness;
CREATE VIEW capa_effectiveness AS
SELECT
    root_cause_category,
    count(*)                                        AS n_capa,
    sum(effective IN ('Yes', 'No'))                 AS n_checked,
    sum(effective = 'Yes')                          AS n_effective,
    round(100.0 * sum(effective = 'Yes') / nullif(sum(effective IN ('Yes', 'No')), 0), 1) AS effective_pct
FROM capa_status
GROUP BY root_cause_category
ORDER BY effective_pct;
