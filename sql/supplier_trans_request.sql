SELECT
    -- === IDENTITY ===
    t.client,
    t.apar_id,
    t.voucher_no,
    t.sequence_no,

    -- === INVOICE DETAIL ===
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
    t.pay_method,
    t.payment_date,
    t.pay_flag,
    t.period,
    t.payperiod,

    -- === REFERENCES ===
    t.ext_inv_ref,
    t.orig_reference,
    t.order_id,
    t.contract_id,
    t.tax_code,
    t.exch_rate,

    -- === AUDIT ===
    t.last_update,
    t.wf_state

FROM asutrans t
WHERE t.status != 'C'
ORDER BY t.client, t.apar_id, t.voucher_no;