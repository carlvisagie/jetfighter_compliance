#!/usr/bin/env python3
"""
PATCH ACQ-IMPLEMENT-2: SAM Contactability Validation Script

Validates SAM contactability extraction on 30 SAM-eligible companies.
Reports:
- Websites discovered
- Contacts discovered
- Decision makers discovered
- Contactability improvement
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.external_verification.sam_gov import (
    extract_sam_contactability,
    sam_contactability_to_dict,
    is_api_configured,
)
from services.acquisition.ideal_customer_profile import (
    get_all_intelligence_records,
    save_intelligence_record,
    EvidencedValue,
    SignalState,
)


def run_sam_validation(limit: int = 30, update_records: bool = True) -> Dict[str, Any]:
    """
    Run SAM contactability validation on SAM-eligible companies.
    
    Args:
        limit: Maximum number of companies to validate
        update_records: Whether to update CustomerIntelligenceRecords with SAM data
    
    Returns:
        Validation report dictionary
    """
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_configured": is_api_configured(),
        "limit": limit,
        "update_records": update_records,
        
        # Pre-validation state
        "pre_validation": {
            "total_records": 0,
            "with_uei": 0,
            "with_website": 0,
            "with_contact_email": 0,
            "with_contact_name": 0,
            "contactable": 0,
        },
        
        # SAM API results
        "sam_results": {
            "queried": 0,
            "api_success": 0,
            "api_failed": 0,
            "not_found": 0,
            "website_found": 0,
            "poc_found": 0,
            "email_found": 0,
            "phone_found": 0,
        },
        
        # Post-validation state
        "post_validation": {
            "with_website": 0,
            "with_contact_email": 0,
            "with_contact_name": 0,
            "contactable": 0,
        },
        
        # Improvement
        "improvement": {
            "website_delta": 0,
            "contact_email_delta": 0,
            "contact_name_delta": 0,
            "contactable_delta": 0,
        },
        
        # Detailed results
        "companies": [],
        
        # Errors
        "errors": [],
    }
    
    if not is_api_configured():
        report["errors"].append("SAM_GOV_API_KEY not configured")
        return report
    
    # Get all records
    all_records = get_all_intelligence_records()
    report["pre_validation"]["total_records"] = len(all_records)
    
    # Filter to records with UEI
    uei_records = [r for r in all_records if r.uei and r.uei.value]
    report["pre_validation"]["with_uei"] = len(uei_records)
    
    # Get unique UEIs (some may be duplicates)
    seen_ueis = set()
    unique_records = []
    for r in uei_records:
        uei = r.uei.value
        if uei not in seen_ueis:
            seen_ueis.add(uei)
            unique_records.append(r)
    
    # Limit to requested count
    records_to_validate = unique_records[:limit]
    
    # Pre-validation metrics
    for r in uei_records:
        if r.website.state == SignalState.KNOWN and r.website.value:
            report["pre_validation"]["with_website"] += 1
        if r.contact_email.state == SignalState.KNOWN and r.contact_email.value:
            report["pre_validation"]["with_contact_email"] += 1
        if r.contact_name.state == SignalState.KNOWN and r.contact_name.value:
            report["pre_validation"]["with_contact_name"] += 1
        if (r.website.state == SignalState.KNOWN and r.website.value and
            r.contact_email.state == SignalState.KNOWN and r.contact_email.value):
            report["pre_validation"]["contactable"] += 1
    
    # Run SAM validation
    print(f"Validating {len(records_to_validate)} companies against SAM.gov...")
    
    for i, record in enumerate(records_to_validate, 1):
        uei = record.uei.value
        company = record.company_name.value or "Unknown"
        
        print(f"  [{i}/{len(records_to_validate)}] {uei} - {company[:40]}...")
        
        company_result = {
            "uei": uei,
            "company_name": company,
            "record_id": record.record_id,
            "pre_website": record.website.value,
            "pre_contact_email": record.contact_email.value,
            "pre_contact_name": record.contact_name.value,
            "sam_result": None,
            "post_website": None,
            "post_contact_email": None,
            "post_contact_name": None,
            "updated": False,
        }
        
        report["sam_results"]["queried"] += 1
        
        try:
            sam_data = extract_sam_contactability(uei)
            company_result["sam_result"] = sam_contactability_to_dict(sam_data)
            
            if sam_data.api_success:
                report["sam_results"]["api_success"] += 1
                
                if sam_data.website:
                    report["sam_results"]["website_found"] += 1
                
                if sam_data.all_pocs:
                    report["sam_results"]["poc_found"] += 1
                
                if sam_data.poc_email:
                    report["sam_results"]["email_found"] += 1
                
                if sam_data.poc_phone:
                    report["sam_results"]["phone_found"] += 1
                
                # Update record if requested
                if update_records:
                    updated = False
                    
                    # Website
                    if sam_data.website and record.website.state == SignalState.UNKNOWN:
                        record.website = EvidencedValue(
                            value=sam_data.website,
                            source="sam_gov_entity_api",
                            confidence=0.95,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    # Contact email
                    if sam_data.poc_email and record.contact_email.state == SignalState.UNKNOWN:
                        record.contact_email = EvidencedValue(
                            value=sam_data.poc_email,
                            source="sam_gov_poc",
                            confidence=0.90,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    # Contact name
                    full_name = f"{sam_data.poc_first_name or ''} {sam_data.poc_last_name or ''}".strip()
                    if full_name and record.contact_name.state == SignalState.UNKNOWN:
                        record.contact_name = EvidencedValue(
                            value=full_name,
                            source="sam_gov_poc",
                            confidence=0.90,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    # Contact phone
                    if sam_data.poc_phone and record.contact_phone.state == SignalState.UNKNOWN:
                        record.contact_phone = EvidencedValue(
                            value=sam_data.poc_phone,
                            source="sam_gov_poc",
                            confidence=0.90,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    # Contact title
                    if sam_data.poc_title and record.contact_title.state == SignalState.UNKNOWN:
                        record.contact_title = EvidencedValue(
                            value=sam_data.poc_title,
                            source="sam_gov_poc",
                            confidence=0.90,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    # Decision maker (if POC looks like decision maker)
                    if sam_data.poc_title:
                        title_lower = sam_data.poc_title.lower()
                        is_decision_maker = any(t in title_lower for t in [
                            "president", "owner", "ceo", "founder", "director",
                            "manager", "officer", "executive", "partner",
                        ])
                        if is_decision_maker and record.decision_maker_name.state == SignalState.UNKNOWN:
                            record.decision_maker_name = EvidencedValue(
                                value=full_name,
                                source="sam_gov_poc",
                                confidence=0.85,
                                state=SignalState.KNOWN,
                            )
                            record.decision_maker_title = EvidencedValue(
                                value=sam_data.poc_title,
                                source="sam_gov_poc",
                                confidence=0.85,
                                state=SignalState.KNOWN,
                            )
                            record.decision_maker_source = EvidencedValue(
                                value="sam_gov",
                                source="sam_gov_poc",
                                confidence=0.85,
                                state=SignalState.KNOWN,
                            )
                            updated = True
                    
                    # Legal name update
                    if sam_data.legal_name and record.legal_name.state == SignalState.UNKNOWN:
                        record.legal_name = EvidencedValue(
                            value=sam_data.legal_name,
                            source="sam_gov_entity_api",
                            confidence=0.99,
                            state=SignalState.KNOWN,
                        )
                        updated = True
                    
                    if updated:
                        save_intelligence_record(record)
                        company_result["updated"] = True
                
                company_result["post_website"] = record.website.value
                company_result["post_contact_email"] = record.contact_email.value
                company_result["post_contact_name"] = record.contact_name.value
                
            elif sam_data.error and "not found" in sam_data.error.lower():
                report["sam_results"]["not_found"] += 1
            else:
                report["sam_results"]["api_failed"] += 1
                
        except Exception as e:
            report["errors"].append(f"Error processing {uei}: {str(e)}")
            report["sam_results"]["api_failed"] += 1
        
        report["companies"].append(company_result)
    
    # Post-validation metrics (re-read records)
    all_records = get_all_intelligence_records()
    uei_records = [r for r in all_records if r.uei and r.uei.value]
    
    for r in uei_records:
        if r.website.state == SignalState.KNOWN and r.website.value:
            report["post_validation"]["with_website"] += 1
        if r.contact_email.state == SignalState.KNOWN and r.contact_email.value:
            report["post_validation"]["with_contact_email"] += 1
        if r.contact_name.state == SignalState.KNOWN and r.contact_name.value:
            report["post_validation"]["with_contact_name"] += 1
        if (r.website.state == SignalState.KNOWN and r.website.value and
            r.contact_email.state == SignalState.KNOWN and r.contact_email.value):
            report["post_validation"]["contactable"] += 1
    
    # Calculate improvement
    report["improvement"]["website_delta"] = (
        report["post_validation"]["with_website"] - report["pre_validation"]["with_website"]
    )
    report["improvement"]["contact_email_delta"] = (
        report["post_validation"]["with_contact_email"] - report["pre_validation"]["with_contact_email"]
    )
    report["improvement"]["contact_name_delta"] = (
        report["post_validation"]["with_contact_name"] - report["pre_validation"]["with_contact_name"]
    )
    report["improvement"]["contactable_delta"] = (
        report["post_validation"]["contactable"] - report["pre_validation"]["contactable"]
    )
    
    return report


def format_report(report: Dict[str, Any]) -> str:
    """Format report as markdown."""
    lines = [
        "# SAM CONTACTABILITY ACTIVATION REPORT",
        "",
        f"**PATCH**: ACQ-IMPLEMENT-2",
        f"**EXECUTED**: {report['timestamp_utc']}",
        f"**API CONFIGURED**: {report['api_configured']}",
        "",
        "---",
        "",
        "## EXECUTIVE SUMMARY",
        "",
        "| Metric | Before | After | Delta |",
        "|--------|--------|-------|-------|",
        f"| **Websites** | {report['pre_validation']['with_website']} | {report['post_validation']['with_website']} | **+{report['improvement']['website_delta']}** |",
        f"| **Contact Emails** | {report['pre_validation']['with_contact_email']} | {report['post_validation']['with_contact_email']} | **+{report['improvement']['contact_email_delta']}** |",
        f"| **Contact Names** | {report['pre_validation']['with_contact_name']} | {report['post_validation']['with_contact_name']} | **+{report['improvement']['contact_name_delta']}** |",
        f"| **Contactable** | {report['pre_validation']['contactable']} | {report['post_validation']['contactable']} | **+{report['improvement']['contactable_delta']}** |",
        "",
        "---",
        "",
        "## SAM API RESULTS",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Companies queried | {report['sam_results']['queried']} |",
        f"| API success | {report['sam_results']['api_success']} |",
        f"| API failed | {report['sam_results']['api_failed']} |",
        f"| UEI not found | {report['sam_results']['not_found']} |",
        f"| Website found | {report['sam_results']['website_found']} |",
        f"| POC found | {report['sam_results']['poc_found']} |",
        f"| Email found | {report['sam_results']['email_found']} |",
        f"| Phone found | {report['sam_results']['phone_found']} |",
        "",
    ]
    
    if report['sam_results']['api_success'] > 0:
        website_rate = round(100 * report['sam_results']['website_found'] / report['sam_results']['api_success'], 1)
        poc_rate = round(100 * report['sam_results']['poc_found'] / report['sam_results']['api_success'], 1)
        email_rate = round(100 * report['sam_results']['email_found'] / report['sam_results']['api_success'], 1)
        
        lines.extend([
            "### Discovery Rates",
            "",
            f"| Field | Rate |",
            f"|-------|------|",
            f"| Website | {website_rate}% |",
            f"| POC | {poc_rate}% |",
            f"| Email | {email_rate}% |",
            "",
        ])
    
    # Company details
    lines.extend([
        "---",
        "",
        "## COMPANY DETAILS",
        "",
        "| # | UEI | Company | Website | Email | POC |",
        "|---|-----|---------|---------|-------|-----|",
    ])
    
    for i, c in enumerate(report['companies'][:30], 1):
        sam = c.get('sam_result', {}) or {}
        website = "✅" if sam.get('website') else "❌"
        email = "✅" if sam.get('poc_email') else "❌"
        poc = sam.get('poc_full_name', '') or "❌"
        company = (c.get('company_name') or 'Unknown')[:30]
        lines.append(f"| {i} | {c['uei']} | {company} | {website} | {email} | {poc[:20]} |")
    
    lines.extend([
        "",
        "---",
        "",
    ])
    
    if report['errors']:
        lines.extend([
            "## ERRORS",
            "",
        ])
        for e in report['errors']:
            lines.append(f"- {e}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SAM Contactability Validation")
    parser.add_argument("--limit", type=int, default=30, help="Max companies to validate")
    parser.add_argument("--no-update", action="store_true", help="Don't update records")
    parser.add_argument("--output", type=str, default="", help="Output file path")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAM CONTACTABILITY VALIDATION")
    print("=" * 60)
    print()
    
    report = run_sam_validation(limit=args.limit, update_records=not args.no_update)
    
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print()
    print(f"API Configured: {report['api_configured']}")
    print(f"Companies Queried: {report['sam_results']['queried']}")
    print(f"API Success: {report['sam_results']['api_success']}")
    print(f"Websites Found: {report['sam_results']['website_found']}")
    print(f"POCs Found: {report['sam_results']['poc_found']}")
    print(f"Emails Found: {report['sam_results']['email_found']}")
    print()
    print(f"Contactable Before: {report['pre_validation']['contactable']}")
    print(f"Contactable After: {report['post_validation']['contactable']}")
    print(f"Improvement: +{report['improvement']['contactable_delta']}")
    
    # Output markdown report
    md_report = format_report(report)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(md_report, encoding="utf-8")
        print(f"\nReport saved to: {output_path}")
    else:
        print("\n" + md_report)
    
    # Also save JSON
    json_path = Path(__file__).parent.parent / "docs" / "SAM_CONTACTABILITY_ACTIVATION_REPORT.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"JSON saved to: {json_path}")
