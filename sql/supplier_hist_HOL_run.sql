USE agresso_HoL;

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
WHERE h.client = 'LA'
  AND h.trans_date >= DATEADD(MONTH, -18, GETDATE())
ORDER BY h.apar_id, h.trans_date;
