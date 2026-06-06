"""Extract the inline boot <script> from ui/vio.html and parse-check it."""
import re
import subprocess
import sys
from pathlib import Path

html = Path("E:/JetFighter_Compliance/ui/vio.html").read_text(encoding="utf-8")

m = re.search(r"<script>\s*(\(function \(\) \{.*?\}\)\(\);)\s*</script>",
              html, re.DOTALL)
if not m:
    print("FAIL: could not locate inline boot IIFE in vio.html")
    sys.exit(1)

js = m.group(1)
tmp = Path("E:/JetFighter_Compliance/.boot-extracted.js")
tmp.write_text(js, encoding="utf-8")

r = subprocess.run(["node", "--check", str(tmp)],
                   capture_output=True, text=True)
if r.returncode != 0:
    print("FAIL: inline boot script does not parse")
    print(r.stderr)
    sys.exit(1)
print(f"OK: inline boot script parses ({len(js)} bytes)")
