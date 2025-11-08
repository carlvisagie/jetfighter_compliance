from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class ExternalItem:
    code: str
    title: str
    note: str
    typical_min_eur: float|None = None
    typical_max_eur: float|None = None

CATALOG: Dict[str, ExternalItem] = {
    "cmmc_l2_c3pao": ExternalItem("cmmc_l2_c3pao","CMMC Level 2  C3PAO Assessment","Pay only if contract requires formal L2", 30000, 120000),
    "soc2": ExternalItem("soc2","SOC 2 Report (CPA)","If a customer insists on SOC 2", 15000, 60000),
    "iso27001": ExternalItem("iso27001","ISO/IEC 27001 Certification","If certificate demanded", 8000, 30000),
    "pci": ExternalItem("pci","PCI DSS (ASV/ROC)","Only if handling card data directly", 1000, 20000),
    "qes": ExternalItem("qes","Qualified eSignature (eIDAS)","Only if QES explicitly required", 50, 300),
    "esign": ExternalItem("esign","Commercial e-sign envelopes","If specific platform required", 2, 50),
    "tsa": ExternalItem("tsa","Qualified timestamp / notarization","If notarized timestamps required", 5, 100),
    "gs1": ExternalItem("gs1","GS1 GTIN/GLN Prefix","If official barcodes required", 35, 250),
    "lab_ce": ExternalItem("lab_ce","Lab Certification (CE/EMC/Radio)","Only for certain product types", 500, 15000),
    "lab_substance": ExternalItem("lab_substance","Material Tests (RoHS/REACH)","Per material/batch as needed", 150, 2000),
    "pentest": ExternalItem("pentest","External Penetration Test","If customer mandates pen test", 3000, 25000),
    "vulnscan": ExternalItem("vulnscan","External Vulnerability Scans","Quarterly/ASV if required", 200, 3000),
    "privacy_counsel": ExternalItem("privacy_counsel","Privacy Legal (DPIA/SCCs)","If outside counsel needed", 500, 10000),
    "bg_checks": ExternalItem("bg_checks","Background Checks","Per person if policy requires", 20, 150),
    "worm": ExternalItem("worm","WORM/Immutable Storage","If immutable archive required", 1, 50),
    "translation": ExternalItem("translation","Certified Translation / Apostille","Only if certified translation needed", 30, 500),
}

TOGGLES = list(CATALOG.keys())

def compute_external_costs(flags: Dict[str,bool]) -> Dict:
    items = []
    total_min = 0.0
    total_max = 0.0
    for code, on in (flags or {}).items():
        if not on: continue
        if code not in CATALOG: continue
        it = CATALOG[code]
        items.append({
            "code": it.code, "title": it.title, "note": it.note,
            "typical_min_eur": it.typical_min_eur, "typical_max_eur": it.typical_max_eur
        })
        if it.typical_min_eur is not None: total_min += it.typical_min_eur
        if it.typical_max_eur is not None: total_max += it.typical_max_eur
    return {"requires_external": len(items) > 0, "items": items, "sum_min_eur": total_min, "sum_max_eur": total_max}
