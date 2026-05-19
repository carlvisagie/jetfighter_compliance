# Task 14 — finish platform UI quality (shop.html standard)
from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "ui"

OPS_NAV = """  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
    <nav class="kyc-nav kyc-nav--ops" aria-label="Operations">
      <a href="/ui/control.html">Control</a>
      <a href="/ui/command.html">Command</a>
      <a href="/ui/status.html">Status</a>
      <a href="/ui/inbox.html">Inbox</a>
      <a href="/ui/shop.html">Public site</a>
    </nav>
  </header>
"""

FOOTER = "  <footer class=\"kyc-footer\">KeepYourContracts.com · Enterprise Compliance Workflow Platform</footer>\n"

_BAD = "m" + "otion"


def scrub_bad_tags(text: str) -> str:
    return text.replace("<motion", "<div").replace("</div>", "</div>")
def fix_utf8(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    if text.startswith("ï»¿"):
        text = text[3:]
    for a, b in {
        "Ã¢â‚¬â€": "—",
        "Ã¢â‚¬â€œ": "–",
        "Ã¢â‚¬Â¦": "…",
        "ÃÂ·": "·",
        "Ã¢â Â": "←",
        "Ã¢â¬â": "—",
    }.items():
        text = text.replace(a, b)
    return text


def ops_nav(current: str | None = None) -> str:
    nav = OPS_NAV
    if current:
        nav = nav.replace(
            f'href="/ui/{current}.html"',
            f'href="/ui/{current}.html" aria-current="page"',
            1,
        )
    return nav


def ensure_ops_subtitle(raw: str, h1: str, subtitle: str) -> str:
    if subtitle in raw:
        return raw
    hdr = (
        f'  <div class="kyc-ops-header">\n'
        f"    <div>\n"
        f"      <h1>{h1}</h1>\n"
        f'      <p class="kyc-ops-subtitle">{subtitle}</p>\n'
        f"    </div>\n"
        f"  </div>\n"
    )
    if re.search(r'<div class="kyc-ops-header">', raw):
        return re.sub(
            r'<motion class="kyc-ops-header">[\s\S]*?</motion>',
            hdr.strip(),
            raw,
            count=1,
            flags=re.DOTALL,
        )
    if "</header>" in raw:
        return raw.replace("</header>\n", f"</header>\n\n{hdr}\n", 1)
    return raw


def wrap_readiness_hero(html: str) -> str:
    if "kyc-hero--readiness" in html:
        return html
    m = re.search(
        r'(<span class="kyc-badge">Readiness operations</span>\s*<h1>.*?</h1>)',
        html,
        re.DOTALL,
    )
    if not m:
        return html
    block = m.group(1)
    wrapped = (
        '<section class="kyc-hero kyc-hero--readiness">\n'
        + block
        + "\n<p class=\"kyc-hero-lead\">Internal readiness workflow for live assessment sessions.</p>\n</section>"
    )
    return html.replace(block, wrapped, 1)


def polish_public_hero(path: Path, badge: str, h1: str, lead: str) -> None:
    raw = fix_utf8(scrub_bad_tags(path.read_text(encoding="utf-8", errors="replace")))
    if "kyc-hero" not in raw and "<h1>" in raw:
        raw = re.sub(
            r"<h1>[^<]+</h1>",
            f'<section class="kyc-hero kyc-hero--compact"><span class="kyc-badge">{badge}</span><h1>{h1}</h1><p>{lead}</p></section>',
            raw,
            count=1,
        )
    if "Enterprise Compliance" not in raw:
        raw = raw.replace("</body>", FOOTER + "</body>")
    path.write_text(raw, encoding="utf-8")
    print("hero", path.name)


def fix_command() -> None:
    p = UI / "command.html"
    raw = fix_utf8(scrub_bad_tags(p.read_text(encoding="utf-8", errors="replace")))
    m = re.search(r'(<div class="page">.*)(<script>)', raw, re.DOTALL)
    if not m:
        print("command: page block not found")
        return
    body_inner = m.group(1).replace('<div class="page">', '<div class="page kyc-command-shell">', 1)
    script_part = raw[raw.index(m.group(2)) :]
    out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KeepYourContracts | Command Center</title>
  <link rel="stylesheet" href="/ui/assets/styles/design-system.css">
  <link rel="stylesheet" href="/ui/assets/styles/layout.css">
  <link rel="stylesheet" href="/ui/assets/styles/components.css">
  <link rel="stylesheet" href="/ui/assets/styles/ops-dashboard.css">
</head>
<body class="kyc-page kyc-surface-ops">
{ops_nav("command")}
  <div class="kyc-ops-header">
    <div>
      <h1>Command center</h1>
      <p class="kyc-ops-subtitle">Consolidated health, events, and system status · Live refresh</p>
    </div>
    <div class="kyc-ops-badges">
      <span class="kyc-pill" id="badge-health"><span class="kyc-badge-dot" id="badge-health-dot"></span> <span id="badge-health-label">Core: Unknown</span></span>
      <span class="kyc-pill" id="badge-refresh-label">Last refresh: —</span>
      <a class="kyc-btn kyc-btn--secondary" href="/ui/control.html">Control panel</a>
    </div>
  </div>
  <main class="kyc-main kyc-main--ops">
{body_inner}
  </main>
{FOOTER}
{script_part}
</body>
</html>
"""
    p.write_text(scrub_bad_tags(out), encoding="utf-8")
    print("fixed command.html")


def ops_page(name: str, h1: str, subtitle: str, current: str | None) -> None:
    p = UI / name
    raw = fix_utf8(scrub_bad_tags(p.read_text(encoding="utf-8", errors="replace")))
    raw = ensure_ops_subtitle(raw, h1, subtitle)
    if "Public site" not in raw:
        raw = re.sub(r"<header class=\"kyc-topbar\">.*?</header>", ops_nav(current), raw, count=1, flags=re.DOTALL)
    if "Enterprise Compliance" not in raw:
        raw = raw.replace("</body>", FOOTER + "</body>")
    p.write_text(raw, encoding="utf-8")
    print("ops", name)


def main() -> None:
    for p in list(UI.glob("*.html")) + list((UI / "readiness").glob("*.html")):
        if any(x in p.name for x in (".bak", ".backup", "before-", "backup-")):
            continue
        t = fix_utf8(scrub_bad_tags(p.read_text(encoding="utf-8", errors="replace")))
        p.write_text(t, encoding="utf-8")

    fix_command()
    ops_page("inbox.html", "Order inbox", "Live operations queue with new-order alerts", "inbox")
    ops_page("event.html", "Chain-of-custody event", "Record custody events and review recent activity", None)
    ops_page("scan.html", "QR & evidence scan", "Mobile-friendly capture for chain-of-custody logging", None)
    ops_page("new_client.html", "New client kickoff", "Manual onboarding when webhooks are not used", None)
    ops_page("webhook_test.html", "Webhook diagnostics", "Send test payment payloads to verify automation", None)
    ops_page("status.html", "Project status", "Workflow steps · external costs · vendor RFQ", "status")
    ops_page("control.html", "Operations control panel", "Monitoring · project actions · system health", "control")

    polish_public_hero(
        UI / "vendor_quote.html",
        "Vendor RFQ",
        "Submit vendor quote",
        "Structured quote capture for external compliance vendors.",
    )
    polish_public_hero(
        UI / "healthz.html",
        "System health",
        "Platform health check",
        "Runtime status from the /healthz endpoint.",
    )
    polish_public_hero(
        UI / "index.html",
        "UI mount",
        "Static UI route",
        "Confirms the /ui static file mount is active.",
    )

    for rp in (UI / "readiness").glob("*.html"):
        t = fix_utf8(scrub_bad_tags(rp.read_text(encoding="utf-8", errors="replace")))
        t = wrap_readiness_hero(t)
        if "Enterprise Compliance" not in t:
            t = t.replace("</body>", FOOTER + "</body>")
        rp.write_text(t, encoding="utf-8")
        print("readiness", rp.name)

    print("task14_finish done")


if __name__ == "__main__":
    main()
