# Search evaluation 2026-11-04 05:43 - `ollama/Qwen3-Embedding-4B-GGUF:Q8_0`

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
- Documents: 47, queries: 103
- Result per query: the first expected case among the first 10 hits. Hit@k: the share of queries found within the first k hits; MRR: mean of 1/rank (0 if not found); R-prec: mean share of the expected cases among the first n hits, n the number expected; Ties: queries where chance decides between an expected case and another at the top (same score).

## Results

| Model | Ratio | Hit@1 | Hit@3 | Hit@5 | MRR | R-prec | Ties | Mean ms | p95 ms | Without meaning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 48% | 54% | 59% | 0.523 | 47% | 11 | 39 | 92 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 96% | 100% | 100% | 0.976 | 94% | 3 | 631 | 896 | 0 |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 88% | 96% | 98% | 0.921 | 86% | 0 | 42 | 83 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 100% | 100% | 67% | 100% | 53% | 8% | 100% | 50% | 0% | 38% | 100% | 100% | 50% | 100% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 100% | 60% | 100% | 100% | 100% | 100% | 0% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

## R-precision by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0 | 98% | 93% | 61% | 100% | 43% | 8% | 100% | 28% | 0% | 35% | 100% | 83% | 33% | 97% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 0.5 | 98% | 97% | 94% | 100% | 93% | 90% | 100% | 94% | 95% | 98% | 100% | 83% | 33% | 97% | 100% |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 1 | 85% | 27% | 83% | 100% | 93% | 90% | 0% | 94% | 95% | 98% | 88% | 83% | 33% | 97% | 100% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama/Qwen3-Embedding-4B-GGUF:Q8_0 | 2560 | 54 | 1.1 | 95.4 | 101.7 | 1.77 |

## Misses

### ollama/Qwen3-Embedding-4B-GGUF:Q8_0, ratio 0.5

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| Solidaritätszuschlag | exact | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
| Stromrechnung | compound | 01-stromrechnung | 1* | 01-stromrechnung, 48-rechnungskorrektur, 21-kontakt-tippfehler |
| Einkommensteuerbescheid | compound | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
