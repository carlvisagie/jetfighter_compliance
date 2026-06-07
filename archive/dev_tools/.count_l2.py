import io
p = r"E:\JetFighter_Compliance\ui\assets\js\vio-level2.js"
print(sum(1 for _ in io.open(p, encoding="utf-8")))
