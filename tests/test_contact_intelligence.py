"""PATCH 13A-18: Tests for Contact Intelligence Engine."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def contact_env(tmp_path, monkeypatch):
    """Set up test environment for contact intelligence tests."""
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


class TestContactPageParsing:
    """Test HTML parsing for contact info."""
    
    def test_extract_mailto_link(self):
        """Email extracted from mailto link."""
        from services.acquisition.contact_intelligence import ContactPageParser
        
        html = '<a href="mailto:info@example.com">Contact Us</a>'
        
        parser = ContactPageParser()
        parser.feed(html)
        
        assert "info@example.com" in parser.emails
    
    def test_extract_email_from_text(self):
        """Email extracted from plain text."""
        from services.acquisition.contact_intelligence import ContactPageParser
        
        html = '<p>Email us at contact@testcompany.com for more info</p>'
        
        parser = ContactPageParser()
        parser.feed(html)
        
        assert "contact@testcompany.com" in parser.emails
    
    def test_extract_phone_from_tel_link(self):
        """Phone extracted from tel: link."""
        from services.acquisition.contact_intelligence import ContactPageParser
        
        html = '<a href="tel:+1-555-123-4567">Call Us</a>'
        
        parser = ContactPageParser()
        parser.feed(html)
        
        assert "+1-555-123-4567" in parser.phones
    
    def test_extract_phone_from_text(self):
        """Phone extracted from plain text."""
        from services.acquisition.contact_intelligence import ContactPageParser
        
        html = '<p>Call us: (555) 123-4567</p>'
        
        parser = ContactPageParser()
        parser.feed(html)
        
        assert any("555" in p and "123" in p for p in parser.phones)


class TestContactExtraction:
    """Test contact extraction logic."""
    
    @patch("services.acquisition.contact_intelligence._fetch_page")
    def test_priority_email_preference(self, mock_fetch):
        """info@ and contact@ emails prioritized over random emails."""
        from services.acquisition.contact_intelligence import extract_contacts_from_page
        
        mock_fetch.return_value = '''
            <html>
            <a href="mailto:random@company.com">Random</a>
            <a href="mailto:info@company.com">Info</a>
            </html>
        '''
        
        result = extract_contacts_from_page("http://example.com")
        
        assert result.email == "info@company.com"
        assert result.confidence >= 0.80
    
    @patch("services.acquisition.contact_intelligence._fetch_page")
    def test_no_email_no_contact(self, mock_fetch):
        """No contact found when page has no email."""
        from services.acquisition.contact_intelligence import extract_contacts_from_page
        
        mock_fetch.return_value = '<html><body>No contact info here</body></html>'
        
        result = extract_contacts_from_page("http://example.com")
        
        assert result.is_valid() is False
        assert result.email is None


class TestContactMetrics:
    """Test contact metrics computation."""
    
    def test_contactable_requires_email_and_identity(self, contact_env):
        """Contactable requires email AND (name OR title)."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.contact_intelligence import compute_contact_metrics
        
        # Record with email but no name/title
        r1 = CustomerIntelligenceRecord()
        r1.record_id = "INT-METRICS-001"
        r1.contact_email = EvidencedValue(
            value="test@example.com",
            source="test",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(r1)
        
        # Record with email AND name
        r2 = CustomerIntelligenceRecord()
        r2.record_id = "INT-METRICS-002"
        r2.contact_email = EvidencedValue(
            value="sales@example.com",
            source="test",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
        r2.contact_name = EvidencedValue(
            value="John Doe",
            source="test",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(r2)
        
        metrics = compute_contact_metrics()
        
        assert metrics["email_known_entities"] == 2
        assert metrics["contactable_entities"] == 1  # Only r2
    
    def test_contact_ready_requires_high_confidence(self, contact_env):
        """CONTACT_READY requires confidence >= 0.70."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.contact_intelligence import compute_contact_metrics
        
        # Low confidence email
        r1 = CustomerIntelligenceRecord()
        r1.record_id = "INT-CONF-001"
        r1.contact_email = EvidencedValue(
            value="test@low.com",
            source="test",
            confidence=0.5,  # Below threshold
            state=SignalState.KNOWN,
        )
        r1.contact_name = EvidencedValue(
            value="Jane Doe",
            source="test",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(r1)
        
        # High confidence email
        r2 = CustomerIntelligenceRecord()
        r2.record_id = "INT-CONF-002"
        r2.contact_email = EvidencedValue(
            value="test@high.com",
            source="test",
            confidence=0.85,  # Above threshold
            state=SignalState.KNOWN,
        )
        r2.contact_name = EvidencedValue(
            value="John Smith",
            source="test",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(r2)
        
        metrics = compute_contact_metrics()
        
        assert metrics["contact_ready_entities"] == 1  # Only r2


class TestContactRecommendation:
    """Test contact recommendation logic."""
    
    def test_contact_ready_recommendation(self, contact_env):
        """CONTACT_READY when email + identity + high confidence."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
        )
        from services.acquisition.contact_intelligence import (
            compute_contact_recommendation,
            ContactRecommendation,
        )
        
        record = CustomerIntelligenceRecord()
        record.contact_email = EvidencedValue(
            value="exec@company.com",
            source="Website",
            confidence=0.85,
            state=SignalState.KNOWN,
        )
        record.contact_name = EvidencedValue(
            value="CEO Name",
            source="Website",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        
        rec, reason = compute_contact_recommendation(record)
        
        assert rec == ContactRecommendation.CONTACT_READY
    
    def test_contactable_recommendation_without_name(self, contact_env):
        """CONTACTABLE when email known but no name."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
        )
        from services.acquisition.contact_intelligence import (
            compute_contact_recommendation,
            ContactRecommendation,
        )
        
        record = CustomerIntelligenceRecord()
        record.contact_email = EvidencedValue(
            value="info@company.com",
            source="Website",
            confidence=0.8,
            state=SignalState.KNOWN,
        )
        # No contact_name
        
        rec, reason = compute_contact_recommendation(record)
        
        assert rec == ContactRecommendation.CONTACTABLE
    
    def test_enrich_recommendation_with_website(self, contact_env):
        """ENRICH when website known but no contact."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
        )
        from services.acquisition.contact_intelligence import (
            compute_contact_recommendation,
            ContactRecommendation,
        )
        
        record = CustomerIntelligenceRecord()
        record.website = EvidencedValue(
            value="https://company.com",
            source="Discovery",
            confidence=0.9,
            state=SignalState.KNOWN,
        )
        # No contact_email
        
        rec, reason = compute_contact_recommendation(record)
        
        assert rec == ContactRecommendation.ENRICH


class TestNoOutreach:
    """Test that contact intelligence never triggers outreach."""
    
    @patch("services.acquisition.contact_intelligence.extract_contacts_from_website")
    def test_no_email_sent_during_enrichment(self, mock_extract, contact_env):
        """Contact enrichment must never send emails."""
        from services.acquisition.ideal_customer_profile import (
            CustomerIntelligenceRecord,
            EvidencedValue,
            SignalState,
            save_intelligence_record,
        )
        from services.acquisition.contact_intelligence import enrich_contact_intelligence
        
        mock_extract.return_value = {
            "email": "discovered@company.com",
            "phone": "555-1234",
            "source_url": "https://company.com/contact",
            "confidence": 0.85,
        }
        
        record = CustomerIntelligenceRecord()
        record.record_id = "INT-NOEMAIL"
        record.company_name = EvidencedValue(
            value="Test Corp",
            source="test",
            confidence=0.95,
            state=SignalState.KNOWN,
        )
        record.website = EvidencedValue(
            value="https://company.com",
            source="test",
            confidence=0.9,
            state=SignalState.KNOWN,
        )
        save_intelligence_record(record)
        
        result = enrich_contact_intelligence(record)
        
        # Result should only be evidence, no outreach
        result_dict = result.to_dict()
        assert "sent" not in str(result_dict).lower()
        assert "outreach" not in str(result_dict).lower()
        assert result.email_found or not result.errors
