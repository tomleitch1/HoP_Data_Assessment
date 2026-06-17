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

**Assumed so far (rules updated on this basis — confirm and adjust if incorrect):**

| Code | Assumed meaning | Requires |
|------|----------------|---------|
| DD | Direct Debit | Sort code + bank account |
| CH | CHAPS | Sort code + bank account |
| FP | Faster Payments | Sort code + bank account |
| BB | BACS credit | Sort code + bank account |
| IN | International | IBAN |
| EU | SEPA / Euro payment | IBAN |
| TF | Telegraphic Transfer | IBAN |

**Still unknown — please confirm:** AS, AU, BO, CA, EF, FC, IB, II, IP, LE, RF, UE, VD, VI

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

## 3. Fixed Asset Transaction Types — `aattrans` unknown codes

**Context:** When profiling the fixed asset transaction ledger (`aattrans`) on the real Parliament databases, the following transaction type codes were found that are not in the Unit4 standard specification we have been working from. Until these are understood, the net book value calculations and several DQ checks cannot be finalised.

**The current NBV formula excludes all of these.** For HOL, TF/TT alone represent approximately £178m — a material omission if these codes belong in the balance calculation.

### Transfer-type pairs (identical row counts and total amounts — likely internal asset transfers)

| Codes | HOC rows | HOC value | HOL rows | HOL value |
|-------|----------|-----------|----------|-----------|
| TF / TT | 51 each | ~£15m each | 50 each | ~£179m / £45m |
| NF / NT | 3,874 each | ~£13m each | 9,857 each | ~£2m each |
| RF / RT | 68 each | £0 (HOC) | 31 each | ~£15m each |

**Questions:**
- What do TF, TT, NF, NT, RF, RT represent?
- When an asset is transferred between cost centres or entities, which codes are used and what is the debit/credit convention?
- Should these be included when calculating an asset's net book value? If so, which side adds to cost and which subtracts?

### WU (HOL only)

| Code | HOL rows | HOL value |
|------|----------|-----------|
| WU | 179 | ~£12.7m |

**Questions:**
- What does WU represent? Is this a write-up (upward revaluation), distinct from VN?
- Should it be included in the NBV calculation?

### OS (both houses, zero amounts, no year-end reversal)

| Code | HOC rows | HOL rows | Amount |
|------|----------|----------|--------|
| OS | 51,297 | 21,799 | Always £0 |

OS is the most unusual code found: very high volume, always zero amount, and uniquely has **no corresponding dc_flag = -1 year-end reset entries** — unlike every other trans_type. This suggests it is a marker or flag transaction rather than a financial posting.

**Questions:**
- What does OS represent?
- Is it expected to always be zero?
- Does it have any significance for migration or asset status?

### TC (small volumes, zero or near-zero amounts)

| Code | HOC rows | HOL rows |
|------|----------|----------|
| TC | 8 | 10 |

**Questions:**
- What does TC represent? Is it a technical correction?
- Are these records expected to persist or should they have been cleared?

### Amount sign convention

The standard trans_type codes (CA, ND, ED, FD, SA) have been confirmed to exist in the data, but we have not yet confirmed whether the `amount` field in `aattrans` is stored as a **signed value** (ND already negative) or as an **absolute positive** (sign determined by trans_type in the formula). This affects whether the NBV calculation is correct.

**Questions:**
- For Normal Depreciation (ND) rows with dc_flag = 1, is `amount` stored as a negative number (e.g. -£240) or a positive number (e.g. +£240)?
- Same question for SA (disposal) rows.

---
