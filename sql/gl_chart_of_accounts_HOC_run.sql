USE Agresso_HoC;

-- HOW TO RUN
-- Run against Agresso_HoC (server mdata837)  → save as gl_chart_of_accounts_HOC.csv

SELECT
    a.client,
    a.account,
    a.description,
    a.account_grp,
    a.account_type,
    a.status,
    a.res_bal,
    a.bflag,
    a.account_rule,
    a.period_from,
    a.period_to,
    a.last_update,
    a.head_account
FROM aglaccounts a
WHERE a.client IN ('CA', 'CM')
ORDER BY a.account;
