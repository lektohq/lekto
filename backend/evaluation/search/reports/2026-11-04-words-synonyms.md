# Search evaluation 2026-11-04 09:12 - `words`

- Embedding endpoint: `none`
- Index: Meilisearch at meilisearch:7700, a temporary index
- LEKTO_SEARCH_CHUNK_SIZE: `1500`
- LEKTO_SEARCH_MAX_CHUNKS: `8`
- LEKTO_SEARCH_MAX_TEXT: `200000`
- LEKTO_SEARCH_SEMANTIC_RATIO: `0.5`
- LEKTO_SEARCH_LOCALES: `deu+eng`
- LEKTO_EMBEDDING_DOCUMENT_PREFIX: ``
- LEKTO_EMBEDDING_QUERY_PREFIX: ``
- Documents: 47, queries: 103
- Result per query: the first expected case among the first 10 hits. Hit@k: the share of queries found within the first k hits; MRR: mean of 1/rank (0 if not found); R-prec: mean share of the expected cases among the first n hits, n the number expected; Ties: queries where chance decides between an expected case and another at the top (same score).

## Results

| Model | Ratio | Hit@1 | Hit@3 | Hit@5 | MRR | R-prec | Ties | Mean ms | p95 ms | Without meaning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 76% | 78% | 79% | 0.769 | 74% | 5 | 12 | 47 | 0 |

Ratio 0 is full text only, 1 is meaning only. 'Without meaning': queries of a ratio above 0 for which the embedding of the query failed, so only the words counted.

## Hit@3 by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 100% | 100% | 83% | 100% | 94% | 15% | 100% | 78% | 60% | 75% | 100% | 100% | 100% | 100% | 100% |

## R-precision by kind of query

| Model | Ratio | exact (10) | number (5) | compound (6) | typo (2) | paraphrase (17) | english (13) | late (2) | confusable (18) | question (10) | purpose (8) | part (2) | inflected (1) | synonym (2) | field (4) | ending (3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| words | 0 | 98% | 93% | 78% | 100% | 87% | 15% | 100% | 78% | 50% | 73% | 100% | 83% | 92% | 97% | 100% |

## Cost of indexing

| Model | Dimensions | Sections | Per document | Embedding s | Rebuild s | s per section |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| words | - | - | - | - | 0.5 | - |

## Misses

### words, ratio 0

Queries not within the first 3 hits, and tied ones (rank with a *).

| Query | Kind | Expected | Rank | First hits |
| --- | --- | --- | ---: | --- |
| Solidaritätszuschlag | exact | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
| Stromrechnung | compound | 01-stromrechnung | 1* | 01-stromrechnung, 48-rechnungskorrektur |
| Einkommensteuerbescheid | compound | 08-einkommensteuerbescheid | 1* | 08-einkommensteuerbescheid, 46-steuerbescheid-ehepartnerin, 47-steuerbescheid-gemeinsam |
| Telefonflatrate | compound | 02-telefonrechnung | - | none |
| Geld zurück vom Finanzamt | paraphrase | 08-einkommensteuerbescheid | - | 26-langer-kontoauszug |
| electricity bill | english | 01-stromrechnung | - | 25-englische-rechnung |
| rental agreement apartment | english | 06-mietvertrag | - | none |
| salary slip | english | 15-lohnabrechnung, 29-lohnabrechnung-angestellte, 34-betraege-ohne-waehrung, 35-lohnabrechnung-gesamtbrutto, 39-lohnabrechnung-versicherung, 43-lohnabrechnung-falsche-zeile | - | none |
| tax refund | english | 08-einkommensteuerbescheid | - | none |
| dentist invoice | english | 05-zahnarztrechnung | - | 25-englische-rechnung |
| Barzahlung an den Elektriker | confusable | 38-quittung-ablagenummer | - | 03-handwerkerrechnung, 32-betrag-deutsch, 44-rechnung-spalten |
| Umzug beim Versandhändler gemeldet | confusable | 23-ohne-datum | - | 12-kreditkartenabrechnung |
| Kontoauszug, auf dem die Internetrechnung abgebucht wurde | confusable | 30-kontoauszug-fremde-kontakte | 4* | 11-kontoauszug, 12-kreditkartenabrechnung, 26-langer-kontoauszug |
| Girokonto-Auszug vom April | confusable | 11-kontoauszug | - | 12-kreditkartenabrechnung |
| Bis wann kann ich die Krankenkasse wechseln? | question | 14-beitragsanpassung-krankenversicherung | - | 16-kuendigungsbestaetigung, 36-zeitnachweis-monat |
| Wann läuft mein Internetvertrag aus? | question | 16-kuendigungsbestaetigung | - | none |
| Wie groß ist die Wohnung? | question | 06-mietvertrag | 2* | 03-handwerkerrechnung, 06-mietvertrag, 13-hausratversicherung |
| Welche Krankheit hat die Hausärztin festgestellt? | question | 04-arztrechnung | - | 46-steuerbescheid-ehepartnerin, 08-einkommensteuerbescheid, 47-steuerbescheid-gemeinsam |
| Ab wann arbeite ich bei Nordlicht? | question | 07-arbeitsvertrag | - | 38-quittung-ablagenummer, 14-beitragsanpassung-krankenversicherung, 21-kontakt-tippfehler |
| Unterlagen zur Altersvorsorge | purpose | 10-renteninformation | - | 32-betrag-deutsch |
| Ausgaben auf Dienstreise | purpose | 12-kreditkartenabrechnung | - | 43-lohnabrechnung-falsche-zeile |
| pension forecast | english | 10-renteninformation | - | none |
| health insurance premium increase | english | 14-beitragsanpassung-krankenversicherung | - | none |
| reminder for an unpaid invoice | english | 17-mahnung | - | 25-englische-rechnung |
| confirmation that my phone contract was cancelled | english | 16-kuendigungsbestaetigung | - | none |
| home contents insurance | english | 13-hausratversicherung, 45-versicherung-jahresbeitrag | - | none |
| refund for returned shoes | english | 18-gutschrift | - | none |
