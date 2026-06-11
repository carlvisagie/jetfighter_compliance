# Government Submission Order Research

**PATCH 13A-5D — GOVERNMENT SUBMISSION ORDER RESEARCH**

*Last Updated: June 11, 2026*

---

## Executive Summary

There is **NO universal federal proposal/document order** mandated by FAR or DFARS. Each solicitation's **Section L (Instructions, Conditions, and Notices to Offerors)** defines the exact volume structure, ordering, naming, and formatting requirements for that specific acquisition.

**Key Finding**: The government expects strict compliance with solicitation-specific instructions. Non-compliance with Section L requirements is one of the most common causes of automatic rejection—before technical evaluation even begins.

**Implications for KYC**:
1. KYC must parse and enforce solicitation-specific instructions when provided
2. KYC must provide a sensible default dossier order when no government-specific order exists
3. Final release gates must verify compliance with solicitation requirements before customer delivery

---

## 1. Universal Rules (FAR/DFARS)

### 1.1 FAR 52.215-1 — Instructions to Offerors (Competitive Acquisition)

**Source**: [acquisition.gov/far/52.215-1](https://www.acquisition.gov/far/52.215-1)

The first page of every competitive proposal must include:
1. Solicitation number
2. Offeror name, address, telephone, facsimile, and electronic address
3. Statement of agreement with all solicitation terms and conditions
4. Names/titles of authorized negotiators
5. Name, title, and signature of authorized person

**Submission Requirements**:
- Submit by exact deadline (no late proposals accepted except narrow exceptions)
- Acknowledge all amendments by specified date
- Follow designated submission method (paper/electronic as specified)
- Mark packages with solicitation number, due date/time, and offeror info

### 1.2 FAR 52.212-1 — Instructions for Commercial Products/Services

**Source**: [acquisition.gov/far/52.212-1](https://www.acquisition.gov/far/52.212-1)

Streamlined requirements for commercial acquisitions. Minimum offer contents:
1. Solicitation number
2. Time specified for receipt
3. Offeror name, address, telephone
4. Technical description sufficient to evaluate compliance
5. Express warranty terms
6. Price and discount terms
7. "Remit to" address (if different)
8. Completed FAR 52.212-3 representations and certifications
9. Acknowledgment of solicitation amendments
10. Past performance information (when evaluation factor)
11. Agreement statement (if not using SF 1449)

### 1.3 Section L — The Source of Truth

**Every solicitation's Section L supersedes general guidance.**

Section L specifies:
- Volume structure and order
- Page limits per volume/section
- Font, spacing, margin requirements
- File naming conventions
- Submission method and portal
- Required attachments and forms
- Exclusions from page counts

**If Section L says it, that is the law for that solicitation.**

---

## 2. Common Volume Structure Models

While no universal order exists, the following models appear frequently across federal agencies:

### 2.1 Standard Three-Volume Model (Most Common)

| Volume | Content |
|--------|---------|
| Volume I | Technical/Management Approach |
| Volume II | Past Performance |
| Volume III | Price/Cost |

### 2.2 Four-Volume Model

| Volume | Content |
|--------|---------|
| Volume I | Technical Approach |
| Volume II | Management Approach |
| Volume III | Past Performance |
| Volume IV | Price/Cost |

### 2.3 Five-Volume Model (Large Acquisitions)

| Volume | Content |
|--------|---------|
| Volume I | Offer and Other Documents (SF forms, certs, reps) |
| Volume II | Technical and Management Proposal |
| Volume III | Past Performance |
| Volume IV | Price Proposal |
| Volume V | Small Business Subcontracting Plan |

### 2.4 DoD/DOE Extended Model

| Volume | Content |
|--------|---------|
| Volume I | Offer Documents (SF 33/1449, signed forms, certifications) |
| Volume II | Technical Proposal |
| Volume III | Past Performance |
| Volume IV | Price Proposal |
| Volume V | Representations & Certifications |
| Volume VI | Small Business/Subcontracting |
| Attachments | Supporting Documents, Resumes, Org Charts |

---

## 3. Agency-Specific Rules

### 3.1 Department of Defense (DoD)

**DFARS 252.215-7009 — Proposal Adequacy Checklist**

When certified cost or pricing data required, offerors must complete DFARS 252.215-7009 checklist addressing FAR 15.408 Table 15-2 requirements:
- Cost element breakdown by year
- Indirect rate support and basis
- Subcontractor cost/pricing data
- Forward pricing rate agreements
- Consolidated Bill of Materials (CBOM)

**Common DoD Formatting**:
- 12-point font minimum (10-point for tables/figures)
- 8.5" x 11" paper
- 1-inch margins on all sides
- Sequential page numbering by volume
- Headers with company name, solicitation number, proposal number

### 3.2 Army/Navy/Air Force

Follow DoD baseline with service-specific addenda. Always check:
- Service-specific portal requirements (PIEE, DoD SAFE)
- Classified handling instructions if applicable
- Topic-specific technical volume requirements

### 3.3 GSA (Multiple Award Schedule)

**Unique Approach**: GSA MAS proposals use the eOffer system with character-limited narrative fields.

- Technical factors completed via 10,000-character prompts in eOffer
- Marketing strategy: 2 pages, 1.15 spacing, Times New Roman 10pt, 1" margins
- Catalog upload to GSA Advantage required
- SF 1449 signature required (digital certificate acceptable via eOffer)

**Source**: [SCP-FSS-001 Instructions](https://www.gsa.gov)

### 3.4 NASA

**NFS 1852.215-81 — Proposal Page Limitations**

NASA-specific provision defining:
- Page limits by volume
- Page = one side of 8.5" x 11" with 1" margins, 12pt font minimum
- Foldouts count as equivalent pages
- Cost section typically not page-limited but restricted to cost/price info only

**NSPIRES/Grants.gov Submission**:
- Single-spaced, 12-point font
- 1-inch margins
- No references to external materials for evaluation (reviewers have no obligation to access)
- Proposals may be rejected without review for exceeding page limits

### 3.5 Department of Energy (DOE)

Large M&O contracts typically require:
- Volume I: Offer and Other Documents (no page limit)
- Volume II: Technical and Management (page limits per factor)
- Volume III: Price Proposal (no page limit)

Each volume must contain:
- Table of contents
- Glossary of abbreviations/acronyms
- Sequential page numbering by volume

### 3.6 Department of Veterans Affairs (VA)

VA-ORD follows SF424 R&R format for research:
- Specific Aims: 1 page
- Research Plan: per FOA/RFA
- Bibliography: 4 pages
- Biographical Sketches: 5 pages each
- Check Service-specific FOA for all limits

### 3.7 Department of Health and Human Services (HHS/NIH)

**NIH Application Guide Page Limits**:
- Project Summary/Abstract: 30 lines
- Project Narrative: 3 sentences
- Specific Aims: 1 page
- Research Strategy: 6-12 pages depending on grant type

**Formatting**:
- 11-point font minimum
- Smaller text in figures acceptable if legible at 100%
- Attachments must be searchable PDF

### 3.8 Department of Homeland Security (DHS)

Follows FAR/DFARS baseline. Check solicitation for:
- Volume structure
- Clearance requirements
- Portal-specific instructions

---

## 4. Portal-Specific Rules

### 4.1 SAM.gov

**Entity Registration Required**:
- Active SAM registration at time of offer
- Unique Entity ID on proposal cover page
- Representations and certifications completed annually

**Contract Opportunities**:
- Download solicitation documents
- Check for amendments throughout solicitation period
- No standardized submission format—follow Section L

### 4.2 PIEE (Procurement Integrated Enterprise Environment)

**DoD Primary Electronic System**

Proposal Manager role required to submit offers.

**File Requirements**:
- Maximum 1.9 GB per attachment
- No system limit on number of attachments
- Supported formats: PDF, DOCX, XLSX, PPTX, and others
- Narrative portions typically required as searchable PDF

**Submission Process**:
1. Log in with Proposal Manager credentials
2. Search by solicitation number
3. Select applicable CAGE code
4. Upload attachments
5. Enter digital signature (PIN + OTP)
6. Submit before deadline

### 4.3 GSA eBuy

**For GSA Schedule Contractors Only**

Prerequisites:
- Awarded GSA MAS contract
- Registered with Vendor Support Center
- Catalog uploaded to GSA Advantage

**Submission**:
- Access via ebuy.gsa.gov with FAS ID
- File size limit: 100 MB per attachment
- Quote valid minimum 7 days past close date
- Include price quote, technical response, required documentation

### 4.4 Grants.gov

**For Grants and Cooperative Agreements**

**File Format**:
- All attachments must be PDF unless otherwise specified
- Filenames: 50 characters max, unique within application
- Allowed characters: A-Z, a-z, 0-9, underscore, hyphen, space, period, parentheses, brackets, &, ~, !, ,, ', @, #, $, %, +, =
- No password protection or encryption

**Common Errors**:
- File names with special characters
- Exceeding 50-character filename limit
- Using Adobe paperclip instead of form attachment buttons
- 0-byte files

### 4.5 FedConnect

Federal business opportunities portal used by multiple agencies.
- Follow solicitation-specific instructions
- Test upload functionality before deadline day

### 4.6 DoD SAFE (Secure Access File Exchange)

For large or sensitive file transfers when specified by solicitation.

---

## 5. Rejection-Risk Checklist

### 5.1 Automatic Rejection Causes (Administrative)

| Failure | Citation | Impact |
|---------|----------|--------|
| Late submission | FAR 52.215-1(c)(3) | Automatic rejection—no discretion |
| Missing amendment acknowledgment | FAR 52.215-1(b) | May be excluded from consideration |
| Missing required volume | Section L | Automatic disqualification |
| Page limit exceeded | Section L | Volume or entire proposal rejected |
| Wrong font/margin | Section L | Non-responsive determination |
| Missing certifications | Section L | Binary: present or absent |
| Wrong portal/email | Section L | Not proper submission |
| Missing signature | SF 33/1449 | Not legally binding |
| Expired SAM registration | FAR 52.204-7 | Award ineligible |

### 5.2 Technically Unacceptable Causes

| Issue | Consequence |
|-------|-------------|
| Failure to address evaluation criteria | Deficiency/weakness assigned |
| Missing key personnel information | Cannot evaluate capability |
| No past performance references | Cannot assess performance confidence |
| Price not on required template | Cannot evaluate pricing |
| Incomplete subcontracting plan (large business) | Ineligible for award |
| Cross-referencing between volumes (when prohibited) | Content not considered |
| Missing required analyses or matrices | Incomplete proposal |

### 5.3 Common Oversights

- Not checking for amendments after initial download
- Counting cover pages incorrectly
- Using different fonts in different sections
- Including cost information outside price volume
- Password-protecting PDFs
- File naming with special characters
- Submitting to CO email when portal required
- Time zone miscalculation (deadline often Eastern)

---

## 6. Documents: Merge vs. Separate

### 6.1 Documents That Should NEVER Be Merged

| Document | Reason |
|----------|--------|
| SF 33 / SF 1449 | Government form requiring specific signature block |
| Price/Cost Sheets | Often separate evaluation team |
| Certifications & Representations | Legal documents requiring individual signatures |
| Past Performance Questionnaires | May go directly to references |
| Subcontracting Plan | FAR 52.219-9 compliance document |
| OCI (Organizational Conflict of Interest) Disclosure | Separate evaluation |
| Financial Statements | Confidential/responsibility determination |
| Key Personnel Resumes | Often evaluated separately |

### 6.2 Documents That Should Be Bundled

| Bundle | Contents |
|--------|----------|
| Technical Volume | Technical approach, methodology, staffing plan, org chart |
| Management Volume | Management approach, QC plan, risk mitigation |
| Past Performance Volume | All contract references, PPQs, performance narratives |
| Administrative Volume | Representations, certs, SF forms, acknowledgments |

### 6.3 Attachment vs. Embedded

- **Attachments**: Large documents, forms, supporting materials
- **Embedded**: Small graphics, tables, charts within narrative

---

## 7. Metadata and Preservation

### 7.1 Critical Metadata to Track

| Metadata | Purpose |
|----------|---------|
| Solicitation Number | Primary identifier |
| Amendment Numbers (all) | Compliance verification |
| Response Deadline (date/time/timezone) | Submission gate |
| Set-Aside Status | Eligibility determination |
| NAICS Code | Size standard determination |
| Place of Performance | Geographic requirements |
| Period of Performance | Schedule compliance |
| Contract Type | Pricing approach |
| Evaluation Factors & Weights | Proposal prioritization |
| Page Limits per Volume | Compliance gate |
| Submission Portal | Delivery method |

### 7.2 Preservation Requirements

- Original solicitation document
- All amendments in chronological order
- All Q&A responses
- Compliance matrix mapping requirements to proposal sections
- Submission confirmation/receipt
- Timestamp evidence

---

## 8. Canonical KYC Default Dossier Order

**When no solicitation-specific order exists**, use the following KYC standard order:

### 8.1 Administrative Documents (Volume 0 / Cover)

1. Cover Letter
2. Signed SF 33 or SF 1449 (if applicable)
3. Amendment Acknowledgments (all)
4. Table of Contents
5. Compliance Matrix

### 8.2 Technical/Management Volume

1. Executive Summary
2. Technical Approach
   - Understanding of Requirements
   - Methodology/Solution Design
   - Technical Risk Mitigation
3. Management Approach
   - Program Management
   - Organizational Structure
   - Key Personnel (with resumes)
   - Staffing Plan
   - Quality Control Plan
4. Phase-In/Transition Plan (if applicable)

### 8.3 Past Performance Volume

1. Past Performance Summary
2. Contract References (3-5 relevant contracts)
   - Contract Number
   - Customer/Agency
   - Contract Value
   - Period of Performance
   - Scope Relevance
   - Point of Contact
3. Past Performance Questionnaires (if required)

### 8.4 Price/Cost Volume

1. Price Summary
2. Price Breakdown by CLIN
3. Basis of Estimate (for cost-type)
4. Supporting Schedules
5. Subcontractor Pricing (if applicable)

### 8.5 Representations & Certifications

1. FAR 52.212-3 or FAR 52.204-8 (as applicable)
2. DFARS 252.212-7000 (for DoD)
3. Agency-Specific Certifications
4. SAM.gov Verification

### 8.6 Small Business Subcontracting Plan (if applicable)

1. Goals by Category
2. Methods for Development
3. Program Administrator
4. Flow-Down Provisions

### 8.7 Supporting Attachments

1. Organizational Conflict of Interest Disclosure
2. Financial Statements (if required)
3. Licenses/Certifications (if required)
4. Letters of Commitment (teaming partners)
5. Insurance Certificates (if required)

---

## 9. Solicitation-Specific Override Rules

### 9.1 Detection

KYC must detect and flag:
- Explicit volume ordering in Section L
- Page limits per section
- Font/margin requirements
- File naming conventions
- Submission portal instructions
- Specific forms required
- Evaluation factor structure (from Section M)

### 9.2 Enforcement

When solicitation specifies order:
1. Parse Section L for explicit volume structure
2. Override KYC default order
3. Display solicitation-required order to customer
4. Block release if required volumes missing
5. Warn if page limits approached/exceeded

### 9.3 Compliance Matrix Generation

Automatically generate compliance matrix mapping:
- Section L requirement → Proposal location
- Section M evaluation factor → Evidence location
- Required forms → Completion status
- Amendments → Acknowledgment status

---

## 10. Recommended Product Behavior

### 10.1 Solicitation-Specific Order (A)

If uploaded solicitation specifies volume order:
```
Volume I: Technical
Volume II: Price
Volume III: Past Performance
```

KYC must:
- Parse and detect the specified order
- Display the required order to customer
- Enforce that order in final package assembly
- Block release if order not followed

### 10.2 Default KYC Dossier Order (B)

If no government-specific order exists:
- Use KYC canonical order (Section 8 above)
- Clearly label as "KYC Recommended Order"
- Allow customer override with justification

### 10.3 Submission Package Facsimile (C)

Create customer-visible package preview showing:
- Exact volume order
- Exact file names (per naming convention)
- All documents included with status
- Missing documents flagged
- Rejection risks highlighted
- Page counts vs. limits
- Compliance matrix view

### 10.4 Final Release Gates (D)

Block release if:
- Required solicitation instruction not satisfied
- Required volume missing
- File naming invalid per Section L
- Required signature missing from SF forms
- Required representation not completed
- Amendment acknowledgment missing
- Page/format requirements violated
- SAM registration expired
- Submission deadline passed

---

## 11. Recommended Future Patches

### PATCH 13A-5E: Solicitation Parser

Implement automated parsing of Section L to detect:
- Volume structure
- Page limits
- Formatting requirements
- Required forms
- Submission portal
- Deadline extraction

### PATCH 13A-5F: Compliance Matrix Generator

Auto-generate compliance matrix from:
- Section L requirements
- Section M evaluation factors
- Solicitation attachments

### PATCH 13A-5G: Package Facsimile Builder

Create preview capability showing:
- Final assembled package
- Volume order
- Document inventory
- Page counts
- Compliance status

### PATCH 13A-5H: Release Gate Enforcement

Implement blocking gates for:
- Missing volumes
- Unsigned forms
- Missing certifications
- Page limit violations
- Amendment acknowledgments

---

## 12. Evidence Citations

### Primary Sources (Official)

| Source | URL |
|--------|-----|
| FAR 52.215-1 | https://www.acquisition.gov/far/52.215-1 |
| FAR 52.212-1 | https://www.acquisition.gov/far/52.212-1 |
| FAR 52.212-3 | https://www.acquisition.gov/far/52.212-3 |
| FAR 15.208 | https://www.acquisition.gov/far/15.208 |
| FAR 19.704 | https://www.acquisition.gov/far/19.704 |
| DFARS 252.215-7009 | https://www.acquisition.gov/dfars/252.215-7009 |
| NFS 1852.215-81 | https://www.acquisition.gov/nfs/part-1852 |
| NASA Proposer's Guide | https://www.nasa.gov/wp-content/uploads/2023/09/2023-nasa-proposers-guide-final.pdf |
| NIH Page Limits | https://grants.nih.gov/grants-process/write-application/how-to-apply-application-guide/page-limits |
| Grants.gov Applicant FAQs | https://www.grants.gov/applicants/applicant-faqs |
| PIEE FAQs | https://dodprocurementtoolbox.com |
| GSA SCP-FSS-001 | https://www.gsa.gov |
| SAM.gov Entity Checklist | https://sam.gov |

### GAO Protest Decisions (Precedent)

| Decision | Finding |
|----------|---------|
| B-255815 | Missing resume/financial statements = non-responsive |
| B-413155.4 | Failure to use required attachment version = rejection |
| B-298436.2 | Missing teaming partner info = technically unacceptable |
| B-424285.2 | Significant weaknesses/deficiencies = exclusion from competitive range |
| B-419646 | Not susceptible to remediation = proper exclusion |

---

## 13. Remaining Unknowns

### 13.1 Areas Requiring Further Research

1. **Court of Federal Claims decisions** on document ordering
2. **Agency-specific portal limitations** (file size, character limits)
3. **Classified submission procedures** (varies by agency/program)
4. **International procurement** (NATO, FMS)
5. **Task order proposals** under IDIQs (may have simplified procedures)

### 13.2 Customer-Specific Considerations

- Customer's typical agency targets
- Customer's contract type history
- Customer's teaming arrangements
- Customer's small business status

### 13.3 Edge Cases

- Late proposal exceptions (government mishandling)
- Amendment issued after submission
- Portal failures at deadline
- Multi-award IDIQ ordering complexity

---

## Conclusion

**There is no universal federal document order.** Section L of each solicitation is the governing authority for that acquisition.

KYC must:
1. Parse solicitation instructions when available
2. Provide sensible defaults when not available
3. Enforce compliance at final release
4. Block delivery of non-compliant packages

The goal is to prevent customer rejection before technical evaluation even begins—which remains the #1 cause of lost opportunities in federal contracting.

---

*Document prepared for KeepYourContracts platform compliance intelligence engine.*
