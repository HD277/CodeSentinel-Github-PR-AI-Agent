# CodeSentinel Evaluation Report
**Run Timestamp:** `2026-06-06T15:30:46.743663`
**Status:** ✅ PASSING

## Summary Metrics
| Metric | Current Run | Target / Baseline |
| :--- | :---: | :---: |
| JSON Parse Success Rate | `100.0%` | `100.0%` |
| Recall (Bugs Caught) | `100.0%` | `100.0%` |
| Precision (Accuracy) | `100.0%` | `100.0%` |
| Avg Latency | `38.28s` | `38.28s` |
| Avg Tokens | `6627.0` | `6627.0` |

## Detailed Case Breakdown
| Case ID | Success | Findings | Expected | Recall | Precision | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `case_1_sql_injection` | ✅ | 4 | 1 | 100% | 100% | `44.04s` |
| `case_2_resource_leak` | ✅ | 4 | 1 | 100% | 100% | `39.0s` |
| `case_3_logic_off_by_one` | ✅ | 3 | 1 | 100% | 100% | `31.79s` |