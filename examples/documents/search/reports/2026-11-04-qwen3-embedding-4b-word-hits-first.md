# Search evaluation 2026-11-04 13:03 - `ollama/Qwen3-Embedding-4B-GGUF:Q8_0`

- Embedding endpoint: Ollama in the home network through LiteLLM (2 vGPUs, the model in video memory); vectors of the earlier runs, cached
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
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 74% | 77% | 79% | 0.757 | 74% | 3 | 26 | 56 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 93% | 97% | 98% | 0.955 | 90% | 0 | 72 | 97 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 88% | 96% | 98% | 0.919 | 85% | 0 | 72 | 98 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 100% | 100% | 100% | 80% | 100% | 86% | 100% | 75% | 0% | 93% | 40% | 29% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% | 100% | 100% | 100% | 100% | 90% | 100% | 86% | 100% | 100% | 90% | 100% | 100% | 86% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 100% | 86% | 100% | 100% | 100% | 90% | 100% | 86% | 100% | 100% | 90% | 93% | 100% | 100% |

## R-precision by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 97% | 89% | 88% | 79% | 100% | 77% | 88% | 65% | 0% | 93% | 40% | 30% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% | 100% | 97% | 94% | 87% | 77% | 100% | 77% | 100% | 86% | 87% | 93% | 85% | 82% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 88% | 79% | 97% | 94% | 94% | 77% | 100% | 76% | 100% | 86% | 87% | 64% | 85% | 82% |

## The floor of the meaning

Per floor (`LEKTO_SEARCH_MEANING_MIN_SCORE`): the share of the queries found whose expected case stays (a word of the query shows in it, or the meaning scores it at least so high), and of 10 nonsense queries (abdidon, Quarxelbum, Flimpstok, …) the share left without a result. Measured without a floor.

| Model | Ratio | 0.60 | 0.62 | 0.64 | 0.66 | 0.68 | 0.70 | 0.72 | 0.74 | 0.76 | 0.78 | 0.80 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% / 0% | 100% / 0% | 100% / 0% | 100% / 10% | 100% / 70% | 100% / 80% | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 100% / 0% | 100% / 0% | 100% / 0% | 100% / 10% | 100% / 70% | 99% / 80% | 96% / 100% | 91% / 100% | 86% / 100% | 81% / 100% | 68% / 100% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 2560 | 411 | 1.3 | 0.0 | 1.9 | 0.00 |

## Misses

### ollama/Qwen3-Embedding-4B-GGUF:Q8_0, ratio 0.5

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| 13. Gehalt | synonym | lohn-max-2024-11, lohn-max-2025-11 | - | direktbank-2024-q4, steuer-2024, steuer-2025 |
| Erstattungen | ending | steuer-2024, steuer-2025 | 5 | spende-2024, spende-2025, sepa-musikschule |
| holiday pay | english | lohn-max-2024-06, lohn-max-2025-06, lohn-max-2026-06 | - | zeitnachweis-2026-07, zeitnachweis-2026-08, zeitnachweis-2026-04 |
| Handwerkerleistungen für die Steuererklärung | purpose | krause-rechnung, maler-quittung, maler-rechnung, umzug-rechnung | 4 | finanzamt-anforderung, steuer-2024, steuer-2025 |
