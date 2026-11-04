"""Words people search for in place of the words a document uses, by language: a group holds
words for the same document or the same thing in one ("Weihnachtsgeld", "13 Gehalt",
"Einmalzahlung"), and each finds what the others find (Meilisearch's `synonyms`, both ways).

German: groups for the documents of a household (work, pension, tax, housing, bank, insurance,
car, health, authorities, shopping, school and leisure), selected from OpenThesaurus
(https://www.openthesaurus.de, LGPL 2.1 or later, or CC BY-SA 4.0) and extended by Lekto with
the words OpenThesaurus lacks ("Einmalzahlung", "13 Gehalt", "SF-Klasse"). Only words that
mean the same in documents: OpenThesaurus also puts "Schätzung" beside "Rechnung" and "Einsatz"
beside "Kaution". Nor words that letters carry elsewhere: "Kundendienst" in a footer, "Entgelt"
as a bank's fee, "Rente" in the "Rentenversicherung" of every pay slip.

Meilisearch takes a synonym as a whole word, but splits German compounds in the documents and
in most queries: a word it splits finds nothing through the list
("Arbeitsunfähigkeitsbescheinigung", "Überweisung", "Rechnung"), nor does a phrase with a point
(an ordinal is written without; the adapter takes the point out of a query). A test asks every
word of every group against a real Meilisearch; what did not work there is left out. Other
languages have none yet: there is no use for them (Tobi, 04.11.2026).
"""

from collections import defaultdict
from collections.abc import Collection

MAX_PER_WORD = 50  # Meilisearch ignores the synonyms of a word beyond

