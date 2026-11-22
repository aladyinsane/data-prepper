-- kind: check
-- severity: error
-- Structural check, not a methodology rule.
-- Rows returned are NMRC rows whose report record number is not in RPT.
select n._file, n._row, n.RPT_REC_NUM, n.WKSHT_CD, n.LINE_NUM, n.CLMN_NUM
from nmrc n
left join rpt r on r.RPT_REC_NUM = n.RPT_REC_NUM
where r.RPT_REC_NUM is null;
