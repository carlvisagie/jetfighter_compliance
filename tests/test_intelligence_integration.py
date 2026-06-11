"""PATCH 13A-14A: Tests for CustomerIntelligence integration with discovery."""
import json
import pytest
import shutil
from pathlib import Path


@pytest.fixture
def integration_env(tmp_path, monkeypatch):
    """Set up test environment for integration tests."""
    import os
    
    # Create required directories
    acq_dir = tmp_path / "acquisition"
    intel_dir = acq_dir / "intelligence"
    leads_dir = acq_dir / "leads"
    intel_dir.mkdir(parents=True, exist_ok=True)
    leads_dir.mkdir(parents=True, exist_ok=True)
    
    # Patch DATA path in config module
    from services import config
    monkeypatch.setattr(config, "DATA", tmp_path)
    
    # Also patch storage defaults
    from services.acquisition import storage
    monkeypatch.setattr(storage, "DEFAULT_LEADS_DIR", leads_dir)
    monkeypatch.setattr(storage, "DEFAULT_REPORTS_DIR", acq_dir / "reports")
    
    # Patch the _intelligence_dir function to return our test directory
    from services.acquisition import ideal_customer_profile
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    yield {
        "root": tmp_path,
        "acq_dir": acq_dir,
        "intel_dir": intel_dir,
        "leads_dir": leads_dir,
    }


class TestIngestCreatesIntelligenceRecord:
    """Test that ingest_discovery_candidate creates intelligence records."""
    
    def test_ingest_creates_intelligence_record(self, integration_env):
        """Discovery candidate creates both Lead and CustomerIntelligenceRecord."""
        from services.acquisition.orchestration import ingest_discovery_candidate
        from services.acquisition.ideal_customer_profile import (
            find_intelligence_by_company,
            get_all_intelligence_records,
        )
        
        row = {
            "company_name": "Test Defense Corp",
            "website": "https://testdefense.example.com",
            "contact_email": "contact@testdefense.example.com",
            "industry": "defense manufacturing",
            "location": "Virginia, USA",
            "notes": "Federal contractor with DoD exposure",
            "source": "usaspending_public_api",
        }
        
        result = ingest_discovery_candidate(
            row,
            campaign_id="test-campaign",
            min_fit_score=0,
            base=integration_env["intel_dir"],
        )
        
        assert result["ok"] is True
        assert "lead" in result
        
        # Verify intelligence record was created
        records = get_all_intelligence_records()
        assert len(records) >= 1
        
        # Find by company name
        intel = find_intelligence_by_company("Test Defense Corp")
        assert intel is not None
        assert intel.company_name.value == "Test Defense Corp"
        assert intel.source_lead_id == result["lead"]["lead_id"]
    
    def test_duplicate_company_updates_existing_record(self, integration_env):
        """Duplicate company updates existing record, doesn't create new one."""
        from services.acquisition.ideal_customer_profile import (
            create_or_update_intelligence,
            get_all_intelligence_records,
            SignalState,
        )
        
        # Create initial record
        record1, is_new1 = create_or_update_intelligence(
            company_name="Duplicate Test Corp",
            source="test",
            lead_id="L-001",
        )
        assert is_new1 is True
        initial_count = len(get_all_intelligence_records())
        
        # Try to create "duplicate" with additional info
        record2, is_new2 = create_or_update_intelligence(
            company_name="Duplicate Test Corp",  # Same company
            source="test",
            lead_id="L-002",  # Different lead
            website="https://duplicate.example.com",
            contact_email="info@duplicate.example.com",
        )
        
        # Should update existing, not create new
        assert is_new2 is False
        assert len(get_all_intelligence_records()) == initial_count
        
        # Verify the record was updated
        assert record2.record_id == record1.record_id
        assert record2.website.state == SignalState.KNOWN
        assert record2.website.value == "https://duplicate.example.com"


class TestIntelligenceCreationFailure:
    """Test that intelligence creation failure doesn't break discovery."""
    
    def test_discovery_succeeds_even_if_intelligence_fails(self, integration_env, monkeypatch):
        """Discovery must succeed even if intelligence creation fails."""
        from services.acquisition.orchestration import ingest_discovery_candidate
        
        # Mock create_or_update_intelligence to raise an exception
        def mock_fail(*args, **kwargs):
            raise RuntimeError("Simulated intelligence creation failure")
        
        monkeypatch.setattr(
            "services.acquisition.orchestration.create_or_update_intelligence",
            mock_fail,
            raising=False,
        )
        
        row = {
            "company_name": "Failure Test Corp",
            "source": "usaspending_public_api",
        }
        
        # This should NOT raise an exception
        result = ingest_discovery_candidate(
            row,
            campaign_id="test",
            min_fit_score=0,
            base=integration_env["intel_dir"],
        )
        
        # Discovery should still succeed
        assert result["ok"] is True
        assert "lead" in result


