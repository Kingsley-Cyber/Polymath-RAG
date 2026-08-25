# THREE-MODE BENCHMARK V1 (behavioral, MEASURED)

- corpus: release-books-v1 · contract: neural-embed-v1
- captured: 20260825T130730Z · k=10

| query | class | VECTOR ms | HYBRID ms | GRAPH ms | top fused (HYBRID) |
|---|---|---|---|---|---|
| q01 | exact_fact | 684.2 | 1973.0 | 991.9 | chunk_06f25ac9ce78c6c6f3889150027f18c93402c0f1f7 |
| q02 | identifier | 584.6 | 994.4 | 1029.0 | chunk_200a8530c9ecc0a95b77d16aaea32d89f4f0577e6d |
| q03 | procedure | 609.2 | 960.8 | 980.4 | chunk_3f220076b84d2a9129106bbf5b41380582aeabf6bd |
| q04 | concept | 588.7 | 959.2 | 964.3 | chunk_56791e5a9b307e72b21879f589827b170fb976bfb9 |
| q05 | semantic_paraphrase | 581.4 | 939.1 | 944.8 | chunk_1808933f351d20508314d1fd4b58e460d1ce59d0fd |
| q06 | broad_exploration | 566.8 | 966.9 | 956.7 | chunk_13584637ad0116d1e69d7c0efc42a103a5d9c20dd6 |
| q07 | relationship | 597.0 | 984.7 | 986.6 | chunk_acb3d90ddad693c94a93967800f1d3110cb916e5c3 |
| q08 | cross_domain | 571.1 | 950.9 | 969.9 | chunk_369d00475218692fb17c3d870892b7697b03ce7946 |
| q09 | ambiguous | 581.8 | 964.3 | 953.1 | chunk_00240811403d8a4cfe25831dd3aea6e9bf8fe0ed56 |
| q10 | no_answer | 583.8 | 957.9 | 972.4 | chunk_03d56635dec69f25971b29a71dc2d74a80ad82a9e9 |

Full captures: THREE-MODE-BENCHMARK-20260825T130730Z.json

NOTE: behavioral measurements only — no accuracy claim without a sealed judged set.
