"""PATCH 13A-9: Tests for intake classification system."""
import pytest
from pathlib import Path


@pytest.fixture
def classification_env(tmp_path, monkeypatch):
    """Isolated environment for classification tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("KYC_DATA", str(data_dir))
    
    # Create intakes directory structure
    intakes_dir = data_dir / "intakes"
    intakes_dir.mkdir()
    
    # Force reload of config
    import importlib
    import services.config
    importlib.reload(services.config)
    
    return data_dir


def test_auto_classify_test_email(classification_env):
    """Test emails should be classified as TEST."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-001",
        company_name="Acme Corp",
        contact_email="test@aegis.example",
    )
    assert cls == IntakeClassification.TEST
    assert "test" in reason.lower()


def test_auto_classify_validation_email(classification_env):
    """Verify emails should be classified as VALIDATION."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-002",
        company_name="Acme Corp",
        contact_email="verify123@test.keepyourcontracts.com",
    )
    assert cls == IntakeClassification.VALIDATION


def test_auto_classify_validation_company(classification_env):
    """Company names with Verify/Test patterns should be VALIDATION."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-003",
        company_name="PATCH13A4C Verify 20260611_102735",
        contact_email="user@company.com",
    )
    assert cls == IntakeClassification.VALIDATION


def test_auto_classify_validation_mode_flag(classification_env):
    """validation_mode flag should override other signals."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-004",
        company_name="Real Company LLC",
        contact_email="user@realcompany.com",
        validation_mode=True,
    )
    assert cls == IntakeClassification.VALIDATION
    assert "validation_mode" in reason


def test_auto_classify_unknown_requires_review(classification_env):
    """Unknown intakes without test signals should require review."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-005",
        company_name="Real Manufacturing Corp",
        contact_email="contact@realmanufacturing.com",
    )
    assert cls == IntakeClassification.REVIEW_REQUIRED


def test_classification_persistence(classification_env):
    """Classifications should persist to disk."""
    from services.intake.classification import (
        set_classification,
        get_classification,
        load_classifications,
        IntakeClassification,
    )
    
    set_classification(
        "FB-006",
        IntakeClassification.TEST,
        reason="manual test",
    )
    
    # Should be retrievable
    record = get_classification("FB-006")
    assert record is not None
    assert record["classification"] == "TEST"
    
    # Should persist across loads
    all_cls = load_classifications()
    assert "FB-006" in all_cls


def test_promote_to_real(classification_env):
    """Operator should be able to promote intake to REAL."""
    from services.intake.classification import (
        promote_to_real,
        get_classification,
    )
    
    result = promote_to_real("FB-007", operator_note="Verified customer")
    assert result["classification"] == "REAL"
    assert result["operator_override"] is True
    
    record = get_classification("FB-007")
    assert record["classification"] == "REAL"


def test_demote_to_test(classification_env):
    """Operator should be able to demote intake to TEST."""
    from services.intake.classification import (
        demote_to_test,
        get_classification,
    )
    
    result = demote_to_test("FB-008", operator_note="Internal testing")
    assert result["classification"] == "TEST"
    assert result["operator_override"] is True


def test_classification_summary(classification_env):
    """Summary should count by classification type."""
    from services.intake.classification import (
        set_classification,
        get_classification_summary,
        IntakeClassification,
    )
    
    set_classification("FB-010", IntakeClassification.TEST, "test")
    set_classification("FB-011", IntakeClassification.TEST, "test")
    set_classification("FB-012", IntakeClassification.VALIDATION, "validation")
    set_classification("FB-013", IntakeClassification.REAL, "real customer")
    
    summary = get_classification_summary()
    assert summary["by_type"]["TEST"] == 2
    assert summary["by_type"]["VALIDATION"] == 1
    assert summary["by_type"]["REAL"] == 1
    assert summary["real_customer_count"] == 1
    assert summary["first_real_customer_arrived"] is True
    assert summary["first_real_customer_id"] == "FB-013"


def test_operator_personal_email_is_test(classification_env):
    """Operator's personal email should be classified as TEST."""
    from services.intake.classification import auto_classify_intake, IntakeClassification
    
    cls, reason = auto_classify_intake(
        "FB-020",
        company_name="Aegis",
        contact_email="carlhvisagie@yahoo.com",
    )
    assert cls == IntakeClassification.TEST
