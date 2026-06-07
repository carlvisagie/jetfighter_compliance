"""Quick scan of every ui/*.html file - title + first heading + size."""
import io
import re
import glob


def first_match(text, pattern, group=1):
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return (m.group(group).strip() if m else "")[:80]


for path in sorted(glob.glob("ui/*.html")):
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    title = first_match(text, r"<title>(.*?)</title>")
    h1 = first_match(text, r"<h1[^>]*>(.*?)</h1>")
    h2 = first_match(text, r"<h2[^>]*>(.*?)</h2>")
    # Strip tags from headings.
    h1 = re.sub(r"<[^>]+>", "", h1)
    h2 = re.sub(r"<[^>]+>", "", h2)
    print(f"{path:30s}  {len(text):>6}  title={title!r:40s}  h1={h1!r:40s}  h2={h2!r}")
