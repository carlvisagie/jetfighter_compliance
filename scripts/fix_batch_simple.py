"""Simple manual fixes for remaining 13 files - NO regex."""
from pathlib import Path

# 2/14: services/process.py
file = Path("services/process.py")
content = file.read_text(encoding="utf-8")
# Add import after typing
content = content.replace(
    "from typing import Dict, List, Optional",
    "from typing import Dict, List, Optional\nfrom .defensive_wiring import safe_write_json"
)
# Replace _save function
old_save = '''def _save(project_id: str, obj: Dict):
    _wf_path(project_id).write_text(json.dumps(obj, indent=2))

    # Emit telemetry so organism knows workflow changed'''
new_save = '''def _save(project_id: str, obj: Dict):
    safe_write_json(_wf_path(project_id), obj, component="workflow", context=f"workflow {project_id}", severity="critical")

    # Emit telemetry so organism knows workflow changed'''
content = content.replace(old_save, new_save)
file.write_text(content, encoding="utf-8")
print("OK 2/14: process.py")

# 3/14: services/rfq.py  
file = Path("services/rfq.py")
content = file.read_text(encoding="utf-8")
# Add import after dataclasses
content = content.replace(
    "from dataclasses import dataclass, asdict, field",
    "from dataclasses import dataclass, asdict, field\nfrom .defensive_wiring import safe_write_json"
)
# Replace save_rfq
old_rfq = '''def save_rfq(obj: RFQ):
    d = asdict(obj)
    d["bids"] = [asdict(b) for b in (obj.bids or [])]
    _rfq_path(obj.rfq_id).write_text(json.dumps(d, indent=2))

    # Emit telemetry so organism knows RFQ state changed'''
new_rfq = '''def save_rfq(obj: RFQ):
    d = asdict(obj)
    d["bids"] = [asdict(b) for b in (obj.bids or [])]
    safe_write_json(_rfq_path(obj.rfq_id), d, component="rfq", context=f"rfq {obj.rfq_id}", severity="critical")

    # Emit telemetry so organism knows RFQ state changed'''
content = content.replace(old_rfq, new_rfq)
file.write_text(content, encoding="utf-8")
print("OK 3/14: rfq.py")

# 4/14: services/acquisition/memory.py
file = Path("services/acquisition/memory.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom ..defensive_wiring import safe_write_json"
)
old_weights = '(root / WEIGHTS_JSON).write_text(json.dumps(weights, indent=2), encoding="utf-8")'
new_weights = 'safe_write_json(root / WEIGHTS_JSON, weights, component="acquisition", context="weights mirror", severity="warning")'
content = content.replace(old_weights, new_weights)
file.write_text(content, encoding="utf-8")
print("OK 4/14: acquisition/memory.py")

# 5/14: services/reports.py
file = Path("services/reports.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom .defensive_wiring import safe_write_text"
)
old_report = 'report_path.write_text("\\n".join(lines), encoding="utf-8")'
new_report = 'safe_write_text(report_path, "\\n".join(lines), component="reports", context=f"binder {project_id}", severity="warning")'
content = content.replace(old_report, new_report)
file.write_text(content, encoding="utf-8")
print("OK 5/14: reports.py")

# 6/14: services/memory/entity_graph.py
file = Path("services/memory/entity_graph.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from typing import Any, Dict, List, Optional, Tuple",
    "from typing import Any, Dict, List, Optional, Tuple\nfrom ..defensive_wiring import safe_write_text"
)
old_graph = 'ENTITY_GRAPH_FILE.write_text(json.dumps(graph, indent=2, ensure_ascii=False))'
new_graph = 'safe_write_text(ENTITY_GRAPH_FILE, json.dumps(graph, indent=2, ensure_ascii=False), component="entity_graph", context="graph save", severity="critical")'
content = content.replace(old_graph, new_graph)
file.write_text(content, encoding="utf-8")
print("OK 6/14: memory/entity_graph.py")

# 7/14: services/memory/learning.py
file = Path("services/memory/learning.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom ..defensive_wiring import safe_write_json"
)
old_learning = 'LEARNING_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")'
new_learning = 'safe_write_json(LEARNING_STATE_FILE, state, component="learning", context="learning_state save", severity="critical")'
content = content.replace(old_learning, new_learning)
file.write_text(content, encoding="utf-8")
print("OK 7/14: memory/learning.py")

# 8/14: services/memory/organism_observability.py
file = Path("services/memory/organism_observability.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom ..defensive_wiring import safe_write_text"
)
old_obs = 'OBSERVABILITY_FILE.write_text(json.dumps(obs, indent=2))'
new_obs = 'safe_write_text(OBSERVABILITY_FILE, json.dumps(obs, indent=2), component="observability", context="observability save", severity="warning")'
content = content.replace(old_obs, new_obs)
file.write_text(content, encoding="utf-8")
print("OK 8/14: memory/organism_observability.py")

# 9/14: services/alerts/telemetry.py
file = Path("services/alerts/telemetry.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom ..defensive_wiring import safe_append_jsonl"
)
old_alert_tel = '''with open(ALERT_TELEMETRY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\\n")'''
new_alert_tel = 'safe_append_jsonl(ALERT_TELEMETRY_FILE, record, component="alerts", context="alert telemetry", severity="warning")'
content = content.replace(old_alert_tel, new_alert_tel)
file.write_text(content, encoding="utf-8")
print("OK 9/14: alerts/telemetry.py")

# 10/14: services/telemetry_diagnostics.py
file = Path("services/telemetry_diagnostics.py")
content = file.read_text(encoding="utf-8")
content = content.replace(
    "from pathlib import Path",
    "from pathlib import Path\nfrom .defensive_wiring import safe_write_text"
)
old_diag = 'diag_file.write_text("\\n".join(lines), encoding="utf-8")'
new_diag = 'safe_write_text(diag_file, "\\n".join(lines), component="telemetry_diagnostics", context="diagnostic report", severity="warning")'
content = content.replace(old_diag, new_diag)
file.write_text(content, encoding="utf-8")
print("OK 10/14: telemetry_diagnostics.py")

print("\n=== BATCH COMPLETE: 10/14 files fixed ===")
print("Remaining: engine.py (6 writes), customer_session.py (2 writes), intake/kickoff.py (2 writes), cognition/storage.py (9 writes)")
