USE agresso_HoL;

-- NOTE: attribute_id = 'A5' was confirmed for HoC. Verify this is correct for HoL
-- by running: SELECT DISTINCT attribute_id FROM agladdress WHERE client = 'LA' AND address_type = '1'

SELECT
    -- === IDENTITY ===
    h.client,
    h.apar_id,
    h.apar_name,
    h.short_name,
    h.apar_gr_id,
    h.status,
    h.apar_once,

    -- === REGISTRATION & TAX ===
    h.vat_reg_no,
    h.comp_reg_no,
    h.country_code,
    h.tax_code,
    h.tax_system,

    -- === PAYMENT CONFIGURATION ===
    h.terms_id,
    h.pay_method,
    h.currency,
    h.pay_delay,

    -- === BANK DETAILS ===
    h.clearing_code,
    h.bank_account,
    h.iban,
    h.swift,

    -- === ADDRESS ===
    a.address,
    a.place,
    a.zip_code,
    a.province,

    -- === STATUS & DATES ===
    h.expired_date,
    h.last_update,
    h.wf_state,

    -- === ACTIVITY ===
    lt.last_trans_date

FROM asuheader h
LEFT JOIN (
    SELECT client, dim_value, address, place, zip_code, province,
           ROW_NUMBER() OVER (PARTITION BY client, dim_value ORDER BY sequence_no) AS rn
    FROM agladdress
    WHERE attribute_id = 'A5'
      AND address_type = '1'
) a ON  a.client    = h.client
    AND a.dim_value = h.apar_id
    AND a.rn        = 1
LEFT JOIN (
    SELECT client, apar_id, MAX(trans_date) AS last_trans_date
    FROM (
        SELECT client, apar_id, trans_date FROM asutrans  WHERE client = 'LA'
        UNION ALL
        SELECT client, apar_id, trans_date FROM asuhistr  WHERE client = 'LA'
    ) t
    GROUP BY client, apar_id
) lt ON lt.client  = h.client
    AND lt.apar_id = h.apar_id
WHERE h.client = 'LA'
ORDER BY h.client, h.apar_id;
