import subprocess, sys
msg = (
    "fix: ghost reprocess button, remove demand text, spread gap story\n\n"
    "Three user-visible complaints fixed:\n\n"
    "1. PURPLE BUTTON UNDER RIBBON\n"
    "   .vio-l2-reproc opacity: 0.12 at rest, neutral faint color.\n"
    "   Button is invisible at a glance; hover reveals it to 0.7.\n"
    "   Armed-state (two-phase confirm) glows amber.\n\n"
    "2. TEXT ON CANVAS\n"
    "   Removed text label from drawDemandMarker. Arrow shape IS the\n"
    "   demand signal. Label survives as SVG <title> for tooltip only.\n\n"
    "3. ZERO STORY BEING TOLD\n"
    "   Gaps/confirmations were anchored to intake timestamp (same moment\n"
    "   as papers) -- all events compressed into one left-side cluster.\n"
    "   Re-anchored to ts:null = axis.timeToX(null) = rightmost (now).\n"
    "   Result: papers left (what arrived), gaps right (what is still\n"
    "   needed NOW). Contrast across spine IS the story.\n"
    "   Demand marker follows: gap/confirmation anchors now point at nowX.\n"
)
r = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True)
print(r.stdout)
print(r.stderr)
sys.exit(r.returncode)
