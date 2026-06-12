"""PATCH 13A-15: Tests for Evidence Enrichment Engine."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def enrichment_env(tmp_path, monkeypatch):
    """Set up test environment for enrichment tests."""
    from services import config
    from services.acquisition import ideal_customer_profile
    
    # Create required directories
    intel_dir = tmp_path / "acquisition" / "intelligence"
    intel_dir.mkdir(parents=True, exist_ok=True)
    
    # Patch paths
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    yield {
        "root": tmp_path,
        "intel_dir": intel_dir,
    }


class TestEnrichmentEvidence:
    """Test evidence collection data structures."""
    
    def test_enrichment_evidence_creation(self):
        """EnrichmentEvidence captures field, value, source, confidence."""
        from services.acquisition.evidence_enrichment import EnrichmentEvidence
        
        evidence = EnrichmentEvidence(
            field_name="contract_value",
            value=12500000,
            source="USASpending Award Search",
            confidence=0.95,
        )
        
        assert evidence.field_name == "contract_value"
        assert evidence.value == 12500000
        assert evidence.source == "USASpending Award Search"
        assert evidence.confidence == 0.95
        assert evidence.collected_utc  # Auto-populated
    
    def test_enrichment_result_to_dict(self):
        """EnrichmentResult converts to dict with before/after metrics."""
        from services.acquisition.evidence_enrichment import EnrichmentResult, EnrichmentEvidence
        
        result = EnrichmentResult(
            record_id="INT-TEST-001",
            company_name="Test Corp",
            success=True,
            before_completeness=25,
            after_completeness=50,
            before_enrichment=20,
            after_enrichment=45,
            before_tier="TIER_3",
            after_tier="TIER_2",
            before_recommendation="ENRICH",
            after_recommendation="WATCH",
            evidence_collected=[
                EnrichmentEvidence("contract_value", 1000000, "USASpending", 0.95),
                EnrichmentEvidence("naics", "332710", "USASpending", 0.9),
            ],
        )
        
        d = result.to_dict()
        
        assert d["record_id"] == "INT-TEST-001"
        assert d["company_name"] == "Test Corp"
        assert d["success"] is True
        assert d["evidence_collected"] == 2
        assert d["before"]["completeness"] == 25
        assert d["after"]["completeness"] == 50
        assert d["delta"]["completeness"] == 25
        assert d["delta"]["tier_changed"] is True
        assert d["delta"]["recommendation_changed"] is True


class TestUSASpendingAPI:
    """Test USASpending API queries."""
    
    def test_search_recipient_by_name_empty(self):
        """Empty name returns empty list."""
        from services.acquisition.evidence_enrichment import search_recipient_by_name
        
        assert search_recipient_by_name("") == []
        assert search_recipient_by_name("ab") == []  # Too short
    
    @patch("services.acquisition.evidence_enrichment._api_request")
    def test_search_recipient_by_name_success(self, mock_api):
        """Successful recipient search returns results."""
        from services.acquisition.evidence_enrichment import search_recipient_by_name
        
        mock_api.return_value = {
            "results": [
                {"recipient_name": "Test Corp", "uei": "ABC123"},
                {"recipient_name": "Test Inc", "uei": "DEF456"},
            ]
        }
        
        results = search_recipient_by_name("Test Corp")
        
        assert len(results) == 2
        assert results[0]["recipient_name"] == "Test Corp"
        mock_api.assert_called_once()
    
    @patch("services.acquisition.evidence_enrichment._api_request")
    def test_get_recipient_awards_success(self, mock_api):
        """Award search returns aggregated data."""
        from services.acquisition.evidence_enrichment import get_recipient_awards
        
        mock_api.return_value = {
            "results": [
                {
                    "Award Amount": 1000000,
                    "Awarding Agency": "Department of Defense",
                    "NAICS Code": "332710",
                    "Start Date": "2024-01-15",
                },
                {
                    "Award Amount": 500000,
                    "Awarding Agency": "Department of the Navy",
                    "NAICS Code": "332710",
                    "Start Date": "2023-06-01",
                },
            ]
        }
        
        result = get_recipient_awards("Test Corp")
        
        assert result["ok"] is True
        assert result["awards_found"] == 2
        assert result["total_value"] == 1500000
        assert result["contract_count"] == 2
        assert result["has_dod_exposure"] is True
        assert "332710" in result["naics_codes"]


class TestIndustryIndicators:
    """Test industry indicator detection."""
    
    def test_manufacturing_indicator_from_naics(self):
        """Manufacturing detected from NAICS codes."""
        from services.acquisition.evidence_enrichment import detect_industry_indicators
        
        indicators = detect_industry_indicators(
            "Some Company",
            naics_codes=["332710"],  # Machine Shops
            agencies=[],
        )
        
        assert indicators.get("manufacturing_exposure") is True
    
    def test_manufacturing_indicator_from_name(self):
        """Manufacturing detected from company name."""
        from services.acquisition.evidence_enrichment import detect_industry_indicators
        
        indicators = detect_industry_indicators(
            "Precision Machining Inc",
            naics_codes=[],
            agencies=[],
        )
        
        assert indicators.get("manufacturing_exposure") is True
    
    def test_dod_indicator_from_agency(self):
        """DoD exposure detected from awarding agency."""
        from services.acquisition.evidence_enrichment import detect_industry_indicators
        
        indicators = detect_industry_indicators(
            "Generic Corp",
            naics_codes=[],
            agencies=["Department of Defense"],
        )
        
        assert indicators.get("dod_exposure") is True
    
    def test_aerospace_indicator_from_name(self):
        """Aerospace detected from company name."""
        from services.acquisition.evidence_enrichment import detect_industry_indicators
        
        indicators = detect_industry_indicators(
            "Aerospace Components LLC",
            naics_codes=[],
            agencies=[],
        )
        
        assert indicators.get("aerospace_exposure") is True


class TestCMMCDFARSLikelihood:
    """Test CMMC/DFARS likelihood estimation."""
    
    def test_high_likelihood_dod_manufacturing(self):
        """DoD + manufacturing = high CMMC/DFARS likelihood."""
        from services.acquisition.evidence_enrichment import estimate_cmmc_dfars_likelihood
        
        likelihood = estimate_cmmc_dfars_likelihood(
            dod_exposure=True,
            manufacturing=True,
            defense_in_name=True,
        )
        
        assert likelihood["cmmc_likelihood"] >= 0.8
        assert likelihood["dfars_likelihood"] >= 0.8
    
    def test_low_likelihood_no_dod(self):
        """No DoD exposure = low likelihood."""
        from services.acquisition.evidence_enrichment import estimate_cmmc_dfars_likelihood
        
        likelihood = estimate_cmmc_dfars_likelihood(
            dod_exposure=False,
            manufacturing=True,
            defense_in_name=False,
        )
        
        assert likelihood["cmmc_likelihood"] == 0.0
        assert likelihood["dfars_likelihood"] == 0.0
    
    def test_likelihood_capped_at_90(self):
        """Likelihood never exceeds 0.9 (no false certainty)."""
        from services.acquisition.evidence_enrichment import estimate_cmmc_dfars_likelihood
        
        likelihood = estimate_cmmc_dfars_likelihood(
            dod_exposure=True,
            manufacturing=True,
            defense_in_name=True,
        )
        
        assert likelihood["cmmc_likelihood"] <= 0.9
        assert likelihood["dfars_likelihood"] <= 0.9


class TestEnrichSingleCompany:
    """Test single company enrichment."""
    
    @patch("services.acquisition.evidence_enrichment.search_recipient_by_name")
    @patch("services.acquisition.evidence_enrichment.get_recipient_awards")
    @patch("services.acquisition.evidence_enrichment.discover_company_website")
    def test_enrich_collects_evidence(
        self,
        mock_website,
        mock_awards,
        mock_search,
        enrichment_env,
    ):
        """Enrichment collects evidence from multiple sources."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.evidence_enrichment import enrich_single_company
        
        # Mock API responses
        mock_search.return_value = [{"recipient_name": "Test Corp", "uei": "ABC123XYZ"}]
        mock_awards.return_value = {
            "ok": True,
            "awards_found": 5,
            "total_value": 2500000,
            "contract_count": 5,
            "most_recent_award": "2024-06-15",
            "agencies": ["Department of Defense"],
            "naics_codes": ["332710"],
            "has_dod_exposure": True,
        }
        mock_website.return_value = None  # No website found
        
        # Create test record
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-TEST-ENRICH-001"
        record.company_name = EvidencedValue(
            value="Test Corp",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(record)
        
        # Enrich
        result = enrich_single_company(record, pause_seconds=0)
        
        assert result.success is True
        assert len(result.evidence_collected) > 0
        
        # Check evidence was collected
        evidence_fields = [e.field_name for e in result.evidence_collected]
        assert "uei" in evidence_fields
        assert "contract_count" in evidence_fields
        assert "contract_value" in evidence_fields
    
    def test_enrich_handles_missing_company_name(self, enrichment_env):
        """Enrichment fails gracefully with no company name."""
        from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
        from services.acquisition.evidence_enrichment import enrich_single_company
        
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-TEST-NONAME"
        
        result = enrich_single_company(record, pause_seconds=0)
        
        assert result.success is False
        assert "No company name" in result.errors[0]


class TestEnrichmentComparison:
    """Test before/after comparison generation."""
    
    @patch("services.acquisition.evidence_enrichment.enrich_single_company")
    def test_comparison_shows_deltas(self, mock_enrich, enrichment_env):
        """Comparison report shows before/after deltas."""
        from services.acquisition.evidence_enrichment import (
            EnrichmentResult,
            EnrichmentEvidence,
        )
        
        # Mock enrichment result
        mock_result = EnrichmentResult(
            record_id="INT-001",
            company_name="Delta Corp",
            success=True,
            before_completeness=25,
            after_completeness=50,
            before_enrichment=20,
            after_enrichment=45,
            before_tier="TIER_3",
            after_tier="TIER_2",
            before_recommendation="ENRICH",
            after_recommendation="WATCH",
            evidence_collected=[
                EnrichmentEvidence("contract_value", 1000000, "USASpending", 0.95),
            ],
        )
        mock_enrich.return_value = mock_result
        
        # The delta calculation happens in to_dict()
        d = mock_result.to_dict()
        
        assert d["delta"]["completeness"] == 25
        assert d["delta"]["enrichment"] == 25
        assert d["delta"]["tier_changed"] is True
        assert d["delta"]["recommendation_changed"] is True


class TestNoOutreach:
    """Test that enrichment never triggers outreach."""
    
    @patch("services.acquisition.evidence_enrichment.search_recipient_by_name")
    @patch("services.acquisition.evidence_enrichment.get_recipient_awards")
    def test_no_emails_during_enrichment(
        self,
        mock_awards,
        mock_search,
        enrichment_env,
    ):
        """Enrichment must never send emails."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.evidence_enrichment import enrich_single_company
        
        mock_search.return_value = []
        mock_awards.return_value = {"ok": True, "awards_found": 0}
        
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-NOEMAIL-001"
        record.company_name = EvidencedValue(
            value="No Email Corp",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        record.contact_email = EvidencedValue(
            value="ceo@noemail.com",
            source="test",
            confidence=0.9,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(record)
        
        # This should NEVER trigger any email sending
        result = enrich_single_company(record, pause_seconds=0)
        
        # Result should be evidence collection only
        assert result.success is True
        # No email-related fields in result
        assert "email_sent" not in result.to_dict()
