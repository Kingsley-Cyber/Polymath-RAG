# G1 QUALIFICATION: HASH vs NEURAL (behavioral)

- corpus: `release-books-v1` · k=10 · captured 20260825T175110Z

| provider | semantic hit | identifier/exact hit |
|---|---|---|
| hash-embed-v1 | 0/4 | 0/4 |
| neural-embed-v1 | **2/4** | 4/4 |

| query | class | expect | hash hit@k | neural hit@k |
|---|---|---|---|---|
| q01 | semantic | site_reliability | ✗ | ✗ |
| q02 | semantic | fundamentals_of_software | ✗ | ✓ |
| q03 | semantic | influence_psychology | ✗ | ✗ |
| q04 | semantic | release_it | ✗ | ✓ |
| q05 | identifier | splunk | ✗ | ✓ |
| q06 | identifier | wazuh | ✗ | ✓ |
| q07 | procedure | malware | ✗ | ✓ |
| q08 | exact_fact | enterprise_integration | ✗ | ✓ |
| q09 | broad | data_engineering | ✗ | ✓ |
| q10 | no_answer | — | ✗ | ✗ |

VERDICT: NEURAL CUTOVER QUALIFIED (rule: neural materially beats hash on semantic classes while never losing identifier/exact classes)
