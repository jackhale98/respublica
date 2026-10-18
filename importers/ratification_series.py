"""The books and series imported by importers/ratification.py.

Each series names its book, the printed pages the edition's table of contents
gives for it, the pattern of its essay headings, and its attribution as the
edition gives it. `position` (anti or federalist) is Res Publica's editorial
classification, documented in docs/editions.md.
"""

BOOKS = {
    "ford-essays": {
        "edition": "Paul Leicester Ford, ed., Essays on the Constitution of the United States (Brooklyn, 1892)",
        "item": "essaysonconstitu00forduoft",
        "primary": "ia-ford-essays-1892-toronto-xml",
        "references": {"brittle": "ia-ford-essays-1892-brittle-txt", "google": "ia-ford-essays-1892-google-txt"},
    },
    "ford-pamphlets": {
        "edition": "Paul Leicester Ford, ed., Pamphlets on the Constitution of the United States (Brooklyn, 1888)",
        "item": "cu31924020874099",
        "primary": "ia-ford-pamphlets-1888-cornell-xml",
        "references": {"google": "ia-ford-pamphlets-1888-google-txt"},
    },
    "mcmaster-stone": {
        "edition": "John Bach McMaster and Frederick D. Stone, eds., Pennsylvania and the Federal Constitution, 1787–1788 (Lancaster, 1888)",
        "item": "cu31924030454387",
        "primary": "ia-mcmaster-stone-1888-cornell-xml",
        "references": {"pitt": "ia-mcmaster-stone-1888-pitt-txt"},
    },
}

SERIES = [
    {
        "slug": "Cato",
        "work_id": "cato",
        "title": "The Letters of Cato",
        "short": "Cato",
        "book": "ford-essays",
        "pages": (241, 278),
        "essays": 7,
        "essay_heading": r"^CATO,?\s+([IVXL1l|]+)\.?$",
        "signature": r"^Cato\.?$",
        "signature_inline": r"Cato\.",
        "attribution": {"byline": "Written by George Clinton", "kind": "single", "names": ["George Clinton"]},
        "position": "anti",
        "date": "1787-09-27/1788-01-03",
    },
]
