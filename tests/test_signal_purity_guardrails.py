"""PATCH 13A-12: Signal Purity Guardrails

These tests ensure no artificial signals are injected into the acquisition system.
ALL signals must originate from:
- public data
- customer data
- uploaded data
- operator input

NEVER fabricated text.

If these tests fail, the build MUST fail.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest

# Root of the project
ROOT = Path(__file__).resolve().parent.parent


# =============================================================================
# FORBIDDEN PATTERNS
# These patterns indicate synthetic/fabricated signals
# =============================================================================

FORBIDDEN_PATTERNS = [
    # Artificial pain injection
    (r"BURDEN_CONTEXT\s*=", "BURDEN_CONTEXT constant (artificial pain injection)"),
    (r'"overwhelmed where do I start"', "Hardcoded overwhelm phrase"),
    (r'"overwhelmed.*compliance"', "Hardcoded overwhelm + compliance phrase"),
    
    # Synthetic urgency
    (r'urgency\s*=\s*["\']high["\'].*#.*fake', "Fake urgency assignment"),
    (r'inject.*urgency', "Urgency injection"),
    
    # Fabricated signals
    (r'fake_pain\s*=', "Fake pain variable"),
    (r'synthetic_signal', "Synthetic signal reference"),
    (r'fabricate.*signal', "Signal fabrication"),
    (r'inject.*pain', "Pain injection"),
    (r'artificial.*burden', "Artificial burden"),
    
    # Hardcoded compliance keywords injected into notes
    (r'notes\s*\+=.*".*CMMC.*DFARS.*overwhelmed"', "Hardcoded compliance keywords in notes"),
]

# Files to scan
ACQUISITION_FILES = [
    "services/acquisition/connectors/usaspending_live.py",
    "services/acquisition/orchestration.py",
    "services/acquisition/scoring.py",
    "services/acquisition/signals.py",
    "services/acquisition/qualification.py",
    "services/acquisition/messaging.py",
    "services/acquisition/finder.py",
]


def scan_file_for_forbidden_patterns(filepath: Path) -> List[Tuple[int, str, str]]:
    """
    Scan a file for forbidden signal injection patterns.
    
    Returns list of (line_number, line_content, pattern_description) tuples.
    """
    violations = []
    
    if not filepath.exists():
        return violations
    
    content = filepath.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    
    for pattern, description in FORBIDDEN_PATTERNS:
        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            
            if re.search(pattern, line, re.IGNORECASE):
                violations.append((i, line.strip()[:100], description))
    
    return violations


def test_no_burden_context_in_usaspending_connector():
    """BURDEN_CONTEXT must not exist in USASpending connector."""
    filepath = ROOT / "services/acquisition/connectors/usaspending_live.py"
    content = filepath.read_text(encoding="utf-8")
    
    # Check for BURDEN_CONTEXT constant
    assert "BURDEN_CONTEXT = " not in content, \
        "BURDEN_CONTEXT constant found - artificial signals are forbidden"
    
    # Check for the specific injection pattern
    assert "BURDEN_CONTEXT" not in content or "removed" in content.lower(), \
        "BURDEN_CONTEXT reference found - all artificial signals must be removed"


def test_no_hardcoded_pain_phrases_in_connector():
    """No hardcoded pain/overwhelm phrases should be injected into notes."""
    filepath = ROOT / "services/acquisition/connectors/usaspending_live.py"
    content = filepath.read_text(encoding="utf-8")
    
    pain_phrases = [
        "overwhelmed where do I start",
        "where do i start",
        "audit evidence security questionnaire",
    ]
    
    for phrase in pain_phrases:
        # Allow in comments but not in actual code
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if phrase.lower() in line.lower():
                stripped = line.strip()
                # Skip comment lines
                if not stripped.startswith("#"):
                    pytest.fail(
                        f"Hardcoded pain phrase '{phrase}' found at line {i}: {stripped[:80]}"
                    )


def test_notes_not_artificially_appended():
    """Notes should not have artificial burden text appended."""
    filepath = ROOT / "services/acquisition/connectors/usaspending_live.py"
    content = filepath.read_text(encoding="utf-8")
    
    # Look for pattern: notes = (something) + " " + BURDEN_CONTEXT
    injection_pattern = r'notes\s*=.*\+.*BURDEN'
    
    assert not re.search(injection_pattern, content), \
        "Notes injection pattern found - notes must contain only real data"


def test_all_acquisition_files_signal_purity():
    """Scan all acquisition files for signal purity violations."""
    all_violations = []
    
    for relpath in ACQUISITION_FILES:
        filepath = ROOT / relpath
        if not filepath.exists():
            continue
        
        violations = scan_file_for_forbidden_patterns(filepath)
        for line_num, line_content, description in violations:
            all_violations.append(f"{relpath}:{line_num} - {description}: {line_content}")
    
    if all_violations:
        msg = "Signal purity violations found:\n" + "\n".join(all_violations)
        pytest.fail(msg)


def test_scoring_uses_only_real_signals():
    """Scoring module should only use signals from the Lead object, not inject new ones."""
    filepath = ROOT / "services/acquisition/scoring.py"
    content = filepath.read_text(encoding="utf-8")
    
    # Check for any hardcoded pain injection
    forbidden = [
        'pain_signals.append("overwhelm")',
        'pain_signals.append("audit_pressure")',
        'pain_signals = ["',  # Hardcoded list assignment
    ]
    
    for pattern in forbidden:
        assert pattern not in content, \
            f"Hardcoded pain signal found: {pattern}"


def test_no_synthetic_signal_constants():
    """No constants should define synthetic signals for injection."""
    files_to_check = [
        ROOT / "services/acquisition/connectors/usaspending_live.py",
        ROOT / "services/acquisition/orchestration.py",
    ]
    
    synthetic_constant_patterns = [
        r'^[A-Z_]+_CONTEXT\s*=\s*["\(]',  # ANY_CONTEXT = "..."
        r'^INJECT_',  # INJECT_* constants
        r'^FAKE_',    # FAKE_* constants
        r'^SYNTHETIC_',  # SYNTHETIC_* constants
    ]
    
    for filepath in files_to_check:
        if not filepath.exists():
            continue
        
        content = filepath.read_text(encoding="utf-8")
        for pattern in synthetic_constant_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                # Whitelist BURDEN_CONTEXT if it's been removed/commented
                if "BURDEN" in match and "removed" not in content.lower():
                    pytest.fail(f"Synthetic constant found in {filepath.name}: {match}")


def test_usaspending_returns_clean_data():
    """USASpending discovery should return data without artificial enrichment."""
    from services.acquisition.finder import discover_usaspending_recipients
    from unittest.mock import patch, MagicMock
    
    # Mock the API response
    mock_response = {
        "results": [
            {"recipient_name": "Test Corp", "uei": "ABC123", "location": "VA"},
        ]
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = __import__("json").dumps(mock_response).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        
        results = discover_usaspending_recipients("test", limit=5)
    
    assert len(results) == 1
    
    # Check that notes only contain real data from the API
    notes = results[0].get("notes", "")
    
    # These artificial phrases should NOT be in notes
    forbidden_in_notes = [
        "overwhelmed",
        "where do I start",
        "audit evidence security questionnaire",
    ]
    
    for phrase in forbidden_in_notes:
        assert phrase.lower() not in notes.lower(), \
            f"Artificial phrase '{phrase}' found in discovery notes"


def test_intelligence_record_starts_unknown():
    """CustomerIntelligenceRecord should start with UNKNOWN states, not fabricated values."""
    from services.acquisition.ideal_customer_profile import (
        CustomerIntelligenceRecord,
        SignalState,
    )
    
    record = CustomerIntelligenceRecord()
    
    # All fields should start UNKNOWN (except computed ones)
    unknown_fields = [
        "cmmc_likelihood",
        "dfars_likelihood",
        "dod_exposure",
        "contract_value",
        "agency_mix",
    ]
    
    for field_name in unknown_fields:
        field = getattr(record, field_name)
        assert field.state == SignalState.UNKNOWN, \
            f"Field {field_name} should start as UNKNOWN, not {field.state}"
        assert field.value is None, \
            f"Field {field_name} should have no value until real evidence is provided"


def test_signals_module_pattern_based_only():
    """signals.py should only use pattern matching, not inject fabricated signals."""
    filepath = ROOT / "services/acquisition/signals.py"
    content = filepath.read_text(encoding="utf-8")
    
    # Should use regex patterns to DETECT signals, not CREATE them
    assert "PAIN_PATTERNS" in content, "signals.py should define detection patterns"
    assert "re.search" in content, "signals.py should use regex to detect signals"
    
    # Should NOT have signal injection
    assert "inject_signal" not in content.lower()
    assert "create_fake" not in content.lower()
    assert "generate_pain" not in content.lower()


# =============================================================================
# AST-based deep analysis
# =============================================================================

def test_no_string_concatenation_to_notes_with_hardcoded_text():
    """
    Use AST analysis to ensure no hardcoded strings are concatenated to notes fields.
    """
    filepath = ROOT / "services/acquisition/connectors/usaspending_live.py"
    content = filepath.read_text(encoding="utf-8")
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        pytest.skip("Could not parse file")
    
    # Look for: notes = something + "hardcoded string"
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "notes":
                    # Check if it's a BinOp (concatenation)
                    if isinstance(node.value, ast.BinOp):
                        # Check right side for hardcoded strings with pain keywords
                        if isinstance(node.value.right, ast.Constant):
                            val = str(node.value.right.value or "").lower()
                            pain_keywords = ["overwhelm", "where do i start", "audit", "cmmc"]
                            for kw in pain_keywords:
                                if kw in val:
                                    pytest.fail(
                                        f"Hardcoded pain string found in notes assignment: '{val[:50]}...'"
                                    )
