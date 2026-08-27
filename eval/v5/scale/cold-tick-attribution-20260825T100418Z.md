# COLD-TICK ATTRIBUTION (offline, MEASURED)

- captured: 20260825T100418Z  label: post-bulk-fix

## mode=full — wall 79.17 s

runs evaluated: 10233

| phase | ms | share of census_total |
|---|---|---|
| runs_query_ms | 102.4 | 0.1% |
| dirty_select_ms | 0.0 | 0.0% |
| attempts_fetch_ms | 88.3 | 0.1% |
| python_loop_ms | 78961.4 | 99.7% |
| receipt_checks_ms | 10224.3 | 12.9% |

| SQL bucket | ms | queries |
|---|---|---|
| scheduler_cursors | 64867.4 | 2 |
| receipt_anti_join | 10164.8 | 100 |
| runs_active_scan | 99.7 | 1 |
| stage_attempts | 81.8 | 1 |

SQL total 75213.7 ms / 104 statements.

## mode=auto — wall 0.31 s

runs evaluated: 10232

| phase | ms | share of census_total |
|---|---|---|
| runs_query_ms | 102.3 | 33.3% |
| dirty_select_ms | 20.2 | 6.6% |
| attempts_fetch_ms | 0.0 | 0.0% |
| python_loop_ms | 174.8 | 57.0% |
| receipt_checks_ms | 0.0 | 0.0% |

| SQL bucket | ms | queries |
|---|---|---|
| stage_attempts | 174.2 | 210 |
| runs_active_scan | 100.2 | 1 |
| scheduler_cursors | 8.0 | 2 |

SQL total 282.4 ms / 213 statements.

Transactions rolled back — zero durable writes.
