from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "b3_strategy_lab/cotahist.py",
    'STANDARD_EQUITY_BDI_CODES = ("02", "05", "06", "07", "08", "09", "11")\n',
    'STANDARD_EQUITY_BDI_CODES = ("02", "05", "06", "07", "08", "09", "11")\n'
    '# BDI 58 (OUTROS) can still carry the same listed ON/PN share while B3 places\n'
    '# the instrument under special trading conditions. It is deliberately kept\n'
    '# separate from the standard set so callers must opt into company-equity\n'
    '# metadata filtering instead of accepting every BDI 58 record blindly.\n'
    'SPECIAL_COMPANY_EQUITY_BDI_CODES = ("58",)\n'
    'COMPANY_EQUITY_BDI_CODES = STANDARD_EQUITY_BDI_CODES + SPECIAL_COMPANY_EQUITY_BDI_CODES\n',
)
replace_once(
    "b3_strategy_lab/point_in_time.py",
    "from .cotahist import STANDARD_EQUITY_BDI_CODES, parse_cotahist_lines\n",
    "from .cotahist import COMPANY_EQUITY_BDI_CODES, STANDARD_EQUITY_BDI_CODES, parse_cotahist_lines\n",
)
replace_once(
    "b3_strategy_lab/point_in_time.py",
    "STANDARD_BDI_CODES = STANDARD_EQUITY_BDI_CODES\n",
    "# Candidate BDI codes for company shares. BDI 58 is admitted only through\n"
    "# _mask_non_company_equity_records, which still requires market 010, a valid\n"
    "# listed-share ticker and ON/PN specification.\n"
    "STANDARD_BDI_CODES = COMPANY_EQUITY_BDI_CODES\n",
)
replace_once(
    "scripts/sync_official_universe.py",
    "    base_fractional_ticker,\n    read_fractional_cotahist,\n",
    "    base_fractional_ticker,\n    read_fractional_cotahist,\n    read_standard_company_equity_cotahist,\n",
)
replace_once(
    "scripts/sync_official_universe.py",
    '        quotes = [quote for quote in read_cotahist(archive, tickers=tickers) if quote.date < exclude_date and (end_date is None or quote.date <= end_date)]\n',
    '        quotes = [\n'
    '            quote\n'
    '            for quote in read_standard_company_equity_cotahist(archive)\n'
    '            if quote.ticker in tickers\n'
    '            and quote.date < exclude_date\n'
    '            and (end_date is None or quote.date <= end_date)\n'
    '        ]\n',
)
