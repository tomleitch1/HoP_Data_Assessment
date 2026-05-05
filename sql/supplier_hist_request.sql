SELECT
    -- === IDENTITY ===
    h.client,
    h.apar_id,
    h.voucher_no,
    h.sequence_no,

    -- === TRANSACTION DETAIL ===
    h.voucher_type,
    h.voucher_date,
    h.trans_date,
    h.status,

    -- === AMOUNTS ===
    h.amount,
    h.rest_amount,
    h.currency,

    -- === REFERENCES ===
    h.orig_reference

FROM asuhistr h
WHERE h.trans_date >= DATE_SUB(NOW(), INTERVAL 18 MONTH)
ORDER BY h.client, h.apar_id, h.trans_date;