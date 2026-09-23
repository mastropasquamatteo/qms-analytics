-- 01_nonconformities.sql
-- Monthly volume and cost of nonconformities (NC), and NC count per supplier and quarter.

DROP VIEW IF EXISTS nc_monthly;
CREATE VIEW nc_monthly AS
SELECT
    substr(nc_date, 1, 7)                                   AS month,
    count(*)                                                AS n_nc,
    sum(severity IN ('Major', 'Critical'))                  AS n_major_critical,
    round(sum(cost_eur), 2)                                 AS cost_eur
FROM nonconformities
GROUP BY month;

DROP VIEW IF EXISTS nc_supplier_quarter;
CREATE VIEW nc_supplier_quarter AS
SELECT
    supplier_id,
    substr(nc_date, 1, 4) || '-Q' || ((cast(substr(nc_date, 6, 2) AS integer) + 2) / 3) AS quarter,
    count(*)                                                AS n_nc,
    round(sum(cost_eur), 2)                                 AS cost_eur
FROM nonconformities
WHERE supplier_id <> ''
GROUP BY supplier_id, quarter;
