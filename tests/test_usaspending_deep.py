"""PATCH 13A-17: Tests for USASpending Deep Enrichment Engine."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def deep_env(tmp_path, monkeypatch):
    """Set up test environment for deep enrichment tests."""
    from services import config
    from services.acquisition import ideal_customer_profile
    
    intel_dir = tmp_path / "acquisition" / "intelligence"
    intel_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(ideal_customer_profile, "_intelligence_dir", lambda: intel_dir)
    
    yield {
        "root": tmp_path,
        "intel_dir": intel_dir,
    }


class TestUEIAcquisition:
    """Test UEI acquisition from USASpending."""
    
    @patch("services.acquisition.usaspending_deep._api_request")
    def test_acquire_uei_exact_match(self, mock_api):
        """UEI acquired with high confidence on exact match."""
        from services.acquisition.usaspending_deep import acquire_uei
        
        mock_api.return_value = {
            "results": [
                {
                    "recipient_name": "TEST CORP",
                    "uei": "ABC123XYZ",
                    "location": "Virginia",
                }
            ]
        }
        
        result = acquire_uei("TEST CORP")
        
        assert result.is_found() is True
        assert result.uei == "ABC123XYZ"
        assert result.confidence == 1.0
        assert result.location == "Virginia"
    
    @patch("services.acquisition.usaspending_deep._api_request")
    def test_acquire_uei_partial_match(self, mock_api):
        """UEI acquired with lower confidence on partial match."""
        from services.acquisition.usaspending_deep import acquire_uei
        
        mock_api.return_value = {
            "results": [
                {
                    "recipient_name": "TEST CORPORATION INC",
                    "uei": "DEF456",
                }
            ]
        }
        
        result = acquire_uei("TEST CORP")
        
        assert result.is_found() is True
        assert result.uei == "DEF456"
        assert result.confidence < 1.0
    
    @patch("services.acquisition.usaspending_deep._api_request")
    def test_acquire_uei_no_results(self, mock_api):
        """No UEI when API returns no results."""
        from services.acquisition.usaspending_deep import acquire_uei
        
        mock_api.return_value = {"results": []}
        
        result = acquire_uei("UNKNOWN COMPANY")
        
        assert result.is_found() is False
        assert result.uei is None


class TestAwardProfile:
    """Test award profile aggregation."""
    
    @patch("services.acquisition.usaspending_deep._api_request")
    def test_award_profile_dod_detection(self, mock_api):
        """DoD exposure correctly detected from agency names."""
        from services.acquisition.usaspending_deep import get_award_profile_by_name_fallback
        
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
        
        profile = get_award_profile_by_name_fallback("Test Corp")
        
        assert profile.success is True
        assert profile.contract_count == 2
        assert profile.total_contract_value == 1500000
        assert profile.dod_award_count == 2
        assert profile.dod_percentage > 0
    
    @patch("services.acquisition.usaspending_deep._api_request")
    def test_award_profile_naics_aggregation(self, mock_api):
        """NAICS codes properly aggregated."""
        from services.acquisition.usaspending_deep import get_award_profile_by_name_fallback
        
        mock_api.return_value = {
            "results": [
                {"Award Amount": 100, "NAICS Code": "332710", "Start Date": "2024-01-01"},
                {"Award Amount": 200, "NAICS Code": "332710", "Start Date": "2024-02-01"},
                {"Award Amount": 300, "NAICS Code": "336411", "Start Date": "2024-03-01"},
            ]
        }
        
        profile = get_award_profile_by_name_fallback("Test Corp")
        
        assert profile.success is True
        assert "332710" in profile.naics_codes
        assert profile.primary_naics == "332710"  # Most common


class TestNAICSIntelligence:
    """Test NAICS-based industry analysis."""
    
    def test_manufacturing_detection_from_naics(self):
        """Manufacturing detected from NAICS 31-33."""
        from services.acquisition.usaspending_deep import analyze_naics
        
        intel = analyze_naics(["332710", "332994"])
        
        assert intel.is_manufacturing is True
        assert intel.manufacturing_confidence >= 0.9
    
    def test_aerospace_detection_from_naics(self):
        """Aerospace detected from NAICS 3364xx."""
        from services.acquisition.usaspending_deep import analyze_naics
        
        intel = analyze_naics(["336411", "336412"])
        
        assert intel.is_aerospace is True
        assert intel.aerospace_confidence >= 0.9
    
    def test_manufacturing_detection_from_name(self):
        """Manufacturing detected from company name when no NAICS."""
        from services.acquisition.usaspending_deep import analyze_naics
        
        intel = analyze_naics([], "Precision Machining Inc")
        
        assert intel.is_manufacturing is True
        assert intel.manufacturing_confidence >= 0.5


class TestComplianceExposure:
    """Test compliance exposure assessment."""
    
    def test_cmmc_high_likelihood(self):
        """CMMC likelihood high with DoD exposure + manufacturing."""
        from services.acquisition.usaspending_deep import assess_compliance_exposure
        
        exposure = assess_compliance_exposure(
            dod_percentage=80.0,
            dod_award_count=10,
            is_manufacturing=True,
            is_defense=True,
            naics_codes=["332710"],
        )
        
        assert exposure.cmmc_likelihood >= 0.8
        assert len(exposure.cmmc_evidence) > 0
    
    def test_dfars_no_dod(self):
        """DFARS likelihood low without DoD exposure."""
        from services.acquisition.usaspending_deep import assess_compliance_exposure
        
        exposure = assess_compliance_exposure(
            dod_percentage=0.0,
            dod_award_count=0,
            is_manufacturing=True,
            is_defense=False,
            naics_codes=[],
        )
        
        assert exposure.dfars_likelihood == 0.0
    
    def test_likelihood_capped(self):
        """Likelihood never exceeds 0.95."""
        from services.acquisition.usaspending_deep import assess_compliance_exposure
        
        exposure = assess_compliance_exposure(
            dod_percentage=100.0,
            dod_award_count=100,
            is_manufacturing=True,
            is_defense=True,
            naics_codes=["336411"],
        )
        
        assert exposure.cmmc_likelihood <= 0.95
        assert exposure.dfars_likelihood <= 0.95


class TestDeepEnrichment:
    """Test deep enrichment end-to-end."""
    
    @patch("services.acquisition.usaspending_deep.acquire_uei")
    @patch("services.acquisition.usaspending_deep.get_award_profile_by_uei")
    def test_deep_enrich_collects_fields(
        self,
        mock_awards,
        mock_uei,
        deep_env,
    ):
        """Deep enrichment collects multiple fields."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.usaspending_deep import (
            deep_enrich_record,
            UEIResult,
            AwardProfile,
        )
        
        # Mock UEI acquisition
        mock_uei.return_value = UEIResult(
            uei="TEST123",
            recipient_name="Test Corp",
            location="Texas",
            confidence=0.95,
        )
        
        # Mock award profile
        mock_awards.return_value = AwardProfile(
            success=True,
            contract_count=5,
            total_contract_value=2500000,
            most_recent_award_date="2024-06-15",
            naics_codes=["332710"],
            primary_naics="332710",
            agencies=["Department of Defense"],
            dod_award_count=3,
            dod_award_value=1500000,
            dod_percentage=60.0,
            primary_location="Austin, TX",
        )
        
        # Create test record
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-DEEP-001"
        record.company_name = EvidencedValue(
            value="Test Corp",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(record)
        
        # Enrich
        result = deep_enrich_record(record, pause_seconds=0)
        
        assert result.success is True
        assert result.uei_acquired is True
        assert result.uei == "TEST123"
        assert len(result.fields_added) >= 5
        assert result.completeness_after > result.completeness_before
    
    def test_deep_enrich_no_company_name(self, deep_env):
        """Deep enrichment fails gracefully without company name."""
        from services.acquisition.ideal_customer_profile import CustomerIntelligenceRecord
        from services.acquisition.usaspending_deep import deep_enrich_record
        
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-NONAME"
        
        result = deep_enrich_record(record, pause_seconds=0)
        
        assert result.success is False
        assert "No company name" in result.errors


class TestNoOutreach:
    """Test that deep enrichment never triggers outreach."""
    
    @patch("services.acquisition.usaspending_deep.acquire_uei")
    @patch("services.acquisition.usaspending_deep.get_award_profile_by_uei")
    def test_no_emails_during_deep_enrichment(
        self,
        mock_awards,
        mock_uei,
        deep_env,
    ):
        """Deep enrichment must never send emails."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.usaspending_deep import (
            deep_enrich_record,
            UEIResult,
            AwardProfile,
        )
        
        mock_uei.return_value = UEIResult()
        mock_awards.return_value = AwardProfile(success=True)
        
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-NOEMAIL"
        record.company_name = EvidencedValue(
            value="No Email Corp",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(record)
        
        result = deep_enrich_record(record, pause_seconds=0)
        
        # Result should be evidence only
        result_dict = result.to_dict()
        assert "email_sent" not in result_dict
        assert "outreach" not in str(result_dict).lower()
