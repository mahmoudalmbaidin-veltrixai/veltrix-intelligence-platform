# Arabic and Unicode Export Report

The rendering pipeline now wraps logical text before Arabic shaping and Unicode bidirectional reordering. PDF uses registered DejaVu Sans/DejaVu Sans Bold when available, with a production-safe Arial fallback on Windows; PNG uses the same resolved TrueType family.

Verified fixture combinations include Arabic only, English only, Arabic-English, Arabic with Western/Arabic numerals, English-Arabic, long bilingual category labels, narrow content cards, table headers/cells, titles, legends, notes, punctuation, and filters.

Visual findings after correction:

- complete Arabic halves of bilingual chart labels are visible;
- Arabic glyphs are connected and ordered correctly;
- mixed text wraps by words rather than truncating a shaped run;
- titles, legends, tables, notes, PDF, PNG, and attachment-bound artifacts retain Unicode;
- no tofu glyphs or clipped inspected lines were found in the final 20-page PDF.

The canonical JSON/CSV use UTF-8 (`utf-8-sig` for CSV interoperability), so the machine-readable representation remains lossless even where a static channel cannot express interaction behavior.
