import pandas as pd
import re

# ── Spelled numbers ────────────────────────────────────────────────────────────
SPELLED_NUMBERS = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'eleven': '11', 'twelve': '12', 'twenty': '20', 'thirty': '30',
    'forty': '40', 'fifty': '50', 'hundred': '100'
}

# ── Street-type keywords (multi-language) ──────────────────────────────────────
STREET_WORDS_PAT = re.compile(
    r'\b(street|st\.?|road|rd\.?|avenue|ave\.?|boulevard|blvd|drive|dr\.?|lane|ln|way|place|'
    r'court|ct|terrace|crescent|close|grove|gardens|park|square|walk|row|gate|hill|bridge|'
    r'jalan|soi|'
    r'strasse|str\.?|straat|laan|gatan|vägen|vagen|allé|allee|torg|'
    r'rue|calle|via|viale|allée|boul\.?|'
    r'quay|wharf|embankment|circus|mews|parkway|pkwy|highway|hwy|broadway|commons|manor|'
    r'trail|path|bend|loop|run|pike|'
    r'minories|houndsditch|bishopsgate|leadenhall|fenchurch|walbrook|'
    r'rajchadapisek|wireless|petchaburi|federation|perouse|cervantes|girouard|kléber|'
    r'lasalle|wacker|peachtree|michigan|market|'
    r'karve|dong|lu|jie|hutong)\b',
    re.IGNORECASE
)

ORDINAL_PAT = re.compile(r'^\d+(?:st|nd|rd|th)\b', re.IGNORECASE)

# ── Noise token patterns ───────────────────────────────────────────────────────

# PO Box token including its number
PO_BOX_TOKEN_PAT = re.compile(
    r',?\s*\b(?:p\.?\s*o\.?\s*box|po\s*box|gpo\s*box|b\.?\s*p\.?\s*|bp\s*|postbus|'
    r'boite\s*postale|boîte\s*postale|apartado|case\s*postale|'
    r'private\s*bag|locked\s*bag|mail\s*stop)\s*\d*\b,?',
    re.IGNORECASE
)

# Floor/Level token: "Level 26", "Floor 3", "Fl. 5", "Lv. 2"
FLOOR_TOKEN_PAT = re.compile(
    r'\b(?:level|floor|fl\.?|lv\.?|étage|etage|verdieping|piso|piano)\s*'
    r'[\d&]+(?:\w*)[\s,]*',
    re.IGNORECASE
)

# Standalone L-prefix floor: "L22", "L 5" not followed by a street word
L_FLOOR_PAT = re.compile(
    r'\bL\s*\d+\b(?!\s*\w*\s*(?:street|road|avenue|blvd|lane|way|place|drive|court|'
    r'rue|calle|via|quay|str|strasse|straat|laan|gatan|vägen))',
    re.IGNORECASE
)

# Suite/Unit token including its identifier
SUITE_TOKEN_PAT = re.compile(
    r'\b(?:suite|ste\.?|unit|apt\.?|room|bureau|ufficio|büro)\s*[\w.\-]+\s*,?\s*',
    re.IGNORECASE
)

# Ordinal floor: "1st Floor", "7th Floor", "29th Floor"
ORDINAL_FLOOR_PAT = re.compile(
    r'\b\d+(?:st|nd|rd|th)\s+(?:floor|fl\.?|level|étage)\b\s*,?\s*',
    re.IGNORECASE
)

