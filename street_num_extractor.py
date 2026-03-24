import pandas as pd
import re

# ── Configuration ─────────────────────────────────────────────────────────────

SPELLED_NUMBERS = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'eleven': '11', 'twelve': '12', 'twenty': '20', 'thirty': '30',
    'forty': '40', 'fifty': '50', 'hundred': '100'
}

STREET_WORDS_PAT = re.compile(
    r'\b(street|st\.?|road|rd\.?|avenue|ave\.?|boulevard|blvd|drive|dr\.?|lane|ln|way|place|'
    r'court|ct|terrace|crescent|close|grove|gardens|park|square|walk|row|gate|hill|bridge|'
    r'jalan|soi|strasse|str\.?|allée|allee|rue|calle|via|viale|laan|straat|gatan|vägen|vagen|'
    r'quay|wharf|embankment|circus|mews|parkway|pkwy|highway|hwy|broadway|commons|manor|'
    r'trail|path|bend|loop|run|pike|minories|houndsditch|bishopsgate|leadenhall|fenchurch|'
    r'rajchadapisek|wireless|petchaburi|federation|perouse|cervantes|girouard|kléber)\b',
    re.IGNORECASE
)

ORDINAL_PAT = re.compile(r'^\d+(?:st|nd|rd|th)\b', re.IGNORECASE)

# ── Helper functions ──────────────────────────────────────────────────────────

def has_street_word(text):
    """Return True if text contains a recognisable street-type keyword."""
    return bool(STREET_WORDS_PAT.search(text))


def find_num_before_street_word(text):
    """
    Return the number token that appears immediately before a street keyword.
    E.g. 'Aon Tower 201 Kent Street' → '201'
         '34 Jalan Sultan Ismail'    → '34'
    """
    m = re.search(
        r'\b(\d+(?:\s*[-–]\s*\d+)?[a-zA-Z]?)\s+(?:\w+\s+){0,3}' + STREET_WORDS_PAT.pattern,
        text, re.IGNORECASE
    )
    return m.group(1).strip() if m else None


def extract_from_city_postal(line):
    """
    Last-resort: pull a trailing 3–5 digit number from a city+postal line.
    E.g. 'GAUTENG 2193' → '2193',  '-7530' → '7530'
    """
    line = line.strip().lstrip('-').strip()
    m = re.search(r'(\d{3,5})\s*$', line)
    if m:
        return (m.group(1), 'faible', 'plain')
    return None


