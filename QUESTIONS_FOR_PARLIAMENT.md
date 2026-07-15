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

## 4. Fixed Asset Depreciation Methods — `aatassetbook` method codes

**Context:** The data dictionary and Unit4 specification we have been working from documents four depreciation methods: `LIN` (Straight Line), `BAL` (Reducing Balance), `EXP` (Expense), `SYD` (Sum of Years Digits). The real Parliament data in `aatassetbook` uses entirely different codes: **LNA, LNB, MAN, NOD**. None of these appear in the data dictionary.

Until we understand what each code means, several data quality checks cannot be written or validated — including the check for invalid method codes (which would currently flag every single record as invalid), and any check that tests whether the correct supporting fields are present for a given method.

**Questions:**

- What do each of the following depreciation method codes mean in your Agresso installation?

  | Code | Your description |
  |------|-----------------|
  | LNA | |
  | LNB | |
  | MAN | |
  | NOD | |

- For each method: does it require a **useful life** (`lifetime` field) to calculate the depreciation charge?
- For each method: does it require a **depreciation rate** (`depr_percent` field)?
- Is any of these the equivalent of an "expense" method — where the full cost is written off immediately in one go rather than spread over time?

**Checks affected:** `DQ-AD-V01`, `DQ-AG-V01`, `DQ-AD-V04`, `DQ-AD-C04`, `DQ-AD-C05`, `DQ-AG-C05`, `DQ-AG-C06`

---

## 5. PO Line Invoicing Fields — `arr_amount`/`arr_val` vs `invoiced` disagree

**Context:** `apodetail` carries three fields that all appear, per the extract's own documentation, to represent "how much has been invoiced" on a PO line: `arr_amount` (invoice received, local currency), `arr_val` (invoice received, order currency), and `invoiced` (invoiced at the order's exchange rate). Inspecting real HoC PO line records shows these disagreeing in opposite directions on different lines, not just failing to match numerically:

| Example | amount | com_amount | vow_amount | vow_val | arr_amount | arr_val | invoiced |
|---|---|---|---|---|---|---|---|
| Line 1 (O status) | 1740 | 1740 | 1740 | 200 | 1740 | 200 | **0** |
| Line 2 | 90.63 | 90.63 | 90.63 | 12 | — | **0** | **75.3** |

- Line 1: `arr_amount`/`arr_val` say the line is fully invoiced; `invoiced` says nothing has been invoiced.
- Line 2: `arr_val` says nothing has been invoiced; `invoiced` shows a real, partial, non-zero figure.

If these were simple currency-conversion duplicates of the same underlying fact, they couldn't disagree in opposite directions like this. Working hypothesis (unconfirmed): `invoiced` may be period-specific ("invoiced this period") rather than a cumulative running total the way `arr_amount`/`arr_val` appear to be — which would explain a historically-fully-invoiced line reading `0` if all its invoicing happened in an earlier period.

This has a direct, practical impact: the PO tab's "Fulfilment of the Live Book" breakdown uses `arr_amount` as the definitive invoiced figure. If `invoiced` sometimes reflects real invoicing progress that `arr_amount` misses (as in Line 2), that breakdown could understate invoicing progress on some POs.

**Questions:**
- What does the `invoiced` field represent, and how does it differ from `arr_amount`/`arr_val`? Is it a period figure rather than a cumulative one?
- Which field should be treated as authoritative for "how much of this PO line has been invoiced"?
- Separately: `vow_val`/`arr_val` (order currency) are consistently ~8–9x smaller than `vow_amount`/`arr_amount` (local currency) on both example lines — is that a real FX rate, and if so, what currency/rate produces that ratio?

**Affects:** PO tab "Fulfilment of the Live Book" breakdown (`dashboard/tabs/po.py`, `_render_active_fulfilment`), any future PO invoicing-progress DQ checks.

**Update (July 2026) — `vow_val`/`arr_val` may be quantities, not order-currency values.** A further real line found during manual Excel review directly contradicts the FX-ratio hypothesis above: `amount = 37.5`, `unit_price = 7.5`, `vow_val = 5` — and `37.5 / 7.5 = 5` exactly, implying `vow_val` here is a received **quantity**, not a value in order currency as the SQL extract's own column comment states (`d.vow_val, -- goods receipted value (order currency)`). This may mean the "8–9x smaller" ratio observed on the two lines above was coincidental rather than a real FX rate. The new DQ check `PO_LINE_MATCH_EXCEEDS_RECEIPT` (`arr_val > vow_val`) was built without resolving this ambiguity — the sequencing logic holds whether the fields are quantities or values, since matched should never exceed received in either unit — but the *label* on the column is now in question.

**Questions (addendum):**
- Are `vow_val` and `arr_val` quantities (units received/matched) or values in order currency? The two pieces of evidence above point in different directions.
- If they are quantities, is there a separate field carrying the received/matched value in order currency, and is it currently extracted?

---
