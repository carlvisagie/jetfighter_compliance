"""Comprehensive wiring audit - find all disconnected components."""
import re
from pathlib import Path
from collections import defaultdict

server = Path("server.py").read_text(encoding="utf-8")

# Find all endpoints
endpoints = re.findall(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\'].*?\ndef ([a-z_]+)', server, re.DOTALL)

# Find endpoints with telemetry
telemetry_functions = re.findall(r'def ([a-z_]+).*?(?=\ndef |\Z)', server, re.DOTALL)
wired_endpoints = []
silent_endpoints = []

for method, path, func_name in endpoints:
    # Find function body
    func_match = re.search(rf'def {func_name}\(.*?\n(.*?)(?=\ndef |\Z)', server, re.DOTALL)
    if not func_match:
        continue
    
    func_body = func_match.group(1)
    
    # Check for nervous system connections
    has_telemetry = 'emit_telemetry' in func_body
    has_timeline = 'append_timeline' in func_body or 'link_' in func_body
    has_learning = 'record_learning_signal' in func_body
    has_memory_write = 'safe_write_after' in func_body or 'resolve_or_create_entity' in func_body
    has_try_except = 'try:' in func_body and 'except' in func_body
    
    wired = has_telemetry or has_timeline or has_learning or has_memory_write
    
    entry = {
        'method': method.upper(),
        'path': path,
        'function': func_name,
        'telemetry': has_telemetry,
        'timeline': has_timeline,
        'learning': has_learning,
        'memory_write': has_memory_write,
        'try_except': has_try_except,
        'wired': wired
    }
    
    if wired:
        wired_endpoints.append(entry)
    else:
        silent_endpoints.append(entry)

print(f"=== WIRING AUDIT ===\n")
print(f"Total endpoints: {len(endpoints)}")
print(f"Wired (connected to nervous system): {len(wired_endpoints)}")
print(f"Silent (can fail without organism knowing): {len(silent_endpoints)}\n")

print(f"=== DISCONNECTED ENDPOINTS (HIGH RISK) ===\n")
for ep in silent_endpoints[:30]:
    risk = "CRITICAL" if not ep['try_except'] else "HIGH"
    print(f"{risk:8} {ep['method']:6} {ep['path']:50} {ep['function']}")

print(f"\n... and {len(silent_endpoints) - 30} more silent endpoints\n")

print(f"=== WIRED ENDPOINTS (GOOD) ===\n")
for ep in wired_endpoints[:15]:
    signals = []
    if ep['telemetry']: signals.append('TEL')
    if ep['timeline']: signals.append('TL')
    if ep['learning']: signals.append('LRN')
    if ep['memory_write']: signals.append('MEM')
    sig_str = ','.join(signals)
    print(f"OK       {ep['method']:6} {ep['path']:50} [{sig_str}]")

print(f"\n... and {len(wired_endpoints) - 15} more wired endpoints")
