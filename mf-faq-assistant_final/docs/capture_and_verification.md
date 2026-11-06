# How sources were captured and verified (4 Nov 2026)

## Why a browser was used

The development network's proxy blocked hdfcfund.com, files.hdfcfund.com, sebi.gov.in and amfiindia.com.
Instead of using third-party copies, every source was opened in a normal browser and read there.

## Steps

1. **Scheme pages (S01-S04).** Opened each Direct-plan page on hdfcfund.com. Values (exit load, TER Direct/Regular,
   minimum SIP, riskometer, benchmark, lock-in) were read from the page's embedded scheme data (`__NEXT_DATA__`), not
   from search snippets.
2. **PDFs (S05-S14, S16, S22).** Loaded SEBI's own pdf.js on sebi.gov.in and extracted text from each official PDF
   (HDFC's file server allows cross-origin reads). Page counts and server last-modified dates were recorded.
3. **TER report (S18).** Unzipped the official XLSX in the browser and read the daily Regular/Direct TER for the four
   schemes. All eight values on 31 Oct 2026 match the scheme pages.
4. **HTML pages (S15, S17, S19-S21).** Read the rendered page text.
5. **Storing.** Short verbatim excerpts were saved to `data/raw/captures.json`. PDF excerpts are normalized for spacing only.

## Verification

After `captures.json` was written, every excerpt was checked against the live source again, in the browser:

| Sources | Check | Result |
|---|---|---|
| S01-S04 scheme pages | Every stored field compared with `__NEXT_DATA__` (TER, SIP and riskometer exact; text fields as substrings) | All match |
| S02 page definitions | TER, lock-in and benchmark definitions found in page | All match |
| S05-S14, S16 PDFs | Every excerpt found in the extracted text | All match |
| S22 SEBI circular | 1 excerpt exact; the six-levels excerpt matches only with whitespace removed, because pdf.js splits words ("level s", "R isk") | Match (spacing only) |
| S17, S19-S21 | Every excerpt found in the page HTML | All match, except one SMS-format line in S19 whose angle brackets broke the automated check; confirmed manually in the rendered page |
| S15 | Not in the server HTML (rendered client-side); confirmed in the rendered page text | Match |

## Limitations

- Minimum lump-sum amounts come from the KIMs dated 21 Nov 2025; later addenda, if any, were not checked.
- SIDs (72-74 pages) were only partially ingested (cover description). The assistant links to them for detailed rules.
- Scheme-page TER has no date of its own; the TER report confirms it for 31 Oct 2026 only.
