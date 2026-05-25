"""One-shot patch: noindex + standard operator nav on internal UI pages."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"

NOINDEX = '  <meta name="robots" content="noindex, nofollow">\n'

INTERNAL_NAV = """    <nav class="kyc-nav kyc-nav--ops" aria-label="Operations">
      {links}
    </nav>"""

NAV_ITEMS = [
    ("control.html", "Control"),
    ("command.html", "Command"),
    ("status.html", "Status"),
    ("inbox.html", "Inbox"),
    ("memory.html", "Intelligence"),
    ("knowledge.html", "Knowledge"),
    ("shop.html", "Public site"),
]

INTERNAL_REL = [
    "command.html",
    "control.html",
    "event.html",
    "healthz.html",
    "inbox.html",
    "memory.html",
    "knowledge.html",
    "lead_discovery.html",
    "new_client.html",
    "onboarding_validation.html",
    "scan.html",
    "status.html",
    "webhook_test.html",
    "readiness/follow-up.html",
    "readiness/index.html",
    "readiness/outreach.html",
    "readiness/pre-call.html",
    "readiness/questions.html",
    "readiness/report.html",
    "readiness/scoring.html",
    "readiness/script.html",
]

NAV_RE = re.compile(
    r"<nav class=\"kyc-nav kyc-nav--ops\"[^>]*>.*?</nav>",
    re.DOTALL,
)


def current_page_href(rel: str) -> str | None:
    name = Path(rel).name
    if name in {item[0] for item in NAV_ITEMS}:
        return name
    return None


def build_nav(rel: str) -> str:
    current = current_page_href(rel)
    prefix = "../" if rel.startswith("readiness/") else "/ui/"
    lines = []
    for href, label in NAV_ITEMS:
        path = f"{prefix}{href}"
        if current == href:
            lines.append(f'      <a href="{path}" aria-current="page">{label}</a>')
        else:
            lines.append(f'      <a href="{path}">{label}</a>')
    return INTERNAL_NAV.format(links="\n".join(lines))


def add_noindex(text: str) -> str:
    if "noindex" in text:
        return text
    viewport_patterns = [
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
    ]
    for pat in viewport_patterns:
        if pat in text:
            return text.replace(pat, pat + NOINDEX, 1)
    charset_patterns = [
        '  <meta charset="utf-8">\n',
        '<meta charset="utf-8" />\n',
    ]
    for pat in charset_patterns:
        if pat in text:
            return text.replace(pat, pat + NOINDEX, 1)
    return text


def patch_file(rel: str) -> bool:
    path = UI / rel
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    text = add_noindex(text)
    nav = build_nav(rel)
    if NAV_RE.search(text):
        text = NAV_RE.sub(nav, text, count=1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for rel in INTERNAL_REL:
        if patch_file(rel):
            changed.append(rel)
    print(f"Patched {len(changed)} files:")
    for c in changed:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
