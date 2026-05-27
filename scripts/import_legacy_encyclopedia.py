#!/usr/bin/env python3
"""
One-time import from legacy local paths — NOT called at runtime.

Example:
  python scripts/import_legacy_encyclopedia.py --source "E:/KYC/Encyclopedia/KYC_Encyclopedia_SingleFile_10k.html"
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "knowledge_cockpit"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="Path to legacy single-file encyclopedia HTML")
    args = p.parse_args()
    src = Path(args.source)
    if not src.is_file():
        raise SystemExit(f"Not found: {src}")
    text = src.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const DATA = (\{.*\});\s*</script>", text, re.S)
    if not m:
        raise SystemExit("DATA blob not found in HTML")
    data = json.loads(m.group(1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "control_matrix.json").write_text(json.dumps(data.get("matrix", []), indent=2), encoding="utf-8")
    (OUT / "control_family_xref.json").write_text(json.dumps(data.get("xref", {}), indent=2), encoding="utf-8")
    print("Imported matrix/xref. Re-run scripts/build_knowledge_cockpit_data.py for concepts.")


if __name__ == "__main__":
    main()
