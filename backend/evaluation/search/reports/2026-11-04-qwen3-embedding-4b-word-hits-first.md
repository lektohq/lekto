# Search evaluation 2026-11-04 13:02 - `ollama/Qwen3-Embedding-4B-GGUF:Q8_0`

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
- Documents: 47, queries: 103
- Result per query: the first expected case among the first 10 hits. Hit@k: the share of queries found within the first k hits; MRR: mean of 1/rank (0 if not found); R-prec: mean share of the expected cases among the first n hits, n the number expected; Ties: queries where chance decides between an expected case and another at the top (same score).

## Results

| Model | Ratio | Hit@1 | Hit@3 | Hit@5 | MRR | R-prec | Ties | Mean ms | p95 ms | Without meaning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 77% | 78% | 79% | 0.774 | 75% | 6 | 15 | 48 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 97% | 100% | 100% | 0.982 | 95% | 3 | 26 | 59 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 89% | 96% | 98% | 0.927 | 88% | 0 | 24 | 57 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 83% | 100% | 94% | 15% | 100% | 78% | 60% | 75% | 100% | 100% | 100% | 100% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 100% | 60% | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

## R-precision by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 98% | 93% | 78% | 100% | 93% | 15% | 100% | 78% | 50% | 73% | 100% | 83% | 92% | 97% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 98% | 97% | 94% | 100% | 93% | 90% | 100% | 94% | 95% | 98% | 100% | 83% | 92% | 97% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 85% | 27% | 83% | 100% | 93% | 90% | 0% | 94% | 95% | 98% | 100% | 83% | 92% | 97% | 100% |

## The floor of the meaning

Per floor (`LEKTO_SEARCH_MEANING_MIN_SCORE`): the share of the queries found whose expected case stays (a word of the query shows in it, or the meaning scores it at least so high), and of 10 nonsense queries (abdidon, Quarxelbum, Flimpstok, …) the share left without a result. Measured without a floor.

| Model | Ratio | 0.60 | 0.62 | 0.64 | 0.66 | 0.68 | 0.70 | 0.72 | 0.74 | 0.76 | 0.78 | 0.80 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% / 0% | 100% / 0% | 100% / 30% | 100% / 70% | 100% / 80% | 100% / 90% | 100% / 100% | 100% / 100% | 99% / 100% | 98% / 100% | 98% / 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 100% / 0% | 100% / 0% | 100% / 30% | 100% / 70% | 100% / 80% | 99% / 90% | 98% / 100% | 95% / 100% | 88% / 100% | 77% / 100% | 65% / 100% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 2560 | 54 | 1.1 | 0.0 | 0.7 | 0.00 |

## Misses

### ollama/Qwen3-Embedding-4B-GGUF:Q8_0, ratio 0.5

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| Solidaritätszuschlag | exact | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
| Stromrechnung | compound | 01-stromrechnung | 1* | 01-stromrechnung, 48-rechnungskorrektur, 21-kontakt-tippfehler |
| Einkommensteuerbescheid | compound | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