GERMAN: tuple[tuple[str, ...], ...] = (
    # Work
    (
        "Gehaltsabrechnung",
        "Lohnabrechnung",
        "Entgeltabrechnung",
        "Verdienstabrechnung",
        "Gehaltszettel",
        "Lohnzettel",
        "Lohnstreifen",
        "Entgeltnachweis",
        "Verdienstnachweis",
        "Gehaltsnachweis",
    ),
    ("Gehalt", "Lohn", "Arbeitsentgelt", "Verdienst", "Bezüge"),
    (
        "Weihnachtsgeld",
        "Jahressonderzahlung",
        "Weihnachtsgratifikation",
        "13 Gehalt",
        "13 Monatsgehalt",
        "Einmalzahlung",
        "Sonderzahlung",
    ),
    ("Arbeitsvertrag", "Anstellungsvertrag", "Beschäftigungsvertrag", "Dienstvertrag"),
    ("Arbeitszeugnis", "Dienstzeugnis"),
    ("Überstunden", "Mehrarbeit", "Plusstunden"),
    ("Abfindung", "Abfindungszahlung"),
    ("Zeitnachweis", "Stundennachweis", "Stundenzettel", "Arbeitszeitnachweis"),
    ("Gehaltserhöhung", "Gehaltsanpassung", "Lohnerhöhung"),
    # Pension
    ("Altersrente", "Altersruhegeld"),
    ("Renteninformation", "Rentenauskunft"),
    ("Altersvorsorge", "Altersversorgung", "Altersabsicherung"),
    ("Betriebsrente", "bAV"),
    # Tax
    ("Steuerbescheid", "Einkommensteuerbescheid"),
    ("Steuererklärung", "Einkommensteuererklärung"),
    ("Kfz-Steuer", "Kraftfahrzeugsteuer", "Autosteuer"),
    ("Spendenquittung", "Spendennachweis"),
    # Housing
    ("Mietvertrag", "Wohnungsmietvertrag", "Mietvereinbarung"),
    ("Vermieter", "Wohnungsgeber"),
    ("Wohnungsgeberbescheinigung", "Vermieterbescheinigung"),
    ("Nebenkostenabrechnung", "Betriebskostenabrechnung"),
    ("Nebenkosten", "Betriebskosten", "Wohnnebenkosten"),
    ("Kaution", "Mietkaution", "Mietsicherheit"),
    ("Mieterhöhung", "Mietanpassung", "Mietpreiserhöhung"),
    ("Miete", "Mietzins"),
    ("Hausverwaltung", "Mietverwaltung", "Wohnungsverwaltung", "Immobilienverwaltung"),
    ("Umzug", "Wohnortwechsel", "Wohnsitzwechsel"),
    ("Meldebestätigung", "Anmeldebestätigung", "Wohnsitzanmeldung", "Ummeldung"),
    ("Hausratversicherung", "Hausratsversicherung"),
    ("Stromrechnung", "Stromabrechnung"),
    ("Zählerstand", "Zählerablesung", "Ablesung"),
    ("Abschlag", "Abschlagszahlung", "Abschlagsbetrag"),
    ("Rundfunkbeitrag", "Rundfunkgebühr", "GEZ", "GEZ-Gebühr"),
    ("Müllgebühr", "Abfallgebühr"),
    # Bank
    ("Kontoauszug", "Bankauszug"),
    ("Girokonto", "Gehaltskonto", "Sichtkonto"),
    ("Lastschrift", "Abbuchung", "Bankeinzug", "Lastschrifteinzug"),
    ("SEPA-Mandat", "Lastschriftmandat", "Einzugsermächtigung"),
    ("Geldüberweisung", "Banküberweisung"),
    ("Kreditkartenabrechnung", "Kreditkartenauszug", "Kartenabrechnung"),
    ("Kontoführungsgebühr", "Kontoführungsentgelt", "Kontogebühr", "Kontoentgelt"),
    ("Darlehen", "Kredit"),
    ("Sparbuch", "Sparkonto"),
    ("Depot", "Wertpapierdepot"),
    # Insurance
    ("Versicherungsschein", "Police", "Versicherungspolice"),
    ("Versicherungsbeitrag", "Versicherungsprämie"),
    ("Beitragsrechnung", "Prämienrechnung", "Beitragsabrechnung"),
    ("Beitragsanpassung", "Beitragserhöhung", "Prämienanpassung"),
    ("Selbstbeteiligung", "Eigenanteil"),
    (
        "Haftpflichtversicherung",
        "Privathaftpflichtversicherung",
        "Privathaftpflicht",
        "Haftpflicht",
    ),
    ("Kfz-Versicherung", "Autoversicherung", "Kfz-Haftpflicht", "Kraftfahrzeugversicherung"),
    ("Schadenfreiheitsklasse", "SF-Klasse", "Schadenfreiheitsrabatt", "SF-Einstufung"),
    ("Krankenkasse", "Krankenversicherung", "Gesundheitskasse"),
    ("Schadenmeldung", "Schadensmeldung", "Schadenanzeige", "Schadensanzeige"),
    ("Schadenregulierung", "Schadensregulierung"),
    ("Rechtsschutzversicherung", "Rechtsschutz"),
    ("Berufsunfähigkeitsversicherung", "BU-Versicherung"),
    ("Zahnzusatzversicherung", "Zahnversicherung"),
    ("Familienversicherung", "Familienmitversicherung"),
    # Car
    ("Auto", "Kfz", "Pkw", "Kraftfahrzeug"),
    ("Hauptuntersuchung", "HU", "TÜV"),
    ("Führerschein", "Fahrerlaubnis"),
    ("Werkstattrechnung", "Reparaturrechnung"),
    ("Inspektion", "Wartung"),
    ("Reifenwechsel", "Radwechsel"),
    (
        "Bußgeldbescheid",
        "Bußgeld",
        "Geldbuße",
        "Strafzettel",
        "Knöllchen",
        "Strafmandat",
        "Verwarngeld",
    ),
    ("Anhörungsbogen", "Anhörung"),
    ("Tankquittung", "Tankbeleg", "Tankbon"),
    ("Leasingvertrag", "Leasing"),
    # Health
    ("Arztrechnung", "Privatrechnung", "Arztliquidation"),
    ("Physiotherapie", "Krankengymnastik", "Physio"),
    ("Rezept", "ärztliche Verordnung"),
    ("Krankenhaus", "Klinik", "Klinikum", "Hospital"),
    ("Entlassbrief", "Arztbrief", "Entlassungsbericht"),
    ("Laborbefund", "Laborbericht", "Laborwerte", "Blutwerte"),
    ("Brille", "Sehhilfe"),
    ("Zahnersatz", "Zahnprothese"),
    ("Hausarzt", "Allgemeinmediziner", "Allgemeinarzt"),
    # Authorities and family
    ("Personalausweis", "Ausweis", "Perso"),
    ("Reisepass", "Pass"),
    ("Geburtsurkunde", "Geburtsschein"),
    ("Heiratsurkunde", "Eheurkunde"),
    ("Sterbeurkunde", "Todesurkunde"),
    ("Elterngeld", "Erziehungsgeld"),
    ("Widerspruch", "Einspruch"),
    ("Erbschein", "Erbnachweis"),
    # Shopping and contracts
    ("Quittung", "Kassenbon", "Kassenbeleg", "Kassenzettel", "Bon"),
    ("Mahnung", "Zahlungserinnerung", "Mahnschreiben", "Zahlungsaufforderung"),
    ("Lieferschein", "Warenbegleitschein"),
    ("Auftragsbestätigung", "Bestellbestätigung"),
    ("Angebot", "Offerte", "Kostenangebot"),
    ("Retoure", "Rückversand"),
    ("Reklamation", "Beanstandung", "Mängelrüge"),
    ("Garantie", "Herstellergarantie", "Garantiezertifikat", "Garantieschein"),
    ("Gewährleistung", "Mängelhaftung", "Sachmängelhaftung"),
    ("Abonnement", "Abo"),
    ("Handy", "Smartphone"),
    ("Telefonrechnung", "Handyrechnung", "Mobilfunkrechnung"),
    ("Internetanschluss", "DSL-Anschluss", "Breitbandanschluss"),
    # School and leisure
    ("Klassenfahrt", "Schulfahrt", "Schulausflug"),
    ("Kindertagesstätte", "Kindergarten"),
    ("Elternbrief", "Elternschreiben", "Elterninformation"),
    ("Mitgliedsbeitrag", "Vereinsbeitrag"),
    ("Rechtsanwalt", "Anwalt", "Rechtsanwältin", "Anwältin"),
    ("Volkshochschule", "VHS"),
    ("Bahnticket", "Fahrkarte", "Fahrschein", "Zugticket", "Bahnfahrkarte"),
    ("Flugticket", "Flugschein"),
    ("Bordkarte", "Boardingpass"),
    ("Hotelrechnung", "Hotelquittung"),
    ("Reisekosten", "Reisespesen", "Spesen"),
    ("Dienstreise", "Geschäftsreise"),
)
BY_LOCALE = {"deu": GERMAN}


def synonyms(locales: Collection[str]) -> dict[str, list[str]]:
    """The synonyms of the languages, as Meilisearch takes them: for each word the others of
    its groups, sorted."""
    found: defaultdict[str, set[str]] = defaultdict(set)
    for locale in locales:
        for group in BY_LOCALE.get(locale, ()):
            for word in group:
                found[word].update(other for other in group if other != word)
    return {word: sorted(others) for word, others in sorted(found.items())}
