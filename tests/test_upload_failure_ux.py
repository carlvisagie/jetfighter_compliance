import re
from pathlib import Path

def test_upload_failure_ux_magic_link_not_shown():
    js = Path("ui/assets/js/intake.js").read_text(encoding="utf-8")
    assert "Use your magic link to retry missing files." not in js
    assert "Some selected files did not upload successfully. Please re-select the missing files below and upload again." in js

def test_upload_failure_ux_missing_file_count_shown():
    js = Path("ui/assets/js/intake.js").read_text(encoding="utf-8")
    assert "missingCount + ' selected files did not verify" in js

def test_upload_failure_ux_verified_file_count_shown():
    js = Path("ui/assets/js/intake.js").read_text(encoding="utf-8")
    assert "verified_file_count" in js

def test_upload_failure_ux_missing_filenames_shown():
    js = Path("ui/assets/js/intake.js").read_text(encoding="utf-8")
    assert "Missing files:\\n" in js
    assert "missingFiles.forEach(" in js

def test_upload_failure_ux_customer_can_retry():
    js = Path("ui/assets/js/intake.js").read_text(encoding="utf-8")
    # Verify the selector is cleared so they can retry
    assert "selectedFiles = [];" in js
    assert "window.kycExpectedRetryCount = missingCount;" in js
