"""The books and series imported by importers/ratification.py.

Each series names its book, the printed pages it fills (from its title page
to the page before the next section), the pattern of its essay headings
(NUM is the essay's number), its signature, and its attribution as the
edition gives it: in the words of the section's title page unless
`attribution.source` names another place in the edition. `position` (anti,
federalist or other) is Res Publica's classification, not the edition's;
see docs/editions.md.
"""

# A speaker's name opening a paragraph of debates, in capitals ("Mr.
# MADISON.", "Gov. RANDOLPH observed", "Mr. GEORGE NICHOLAS"), as OCR reads it.
SPEAKER = r"^(?:Mr|Gov|Judge|Col|Gen)\W{0,2}\s+[A-Z][A-Z]{2,}\b"

BOOKS = {
    "ford-essays": {
        "edition": "Paul Leicester Ford, ed., Essays on the Constitution of the United States (Brooklyn, 1892)",
        "short": "Ford, Essays on the Constitution (1892)",
        "item": "essaysonconstitu00forduoft",
        "primary": "ia-ford-essays-1892-toronto-xml",
        "references": {"brittle": "ia-ford-essays-1892-brittle-txt", "google": "ia-ford-essays-1892-google-txt"},
    },
    "ford-pamphlets": {
        "edition": "Paul Leicester Ford, ed., Pamphlets on the Constitution of the United States (Brooklyn, 1888)",
        "short": "Ford, Pamphlets on the Constitution (1888)",
        "item": "cu31924020874099",
        "primary": "ia-ford-pamphlets-1888-cornell-xml",
        "references": {"google": "ia-ford-pamphlets-1888-google-txt"},
    },
    "mcmaster-stone": {
        "edition": "John Bach McMaster and Frederick D. Stone, eds., Pennsylvania and the Federal Constitution, 1787–1788 (Lancaster, 1888)",
        "short": "McMaster and Stone, Pennsylvania and the Federal Constitution (1888)",
        "item": "cu31924030454387",
        "primary": "ia-mcmaster-stone-1888-cornell-xml",
        "references": {"pitt": "ia-mcmaster-stone-1888-pitt-txt"},
    },
    "mass-debates": {
        "edition": "Debates and Proceedings in the Convention of the Commonwealth of Massachusetts, held in the year 1788 (Boston, 1856)",
        "short": "Debates and Proceedings in the Convention of Massachusetts (1856)",
        "item": "debatesproceedin00mass",
        "primary": "ia-mass-debates-1856-nypl-xml",
        "references": {"uc": "ia-mass-debates-1856-uc-txt", "google": "ia-mass-debates-1856-google-txt",
                       "cornell": "ia-mass-debates-1856-cornell-txt"},
    },
    # Elliot's Debates, vol. 3 (Virginia), in the standard (Lippincott)
    # pagination: Patrick Henry's speeches (importers/elliot.py). Not the
    # separate setting "printed on the Pennsylvania Avenue" (UNC's scans),
    # whose pages differ.
    "elliot-3": {
        "edition": "Jonathan Elliot, ed., The Debates in the Several State Conventions on the Adoption of the Federal Constitution, vol. 3 (2nd ed., Philadelphia: J. B. Lippincott, 1907 printing)",
        "short": "Elliot, Debates, vol. 3",
        "item": "debatesinseveral03elliuoft",
        "primary": "ia-elliot-v3-1907-toronto-xml",
        "references": {"cornell": "ia-elliot-v3-1876-cornell-txt", "harvard": "ia-elliot-v3-1861-google-txt",
                       "google": "ia-elliot-v3-1836-google-txt"},
        # Specks hide some running heads, and the printer's signature marks
        # ("VOL. III. 7") stand at the foot of every eighth page. A speaker's
        # words begin a paragraph with the name in capitals ("Mr. MADISON.",
        # "Gov. RANDOLPH observed").
        # (OCR reads "III." as "HI." or "in.", and the sheet's number badly.)
        "set_aside": True, "signature_marks": r"(?i)^VO[LT]\.?(?:\s+\S{1,4}){1,3}\s*$",
        "speaker_lines": SPEAKER,
        # "580 DEBATES. [Nicholas." on the left, "Henry.] VIRGINIA. 579" on the right.
        "running_head": r"\bDEBATES\.?\s*\[\s*\S+$|^\S*\]?\s*VIRGINIA\b",
    },
    # Vols. 2 and 4, the same printing: the scans the Library of Congress's
    # transcription of the other conventions is checked against
    # (importers/conventions.py; decision 68).
    "elliot-2": {
        "edition": "Jonathan Elliot, ed., The Debates in the Several State Conventions on the Adoption of the Federal Constitution, vol. 2 (2nd ed., Philadelphia: J. B. Lippincott, 1907 printing)",
        "short": "Elliot, Debates, vol. 2",
        "item": "debatesinseveral02elliuoft",
        "primary": "ia-elliot-v2-1907-toronto-xml",
        "references": {},
    },
    "elliot-4": {
        "edition": "Jonathan Elliot, ed., The Debates in the Several State Conventions on the Adoption of the Federal Constitution, vol. 4 (2nd ed., Philadelphia: J. B. Lippincott, 1907 printing)",
        "short": "Elliot, Debates, vol. 4",
        "item": "debatesinseveral04elliuoft",
        "primary": "ia-elliot-v4-1907-toronto-xml",
        "references": {},
    },
}

