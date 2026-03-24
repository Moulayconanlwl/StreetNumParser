# Street Number Extractor

A rule-based Python script that extracts street/building numbers from multi-column
address data in Excel files. Designed for messy, multinational address datasets
containing formats from AU, UK, FR, US, CA, NZ, BE, CH, TH, HK, and more.

## Accuracy

Validated against 229 labelled rows: **95.6% accuracy (218/229 correct)**.

## Input Format

The script expects an Excel file with at least these three columns:

| Column         | Description                   |
|----------------|-------------------------------|
| `CLIADDLN3_LA` | Primary address line          |
| `CLIADDLN4_LA` | Secondary address line        |
| `CLIADDLN5_LA` | City / postal / tertiary line |

The full address is the concatenation of these three columns.

## Output

Four new columns are appended to the original file:

| Column                 | Description                                              |
|------------------------|----------------------------------------------------------|
| `ExtractedNumber`      | The extracted street/building number                     |
| `ExtractedLineUsed`    | Which source line the number was taken from              |
| `ExtractedConfidence`  | `fort` (high) / `moyen` (medium) / `faible` (low)        |
| `ExtractedKind`        | `plain`, `range`, `suffix`, `slash`, or `spelled`        |

## How It Works

The script processes each row by scanning `CLIADDLN3_LA → CLIADDLN4_LA → CLIADDLN5_LA`
in order, applying the following rules:

### Line-level prefix detection

| Prefix pattern                        | Behaviour                                                  |
|---------------------------------------|------------------------------------------------------------|
| `Level X` alone                       | Skip → check next line                                     |
| `Level X, 85 Castlereagh Street`      | Extract number after comma (`85`)                          |
| `L 22 225 George St` (no comma, has street word) | Return floor token (`22`)               |
| `Level 27 PWC Tower` (no street word) | Skip → next line gives `188 Quay St.`                     |
| `Suite 101, 575-100 Street SW`        | Skip suite prefix, extract from remainder (`575-100`)     |
| `Suite 13.01B, 13th Floor, 34 Jalan` | Scan entire line for number before street word (`34`)      |
| `7th Floor 15-18 LIME STREET`         | Skip ordinal floor, extract range (`15-18`)                |
| `- 31 RUE DE LA FEDERATION`           | Strip leading dash, extract (`31`)                         |
| `CU1-3, Shed 24 Princes Wharf`        | Skip CU prefix, extract from remainder (`24`)              |

### Number format detection (priority order)

| Priority | Pattern                   | Example input               | Extracted  |
|----------|---------------------------|-----------------------------|------------|
| 1        | Asian floor               | `24/F.`                     | `24/F`     |
| 2        | Compound slash+range      | `2922/222-227 Charn Issara` | `2922/222` |
| 3        | Full slash                | `48/15 Soi Rajchadapisek`   | `48/15`    |
| 4        | Range at start            | `42-47 MINORIES`            | `42-47`    |
| 5        | Spaced slash              | `39 / 1`                    | `39`       |
| 6        | Number+letter suffix      | `66a Victoria Road`         | `66a`      |
| 7        | Plain leading number      | `277 Willis Avenue`         | `277`      |
| 8        | `No.` keyword             | `No. 296 Jen Ai Road`       | `296`      |
| 9        | Embedded suffix           | `Jollemanhof 14a`           | `14a`      |
| 10       | Before street keyword     | `Aon Tower 201 Kent Street` | `201`      |
| 11       | Generic embedded fallback | `IBEX HOUSE 42-47 MINORIES` | `42-47`    |
| 12       | Spelled number            | `One Lime Street`           | `1`        |

**Ordinals excluded**: `1st`, `2nd`, `3rd`, `13th`, etc. are never mistaken for
street number suffixes.


## Usage

```bash
python street_extractor.py
```

***
