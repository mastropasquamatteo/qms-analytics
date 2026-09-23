-- 04_audits.sql
-- Audit findings by ISO 13485:2016 clause, and clauses that keep coming back.

DROP VIEW IF EXISTS findings_by_clause;
CREATE VIEW findings_by_clause AS
SELECT
    f.clause,
    f.clause_title,
    count(*)                                        AS n_findings,
    count(DISTINCT f.audit_id)                      AS n_audits,
    sum(f.finding_type = 'Major NC')                AS n_major,
    sum(f.finding_type = 'Minor NC')                AS n_minor,
    sum(f.finding_type = 'Observation')             AS n_observation,
    sum(f.closed_date = '')                         AS n_open
FROM audit_findings f
GROUP BY f.clause, f.clause_title
ORDER BY n_findings DESC, f.clause;

-- A clause raised in at least 5 of the 14 audits (more than a third) is a systemic issue, not a one-off.
DROP VIEW IF EXISTS repeat_clauses;
CREATE VIEW repeat_clauses AS
SELECT *
FROM findings_by_clause
WHERE n_audits >= 5;