# Trailing postal codes (stripped only at end of string)
POSTAL_STRIP_PAT = re.compile(
    r'(?:'
    r'(?<=[A-Za-z]{2}\s)(?:[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})'   # UK after city
    r'|(?<=[A-Za-z]\s)\d{5}(?:-\d{4})?(?=\s*$)'                       # US ZIP at end
    r'|(?<=[A-Za-z]\s)[A-Z]\d[A-Z]\s*\d[A-Z]\d(?=\s*$)'              # CA at end
    r'|\b\d{4}\s*[A-Z]{2}(?=\s*$)'                                     # NL at end
    r'|\b\d{3}-\d{4}(?=\s*$)'                                          # JP at end
    r')',
    re.IGNORECASE
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def has_street_word(text: str) -> bool:
    return bool(STREET_WORDS_PAT.search(text))

def find_num_before_street_word(text: str):
    m = re.search(
        r'\b(\d+(?:\s*[-–]\s*\d+)?[a-zA-Z]?)\s+(?:\w+\s+){0,3}' + STREET_WORDS_PAT.pattern,
        text, re.IGNORECASE
    )
    return m.group(1).strip() if m else None

def extract_no_prefix(text: str):
    m = re.search(r'\bNo\.?\s*(\d+(?:[a-zA-Z])?(?:\s*[-–]\s*\d+)?)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'#\s*(\d{2,}(?:[-–]\d+)?)', text)
    if m:
        return m.group(1).strip()
    return None

def strip_noise(line: str) -> str:
    """
    Remove noise tokens from a line WITHOUT skipping it.
    Strips: Asian floor (24/F), PO Box + number, ordinal floor,
            floor/level + number, L-floor, suite/unit, trailing postal code.
    The street number may still remain after stripping.
    """
    s = line

    # Strip Asian floor notation: 24/F, 15/F, 8/F
    s = re.sub(r'\b\d+/[Ff]\.?\b\s*,?\s*', ' ', s)

    # Strip PO Box segment and its number
    s = PO_BOX_TOKEN_PAT.sub(' ', s)

    # Strip ordinal floor: "7th Floor", "2nd Floor"
    s = ORDINAL_FLOOR_PAT.sub(' ', s)

    # Strip floor/level + number: "Level 26", "Floor 3"
    s = FLOOR_TOKEN_PAT.sub(' ', s)

    # Strip standalone L-floor: "L22", "L 5"
    s = L_FLOOR_PAT.sub(' ', s)

    # Strip suite/unit + identifier: "Suite 500", "Unit 3B"
    s = SUITE_TOKEN_PAT.sub(' ', s)

    # Strip trailing postal code
    s = POSTAL_STRIP_PAT.sub(' ', s)

    # Clean up extra spaces and punctuation
    s = re.sub(r'\s{2,}', ' ', s)
    s = s.strip().strip(',').strip('-').strip()

    return s


# ── Core parser ────────────────────────────────────────────────────────────────

def parse_line(line: str):
    """
    Extract street/building number from a cleaned line.
    Returns (number_str, confidence, kind) or None.

    Priority:
      1. Compound slash+range   2922/222-227 → 2922/222
      2. Full slash number      1/1, 48/15, 87/2
      3. Range at start         42-47, 109-133
      4. Spaced slash           39 / 1 → 39
      5. Number+letter at start 66a, 142B
      6. Plain leading number   277, 24919, 100234
      7. No. / # pattern        No. 296, #09-06
      8. Number+letter embedded Jollemanhof 14a
      9. Number before street keyword  Aon Tower 201 Kent Street
     10. Spelled number         One Lime Street → 1
    """
    line = line.strip().rstrip(' -,').strip()
    if not line or line in ('nan', '-'):
        return None

    # 1. Compound slash+range: "2922/222-227" → "2922/222"
    m = re.match(r'^(\d+/\d+)[-–]\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 2. Full slash number: "1/1", "48/15", "87/2"
    m = re.match(r'^(\d{1,6}/\d{1,6})\b', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 3. Range at start: "42-47", "109 - 133"
    m = re.match(r'^(\d+\s*[-–]\s*\d+)\b', line)
    if m:
        return (m.group(1).strip(), 'fort', 'range')

    # 4. Spaced slash: "39 / 1" → "39"
    m = re.match(r'^(\d+)\s*/\s*\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 5. Number+letter suffix at start (not ordinals): "66a", "142B"
    if not ORDINAL_PAT.match(line):
        m = re.match(r'^(\d+[a-zA-Z])\b', line)
        if m:
            return (m.group(1), 'fort', 'suffix')

    # 6. Plain leading number (any length — 5/6 digit street numbers allowed)
    m = re.match(r'^(\d+)\b', line)
    if m:
        return (m.group(1), 'fort', 'plain')

    # 7. No. / # pattern: "No. 296", "#09-06"
    n = extract_no_prefix(line)
    if n:
        return (n, 'fort', 'no_prefix')

    # 8. Number+letter embedded: "Jollemanhof 14a", "Jerozolimskie 142B"
    m = re.search(r'\b(\d+[a-zA-Z])\b', line)
    if m and not ORDINAL_PAT.match(m.group(1)):
        return (m.group(1), 'moyen', 'suffix_embedded')

    # 9. Number immediately before a street keyword
    n2 = find_num_before_street_word(line)
    if n2:
        return (n2, 'moyen', 'near_street')

    # 10. Spelled number at start: "One Lime Street" → "1"
    fw = line.split()[0].lower() if line.split() else ''
    if fw in SPELLED_NUMBERS:
        return (SPELLED_NUMBERS[fw], 'fort', 'spelled')

    return None


# ── Main extractor ─────────────────────────────────────────────────────────────

def smart_extract(row):
    """
    For each line in LN3 → LN4 → LN5:
      1. Strip noise tokens (Asian floor, PO Box number, floor/level,
         ordinal floor, suite/unit, trailing postal code)
         WITHOUT skipping the line — street number may still be present.
      2. Parse the cleaned line for a street/building number.
      3. Return the first valid result found.
    """
    cols = ['CLIADDLN3_LA', 'CLIADDLN4_LA', 'CLIADDLN5_LA']
    raw_lines = [str(row[c]).strip() for c in cols]

    for raw in raw_lines:
        if not raw or raw in ('nan', '-', ''):
            continue

        # Strip noise but keep the line alive
        cleaned = strip_noise(raw)

        if not cleaned or cleaned in ('nan', '-'):
            continue

        result = parse_line(cleaned)
        if result:
            return pd.Series({
                'ExtractedNumber':     result[0],
                'ExtractedLineUsed':   raw,
                'ExtractedConfidence': result[1],
                'ExtractedKind':       result[2]
            })

    return pd.Series({
        'ExtractedNumber':     '',
        'ExtractedLineUsed':   '',
        'ExtractedConfidence': 'not_found',
        'ExtractedKind':       ''
    })


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    INPUT_FILE  = "exempleAdresse.xlsx"
    OUTPUT_FILE = "addresses_extracted_final.xlsx"

    df = pd.read_excel(INPUT_FILE)

    extracted = df.apply(smart_extract, axis=1)
    df['ExtractedNumber']     = extracted['ExtractedNumber']
    df['ExtractedLineUsed']   = extracted['ExtractedLineUsed']
    df['ExtractedConfidence'] = extracted['ExtractedConfidence']
    df['ExtractedKind']       = extracted['ExtractedKind']

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Done — {OUTPUT_FILE}")
    print(f"Rows:      {len(df)}")
    print(f"Found:     {(df['ExtractedNumber'] != '').sum()}")
    print(f"Not found: {(df['ExtractedNumber'] == '').sum()}")
