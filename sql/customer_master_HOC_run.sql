-- ============================================================
-- HOW TO RUN
-- Database:  Agresso_HoC
-- Output:    customer_master_HOC.csv
-- Server:    mdata837
-- NOTE: attribute_id for customer records in agladdress is NOT yet confirmed.
--       Before running, verify with:
--       SELECT DISTINCT attribute_id FROM agladdress WHERE client = 'CA' AND address_type = '1'
--       Compare against the supplier attribute_id (A5) to identify the customer equivalent.
--       Replace 'A6' in the join below with the confirmed value.
-- ============================================================

USE Agresso_HoC;

SELECT
    -- === IDENTITY ===
    h.client,
    h.apar_id,
    h.apar_name,
    h.short_name,
    h.apar_gr_id,
    h.status,
    h.apar_once,
    h.main_apar_id,

    -- === REGISTRATION & TAX ===
    h.vat_reg_no,
    h.comp_reg_no,
    h.country_code,
    h.tax_code,
    h.tax_system,

    -- === PAYMENT & CREDIT ===
    h.terms_id,
    h.pay_method,
    h.currency,
    h.pay_delay,
    h.credit_limit,
    h.credit_age,
    h.intrule_id,

    -- === BANK DETAILS ===
    h.clearing_code,
    h.bank_account,
    h.iban,
    h.swift,

    -- === COLLECTION & LEGAL ===
    h.collect_flag,
    h.invoice_code,

    -- === ADDRESS ===
    a.address,
    a.place,
    a.zip_code,
    a.province,

    -- === STATUS & DATES ===
    h.expired_date,
    h.last_update,
    h.wf_state

FROM acuheader h
LEFT JOIN (
    SELECT client, dim_value, address, place, zip_code, province,
           ROW_NUMBER() OVER (PARTITION BY client, dim_value ORDER BY sequence_no) AS rn
    FROM agladdress
    WHERE attribute_id = 'A6'    -- TODO: verify this is the correct attribute_id for customer records
      AND address_type = '1'
) a ON  a.client    = h.client
    AND a.dim_value = h.apar_id
    AND a.rn        = 1
WHERE h.client IN ('CA', 'CM')
ORDER BY h.client, h.apar_id;
