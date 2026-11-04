# Search evaluation 2026-11-04 09:13 - `words`

- Embedding endpoint: `none`
- Index: Meilisearch at meilisearch:7700, a temporary index
- LEKTO_SEARCH_CHUNK_SIZE: `1500`
- LEKTO_SEARCH_MAX_CHUNKS: `8`
- LEKTO_SEARCH_MAX_TEXT: `200000`
- LEKTO_SEARCH_SEMANTIC_RATIO: `0.5`
- LEKTO_SEARCH_LOCALES: `deu+eng`
- LEKTO_EMBEDDING_DOCUMENT_PREFIX: ``
- LEKTO_EMBEDDING_QUERY_PREFIX: ``
- Documents: 321, queries: 122
- Result per query: the first expected case among the first 10 hits. Hit@k: the share of queries found within the first k hits; MRR: mean of 1/rank (0 if not found); R-prec: mean share of the expected cases among the first n hits, n the number expected; Ties: queries where chance decides between an expected case and another at the top (same score).

## Results

| Model | Ratio | Hit@1 | Hit@3 | Hit@5 | MRR | R-prec | Ties | Mean ms | p95 ms | Without meaning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 74% | 77% | 79% | 0.757 | 74% | 3 | 33 | 60 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 100% | 100% | 100% | 100% | 100% | 80% | 100% | 86% | 100% | 75% | 0% | 93% | 40% | 29% |

## R-precision by kind of query

| Model | Ratio | exact (12) | number (7) | compound (6) | part (6) | inflected (7) | synonym (10) | field (10) | ending (7) | typo (4) | paraphrase (12) | english (10) | confusable (14) | question (10) | purpose (7) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 100% | 100% | 97% | 89% | 88% | 79% | 100% | 77% | 88% | 65% | 0% | 93% | 40% | 30% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| words | - | - | - | - | 1.6 | - |

## Misses

### words, ratio 0

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| Zins | inflected | bauspar-2024, bauspar-2025, bauspar-vertrag, darlehen-2024, darlehen-2025, darlehen-vertrag | 1* | bauspar-2024, bauspar-2025, bauspar-vertrag |
| 13. Gehalt | synonym | lohn-max-2024-11, lohn-max-2025-11 | - | direktbank-2024-q4, steuer-2024, steuer-2025 |
| Krankmeldung | synonym | au-max | - | klinik-lena |
| Erstattungen | ending | steuer-2024, steuer-2025 | 5 | spende-2024, spende-2025, sepa-musikschule |
| Geld für den Hund an die Stadt | paraphrase | hundesteuer-2025, hundesteuer-2026 | 2* | haftpflicht-police, hundesteuer-2025, hundesteuer-2026 |
| zu schnell gefahren | paraphrase | bussgeld-anhoerung, bussgeld-bescheid | - | kfz-sf, kuendigung-erika |
| Sprachkurs | paraphrase | vhs-spanisch | - | anwalt-2 |
| Zählerstand abgelesen | paraphrase | strom-ablesung | - | bergmann-mahnung-1, bergmann-mahnung-2, krause-mahnung |
| dog tax | english | hundesteuer-2025, hundesteuer-2026 | - | cloudberry-2025-08, cloudberry-2025-09, cloudberry-2025-10 |
| child benefit | english | kindergeld-2025, kindergeld-2026 | - | none |
| electricity meter reading | english | strom-ablesung | - | mieterhoehung, kaution, kuendigung-birkenweg |
| speeding fine | english | bussgeld-anhoerung, bussgeld-bescheid | - | none |
| car loan | english | darlehen-2024, darlehen-2025, darlehen-vertrag | - | none |
| donation receipt | english | spende-2024, spende-2025 | - | none |
| rent increase | english | mieterhoehung | - | none |
| sick note | english | au-max | - | technik-bestellung, technik-garantie, technik-rechnung |
| bicycle theft | english | schaden-anzeige, schaden-eingang, schaden-regulierung | - | none |
| holiday pay | english | lohn-max-2024-06, lohn-max-2025-06, lohn-max-2026-06 | - | flug-buchung |
| Stromrechnung beim Auszug | confusable | strom-schluss | - | konto-2024-11, konto-2024-04, konto-2024-05 |
| Angebot vom Elektriker | confusable | krause-angebot | 1* | krause-angebot, umzug-angebot, technik-bestellung |
| Wann muss das Auto wieder zur HU? | question | hu-2026 | - | none |
| Wie hoch war die Kaution am Birkenweg? | question | anwalt-1, anwalt-2, kaution, kuendigung-birkenweg | - | vhs-spanisch |
| Was kostet die Musikschule im Monat? | question | musikschule-gebuehr, musikschule-vertrag | - | zwischenzeugnis-max, arbeitsvertrag-erika-foto, arbeitsvertrag-erika |
| Was zahlt die Versicherung für das gestohlene Fahrrad? | question | schaden-regulierung | - | schaden-anzeige, fahrrad-kaufvertrag |
| Wie hoch ist die Miete in der Lindenallee? | question | mieterhoehung, mietvertrag | - | vhs-spanisch |
| In welcher Schadenfreiheitsklasse ist das Auto? | question | kfz-police, kfz-sf | - | musikschule-vertrag |
| Handwerkerleistungen für die Steuererklärung | purpose | krause-rechnung, maler-quittung, maler-rechnung, umzug-rechnung | - | finanzamt-anforderung, steuer-2024, steuer-2025 |
| Nachweis für den Arbeitgeber, dass ich krank war | purpose | au-max | - | klinik-lena |
| Bons vom Wocheneinkauf | purpose | bon-grocery-00, bon-grocery-01, bon-grocery-02, bon-grocery-03, bon-grocery-04, bon-grocery-05, bon-grocery-06, bon-grocery-07, bon-grocery-08, bon-grocery-09, bon-grocery-10, bon-grocery-11, bon-groc | - | bussgeld-bescheid, musikschule-vertrag, sepa-musikschule |
| Belege fürs Tanken | purpose | tanken-0, tanken-1, tanken-2, tanken-3, tanken-4, tanken-5 | 5 | nebenkosten-2024, nebenkosten-2025, ueberweisung-tierheim |
| Werbung im Briefkasten | purpose | werbung-gewinn, werbung-solar | - | mietvertrag, klinik-lena, schule-elternabend |
