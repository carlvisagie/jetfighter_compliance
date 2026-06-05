"""Single-door contract: the Upload orb on the cognitive topology
constellation MUST go DIRECTLY to /ui/vio.html.

Carl, 2026-06-04: "ONLY ONE DOOR INTO VIO — Upload. Other orbs unchanged
— they are organism vitals, not VIO doors."

This guard pins three properties:

1. The click handler for `upload_pipeline` redirects to /ui/vio.html
   immediately (no intermediate detail panel, no scroll-to-queue).
2. Every OTHER orb still calls `showDetail(...)` (i.e. the panel
   behaviour is unchanged for them — they are NOT VIO doors).
3. Hover behaviour on the Upload orb is preserved (mouseenter still
   shows the preview), so the at-a-glance numbers stay available.

A future refactor that "unifies" the click handler (and incidentally
breaks the single-door rule) trips this test.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS   = ROOT / "ui" / "assets" / "js" / "cognitive-topology.js"


def test_upload_orb_redirects_directly_to_vio():
    src = JS.read_text(encoding="utf-8")
    # Find the click handler block. Tolerant of formatting.
    needle = "node.addEventListener('click', function ()"
    idx = src.find(needle)
    assert idx >= 0, "cognitive-topology.js must bind a click handler on .cote-node"

    block = src[idx:idx + 1200]

    # Must short-circuit on upload_pipeline.
    assert "nid === 'upload_pipeline'" in block, (
        "click handler must branch on upload_pipeline to honour the "
        "single-door rule"
    )
    assert "window.location.href = '/ui/vio.html'" in block, (
        "upload_pipeline click MUST redirect to /ui/vio.html — Carl's "
        "single-door rule (2026-06-04). No intermediate detail panel."
    )
    # The early-return prevents showDetail from running for upload.
    assert "return;" in block, (
        "upload_pipeline branch must `return;` after redirect so the "
        "old detail panel does NOT also fire (would flash the panel "
        "before navigation in some browsers)"
    )


def test_non_upload_orbs_still_show_detail_panel():
    """The single-door rule applies ONLY to Upload. Every other orb
    is organism infrastructure — clicking it should still surface its
    detail panel where the operator sees its vitals."""
    src = JS.read_text(encoding="utf-8")
    # The handler must still call showDetail for the non-upload path.
    idx = src.find("node.addEventListener('click'")
    assert idx >= 0
    block = src[idx:idx + 1200]
    assert "showDetail(nid, false" in block, (
        "non-upload orbs must still call showDetail — they are organism "
        "vitals, not VIO doors, and clicking them must surface the "
        "panel"
    )


def test_upload_orb_hover_still_previews():
    """Hovering the Upload orb (or any orb) should still preview the
    detail panel via mouseenter. Carl wants single click → VIO; he
    does NOT want to lose the hover-preview."""
    src = JS.read_text(encoding="utf-8")
    assert "node.addEventListener('mouseenter'" in src, (
        "mouseenter handler must still be wired so operators can "
        "preview an orb's detail without committing to a navigation"
    )
    # And the preview path must still call showDetail with hoverOnly=true.
    idx = src.find("node.addEventListener('mouseenter'")
    block = src[idx:idx + 400]
    assert "showDetail(node.getAttribute('data-node'), true)" in block, (
        "mouseenter must call showDetail(nid, true) (hover-only mode) "
        "so the panel previews without becoming the selected node"
    )


def test_inventory_records_door_status():
    """The kill-list table in VIO_ABSORPTION_INVENTORY.md must keep
    Upload pipeline visible as the single door. If this row vanishes
    in a refactor, the migration map loses the single-door contract."""
    doc = (ROOT / "docs" / "VIO_ABSORPTION_INVENTORY.md").read_text(encoding="utf-8")
    assert "Upload pipeline" in doc, (
        "VIO_ABSORPTION_INVENTORY.md must keep the Upload pipeline "
        "row — it names the single VIO door"
    )
    assert "SOLE door" in doc or "single VIO door" in doc.lower() or "sole door" in doc.lower(), (
        "The inventory must declare Upload as the SOLE door into VIO "
        "(Carl 2026-06-04). Without that declaration the kill-list "
        "loses its anchor."
    )
