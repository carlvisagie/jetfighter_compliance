import re
from pathlib import Path

server = Path("server.py").read_text(encoding="utf-8")
endpoints = re.findall(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)', server)

print(f"Total endpoints: {len(endpoints)}\n")
for method, path in endpoints:
    print(f"{method.upper():6} {path}")