# Roman numeral as OCR reads it (I as 1, l, | or !; II as H; V as Y).
NUM = r"(?P<n>[IVXLHYl1|!vxi]{1,6})[.,;]?"

SERIES = [
    # ---- Ford, Essays on the Constitution (1892). Pages are the printed
    # pages from each section's title page to the page before the next.
    {
        "slug": "Cassius", "work_id": "cassius", "title": "The Letters of Cassius", "short": "Cassius",
        "book": "ford-essays", "pages": (1, 48), "essays": 11,
        "heading": r"CASSIUS,?\s+" + NUM, "signature": "Cassius.",
        "attribution": {"byline": "Written by James Sullivan", "kind": "single", "names": ["James Sullivan"]},
        "position": "federalist", "date": "1787-09-18/1787-12-25",
    },
    {
        "slug": "Agrippa", "work_id": "agrippa", "title": "The Letters of Agrippa", "short": "Agrippa",
        "book": "ford-essays", "pages": (49, 122), "essays": 18,
        # Ford prints two numbers XV (January 22 and 25, 1788) and no XVI.
        "ids": [str(n) for n in range(1, 16)] + ["15b", "17", "18"],
        "heading": r"AGRIPP\S*,?\s+" + NUM, "signature": "Agrippa.",
        "attribution": {"byline": "Accredited to James Winthrop", "kind": "single", "names": ["James Winthrop"]},
        "position": "anti", "date": "1787-11-23/1788-02-05",
    },
    {
        "slug": "GerryReply", "work_id": "gerry-reply", "title": "Replies to a Landholder", "short": "Reply to a Landholder",
        "book": "ford-essays", "pages": (123, 134), "essays": 2,
        "heading": r"REPLY\s+TO\s+A\s+\S+,?\s+" + NUM, "signature": "E. Gerry.",
        "attribution": {"byline": "By Elbridge Gerry", "kind": "single", "names": ["Elbridge Gerry"]},
        "position": "anti", "date": "1788-01-05/1788-04-30",
    },
    {
        "slug": "Landholder", "work_id": "landholder", "title": "The Letters of a Landholder", "short": "Landholder",
        "book": "ford-essays", "pages": (135, 202), "essays": 14,
        # Ford prints two numbers X; his note to the second says it
        # "duplicates the preceding one".
        "ids": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "10b", "11", "12", "13"],
        "heading": r"(?:THE|A)\s+\S*\s*L\S*D\S*\s*H\S*[,;.]?\s+" + NUM, "heading_ignore_case": True,
        "signature": "A Landholder.",
        "attribution": {"byline": "Written by Oliver Ellsworth", "kind": "single", "names": ["Oliver Ellsworth"]},
        "position": "federalist", "date": "1787-11-05/1788-03-24",
    },
    {
        "slug": "Countryman", "work_id": "countryman", "title": "The Letters of a Countryman", "short": "Countryman",
        "book": "ford-essays", "pages": (211, 228), "essays": 5,
        "heading": r"A\s+COUNTRYMAN,?\s+" + NUM, "signature": "A Countryman.",
        "attribution": {"byline": "Written by Roger Sherman", "kind": "single", "names": ["Roger Sherman"]},
        "position": "federalist", "date": "1787-11-14/1787-12-20",
    },
    {
        "slug": "CitizenOfNewHaven", "work_id": "citizen-of-new-haven", "title": "The Letters of a Citizen of New Haven",
        "short": "Citizen of New Haven", "book": "ford-essays", "pages": (229, 242), "essays": 2,
        "heading": r"A\s+C\S+\s+OF\s+NEW\s+HAVEN,?\s+" + NUM, "signature": "A Citizen of New Haven.",
        "attribution": {"byline": "Written by Roger Sherman", "kind": "single", "names": ["Roger Sherman"]},
        "position": "federalist", "date": "1788-12-04/1788-12-25",
    },
    {
        "slug": "Cato", "work_id": "cato", "title": "The Letters of Cato", "short": "Cato",
        "book": "ford-essays", "pages": (243, 278), "essays": 7,
        "heading": r"CATO,?\s+" + NUM, "signature": "Cato.",
        "attribution": {"byline": "Written by George Clinton", "kind": "single", "names": ["George Clinton"]},
        "position": "anti", "date": "1787-09-27/1788-01-03",
    },
    {
        "slug": "Caesar", "work_id": "caesar", "title": "The Letters of Caesar", "short": "Caesar",
        "book": "ford-essays", "pages": (279, 292), "essays": 2,
        "heading": r"C\S{1,3}SAR,?\s+" + NUM, "signature": "Caesar.",
        "attribution": {"byline": "Written by Alexander Hamilton", "kind": "single", "names": ["Alexander Hamilton"]},
        "position": "federalist", "date": "1787-10-01/1787-10-17",
    },
    {
        "slug": "Sydney", "work_id": "sydney", "title": "The Letters of Sydney", "short": "Sydney",
        "book": "ford-essays", "pages": (293, 314), "essays": 2,
        "heading": r"SYDNEY,?\s+" + NUM, "signature": "Sydney.",
        "attribution": {"byline": "Written by Robert Yates", "kind": "single", "names": ["Robert Yates"]},
        "position": "anti", "date": "1788-06-13/1788-06-14",
    },
    {
        "slug": "CursoryRemarks", "work_id": "cursory-remarks", "title": "Cursory Remarks", "short": "Cursory Remarks",
        "book": "ford-essays", "pages": (315, 322), "essays": 1,
        "heading": r"CURSORY\s+REMARKS\.?",
        "attribution": {"byline": "By Hugh Henry Brackenridge", "kind": "single", "names": ["Hugh Henry Brackenridge"]},
        "position": "federalist", "date": "1788-04",
    },
    {
        "slug": "Caution", "work_id": "caution", "title": "Caution", "short": "Caution",
        "book": "ford-essays", "pages": (323, 328), "essays": 1,
        "heading": r"CAUTION\.?", "signature": "Caution.",
        "attribution": {"byline": "Written by Samuel Chase", "kind": "single", "names": ["Samuel Chase"]},
        "position": "anti", "date": "1787-10-12",
    },
    {
        "slug": "FriendToTheConstitution", "work_id": "friend-to-the-constitution", "title": "A Friend to the Constitution",
        "short": "A Friend to the Constitution", "book": "ford-essays", "pages": (329, 336), "essays": 1,
        "heading": r"A\s+FRIEND\s+TO\s+THE\s+CONSTITUTION\.?", "signature": "A Friend to the Constitution,",
        "attribution": {"byline": "Written by Daniel Carroll", "kind": "single", "names": ["Daniel Carroll"]},
        "position": "federalist", "date": "1787-10-16",
    },
    {
        "slug": "LutherMartin", "work_id": "luther-martin", "title": "The Letters of Luther Martin", "short": "Luther Martin",
        "book": "ford-essays", "pages": (337, 384), "essays": 6,
        "heading": r"LUTHER\s+MARTIN\s*,\s*" + NUM, "signature": "Luther Martin.",
        "attribution": {"byline": "Luther Martin", "kind": "single", "names": ["Luther Martin"]},
        "position": "anti", "date": "1788-01-18/1788-04-04",
    },
    {
        "slug": "PlainDealer", "work_id": "plain-dealer", "title": "A Plain Dealer", "short": "A Plain Dealer",
        "book": "ford-essays", "pages": (385, 394), "essays": 1,
        "heading": r"A\s+PLAIN\s+DEALER\.?", "signature": "A Plain Dealer.",
        "attribution": {"byline": "Accredited to Spencer Roane", "kind": "single", "names": ["Spencer Roane"]},
        "position": "anti", "date": "1788-02-13",
    },
    {
        "slug": "WilliamsonRemarks", "work_id": "williamson-remarks", "title": "Remarks on the New Plan of Government",
        "short": "Remarks on the New Plan", "book": "ford-essays", "pages": (395, 406), "essays": 1,
        "heading": r"REMARKS\.?",
        "attribution": {"byline": "By Hugh Williamson", "kind": "single", "names": ["Hugh Williamson"]},
        "position": "federalist", "date": "1788",
    },
    {
        "slug": "SteadyAndOpenRepublican", "work_id": "steady-and-open-republican",
        "title": "A Steady and Open Republican", "short": "A Steady and Open Republican",
        "book": "ford-essays", "pages": (407, 414), "essays": 1,
        "heading": r"A\s+REPUBLICAN\.?", "signature": "A Steady and Open Republican.",
        "attribution": {"byline": "Written by Charles Pinckney", "kind": "single", "names": ["Charles Pinckney"]},
        "position": "federalist", "date": "1788-05-05",
    },
    {
        "slug": "WilliamsLetter", "work_id": "williams-letter", "title": "Letter to the Landholder",
        "short": "Letter to the Landholder", "book": "ford-essays", "pages": (203, 210), "essays": 1,
        "heading": r"THE\s+AMERICAN\s+MERCURY,?", "heading_in_publication": True,
        "attribution": {"byline": "By William Williams", "kind": "single", "names": ["William Williams"]},
        "position": "other", "date": "1788-02-11",
    },
    # ---- McMaster and Stone, Pennsylvania and the Federal Constitution
    # (1888), chapter VII.
    {
        "slug": "Centinel", "work_id": "centinel", "title": "The Letters of Centinel", "short": "Centinel",
        "book": "mcmaster-stone", "pages": (565, 698), "essays": 24,
        "heading": r"C\S{4,8}[,.<]*\s*No\.?\s*" + NUM + r"\s*\*?(?P<rest>\s+To\s.{3,90})?",
        "signature": "Centinel.",
        "attribution": {"byline": "Attributed to Samuel Bryan", "kind": "single", "names": ["Samuel Bryan"],
                        "source": "Ford, Essays on the Constitution (1892), Bibliography, p. 415"},
        "position": "anti", "date": "1787-10-05/1788-11-24",
    },
    # The Address and Reasons of Dissent of the Minority of the Convention of
    # Pennsylvania (chapter VI, "After the Convention Rose"), signed by
    # twenty-one members.
    {
        "slug": "PennsylvaniaMinority", "work_id": "pennsylvania-minority",
        "title": "The Address and Reasons of Dissent of the Minority of the Convention of Pennsylvania",
        "short": "Dissent of the Pennsylvania Minority", "book": "mcmaster-stone", "pages": (454, 482), "essays": 1,
        # OCR runs the title's first line into the editor's note above it.
        "heading": r"THE\s+ADDRESS\s+AND\s+REASONS\s+OF\s+DISSENT\s+OF\s+THE\s+MINORITY",
        "heading_ignore_case": True, "heading_ends_block": True,
        # The book prints the yeas and nays of the final vote after the
        # signatures, in columns OCR reads out of order; the piece ends there.
        "end_at": r"The\s+yeas\s+and\s+nays\s+upon\s+the\s+final\s+vote", "signers": True,
        "attribution": {"byline": "the Minority of the Convention of the State of Pennsylvania", "kind": "body",
                        "names": ["Minority of the Pennsylvania ratifying convention"],
                        "source": "McMaster and Stone, Pennsylvania and the Federal Constitution (1888), p. 454, the title"},
        "position": "anti", "date": "1787-12-18",
    },
    # ---- Ford, Pamphlets on the Constitution (1888).
    {
        "slug": "FederalFarmer", "work_id": "federal-farmer", "title": "Letters from the Federal Farmer to the Republican",
        "short": "Federal Farmer", "book": "ford-pamphlets", "pages": (277, 326), "essays": 5,
        "heading": r"LETTER\s+" + NUM, "signature": "The Federal Farmer.",
        "closing_lines": [r"To the Republican\.?$"],
        "attribution": {"byline": "Written by Richard Henry Lee", "kind": "single", "names": ["Richard Henry Lee"],
                        "source": "Ford, Pamphlets on the Constitution (1888), p. 277, editor's note"},
        "position": "anti", "date": "1787-10-08/1787-10-13",
    },
    # ---- Debates and Proceedings in the Convention of Massachusetts
    # (1856), "Spirit of the Press": Brutus I-IV as reprinted in Boston's
    # Independent Chronicle. The other twelve essays are not in it.
    {
        "slug": "Brutus", "work_id": "brutus", "title": "The Letters of Brutus", "short": "Brutus",
        "book": "mass-debates", "pages": (366, 398), "essays": 4,
        "heading": r"BRUTUS\.?\s*[—–-]*\s*No\.?\s*" + NUM, "signature": "Brutus.",
        "attribution": {"byline": "Brutus was the signature (of Thomas Treadwell, of Suffolk County, N. Y.?)",
                        "kind": "pseudonym", "names": ["Thomas Treadwell?"], "pseudonym": "Brutus",
                        "source": "Ford, Pamphlets on the Constitution (1888), p. 117, editor's note to Webster's The Weakness of Brutus Exposed"},
        "position": "anti", "date": "1787-10-18/1788-04-10",
        # V-XVI (not XI) from the New-York Journal's own pages (importers/nyjournal.py).
        "continued_in": "nyjournal",
        # The newspaper's signature letter-spaced, as OCR reads it ("B R U T U 3.").
        "closing_lines": [r"^B\s?R\s?U\s?\S?\s?T\s?U\s?[S38$]\W*$"],
    },
]
