-- kind: check
-- severity: error
-- Structural check, not a methodology rule.
-- Rows returned are RPT rows where the fiscal year end date is not after the begin date.
-- Dates are stored as YYYY-MM-DD text, so comparing them as text compares them as dates.
-- A row with either date empty is not returned (an empty date is a null, not a wrong order).
select _file, _row, RPT_REC_NUM, FY_BGN_DT, FY_END_DT
from rpt
where FY_END_DT <= FY_BGN_DT;
