-- ============================================================
-- HOW TO RUN
-- Database:  agresso_HoL
-- Output:    customer_open_trans_HOL.csv
-- Server:    mdata837
-- ============================================================

USE agresso_HoL;

SELECT
    -- === IDENTITY ===
    t.client,
    t.apar_id,
    t.voucher_no,
    t.sequence_no,
    t.account,

    -- === TRANSACTION DETAIL ===
    t.voucher_type,
    t.voucher_date,
    t.trans_date,
    t.due_date,
    t.description,

    -- === AMOUNTS ===
    t.amount,
    t.cur_amount,
    t.currency,
    t.rest_amount,
    t.rest_curr,
    t.discount,
    t.dc_flag,

    -- === STATUS & PAYMENT ===
    t.status,
    t.pay_flag,
    t.pay_method,
    t.payment_date,
    t.period,
    t.payperiod,

    -- === REFERENCES ===
    t.ext_inv_ref,
    t.orig_reference,
    t.order_id,
    t.contract_id,
    t.tax_code,
    t.exch_rate,

    -- === AR SPECIFIC ===
    t.rem_level,
    t.remind_date,
    t.collect_status,
    t.collect_agency,
    t.intrule_id,
    t.int_status,

    -- === AUDIT ===
    t.last_update,
    t.wf_state

FROM acutrans t
WHERE t.client = 'LA'
  AND t.status != 'C'
ORDER BY t.client, t.apar_id, t.voucher_no;
