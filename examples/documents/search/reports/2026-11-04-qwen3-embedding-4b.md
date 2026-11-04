# Search evaluation 2026-11-04 05:47 - `ollama/Qwen3-Embedding-4B-GGUF:Q8_0`

- Embedding endpoint: Ollama in the home network through LiteLLM (2 vGPUs, the model in video memory)
- Index: Meilisearch at meilisearch:7700, a temporary index per model
- LEKTO_SEARCH_CHUNK_SIZE: `1500`
- LEKTO_SEARCH_MAX_CHUNKS: `8`
- LEKTO_SEARCH_MAX_TEXT: `200000`
- LEKTO_SEARCH_SEMANTIC_RATIO: `0.5`
- LEKTO_SEARCH_LOCALES: `deu+eng`
- LEKTO_EMBEDDING_DOCUMENT_PREFIX: ``
- LEKTO_EMBEDDING_QUERY_PREFIX: `Instruct: Given a search query, retrieve the German personal documents (letters, invoices, statements, contracts) that answer it
Query:`
- Documents: 321, queries: 122
- Result per query: the first expected case among the first 10 hits. Hit@k: the share of queries found within the first k hits; MRR: mean of 1/rank (0 if not found); R-prec: mean share of the expected cases among the first n hits, n the number expected; Ties: queries where chance decides between an expected case and another at the top (same score).

## Results

| Model | Ratio | Hit@1 | Hit@3 | Hit@5 | MRR | R-prec | Ties | Mean ms | p95 ms | Without meaning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 61% | 66% | 70% | 0.644 | 61% | 3 | 35 | 62 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 91% | 94% | 96% | 0.932 | 88% | 0 | 581 | 775 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 83% | 91% | 93% | 0.874 | 81% | 0 | 39 | 62 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 100% | 100% | 100% | 20% | 100% | 86% | 100% | 50% | 0% | 86% | 0% | 29% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 83% | 100% | 100% | 100% | 100% | 80% | 100% | 86% | 100% | 100% | 90% | 100% | 100% | 86% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 67% | 86% | 100% | 100% | 100% | 80% | 100% | 71% | 100% | 100% | 90% | 93% | 100% | 100% |

## R-precision by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 97% | 89% | 88% | 24% | 100% | 77% | 88% | 32% | 0% | 79% | 0% | 36% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 81% | 100% | 97% | 94% | 87% | 67% | 100% | 77% | 100% | 94% | 87% | 93% | 85% | 82% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 60% | 79% | 97% | 94% | 94% | 67% | 100% | 63% | 100% | 94% | 87% | 64% | 85% | 82% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 2560 | 411 | 1.3 | 1203.7 | 1210.5 | 2.93 |

## Misses

### ollama/Qwen3-Embedding-4B-GGUF:Q8_0, ratio 0.5

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| Urlaubsgeld | exact | lohn-max-2024-06, lohn-max-2025-06, lohn-max-2026-06 | 6 | schule-klassenfahrt, zeitnachweis-2026-07, kindergeld-2026 |
| Tilgung | exact | darlehen-vertrag | - | darlehen-2024, darlehen-2025, konto-2025-09 |
| 13. Gehalt | synonym | lohn-max-2024-11, lohn-max-2025-11 | - | direktbank-2024-q4, konto-2024-05, konto-2024-08 |
| Weihnachtsgratifikation | synonym | lohn-max-2024-11, lohn-max-2025-11 | 8 | gehalt-2026, gehalt-2025, lohn-erika-2025-12 |
| Erstattungen | ending | steuer-2024, steuer-2025 | 5 | spende-2024, spende-2025, sepa-musikschule |
| holiday pay | english | lohn-max-2024-06, lohn-max-2025-06, lohn-max-2026-06 | - | zeitnachweis-2026-07, zeitnachweis-2026-08, zeitnachweis-2026-04 |
| Handwerkerleistungen für die Steuererklärung | purpose | krause-rechnung, maler-quittung, maler-rechnung, umzug-rechnung | 4 | finanzamt-anforderung, steuer-2024, steuer-2025 |