def parse_line(line):
    """
    Extract a street number from a single, already-cleaned address line.

    Priority order:
      1.  Asian floor notation   24/F, 8/F
      2.  Compound slash+range   2922/222-227  → 2922/222
      3.  Full slash number      1/1, 48/15, 87/2, 6/14
      4.  Range at start         42-47, 27 - 37, 575- 100
      5.  Spaced slash           39 / 1  → 39
      6.  Number+letter suffix   66a, 142B  (excluding ordinals 1st/2nd/3rd/Nth)
      7.  Plain leading number   277, 1174
      8.  No. X pattern          No. 296
      9.  Embedded suffix        Jollemanhof 14a
      10. Number before street keyword  (Aon Tower 201 Kent Street → 201)
      11. Generic embedded number
      12. Spelled number         One Lime Street → 1

    Returns (number_str, confidence, kind) or None.
    """
    line = line.strip().rstrip(' -')
    if not line or line in ('nan', '-'):
        return None

    # 1. Asian floor notation: "24/F.", "8/F"
    if re.match(r'^\d+/[Ff]\.?\b', line):
        m = re.match(r'^(\d+)/[Ff]', line)
        return (m.group(1) + '/F', 'fort', 'slash')

    # 2. Compound slash+range: "2922/222-227" → "2922/222"
    m = re.match(r'^(\d+/\d+)[-–]\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 3. Full slash number: "1/1", "48/15", "87/2", "6/14"
    m = re.match(r'^(\d+/\d+)\b', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 4. Range at start: "42-47", "27 - 37", "575- 100", "31-35"
    m = re.match(r'^(\d+\s*[-–]\s*\d+)\b', line)
    if m:
        return (m.group(1).strip(), 'fort', 'range')

    # 5. Spaced slash "39 / 1" → left number only
    m = re.match(r'^(\d+)\s*/\s*\d+', line)
    if m:
        return (m.group(1), 'fort', 'slash')

    # 6. Number+letter suffix at START — but exclude ordinals (1st, 2nd, 13th…)
    if not ORDINAL_PAT.match(line):
        m = re.match(r'^(\d+[a-zA-Z])\b', line)
        if m:
            return (m.group(1), 'fort', 'suffix')

    # 7. Plain leading number
    m = re.match(r'^(\d+)\b', line)
    if m:
        return (m.group(1), 'fort', 'plain')

    # 8. "No. 53" or "No.288"
    m = re.search(r'\bNo\.?\s*(\d+)', line, re.IGNORECASE)
    if m:
        return (m.group(1), 'fort', 'plain')

    # 9. Number+letter EMBEDDED (not at start): "Jollemanhof 14a", "Jerozolimskie 142B"
    m = re.search(r'\b(\d+[a-zA-Z])\b', line)
    if m and not ORDINAL_PAT.match(m.group(1)):
        return (m.group(1), 'fort', 'suffix')

    # 10. Number immediately before a street keyword
    n = find_num_before_street_word(line)
    if n:
        return (n, 'moyen', 'plain')

    # 11. Generic embedded number (fallback)
    m = re.search(r'\b(\d+(?:\s*[-–]\s*\d+)?)\b', line)
    if m:
        raw = m.group(1)
        if re.search(r'[-–]', raw):
            return (raw.strip(), 'faible', 'range')
        return (raw, 'faible', 'plain')

    # 12. Spelled-out number at start
    fw = line.split()[0].lower() if line.split() else ''
    if fw in SPELLED_NUMBERS:
        return (SPELLED_NUMBERS[fw], 'fort', 'spelled')

    return None


# ── Main extraction logic ─────────────────────────────────────────────────────

def smart_extract(row):
    """
    Try CLIADDLN3_LA → CLIADDLN4_LA → CLIADDLN5_LA in order.
    Handles Level/Floor, Suite/Unit, ordinal-floor, leading-dash, and
    city+postal fallback patterns.

    Returns a pd.Series with columns:
        ExtractedNumber, ExtractedLineUsed, ExtractedConfidence, ExtractedKind
    """
    lines = [str(row[c]).strip() for c in ['CLIADDLN3_LA', 'CLIADDLN4_LA', 'CLIADDLN5_LA']]

    for line in lines:
        if not line or line in ('nan', '-', ''):
            continue
        clean = line.rstrip(' -').strip()
        if not clean or clean in ('nan', '-'):
            continue

        # ── Level / L / Floor prefix ─────────────────────────────────────────
        lev_match = re.match(
            r'^(?:L|Level|Floor|Fl\.?|Lv\.?)\s+(\w[\w&]*)\s*(.*)',
            clean, re.IGNORECASE
        )
        if lev_match:
            floor_token = lev_match.group(1)   # e.g. "22", "5&6", "29", "27"
            remainder   = lev_match.group(2).strip().lstrip(',').strip()

            # Pure level line with nothing after → skip, fall through to next line
            if not remainder:
                continue

            # Comma present → street number lives after the comma
            if ',' in clean:
                after_comma = re.split(r',', clean, maxsplit=1)[1].strip()
                result = parse_line(after_comma)
                if result:
                    return pd.Series({
                        'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                        'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
                    })
                # After comma had no number → fall back to the floor token digit
                fm = re.match(r'^(\d+)', floor_token)
                if fm:
                    return pd.Series({
                        'ExtractedNumber': fm.group(1), 'ExtractedLineUsed': line,
                        'ExtractedConfidence': 'fort', 'ExtractedKind': 'plain'
                    })
                continue

            # No comma: if remainder contains a street word → floor token IS the number
            # (e.g. "L 22 225 George St" → 22 ;  "Level 29 Aon Tower 201 Kent Street" → 29)
            if has_street_word(remainder):
                fm = re.match(r'^(\d+)', floor_token)
                if fm:
                    return pd.Series({
                        'ExtractedNumber': fm.group(1), 'ExtractedLineUsed': line,
                        'ExtractedConfidence': 'fort', 'ExtractedKind': 'plain'
                    })

            # No street word in remainder → pure building name, skip to next line
            continue

        # ── Suite / Unit prefix ──────────────────────────────────────────────
        m = re.match(
            r'^(?:suite|ste\.?|unit|apt\.?|room)\s+[\w.]+\s*,\s*(.+)',
            clean, re.IGNORECASE
        )
        if m:
            result = parse_line(m.group(1).strip())
            if result:
                return pd.Series({
                    'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                    'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
                })

        # Multi-segment suite: "Suite 13.01B, 13th Floor, Central Plaza, 34 Jalan Sultan"
        if re.match(r'^(?:suite|ste\.?)', clean, re.IGNORECASE):
            n = find_num_before_street_word(clean)
            if n:
                return pd.Series({
                    'ExtractedNumber': n, 'ExtractedLineUsed': line,
                    'ExtractedConfidence': 'fort', 'ExtractedKind': 'plain'
                })

        # ── CU / unit abbreviated prefix ─────────────────────────────────────
        m = re.match(r'^(?:CU|unit)[\w–-]+\s*,\s*(.+)', clean, re.IGNORECASE)
        if m:
            result = parse_line(m.group(1).strip())
            if result:
                return pd.Series({
                    'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                    'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
                })

        # ── Nth Floor prefix (e.g. "7th Floor 15-18 LIME STREET") ───────────
        m = re.match(r'^\w+\s+(?:floor|fl\.?)\s*,?\s*(.+)', clean, re.IGNORECASE)
        if m:
            result = parse_line(m.group(1).strip())
            if result:
                return pd.Series({
                    'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                    'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
                })

        # ── Leading dash (e.g. "- 31 RUE DE LA FEDERATION") ─────────────────
        m = re.match(r'^-\s*(.+)', clean)
        if m:
            result = parse_line(m.group(1).strip())
            if result:
                return pd.Series({
                    'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                    'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
                })

        # ── Standard parse ────────────────────────────────────────────────────
        result = parse_line(clean)
        if result:
            return pd.Series({
                'ExtractedNumber': result[0], 'ExtractedLineUsed': line,
                'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
            })

    # ── Last resort: extract number from city+postal in LN5 ──────────────────
    # Handles cases like "-" / "GAUTENG 2193" or "-" / "-7530"
    ln5 = str(row['CLIADDLN5_LA']).strip().lstrip('-').strip()
    if ln5 and ln5 not in ('nan', ''):
        result = extract_from_city_postal(ln5)
        if result:
            return pd.Series({
                'ExtractedNumber': result[0], 'ExtractedLineUsed': ln5,
                'ExtractedConfidence': result[1], 'ExtractedKind': result[2]
            })

    return pd.Series({
        'ExtractedNumber': '', 'ExtractedLineUsed': '',
        'ExtractedConfidence': 'not_found', 'ExtractedKind': ''
    })


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    INPUT_FILE  = "exempleAdresse.xlsx"
    OUTPUT_FILE = "addresses_extracted_final2.xlsx"

    df = pd.read_excel(INPUT_FILE)

    extracted = df.apply(smart_extract, axis=1)
    df['ExtractedNumber']      = extracted['ExtractedNumber']
    df['ExtractedLineUsed']    = extracted['ExtractedLineUsed']
    df['ExtractedConfidence']  = extracted['ExtractedConfidence']
    df['ExtractedKind']        = extracted['ExtractedKind']

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Done. Results saved to {OUTPUT_FILE}")
    print(f"Rows processed: {len(df)}")
    print(f"Numbers extracted: {(df['ExtractedNumber'] != '').sum()}")
    print(f"Not found: {(df['ExtractedNumber'] == '').sum()}")
