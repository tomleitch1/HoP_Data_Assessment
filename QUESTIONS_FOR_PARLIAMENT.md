# Questions for Parliament — Agresso Data Clarifications

This file tracks questions that need to be answered by the Parliament finance / data team before certain DQ checks can be fully validated or activated.

---

## 1. Payment Method Codes — International vs Domestic

**Context:** The DQ checks `SUP_INT_NO_IBAN` (payment method set to international but IBAN missing) and `SUP_BACS_NO_BANK` (payment method set to BACS/domestic but bank account or sort code missing) currently return 0 results because they check for codes `'INT'` and `'BACS'` respectively, which do not exist in the real data.

The actual payment method codes in the system are:

> AS, AU, BB, BO, CA, CH, DD, EF, EU, FC, FP, IB, II, IN, IP, LE, RF, TF, UE, VD, VI

**Questions:**
- Which of these codes represent **international payments** that require an IBAN?
- Which represent **domestic electronic payments** that require a sort code and bank account number?
- Even partial mappings are helpful — e.g. "IN = International, DD = Direct Debit"

**Assumed for now:** `IN` = International (requires IBAN), `DD` = Direct Debit/domestic (requires sort code + bank account). Rules updated on this basis — confirm and adjust if incorrect.

**Checks affected:** `SUP_INT_NO_IBAN`, `SUP_BACS_NO_BANK` in `dashboard/core/rules/ap_rules.py`

---

## 2. Credit Note Original Reference — `orig_reference` field

**Context:** The check `AP_CN_NO_REF` looks for credit notes (voucher_type = CN) where `orig_reference` is null. However, in the real data `orig_reference` is always `0` rather than null — this appears to be how Agresso stores "no reference" in this instance.

As a result:
- `AP_CN_NO_REF` returns 0 results (because `0` is not null)
- `AP_ORPHANED_CREDITS` flags all credit notes (because `0` never matches any `voucher_no`)

**Questions:**
- Is `orig_reference = 0` intentional — i.e. is this field not used in your Agresso instance?
- Is there another field (e.g. `ext_inv_ref`) that links a credit note back to its original invoice?
- Should credit notes with `orig_reference = 0` be treated as missing their reference link?

**Checks affected:** `AP_CN_NO_REF`, `AP_ORPHANED_CREDITS`, `HIS_CN_NO_REF` in `dashboard/core/rules/ap_rules.py`

---