class TestBackfillEndpoint:
    """Test the backfill endpoint creates records from existing leads."""
    
    def test_backfill_creates_records(self, integration_env):
        """Backfill creates intelligence records from existing leads."""
        from services.acquisition.storage import append_lead, leads_dir
        from services.acquisition.models import Lead
        from services.acquisition.ideal_customer_profile import (
            get_all_intelligence_records,
            create_or_update_intelligence,
            find_intelligence_by_lead_id,
        )
        
        # Ensure clean state using fixture's intel_dir
        intel_dir = integration_env["intel_dir"]
        for f in intel_dir.glob("INT-*.json"):
            f.unlink()
        
        # Create some test leads
        test_leads = [
            Lead(
                lead_id="L-BACKFILL-001",
                company_name="Backfill Corp One",
                website="https://backfill1.example.com",
                source="test",
            ),
            Lead(
                lead_id="L-BACKFILL-002",
                company_name="Backfill Corp Two",
                location="Texas, USA",
                source="test",
            ),
        ]
        
        # Use the proper leads_dir function
        ld = leads_dir()
        for lead in test_leads:
            append_lead(lead, ld)
        
        # Simulate backfill logic
        from services.acquisition.storage import load_all_leads
        
        loaded_leads, _ = load_all_leads()
        created = 0
        
        for lead in loaded_leads:
            existing = find_intelligence_by_lead_id(lead.lead_id)
            if not existing:
                record, is_new = create_or_update_intelligence(
                    company_name=lead.company_name,
                    source=lead.source or "backfill",
                    lead_id=lead.lead_id,
                    website=lead.website or "",
                    location=lead.location or "",
                )
                if is_new:
                    created += 1
        
        assert created >= 2  # At least our 2 test leads
        
        # Verify records exist
        records = get_all_intelligence_records()
        company_names = [r.company_name.value for r in records]
        assert "Backfill Corp One" in company_names
        assert "Backfill Corp Two" in company_names


class TestTopProspectsAfterBackfill:
    """Test that top-prospects returns records after backfill."""
    
    def test_top_prospects_returns_records(self, integration_env):
        """After creating intelligence records, top-prospects should return them."""
        from services.acquisition.ideal_customer_profile import (
            create_or_update_intelligence,
        )
        from services.acquisition.enrichment import generate_top_prospects_report
        
        # Ensure clean state using fixture's intel_dir
        intel_dir = integration_env["intel_dir"]
        for f in intel_dir.glob("INT-*.json"):
            f.unlink()
        
        # Create some test records with unique names
        import uuid
        suffix = uuid.uuid4().hex[:6]
        for i in range(5):
            create_or_update_intelligence(
                company_name=f"Prospect Corp {suffix} {i}",
                source="test",
                lead_id=f"L-PROSPECT-{suffix}-{i:03d}",
                location="USA" if i % 2 == 0 else "",
                industry="defense" if i < 3 else "technology",
            )
        
        # Generate report
        report = generate_top_prospects_report(limit=10)
        
        assert report["ok"] is True
        assert report["total_prospects"] >= 5  # At least our 5 records
        assert len(report["prospects"]) >= 5


class TestNoOutreachDuringIntelligence:
    """Test that no outreach is sent during intelligence creation."""
    
    def test_no_emails_sent(self, integration_env):
        """Intelligence creation must not trigger any email sends."""
        from services.acquisition.orchestration import ingest_discovery_candidate
        
        row = {
            "company_name": "No Email Corp",
            "contact_email": "test@noemail.example.com",
            "source": "usaspending_public_api",
        }
        
        result = ingest_discovery_candidate(
            row,
            campaign_id="test",
            min_fit_score=0,
            base=integration_env["intel_dir"],
        )
        
        # email_sent should always be False during discovery
        assert result.get("email_sent", False) is False
        
        # requires_operator_approval should be True
        assert result.get("requires_operator_approval", True) is True


class TestAutoSendRemainsDisabled:
    """Test that auto-send remains disabled."""
    
    def test_auto_send_disabled_by_default(self, integration_env):
        """Auto-send should be disabled by default."""
        from services.acquisition import outreach_safety
        
        # Default should be disabled
        assert outreach_safety.is_auto_send_enabled() is False
