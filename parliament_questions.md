# Questions for Parliament

Open questions requiring confirmation from Parliament before proceeding with development.
Contact: Rod / Dan (finance systems team).

---

## GL Journals — Voucher Type Classification (BLOCKING)

**Context:** Running the GL journals extract against `Agresso_HoC` with `fiscal_year = 2025`
and `status IS NULL OR status = ''` (normal posted transactions, BU/BV excluded) produced
~650,000 rows. The breakdown by voucher type is below. Almost none of the codes match the
standard Agresso reference list — Parliament appears to use a heavily customised set.

**Questions:**
1. What does each of the following voucher types mean? (description and originating module)
2. Which of these are **manually-entered GL journals** that need to migrate under Seq 21
   (Current Year Journals)?
3. Which are **system-generated entries** originating from sub-ledger modules (AP, AR,
   payroll, assets) that will be migrated via their own domain and should be excluded here?

| voucher_type | line_count | voucher_count | lines/voucher | Known? | Notes |
|---|---|---|---|---|---|
| FA | 196,355 | 186 | ~1,055 | No | Very large batch — fixed assets? |
| GI | 84,197 | 1,922 | ~44 | No | |
| IB | 59,691 | 27,065 | ~2.2 | No | ~2 lines/voucher — simple postings |
| BC | 59,340 | 362 | ~164 | No | Large batch |
| UB | 52,435 | 109 | ~481 | No | Very large batch |
| BH | 48,216 | 24,108 | 2.0 | No | Exactly 2 lines — standard double-entry |
| ZR | 35,006 | 9,138 | ~3.8 | No | Z-prefix — Parliament custom? |
| BA | 27,659 | 5,988 | ~4.6 | Yes | Batch Input adj for CRS BQT debts |
| PC | 25,243 | 12,615 | 2.0 | Yes | Payroll Manual Cheque |
| PP | 18,115 | 84 | ~216 | Yes | Posting payroll transactions |
| FD | 15,023 | 46 | ~327 | No | Large batch |
| BR | 13,499 | 668 | ~20 | No | |
| BS | 6,026 | 998 | ~6 | No | |
| BD | 4,344 | 259 | ~17 | No | |
| BQ | 4,060 | 225 | ~18 | No | |
| RV | 3,038 | 201 | ~15 | Yes | Reversals |
| SI | 2,422 | 1,121 | ~2.2 | Yes | Stock Purchasing CRS (Invoice) |
| ZC | 684 | 176 | ~3.9 | No | Z-prefix — Parliament custom? |
| ST | 527 | 139 | ~3.8 | No | |
| GB | 471 | 228 | ~2.1 | No | |
| BP | 424 | 46 | ~9.2 | No | |
| PI | 415 | 415 | 1.0 | Yes | Purchase Invoices |
| BG | 210 | 79 | ~2.7 | No | |
| PS | 123 | 27 | ~4.6 | No | |
| ZX | 91 | 26 | ~3.5 | No | Z-prefix |
| UC | 75 | 73 | ~1.0 | No | |
| ZD | 50 | 25 | 2.0 | No | Z-prefix |
| ZP | 22 | 5 | ~4.4 | No | Z-prefix |
| ZZ | 6 | 1 | 6.0 | No | Z-prefix |

**Note:** Standard Agresso manual journal types (JL, AC, RJ, PJ) produced **zero rows**
for HOC — Parliament does not appear to use these standard codes. The scope of Seq 21
cannot be determined without Parliament input on which codes above represent manually-entered
journals.

**Impact if not resolved:** Cannot load or DQ-check GL journals in the dashboard. The
journals dataset is deferred until this is confirmed.

---

## GL Journals — Debit/Credit Convention (BLOCKING for balance checks)

**Context:** `agltransact` has two debit/credit fields:
- `dc_flag` — described as "Debet/Credit flag", no documented valuelist
- `update_flag` — described as "Debit/Credit indicator", documented as 1=Debit, 2=Credit

**Questions:**
1. Which field does Unit4 actually use to drive the posting sign for GL balances?
2. What are the actual values of `dc_flag` in Parliament's data (run:
   `SELECT DISTINCT dc_flag, COUNT(*) FROM agltransact WHERE client IN ('CA','CM') AND fiscal_year = 2025 GROUP BY dc_flag`)?
3. Is `amount` always signed (positive=debit, negative=credit) independently of these flags,
   or is it always positive with the flag determining direction?

**Impact if not resolved:** Cannot write the unbalanced-voucher check (GL_JNL_UNBALANCED),
which is the most critical journal DQ check.

---

## GL Opening Balances — P&L Non-Zero (context question)

**Context:** `GL_BAL_PL_NONZERO` checks for P&L accounts (res_bal = R) with a non-zero net
balance across all periods in the opening balances extract. This check may fire legitimately
if year-end close journals (periods 13–15) are still pending at the time of extraction.

**Questions:**
1. Has the FY2025/26 year-end close been completed (i.e. have periods 13–15 been posted)?
2. If not, which accounts are expected to carry a non-zero P&L balance, and when will the
   close be complete?

**Impact:** Helps interpret GL_BAL_PL_NONZERO results — expected failures vs genuine issues.

---
