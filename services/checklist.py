from typing import List, Dict

SKU_PACKAGES = {
    "CMMC-L1": ["Org scoping", "17 Practices gap check", "SSP template init", "Evidence binder setup", "POA&M skeleton"],
    "CMMC-L2": ["L1 items", "110 Controls mapping", "Policy pack init", "User training plan", "Audit rehearsal"],
    "DPP-ESPR": ["ESPR DPP data model", "Supplier workbook", "QR prototype", "Evidence index", "Handover checklist"]
}

def build_checklist(items: List[str]) -> List[Dict]:
    tasks = []
    for sku in items:
        for step in SKU_PACKAGES.get(sku, ["Project kick-off", "General intake"]):
            tasks.append({"title": step, "status": "todo"})
    tasks += [{"title":"Client intake form received","status":"todo"},
              {"title":"Welcome call scheduled","status":"todo"}]
    return tasks
