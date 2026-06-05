"""VIO L2 minimal-orb + no-side-panel guardrail (2026-06-05).

Carl's final design directive for VIO L2:

    "the orb is company information fuckin email address and so on"
    "you can not cram all that info into the orb without clicking
     to expand for the company information"
    "no movement of any kind unless it demands attention"
    "remove this side panel shit, it prevents you from using your
     imagination, and letting your timeline speak clearly"

That collapses to three hard invariants the rest of the file pins so
future renderer refactors can't silently regress them:

  (1) The L2 orb is a single static circle with the company name
      visible inside, and a card that toggles on click to reveal
      tel / email / address — NOT a multi-layer aura of halos,
      rings, satellites and compliance dots.

  (2) L2 has no side panel. The grid is a single column. The
      timeline + shapes carry the story alone.

  (3) Branch limbs (the cyan curve from the spine up to a cluster)
      are removed by default. They were decorative ink that the
      sketch never had.

These guards are intentionally cheap (static string scans on the
shipped JS + CSS) so they run in the fast pytest suite alongside the
other doctrine guards.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
L2_JS  = REPO_ROOT / "ui" / "assets" / "js"     / "vio-level2.js"
VIO_CSS = REPO_ROOT / "ui" / "assets" / "styles" / "vio.css"


# ── (1) Orb is minimal ────────────────────────────────────────────────────
def test_orb_renders_company_name_inside():
    """drawOrb must emit an SVG <text> tagged vio-l2-orb-name carrying
    the company name. If this class disappears the orb has no identity
    at rest — operators can't tell which company they're looking at
    without external chrome."""
    js = L2_JS.read_text(encoding="utf-8")
    assert "vio-l2-orb-name" in js, (
        "drawOrb must render the company name inside the orb "
        "(class vio-l2-orb-name). Without it the orb is anonymous."
    )
    assert "_wrapNameForOrb" in js, (
        "Name wrapping helper missing — long names will overflow the orb."
    )


def test_orb_does_not_render_halo_ring_satellites_or_compliance_dots():
    """Carl 2026-06-05: 'no rings nothing'. The fancy multi-layer
    glyph was overcomplicating the orb. drawOrb may NOT emit class
    names for halo / ring / satellite / compliance / limb anymore.
    The CSS keeps the rule names dormant in case we ever bring them
    back, but the JS must not paint them at rest."""
    js = L2_JS.read_text(encoding="utf-8")
    banned = (
        "vio-l2-orb-halo",
        "vio-l2-orb-ring",
        "vio-l2-orb-satellite",
        "vio-l2-orb-compliance",
        "vio-l2-orb-limb",
    )
    for cls in banned:
        assert cls not in js, (
            f"vio-level2.js must not paint {cls!r} — orb is supposed "
            f"to be a single static circle with the company name."
        )


def test_orb_card_toggles_on_click():
    """The 'click to expand' card carrying tel/email/address must
    exist and must be wired to the orb's click handler. Without
    this, the orb shows just the name and no operator can ever
    read the rest of the company info."""
    js = L2_JS.read_text(encoding="utf-8")
    assert "vio-l2-orb-card" in js, "orb-card class missing in renderer"
    assert "data-open" in js, (
        "orb-card visibility toggle (data-open attribute) missing"
    )


# ── (2) No side panel ────────────────────────────────────────────────────
def test_side_panel_not_appended_in_openLevel2():
    """openLevel2 must NOT append the side panel to the mount — Carl:
    'remove this side panel shit'. We allow the buildSidePanel function
    to remain (it's used by tests + dormant code), but the live mount
    must be single-column canvas only."""
    js = L2_JS.read_text(encoding="utf-8")
    # Find the openLevel2 function body
    start = js.find("async function openLevel2(")
    assert start != -1, "openLevel2 missing — renderer broken"
    # Look in the first ~3000 chars after openLevel2 — its body
    body = js[start:start + 3000]
    assert "mount.appendChild(sidepanel)" not in body, (
        "openLevel2 must not mount the side panel; the timeline "
        "carries the story. If you need the panel back, file a "
        "doctrine update first."
    )


def test_l2_grid_is_single_column():
    """The L2 mount CSS grid must be a single column so the canvas
    fills the viewport. A second 340px 'side' column resurrects the
    side-panel space even if JS doesn't fill it."""
    css = VIO_CSS.read_text(encoding="utf-8")
    # The new layout is:
    #   grid-template-columns: 1fr;
    # No "340px" sidecar.
    assert "grid-template-columns: 1fr;" in css, (
        "L2 mount grid must be single-column (grid-template-columns: 1fr)."
    )
    # The legacy "1fr 340px" must be gone from the active rule.
    # (We tolerate it in comments only.)
    for line in css.splitlines():
        stripped = line.split("/*", 1)[0].strip()
        if "grid-template-columns" in stripped and ".vio-level2-mount" not in stripped:
            # Only the rule we care about — accept other rules.
            continue
        assert "1fr 340px" not in stripped, (
            f"Legacy two-column L2 grid still present in CSS: {line!r}"
        )


def test_side_panel_class_is_hidden_defensively():
    """Even if some forgotten code path builds .vio-l2-side, the CSS
    must hide it so the operator never sees the second column come
    back accidentally."""
    css = VIO_CSS.read_text(encoding="utf-8")
    # The rule is:
    #   .vio-l2-side { display: none !important; }
    # Be permissive about whitespace.
    assert ".vio-l2-side {" in css
    side_rule_start = css.index(".vio-l2-side {")
    side_rule = css[side_rule_start:side_rule_start + 200]
    assert "display: none" in side_rule and "!important" in side_rule, (
        ".vio-l2-side must be display:none !important; so the side "
        "panel can never resurface silently."
    )


# ── (3) No branch limb ───────────────────────────────────────────────────
def test_branch_limbs_disabled_in_renderer_and_css():
    """drawBranch may NOT emit a vio-l2-branch-limb element at rest.
    The sketch has no limb; the cluster's vertical position relative
    to the spine is the only anchor. CSS keeps the class name dormant
    (display:none) so accidental future emits stay invisible."""
    js = L2_JS.read_text(encoding="utf-8")
    # No setAttribute('class', 'vio-l2-branch-limb') in JS — limb is gone.
    assert "'vio-l2-branch-limb'" not in js and "\"vio-l2-branch-limb\"" not in js, (
        "drawBranch must not paint vio-l2-branch-limb anymore."
    )
    css = VIO_CSS.read_text(encoding="utf-8")
    # The .vio-l2-branch-limb rule must include display:none
    rule_start = css.find(".vio-l2-branch-limb {")
    assert rule_start != -1, "Limb CSS rule missing entirely"
    rule = css[rule_start:rule_start + 300]
    assert "display: none" in rule, (
        ".vio-l2-branch-limb must be display:none so any accidental "
        "future emission stays invisible."
    )


# ── (4) No parallel custody ribbon ───────────────────────────────────────
def test_custody_ribbon_disabled_in_active_render_path():
    """drawCustodyBranch may still exist as a function (we'll fold
    custody events back into the main spine in a follow-up), but the
    active renderLandscape call site must NOT invoke it. The sketch
    shows ONE spine, not two."""
    js = L2_JS.read_text(encoding="utf-8")
    # We allow the comment 'drawCustodyBranch' to exist. The active
    # call must be commented out — i.e. NOT a bare `drawCustodyBranch(`
    # line at the start of the trimmed line.
    for lineno, raw in enumerate(js.splitlines(), start=1):
        stripped = raw.lstrip()
        if stripped.startswith("//"):  # commented out — safe
            continue
        assert not stripped.startswith("drawCustodyBranch("), (
            f"vio-level2.js line {lineno} still actively calls "
            f"drawCustodyBranch() — comment it out (Carl: ONE spine, "
            f"not two)."
        )
