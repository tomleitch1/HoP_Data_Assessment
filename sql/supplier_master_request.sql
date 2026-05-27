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

    -- === STATUS & DATES ===
    h.expired_date,
    h.last_update,
    h.wf_state

FROM asuheader h
ORDER BY h.client, h.apar_id;