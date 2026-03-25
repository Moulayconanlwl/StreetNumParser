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
    r'karve|'
    r'dong|lu|jie|hutong)\b',
    re.IGNORECASE
)

ORDINAL_PAT = re.compile(r'^\d+(?:st|nd|rd|th)\b', re.IGNORECASE)

# ── PO Box / BP in all variants ────────────────────────────────────────────────
PO_BOX_PAT = re.compile(
    r'\b(?:p\.?\s*o\.?\s*box|po\s*box|gpo\s*box|b\.?\s*p\.?(?:\s+\d)|bp\s+\d|postbus|'
    r'boite\s*postale|boîte\s*postale|apartado|case\s*postale|'
    r'private\s*bag|locked\s*bag|mail\s*stop)\b',
    re.IGNORECASE
)

# Floor-only lines with nothing after
FLOOR_ONLY_PAT = re.compile(
    r'^(?:L|Level|Floor|Fl\.?|Lv\.?|F\.?)\s+[\w&]+\s*$',
    re.IGNORECASE
)

# Suite/Unit prefix
SUITE_PAT = re.compile(
    r'^(?:suite|ste\.?|unit|apt\.?|room|bureau|ufficio|büro)\b',
    re.IGNORECASE
)

# Postal code patterns for stripping trailing codes
POSTAL_CODE_PAT = re.compile(
    r'\b('
    r'[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}|'   # UK: EC3M 4BS
    r'\d{5}(?:-\d{4})?|'                          # US ZIP: 60603
    r'[A-Z]\d[A-Z]\s*\d[A-Z]\d|'                 # CA: M5H 3S1
    r'\d{4}\s*[A-Z]{2}|'                          # NL: 3063 ED
    r'\d{4,5}|'                                   # FR/DE/BE/NO/AU/NZ
    r'[A-Z]\d{4}[A-Z]{3}|'                        # IE
    r'\d{3}-\d{4}'                                # JP
    r')\b',
    re.IGNORECASE
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_po_box(line: str) -> bool:
    return bool(PO_BOX_PAT.search(line))

def has_street_word(text: str) -> bool:
    return bool(STREET_WORDS_PAT.search(text))

def strip_postal_suffix(text: str) -> str:
    """Remove trailing postal code + city noise from a line."""
    cleaned = re.sub(
        r'\s+(?:[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}|[A-Z]\d[A-Z]\s*\d[A-Z]\d|\d{4,5}(?:\s+[A-Z]{2})?'
        r'|\d{4}\s*[A-Z]{2})[^\d]*$',
        '', text, flags=re.IGNORECASE
    ).strip().rstrip(' -,').strip()
    return cleaned if cleaned else text

def find_num_before_street_word(text: str):
    """Return the number token immediately before a street keyword."""
    m = re.search(
        r'\b(\d+(?:\s*[-–]\s*\d+)?[a-zA-Z]?)\s+(?:\w+\s+){0,3}' + STREET_WORDS_PAT.pattern,
        text, re.IGNORECASE
    )
    return m.group(1).strip() if m else None

def extract_no_prefix(text: str):
    """Handle 'No. 296', 'No 16', '#09-06' style patterns."""
    m = re.search(r'\bNo\.?\s*(\d+(?:[a-zA-Z])?(?:\s*[-–]\s*\d+)?)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'#\s*(\d{2,}(?:[-–]\d+)?)', text)
    if m:
        return m.group(1).strip()
    return None


# ── Core parser ────────────────────────────────────────────────────────────────

def parse_line(line: str):
    """
    Extract street/building number from a single cleaned line.
    Returns (number_str, confidence, kind) or None.

    Priority:
      1. Asian floor notation  24/F
      2. Compound slash+range  2922/222-227 → 2922/222
      3. Full slash number     1/1, 48/15
      4. Range at start        42-47, 109 - 133
      5. Spaced slash          39 / 1 → 39
      6. Number+letter at start  66a, 142B
      7. Plain leading number  277
      8. No. / # pattern       No. 296, #09-06
      9. Number+letter embedded  Jollemanhof 14a
     10. Number before street keyword  Aon Tower 201 Kent Street
     11. Spelled number        One Lime Street → 1
    """
    line = line.strip().rstrip(' -,').strip()
    if not line or line in ('nan', '-'):
        return None

    # 1. Asian floor notation
    if re.match(r'^\d+/[Ff]\.?\b', line):
        m = re.match(r'^(\d+)/[Ff]', line)
        return (m.group(1) + '/F', 'fort', 'floor_asian')

    # 2. Compound slash+range
    m = re.match(r'^(\d+/\d+)[-–]\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 3. Full slash number
    m = re.match(r'^(\d{1,5}/\d{1,5})\b', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 4. Range at start
    m = re.match(r'^(\d+\s*[-–]\s*\d+)\b', line)
    if m:
        return (m.group(1).strip(), 'fort', 'range')

    # 5. Spaced slash
    m = re.match(r'^(\d+)\s*/\s*\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 6. Number+letter suffix at start (not ordinals)
    if not ORDINAL_PAT.match(line):
        m = re.match(r'^(\d+[a-zA-Z])\b', line)
        if m:
            return (m.group(1), 'fort', 'suffix')

    # 7. Plain leading number
    m = re.match(r'^(\d+)\b', line)
    if m:
        return (m.group(1), 'fort', 'plain')

    # 8. No. / # pattern
    n = extract_no_prefix(line)
    if n:
        return (n, 'fort', 'no_prefix')

    # 9. Number+letter embedded
    m = re.search(r'\b(\d+[a-zA-Z])\b', line)
    if m and not ORDINAL_PAT.match(m.group(1)):
        return (m.group(1), 'moyen', 'suffix_embedded')

    # 10. Number before street keyword
    n2 = find_num_before_street_word(line)
    if n2:
        return (n2, 'moyen', 'near_street')

    # 11. Spelled number at start
    fw = line.split()[0].lower() if line.split() else ''
    if fw in SPELLED_NUMBERS:
        return (SPELLED_NUMBERS[fw], 'fort', 'spelled')

    return None


# ── Line pre-processor ─────────────────────────────────────────────────────────

def preprocess_line(line: str):
    """
    Returns cleaned string to parse, or None if line should be skipped.
    Handles: PO Box, floor-only, postal-only, Level/Floor prefix,
             Suite/Unit prefix, CU prefix, leading dash, Ground Floor prefix.
    """
    c = line.strip().rstrip(' -,').strip()
    if not c or c in ('nan', '-'):
        return None

    # Skip PO Box lines
    if is_po_box(c):
        return None

    # Skip lines that are purely a postal code
    if POSTAL_CODE_PAT.fullmatch(c.strip()):
        return None

    # Skip pure floor-only lines
    if FLOOR_ONLY_PAT.match(c):
        return None

    # Level / Floor / L prefix
    lev_m = re.match(
        r'^(?:L|Level|Floor|Fl\.?|Lv\.?)\s+(\w[\w&]*)\s*(.*)',
        c, re.IGNORECASE
    )
    if lev_m:
        remainder = lev_m.group(2).strip().lstrip(',').strip()
        if not remainder:
            return None
        if ',' in c:
            after = re.split(r',', c, maxsplit=1)[1].strip()
            return after if after else None
        if has_street_word(remainder):
            return remainder
        return None  # e.g. "Level 27 PWC Tower" — building name only, skip

    # Nth-floor prefix: "7th Floor, 15-18 Lime Street"
    nth_floor = re.match(r'^\w+\s+(?:floor|fl\.?)\s*,?\s*(.+)', c, re.IGNORECASE)
    if nth_floor:
        after = nth_floor.group(1).strip()
        if after:
            return after

    # Suite / Unit prefix
    if SUITE_PAT.match(c):
        if ',' in c:
            after = re.split(r',', c, maxsplit=1)[1].strip()
            if re.match(r'^\d', after) or has_street_word(after):
                return after
        n = find_num_before_street_word(c)
        if n:
            return c
        return None

    # CU/unit abbreviated: "CU1–3, Shed 24 Princes Wharf"
    cu_m = re.match(r'^(?:CU|unit)[\w–-]+\s*,\s*(.+)', c, re.IGNORECASE)
    if cu_m:
        return cu_m.group(1).strip()

    # Leading dash: "- 31 RUE DE LA FEDERATION"
    dash_m = re.match(r'^-\s*(.+)', c)
    if dash_m:
        return dash_m.group(1).strip()

    # Ground Floor / Basement prefix
    gf_m = re.match(
        r'^(?:ground|basement|mezzanine|reception|rez[- ]de[- ]chaussée?)\s+(?:floor\s+)?[-–]?\s*(.+)',
        c, re.IGNORECASE
    )
    if gf_m:
        return gf_m.group(1).strip()

    return c


# ── Main extractor ─────────────────────────────────────────────────────────────

def smart_extract(row):
    """
    Tries CLIADDLN3_LA → CLIADDLN4_LA → CLIADDLN5_LA in order.
    For each line: pre-process → strip postal suffix → parse.
    Returns pd.Series: ExtractedNumber, ExtractedLineUsed, ExtractedConfidence, ExtractedKind.
    """
    cols = ['CLIADDLN3_LA', 'CLIADDLN4_LA', 'CLIADDLN5_LA']
    raw_lines = [str(row[c]).strip() for c in cols]

    for raw in raw_lines:
        prep = preprocess_line(raw)
        if prep is None:
            continue

        clean = strip_postal_suffix(prep)
        if not clean:
            clean = prep

        result = parse_line(clean)
        if result:
            # Reject if extracted number is 5–6 pure digits (postal code leak)
            num = result[0].replace(' ', '').replace('-', '')
            if re.fullmatch(r'\d{5,6}', num):
                continue
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
    print(f"Rows: {len(df)}")
    print(f"Found:     {(df['ExtractedNumber'] != '').sum()}")
    print(f"Not found: {(df['ExtractedNumber'] == '').sum()}")
