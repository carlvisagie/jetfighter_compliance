# UI CONTROL PAGE AUDIT — DISCREPANCY REPORT

**Date**: 2026-06-13  
**Scope**: Control page UI (`/ui/control.html`)  
**Status**: CRITICAL — Test data bleeding into production customer-facing views

---

## PRIMARY ISSUE: PATCH IDENTIFIERS IN CUSTOMER PAPERWORK

### Evidence from Screenshots

**Intake Queue Section** shows multiple paperwork items with PATCH identifiers as customer names:

1. **FB-7c74b5f9233c** — `PATCH` prefix appearing
   - Customer shown as test email: `carlhvisagie@yahoo.com`
   - Types showing: `csv, docx, json, txt`
   - Classified: `Unknown, POAM, SSP, NIST questionnaire, Vendor form, Structured metadata, Test artifact`

2. **FB-2da73c738271** — `PATCH` prefix
   - Customer: `carlhvisagie@yahoo.com`
   - Same pattern

3. **FB-c56ce81b469c** — `Audit Test Company`
   - Email: `audit-13a5@test.keptyourcontracts.com`
   - **Missing: SSP, Vendor form**

4. **FB-f2b751c50ef3** — `Aegis Defense Systems`
   - Email: `aegis-13a4f2-verify@aegisdefense.com`
   - **Missing: Vendor form**

5. **FB-1a5b49f8832a** / **FB-97bbf7703e7d** — **`Aegis Defense Systems`** and **`Aegis Defense Systems LLC`**
   - Emails: `aegis-production-verify@aegisdefense.com`, `aegis-real-verify@aegisdefense.com`
   - **Missing: Vendor form**

6. **FB-8f2e7d8b12eb** / **FB-97c6d0777f87** — **`Aegis 13A4F Verification`**
   - Email: `aegis-13a4f-verify@test.jetfighter.com`
   - **TEST EMAIL DOMAIN IN PRODUCTION**
   - **Missing: SSP, Vendor form**

7. **FB-ef534aac1a91** / **FB-02c78e711107** — **`PATCH13A4C Verify 20260611 102938`** / **`PATCH13A4C Verify 20260611 102820`**
   - Email: `verify13a4c_20260611_102958@test.keptyourcontracts.com`
   - **PATCH IDENTIFIER AS CUSTOMER NAME**
   - **Missing: SSP, Vendor form**

8. **FB-a35b09fcabfc2** / **FB-3bd13bb472ac** — **`PATCH13A4C Verify 20260611 102735`**
   - Email: `verify13a4c_20260611_102735@test.keptyourcontracts.com`
   - **PATCH IDENTIFIER AS CUSTOMER NAME**
   - Types: `csv, docx, json, txt`
   - Classified: `Unknown, POAM, SSP, Vendor form, Structured metadata, test artifact`
   - **Missing: SSP, Vendor form**

9. **FB-15e9e4ea9c73** — **`test@aegis.example`**
   - Email displayed as company name
   - **TEST EMAIL AS COMPANY NAME**
   - Types: `csv, docx, json, txt`
   - Classified: `Unknown, POAM, SSP, Vendor form, Structured metadata, Test artifact`

---

## DISCREPANCIES BY CATEGORY

### 1. TEST DATA IN PRODUCTION VIEWS
- **PATCH13A4C Verify** appearing as customer name (multiple entries)
- **PATCH13A4F** appearing as customer identifier
- **`test@aegis.example`** as company name
- **`@test.keptyourcontracts.com`** email domains
- **`@test.jetfighter.com`** email domains
- **Classified: "Test artifact"** appearing in production paperwork

### 2. ORGANISM VIEW — DEBUG DATA VISIBLE
Screenshot showing "Operational organism" displays:
```
TYPES: csv, docx, json, txt
CLASSES:Lblt:Unknown
RECEIVED:2026-06-
```
This looks like internal/debugging data that should not be visible in operator view.

### 3. INCONSISTENT CUSTOMER IDENTIFICATION
- Some entries show email as company name
- Some show PATCH identifiers
- Some show actual company names (Aegis Defense Systems)
- Mix of test and production data in same queue

### 4. MISSING DOCUMENT PATTERNS
Multiple entries show:
- **Missing: SSP, Vendor form**
- **Missing: Vendor form**
This is expected for pending reviews, but pattern is consistent across test entries.

### 5. DUPLICATE/SIMILAR ENTRIES
- Multiple "Aegis Defense Systems" entries with slightly different names
- Multiple "PATCH13A4C" entries with timestamps
- Suggests test data was created multiple times and not cleaned

### 6. FILE LIFECYCLE SECTION
Screenshot 5-6 show document tables with:
- "Preview not supported for this file type — use Download"
- This is functional but not ideal UX
- `.docx` files should be previewable

### 7. PAPERWORK NOTIFICATION BANNER
Shows: `NEW PAPERWORK RECEIVED` with file ID `FB-7c/4b5f9233c`
- Notification appears persistent across multiple screenshots
- Should auto-dismiss or have close button

---

## ROOT CAUSE ANALYSIS

### Why are PATCH identifiers appearing as customer names?

**Hypothesis 1**: Test data not properly segregated
- Test paperwork submissions used "PATCH13A4C" as customer name
- This data was never archived/cleaned
- Now appearing in production operator queue

**Hypothesis 2**: Data field mapping error
- Customer name field incorrectly mapped to test/patch identifier
- Intake form parsing bug

**Hypothesis 3**: Test data cleanup incomplete
- Previous testing left orphan paperwork in queue
- Archive process didn't catch these entries

### Expected vs Actual

**EXPECTED**: Intake queue shows:
- Real customer company names
- Real customer emails (non-test domains)
- No internal identifiers visible
- Clean separation of test vs production data

**ACTUAL**: Intake queue shows:
- Mix of PATCH identifiers, test emails, and some real companies
- Test artifact classifications visible
- Debug/internal data visible in organism view
- No clear test/production separation

---

## RECOMMENDED FIXES

### PHASE 1: IMMEDIATE DATA CLEANUP
1. **Archive all test paperwork** with:
   - `PATCH` prefix in customer name
   - `@test.*` email domains
   - `test@` email prefixes
   - Classification containing "Test artifact"

2. **Verify remaining entries** are real customer data

### PHASE 2: CODE FIXES
1. **Intake form validation**: Block submissions with `PATCH` or `test@` identifiers in production
2. **Data segregation**: Ensure test data routes to separate queue or database
3. **UI filtering**: Control page should filter out test data by default (with toggle to show if needed)

### PHASE 3: ORGANISM VIEW CLEANUP
1. **Remove debug data** from "Operational organism" motion text
2. **Hide internal classifications** like "TYPES:", "CLASSES:Lblt:Unknown", "RECEIVED:"
3. **Format dates properly** instead of showing partial "2026-06-"

### PHASE 4: UX IMPROVEMENTS
1. **Notification banner**: Add dismiss button or auto-hide after 10 seconds
2. **Document preview**: Enable `.docx` preview or better messaging
3. **Missing document indicators**: Clearer visual for required vs optional documents

---

## NEXT ACTIONS

1. Run data audit to count test vs production paperwork
2. Create archive script for test data
3. Patch intake form to reject test identifiers in production
4. Update organism view to hide internal data
5. Test with clean production-only data

**DELIVERABLE**: `docs/UI_CONTROL_PAGE_FIX_REPORT.md` after fixes complete

**PRODUCTION TRUTH FIRST. NO ASSUMPTIONS.**
