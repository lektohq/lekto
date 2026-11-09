"""The words Lekto reads and writes in documents, by language, in one module of the core
(Tobi, 09.11.2026; the search's stop words and synonyms stay in language files): the names of
the months and their other spellings, the words between the ends of a span, of a week, of yes
and no, and of currencies. `periods`, `evidence` and the index build their patterns from them;
a further language or spelling is added here."""

MONTH_NAMES: dict[str, tuple[str, ...]] = {
    "de": (
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}
"""The names of the months, by language, January first."""

# Other ways to write the months than their names: Austrian, without umlauts, abbreviated.
OTHER_MONTH_SPELLINGS = (
    ("jänner", "jaenner", "jan"),
    ("feb",),
    ("maerz", "mär", "mrz", "mar"),
    ("apr",),
    (),
    ("jun",),
    ("jul",),
    ("aug",),
    ("sept", "sep"),
    ("okt", "oct"),
    ("nov",),
    ("dez", "dec"),
)

SPAN_WORDS: tuple[str, ...] = (
    "bis",
    "bis zum",
    "bis einschl",
    "bis einschl.",
    "bis einschließlich",
    "to",
    "until",
    "through",
)
"""Between the ends of a span (`1. bis 30. September 2026`), besides dashes."""

WEEK_WORDS: tuple[str, ...] = ("kw", "kalenderwoche", "calendar week", "week", "wk")
"""Before the number of a week (`KW 38`), each optionally with a full stop."""

WEEK_ABBREVIATION = "KW"
"""How the index writes a week (`KW 38 2026`)."""

TRUTH_WORDS: dict[str, bool] = {
    "true": True,
    "yes": True,
    "ja": True,
    "false": False,
    "no": False,
    "nein": False,
}
"""Yes and no as a document writes them, lower case."""

CURRENCY_WORDS: dict[str, set[str]] = {
    "€": {"EUR"},
    "euro": {"EUR"},
    "euros": {"EUR"},
    "$": {"USD"},
    "us$": {"USD"},
    "dollar": {"USD"},
    "dollars": {"USD"},
    "£": {"GBP"},
    "pfund": {"GBP"},
    "¥": {"JPY", "CNY"},
    "fr.": {"CHF"},
    "sfr.": {"CHF"},
    "sfr": {"CHF"},
    "franken": {"CHF"},
    "kč": {"CZK"},
    "zł": {"PLN"},
    "kr": {"SEK", "NOK", "DKK"},
    "kr.": {"SEK", "NOK", "DKK"},
}
"""Signs and names of currencies, lower case, with the ISO 4217 codes they may mean."""
