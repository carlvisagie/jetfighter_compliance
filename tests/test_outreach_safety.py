"""PATCH 13A-8A: Tests for acquisition outreach safety gate."""
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def safety_env(tmp_path, monkeypatch):
    """Isolated environment for outreach safety tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("KYC_DATA", str(data_dir))
    monkeypatch.setenv("ACQUISITION_AUTO_SEND_ENABLED", "false")
    monkeypatch.setenv("ACQUISITION_DAILY_SEND_CAP", "10")
    
    # Force reload of config
    import importlib
    import services.config
    importlib.reload(services.config)
    
    return data_dir


def test_auto_send_disabled_by_default(safety_env):
    """ACQUISITION_AUTO_SEND_ENABLED must default to false."""
    from services.acquisition.outreach_safety import is_auto_send_enabled
    assert is_auto_send_enabled() is False


def test_auto_send_enabled_when_flag_true(safety_env, monkeypatch):
    """Auto-send enabled only when explicitly set to true."""
    monkeypatch.setenv("ACQUISITION_AUTO_SEND_ENABLED", "true")
    
    import importlib
    import services.config
    importlib.reload(services.config)
    
    from services.acquisition.outreach_safety import is_auto_send_enabled
    assert is_auto_send_enabled() is True


def test_suppression_list(safety_env):
    """Test suppression list add and check."""
    from services.acquisition.outreach_safety import (
        add_to_suppression,
        is_suppressed,
        load_suppression_list,
    )
    
    # Initially empty
    assert len(load_suppression_list()) == 0
    assert is_suppressed("test@example.com") is False
    
    # Add to suppression
    result = add_to_suppression("test@example.com", reason="manual", note="test")
    assert result["ok"] is True
    
    # Now suppressed
    assert is_suppressed("test@example.com") is True
    assert is_suppressed("TEST@EXAMPLE.COM") is True  # Case insensitive


def test_optout_tracking(safety_env):
    """Test opt-out recording and checking."""
    from services.acquisition.outreach_safety import (
        record_optout,
        is_opted_out,
        is_suppressed,
    )
    
    # Initially not opted out
    assert is_opted_out("optout@example.com") is False
    
    # Record opt-out
    result = record_optout("optout@example.com", source="unsubscribe_link")
    assert result["ok"] is True
    
    # Now opted out and also suppressed
    assert is_opted_out("optout@example.com") is True
    assert is_suppressed("optout@example.com") is True


def test_daily_cap(safety_env):
    """Test daily send cap tracking."""
    from services.acquisition.outreach_safety import (
        get_daily_send_cap,
        get_daily_send_count,
        increment_daily_send_count,
        is_daily_cap_reached,
        get_remaining_daily_sends,
    )
    
    # Cap is 10 from fixture
    assert get_daily_send_cap() == 10
    assert get_daily_send_count() == 0
    assert is_daily_cap_reached() is False
    assert get_remaining_daily_sends() == 10
    
    # Increment
    for i in range(10):
        increment_daily_send_count()
    
    assert get_daily_send_count() == 10
    assert is_daily_cap_reached() is True
    assert get_remaining_daily_sends() == 0


def test_eligibility_check_auto_send_disabled(safety_env):
    """Eligibility should fail when auto-send is disabled."""
    from services.acquisition.outreach_safety import check_send_eligibility
    
    result = check_send_eligibility(
        "test@example.com",
        "L-001",
        require_operator_approval=True,
        operator_approved=False,
    )
    
    assert result["eligible"] is False
    assert result["reason"] == "auto_send_disabled"


def test_eligibility_check_with_operator_approval(safety_env):
    """Eligibility should pass with operator approval."""
    from services.acquisition.outreach_safety import check_send_eligibility
    
    result = check_send_eligibility(
        "test@example.com",
        "L-001",
        require_operator_approval=True,
        operator_approved=True,
    )
    
    assert result["eligible"] is True
    assert result["reason"] == "approved"


def test_eligibility_blocked_by_suppression(safety_env):
    """Eligibility should fail for suppressed emails."""
    from services.acquisition.outreach_safety import (
        add_to_suppression,
        check_send_eligibility,
    )
    
    add_to_suppression("blocked@example.com", reason="spam_complaint")
    
    result = check_send_eligibility(
        "blocked@example.com",
        "L-002",
        require_operator_approval=True,
        operator_approved=True,
    )
    
    assert result["eligible"] is False
    assert result["reason"] == "suppressed"


def test_eligibility_blocked_by_daily_cap(safety_env, monkeypatch):
    """Eligibility should fail when daily cap reached."""
    monkeypatch.setenv("ACQUISITION_DAILY_SEND_CAP", "1")
    
    import importlib
    import services.config
    importlib.reload(services.config)
    
    from services.acquisition.outreach_safety import (
        check_send_eligibility,
        increment_daily_send_count,
    )
    
    # Use up the cap
    increment_daily_send_count()
    
    result = check_send_eligibility(
        "test@example.com",
        "L-003",
        require_operator_approval=True,
        operator_approved=True,
    )
    
    assert result["eligible"] is False
    assert result["reason"] == "daily_cap_reached"


def test_send_log(safety_env):
    """Test send attempt logging."""
    from services.acquisition.outreach_safety import (
        log_send_attempt,
        load_send_log,
    )
    
    # Log some attempts
    log_send_attempt("L-001", "test@example.com", approved=True, sent=True, operator_approved=True, auto_send=False)
    log_send_attempt("L-002", "blocked@example.com", approved=False, sent=False, blocked_reason="suppressed", operator_approved=True, auto_send=False)
    
    log = load_send_log()
    assert len(log) == 2
    assert log[0]["lead_id"] == "L-001"
    assert log[0]["sent"] is True
    assert log[1]["lead_id"] == "L-002"
    assert log[1]["sent"] is False
    assert log[1]["blocked_reason"] == "suppressed"


def test_outreach_safety_status(safety_env):
    """Test safety status dashboard data."""
    from services.acquisition.outreach_safety import (
        get_outreach_safety_status,
        add_to_suppression,
        record_optout,
    )
    
    add_to_suppression("sup1@example.com")
    record_optout("opt1@example.com")
    
    status = get_outreach_safety_status()
    
    assert status["auto_send_enabled"] is False
    assert status["daily_cap"] == 10
    assert status["sent_today"] == 0
    assert status["suppression_count"] == 2  # sup1 + opt1 (optout also adds to suppression)
    assert status["optout_count"] == 1
    assert "Auto-send DISABLED" in status["policy_note"]
