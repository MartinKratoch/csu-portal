#!/usr/bin/env python3
"""
update_data.py
Stáhne aktuální data o inflaci z ČSÚ DataStat API a aktualizuje
záložní (fallback) konstanty v index.html.

Spouštěno automaticky GitHub Actions každý pátek v 6:00 UTC.
Lze spustit i ručně: python update_data.py
"""

import re
import csv
import io
import sys
import urllib.request
from datetime import datetime

API_URL = "https://data.csu.gov.cz/api/dotaz/v1/data/vybery/CRUHVD1T2?format=CSV"
HTML_FILE = "index.html"

FIXED_HISTORICAL = {
    1990: 9.7,
    1991: 56.6,
    1992: 11.1,
}


def fetch_data():
    """Stáhne CSV z ČSÚ DataStat API a vrátí slovník {rok: inflace}."""
    print("[{}] Stahuji data z CSU API...".format(datetime.now().strftime('%Y-%m-%d %H:%M')))
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; inflace-updater/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8-sig")
    except Exception as e:
        print("  CHYBA pri stahovani: {}".format(e), file=sys.stderr)
        return {}

    print("  Odpoved API ({} znaku), prvni radky:".format(len(raw)))
    for line in raw.splitlines()[:4]:
        print("    {}".format(repr(line)))

    data = {}
    current_year = datetime.now().year

    for sep in (",", ";", "\t"):
        reader = csv.reader(io.StringIO(raw), delimiter=sep)
        rows = list(reader)
        if len(rows) < 2:
            continue
        for row in rows[1:]:
            clean = [c.strip().strip('"').strip("'").replace(",", ".") for c in row]
            for i in range(len(clean) - 1):
                try:
                    year = int(clean[i])
                    value = float(clean[i + 1])
                    if 1993 <= year <= current_year and -5.0 <= value <= 100.0:
                        data[year] = round(value, 1)
                except ValueError:
                    continue
        if data:
            break

    if data:
        print("  Nacteno {} let z CSU API ({} - {}).".format(len(data), min(data), max(data)))
    else:
        print("  VAROVANI: Z API nebyla nactena zadna data.", file=sys.stderr)
        print("  Cela odpoved:\n{}".format(raw[:800]), file=sys.stderr)

    return data


def build_raw_block(api_data):
    """Sestaví JavaScript blok const RAW = { ... }."""
    combined = {}
    combined.update(FIXED_HISTORICAL)
    combined.update(api_data)
    lines = []
    max_year = max(combined.keys())
    for year in sorted(combined.keys()):
        value = combined[year]
        comment = ""
        if year == 1990:
            comment = "  // CSFR / CSU hist. publikace"
        elif year == 1991:
            comment = "  // CSFR - liberalizace cen"
        elif year == 1992:
            comment = "  // CSFR / CSU hist. publikace"
        elif year == max_year:
            comment = "  // CSU, aktualizovano {}".format(datetime.now().strftime('%d. %m. %Y'))
        lines.append("  {}: {:>5},{}".format(year, value, comment))
    return "const RAW = {\n" + "\n".join(lines) + "\n};"


def update_html(new_raw_block):
    """Nahradí blok const RAW = { ... } v index.html novým blokem."""
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    pattern = r"const RAW = \{[^}]+\};"
    if not re.search(pattern, html, re.DOTALL):
        print("  CHYBA: Blok 'const RAW' nebyl v index.html nalezen.", file=sys.stderr)
        return False

    new_html = re.sub(pattern, new_raw_block, html, count=1, flags=re.DOTALL)

    if new_html == html:
        print("  Zadna zmena dat - soubor nebyl prepsan.")
        return False

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("  index.html aktualizovan.")
    return True


if __name__ == "__main__":
    api_data = fetch_data()

    if not api_data:
        print("Zadna data z API - aktualizace preskocena.")
        print("Stranka zustava nezmenena, fallback data v HTML jsou stale platna.")
        sys.exit(0)  # exit 0 = workflow nespadne

    new_block = build_raw_block(api_data)
    update_html(new_block)
    sys.exit(0)
