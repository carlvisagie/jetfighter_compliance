p = r"E:\JetFighter_Compliance\ui\assets\styles\vio.css"
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()
print(f"TOTAL_LINES={len(lines)}")
print("LAST 5 LINES:")
for i, l in enumerate(lines[-5:], start=len(lines) - 4):
    print(f"  {i}: {l.rstrip()}")
