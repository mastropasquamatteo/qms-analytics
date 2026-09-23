"""
Generate a synthetic quality-management dataset for a fictional
medical device manufacturer, covering 2024 and 2025.

Tables written to data/:
  suppliers.csv          approved suppliers
  inspections.csv        weekly final-test results (units tested, units failed)
  nonconformities.csv    every nonconformity (NC) raised
  capa.csv               corrective and preventive actions opened from NCs
  audit_findings.csv     findings from internal, certification and supplier audits

One real-looking story is built in: in June 2025 a supplier ships a bad
connector lot, final-test failures jump for several weeks, and a CAPA
brings the process back. The analysis has to find it from the data alone.

Everything here is invented. Run:  python generate_data.py
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
START = date(2024, 1, 1)          # a Monday
END = date(2025, 12, 31)
DATA_DIR = Path(__file__).parent / "data"

# Supplier event: bad connector lot from S07
EVENT_START = date(2025, 6, 2)
EVENT_WEEKS = 7
EVENT_SUPPLIER = "S07"

BASE_FAIL_RATE = 0.025
EVENT_FAIL_RATE = 0.052
AFTER_FAIL_RATE = 0.021

# Defect catalogue: (code, description, process, typical source, weight, mean cost EUR)
DEFECTS = [
    ("D01", "Connector crimp defect",            "Assembly",            "supplier", 0.10, 950),
    ("D02", "Dimensional out of tolerance",      "Machining",           "internal", 0.16, 780),
    ("D03", "Solder joint defect",               "Electronics",         "internal", 0.13, 520),
    ("D04", "Seal leak at pressure test",        "Final test",          "internal", 0.06, 1400),
    ("D05", "Wrong or missing label",            "Packaging",           "internal", 0.12, 160),
    ("D06", "Device history record incomplete",  "Documentation",       "internal", 0.11, 90),
    ("D07", "Cosmetic scratch",                  "Assembly",            "internal", 0.10, 70),
    ("D08", "Firmware version mismatch",         "Final test",          "internal", 0.05, 380),
    ("D09", "Incoming material out of spec",     "Incoming inspection", "supplier", 0.08, 610),
    ("D10", "Packaging damage in transit",       "Customer",            "customer", 0.05, 240),
    ("D11", "Test fixture calibration overdue",  "Final test",          "internal", 0.04, 300),
]

# Root-cause categories for CAPA, with the chance that the action proves effective.
# Retraining is the classic weak fix: it is recorded as effective less often.
ROOT_CAUSES = {
    "Training / human error": (0.30, 0.56),
    "Procedure / method":     (0.22, 0.86),
    "Machine / equipment":    (0.16, 0.90),
    "Material / supplier":    (0.18, 0.84),
    "Measurement":            (0.08, 0.88),
    "Design":                 (0.06, 0.92),
}

# ISO 13485:2016 clauses used for audit findings, with how often they come up.
CLAUSES = [
    ("4.2.4", "Control of documents", 0.07),
    ("4.2.5", "Control of records", 0.13),
    ("5.6", "Management review", 0.03),
    ("6.2", "Human resources", 0.05),
    ("7.4", "Purchasing", 0.05),
    ("7.5.1", "Control of production and service provision", 0.05),
    ("7.5.6", "Validation of processes for production and service provision", 0.04),
    ("7.6", "Control of monitoring and measuring equipment", 0.15),
    ("8.2.2", "Complaint handling", 0.04),
    ("8.2.4", "Internal audit", 0.03),
    ("8.3", "Control of nonconforming product", 0.05),
    ("8.5.2", "Corrective action", 0.20),
]


def daterange_weeks():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=7)


def rand_day(rng, start, end):
    return start + timedelta(days=int(rng.integers(0, (end - start).days + 1)))


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(exist_ok=True)

    # Suppliers
    suppliers = pd.DataFrame(
        {
            "supplier_id": [f"S{n:02d}" for n in range(1, 13)],
            "category": rng.choice(["Electronics", "Machined parts", "Cables and connectors", "Packaging", "Plastics"], 12),
        }
    )
    suppliers.loc[suppliers["supplier_id"] == EVENT_SUPPLIER, "category"] = "Cables and connectors"
    supplier_ids = suppliers["supplier_id"].tolist()

    # Weekly final-test inspections
    event_end = EVENT_START + timedelta(weeks=EVENT_WEEKS)
    inspections = []
    for week in daterange_weeks():
        units = int(rng.poisson(420))
        if week < EVENT_START:
            p = BASE_FAIL_RATE
        elif week < event_end:
            p = EVENT_FAIL_RATE
        else:
            p = AFTER_FAIL_RATE
        inspections.append({"week_start": week.isoformat(), "units_tested": units,
                            "units_failed": int(rng.binomial(units, p))})
    inspections = pd.DataFrame(inspections)

    # Nonconformities
    codes = [d[0] for d in DEFECTS]
    weights = np.array([d[4] for d in DEFECTS])
    weights = weights / weights.sum()
    info = {d[0]: d for d in DEFECTS}

    ncs = []

    def add_nc(day, code, supplier=None, severity=None):
        _, desc, process, source, _, mean_cost = info[code]
        if severity is None:
            severity = rng.choice(["Minor", "Major", "Critical"], p=[0.72, 0.24, 0.04])
        mult = {"Minor": 1.0, "Major": 2.2, "Critical": 5.0}[severity]
        if source == "supplier" and supplier is None:
            supplier = rng.choice(supplier_ids)
        ncs.append(
            {
                "nc_date": day.isoformat(),
                "defect_code": code,
                "defect_description": desc,
                "process": process,
                "source": source,
                "supplier_id": supplier if source == "supplier" else "",
                "severity": severity,
                "qty_affected": int(rng.integers(1, 25)),
                "cost_eur": round(float(rng.gamma(2.0, mean_cost * mult / 2.0)), 2),
            }
        )

    n_days = (END - START).days + 1
    for i in range(n_days):
        day = START + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        for _ in range(int(rng.poisson(1.6))):
            add_nc(day, rng.choice(codes, p=weights))

    # Extra connector NCs from the bad lot
    for _ in range(38):
        add_nc(rand_day(rng, EVENT_START, event_end - timedelta(days=3)), "D01",
               supplier=EVENT_SUPPLIER,
               severity=rng.choice(["Minor", "Major", "Critical"], p=[0.45, 0.45, 0.10]))

    ncs = pd.DataFrame(ncs).sort_values("nc_date", kind="stable").reset_index(drop=True)
    ncs.insert(0, "nc_id", [f"NC-{i:05d}" for i in range(1, len(ncs) + 1)])

    # CAPA: all Critical, most Major, a few Minor NCs open one
    rc_names = list(ROOT_CAUSES)
    rc_p = np.array([v[0] for v in ROOT_CAUSES.values()])
    rc_p = rc_p / rc_p.sum()
    open_p = {"Critical": 1.0, "Major": 0.55, "Minor": 0.05}

    capas = []
    event_capa_done = False
    for nc in ncs.itertuples():
        if rng.random() > open_p[nc.severity]:
            continue
        opened = date.fromisoformat(nc.nc_date) + timedelta(days=int(rng.integers(0, 6)))
        if opened > END:
            continue
        root = rng.choice(rc_names, p=rc_p)
        if nc.source == "supplier":
            root = "Material / supplier"
        due = opened + timedelta(days=30 if nc.severity == "Critical" else 60)

        # The one CAPA that fixes the connector problem
        is_event_capa = (not event_capa_done and nc.supplier_id == EVENT_SUPPLIER
                         and EVENT_START <= date.fromisoformat(nc.nc_date) < event_end)
        if is_event_capa:
            event_capa_done = True
            closed = event_end + timedelta(days=5)
            effective = "Yes"
            desc = "Supplier S07 connector lot quarantined, crimp process audited at supplier, incoming inspection tightened"
        else:
            days_to_close = int(rng.lognormal(mean=3.9, sigma=0.55))
            closed = opened + timedelta(days=days_to_close)
            desc = ""
            effective = None

        if closed > END:
            closed_s, eff_date_s, effective = "", "", "Pending"
        else:
            closed_s = closed.isoformat()
            check = closed + timedelta(days=90)
            if check > END:
                eff_date_s, effective = "", "Pending"
            else:
                eff_date_s = check.isoformat()
                if effective is None:
                    effective = "Yes" if rng.random() < ROOT_CAUSES[root][1] else "No"

        capas.append(
            {
                "nc_id": nc.nc_id,
                "opened_date": opened.isoformat(),
                "due_date": due.isoformat(),
                "closed_date": closed_s,
                "root_cause_category": root,
                "effectiveness_check_date": eff_date_s,
                "effective": effective,
                "description": desc,
            }
        )
    capas = pd.DataFrame(capas).sort_values("opened_date", kind="stable").reset_index(drop=True)
    capas.insert(0, "capa_id", [f"CAPA-{i:04d}" for i in range(1, len(capas) + 1)])

    # Audit findings
    audits = []
    for year in (2024, 2025):
        for q, month in enumerate((3, 6, 9, 11), start=1):
            audits.append((f"IA-{year}-Q{q}", "Internal", date(year, month, int(rng.integers(5, 25)))))
        audits.append((f"CA-{year}", "Certification", date(year, 10, int(rng.integers(5, 25)))))
        for k in range(2):
            audits.append((f"SA-{year}-{k + 1}", "Supplier", date(year, 4 + 4 * k, int(rng.integers(5, 25)))))
    audits.sort(key=lambda a: a[2])

    cl_codes = [c[0] for c in CLAUSES]
    cl_titles = {c[0]: c[1] for c in CLAUSES}
    cl_p = np.array([c[2] for c in CLAUSES])
    cl_p = cl_p / cl_p.sum()

    findings = []
    for audit_id, audit_type, audit_date in audits:
        n = int(rng.integers(3, 9))
        for _ in range(n):
            clause = rng.choice(cl_codes, p=cl_p)
            if audit_type == "Supplier":
                clause = rng.choice(["7.4", "7.5.1", "7.6", "8.3"])
            ftype = rng.choice(["Major NC", "Minor NC", "Observation"],
                               p=[0.08, 0.47, 0.45] if audit_type != "Internal" else [0.04, 0.46, 0.50])
            closed = audit_date + timedelta(days=int(rng.integers(20, 120)))
            findings.append(
                {
                    "audit_id": audit_id,
                    "audit_type": audit_type,
                    "audit_date": audit_date.isoformat(),
                    "standard": "ISO 13485:2016",
                    "clause": clause,
                    "clause_title": cl_titles[clause],
                    "finding_type": ftype,
                    "closed_date": closed.isoformat() if closed <= END else "",
                }
            )
    findings = pd.DataFrame(findings)
    findings.insert(0, "finding_id", [f"F-{i:04d}" for i in range(1, len(findings) + 1)])

    suppliers.to_csv(DATA_DIR / "suppliers.csv", index=False)
    inspections.to_csv(DATA_DIR / "inspections.csv", index=False)
    ncs.to_csv(DATA_DIR / "nonconformities.csv", index=False)
    capas.to_csv(DATA_DIR / "capa.csv", index=False)
    findings.to_csv(DATA_DIR / "audit_findings.csv", index=False)

    print(f"Weeks of inspection data: {len(inspections)}")
    print(f"Nonconformities:          {len(ncs)}")
    print(f"CAPA:                     {len(capas)}")
    print(f"Audits / findings:        {len(audits)} / {len(findings)}")


if __name__ == "__main__":
    main()
