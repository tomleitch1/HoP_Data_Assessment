SELECT 
    h.status,
    h.wf_state,
    COUNT(*) AS po_count
FROM apoheader h
WHERE h.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
GROUP BY h.status, h.wf_state
ORDER BY h.status, h.wf_state;


Run that first and it will show you all the combinations that actually exist in Parliament's data. For example you might see:

status = 'O', wf_state = 'T' — 450 POs
status = 'O', wf_state = 'W' — 12 POs (ordered but still in workflow)
status = 'O', wf_state = blank — 200 POs (no workflow used)

That tells you immediately whether workflow is being used on POs at all, and whether there are ordered POs sitting unapproved in workflow.
What only the business can tell you:
Once you see those combinations, Parliament's finance team need to confirm which combinations represent a genuinely approved PO that should be migrated. The data shows you what exists — the business tells you what it means.