-- 02_pareto.sql
-- Pareto of NC cost by defect: which few defects drive most of the cost.

DROP VIEW IF EXISTS pareto_cost;
CREATE VIEW pareto_cost AS
WITH by_defect AS (
    SELECT
        defect_code,
        defect_description,
        count(*)                AS n_nc,
        round(sum(cost_eur), 2) AS cost_eur
    FROM nonconformities
    GROUP BY defect_code, defect_description
)
SELECT
    defect_code,
    defect_description,
    n_nc,
    cost_eur,
    round(100.0 * cost_eur / sum(cost_eur) OVER (), 1)                                   AS share_pct,
    round(100.0 * sum(cost_eur) OVER (ORDER BY cost_eur DESC) / sum(cost_eur) OVER (), 1) AS cumulative_pct
FROM by_defect
ORDER BY cost_eur DESC;
