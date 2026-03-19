SELECT DISTINCT client, dim_1, dim_2, dim_3, dim_4, dim_5, dim_6, dim_7
FROM agltransact
WHERE client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')