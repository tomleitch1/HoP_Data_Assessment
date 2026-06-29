-- =============================================================================
-- po_detail_HOC_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Purchase Order Detail (Lines) Extract — HoC Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : Agresso_HoC
-- Output    : po_detail_HOC.csv
-- Place in  : data/po/
--
-- Extracts all lines belonging to non-terminated PO headers.
-- Joins to apoheader to apply the status != 'T' filter so terminated PO
-- lines are excluded even if they carry their own status.
-- Open commitment is derived in Python as: amount - arr_amount.
-- vow_amount (receipted) and com_amount (pre-amendment committed) are
-- included for audit trail and alternative commitment calculations.
-- Line-level status may differ from header status — both are extracted.
-- =============================================================================

USE Agresso_HoC;

SELECT
    -- === IDENTITY ===
    d.client,
    d.order_id,
    d.line_no,
    d.sequence_no,
    d.apar_id,
    d.voucher_no,
    d.voucher_type,

    -- === STATUS & AMENDMENT ===
    d.status,
    d.amend_no,
    d.rev_status,

    -- === AMOUNTS ===
    d.amount,               -- net ordered, local currency
    d.cur_amount,           -- net ordered, order currency
    d.com_amount,           -- original committed amount pre-amendment
    d.vow_amount,           -- goods receipted value (local currency)
    d.vow_val,              -- goods receipted value (order currency)
    d.arr_amount,           -- invoice received (local currency)
    d.arr_val,              -- invoice received (order currency)
    d.invoiced,             -- invoiced at order exchange rate
    d.cost_amount,          -- cost value
    d.real_amount,          -- real/actual amount
    d.forecast,             -- forecast amount
    d.open_flag,            -- open commitment indicator

    -- === PRICING ===
    d.unit_price,
    d.unit_code,
    d.disc_percent,
    d.discount,
    d.tax_amount,
    d.tax_percent,
    d.tax_code,
    d.tax_system,

    -- === GL CODING ===
    d.account,
    d.att_1_id,             -- dimension attribute type for slot 1
    d.att_2_id,
    d.att_3_id,
    d.att_4_id,
    d.att_5_id,
    d.att_6_id,
    d.att_7_id,
    d.dim_1,                -- line-level dimension value for slot 1
    d.dim_2,
    d.dim_3,
    d.dim_4,
    d.dim_5,
    d.dim_6,
    d.dim_7,

    -- === ARTICLE / DESCRIPTION ===
    d.article,
    d.art_descr,
    d.sup_article,

    -- === DATES & FX ===
    d.deliv_date,
    d.rev_del_date,
    d.order_date,
    d.period,
    d.currency,
    d.exch_rate,

    -- === REFERENCES ===
    d.contract_id,
    d.user_id,

    -- === AUDIT ===
    d.last_update

FROM apodetail d
INNER JOIN apoheader h
    ON  h.client   = d.client
    AND h.order_id = d.order_id
WHERE d.client IN ('CA', 'CM')
  AND h.status != 'T'
ORDER BY d.client, d.order_id, d.line_no, d.sequence_no;
