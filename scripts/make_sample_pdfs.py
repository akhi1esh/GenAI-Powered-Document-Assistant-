"""Generate N synthetic service-note PDFs + ground-truth JSON for evaluation."""
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from textwrap import wrap

CUSTOMERS = ["Northwind Cold Storage", "Apex Dairy Ltd", "Bluefin Foods", "Harbor Logistics", "Summit Bakeries", "Greenfield Pharma"]
TECHS = ["R. Patel", "M. Alvarez", "S. Chen", "J. Okafor", "L. Novak"]
ASSETS = [("Compressor", "CMP"), ("Chiller", "CHL"), ("Generator", "GEN"), ("Conveyor Motor", "CNV"), ("Boiler", "BLR")]
FAULTS = ["loud rattling and intermittent shutdown", "overheating during peak load", "oil leak near the base",
          "unusual vibration at start-up", "pressure dropping below spec"]
PARTS = [("drive belt", "BLT"), ("capacitor", "CAP"), ("pressure valve", "VLV"), ("bearing", "BRG"), ("filter", "FLT")]
ACTIONS = ["Cleaned condenser coils", "Tightened mounting bolts", "Recalibrated pressure sensor", "Lubricated moving parts"]
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
fmt = lambda d: f"{d.day} {MONTHS[d.month-1]} {d.year}"


def make(i: int, rng: random.Random):
    atype, acode = rng.choice(ASSETS)
    d = date(2025, 1, 1) + timedelta(days=rng.randint(0, 330))
    parts = [(n, f"{c}-{rng.randint(10, 99)}", rng.randint(1, 3)) for n, c in rng.sample(PARTS, rng.randint(1, 3))]
    acts = rng.sample(ACTIONS, rng.randint(1, 2))
    sev = rng.choice(["low", "medium", "high", "critical"])
    follow = rng.random() < 0.6
    fu = d + timedelta(days=rng.randint(30, 120)) if follow else None
    cost = round(rng.uniform(120, 2500), 2)
    hrs = round(rng.choice([1, 1.5, 2, 2.5, 3.5, 4, 6]), 1)
    rid, aid = f"SR-{1000+i}", f"A-{rng.randint(1000, 9999)}"
    cust, tech, fault = rng.choice(CUSTOMERS), rng.choice(TECHS), rng.choice(FAULTS)

    replaced = " and ".join(f"{n} (P/N {pn}, qty {q})" for n, pn, q in parts)
    body = (f"Customer reported {fault}. Technician inspected the unit and found worn components. "
            f"Replaced {replaced}. " + ". ".join(acts) + f". Labor {hrs} hrs. Total cost ${cost:,.2f}. "
            f"Severity: {sev}." + (f" Recommend follow-up inspection by {fmt(fu)}." if fu else " No further action needed."))
    lines = [f"SERVICE REPORT #{rid}", f"Date of visit: {fmt(d)}", f"Customer: {cust}",
             f"Unit: {atype} {acode}-{rng.randint(100, 999)} (Asset ID {aid})", f"Tech: {tech}", "", "Notes:"] + wrap(body, 85)
    truth = {
        "report_id": rid, "service_date": d.isoformat(), "customer_name": cust, "asset_id": aid,
        "asset_type": atype, "technician": tech, "issue_description": fault,
        "actions_taken": [f"Replaced {n}" for n, _, _ in parts] + acts,
        "parts_replaced": [{"name": n, "part_number": pn, "quantity": q} for n, pn, q in parts],
        "labor_hours": hrs, "total_cost": cost, "severity": sev,
        "follow_up_required": follow, "follow_up_date": fu.isoformat() if fu else None,
    }
    return lines, truth


def main(n=30, out="data/samples", seed=7):
    rng = random.Random(seed)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        lines, truth = make(i, rng)
        c = canvas.Canvas(str(out / f"service_{i:03d}.pdf"), pagesize=letter)
        y = 740
        for ln in lines:
            c.drawString(60, y, ln); y -= 16
        c.save()
        (out / f"service_{i:03d}.truth.json").write_text(json.dumps(truth, indent=2))
    print(f"wrote {n} PDFs to {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
