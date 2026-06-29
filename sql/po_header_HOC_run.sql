-- =============================================================================
-- po_header_HOC_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Purchase Order Header Extract — HoC Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : Agresso_HoC
-- Output    : po_header_HOC.csv
-- Place in  : data/po/
--
-- Extracts all PO headers from apoheader — all statuses included.
-- Status meaning not yet confirmed by Parliament (O, N, F, C, A, P, T).
-- Python filters to the relevant population for each analysis.
-- HoC only — no HOL equivalent (apoheadhistr confirmed empty at Parliament).
-- wf_state is not used at Parliament so is excluded from this extract.
-- =============================================================================

USE Agresso_HoC;

SELECT
    -- === IDENTITY ===
    h.client,
    h.order_id,
    h.apar_id,
    h.order_type,
    h.voucher_no,
    h.voucher_type,

    -- === STATUS & AMENDMENT ===
    h.status,
    h.amend_no,             -- >0 indicates this PO has been amended; higher migration risk

    -- === DATES ===
    h.order_date,
    h.voucher_date,
    h.deliv_date,
    h.confirm_date,
    h.obs_date,
    h.period,

    -- === PAYMENT CONTEXT ===
    h.currency,
    h.exch_rate,
    h.pay_method,
    h.terms_id,

    -- === GL CODING DEFAULTS ===
    h.att_id_1,             -- dimension attribute type for slot 1
    h.att_id_2,
    h.att_id_3,
    h.att_id_4,
    h.att_id_5,
    h.att_id_6,
    h.att_id_7,
    h.dim_value_1,          -- default dimension value for slot 1
    h.dim_value_2,
    h.dim_value_3,
    h.dim_value_4,
    h.dim_value_5,
    h.dim_value_6,
    h.dim_value_7,

    -- === REFERENCES ===
    h.contract_id,
    h.responsible,
    h.responsible2,
    h.user_id,
    h.ext_ord_ref,
    h.ext_inv_ref,
    h.client_ref,

    -- === DESCRIPTION ===
    h.text1,
    h.text2,
    h.header_note,

    -- === OVERRUN TOLERANCES ===
    h.overrun_pct,
    h.overrun_pct_a,
    h.overrun_pct_o,

    -- === AUDIT ===
    h.last_update

FROM apoheader h
WHERE h.client IN ('CA', 'CM')
ORDER BY h.client, h.order_id;
