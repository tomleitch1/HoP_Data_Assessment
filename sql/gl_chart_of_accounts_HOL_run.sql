USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_chart_of_accounts_HOL.csv

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
WHERE a.client = 'LA'
ORDER BY a.account;
