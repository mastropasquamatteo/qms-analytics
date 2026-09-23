-- 00_params.sql
-- Reporting date: everything open after this date counts as open.

DROP TABLE IF EXISTS params;
CREATE TABLE params AS SELECT '2025-12-31' AS report_date;
