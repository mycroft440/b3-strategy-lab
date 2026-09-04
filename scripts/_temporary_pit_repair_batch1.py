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
    "import os\n",
    "import os\nimport re\n",
)
replace_once(
    "b3_strategy_lab/cotahist.py",
    'STANDARD_EQUITY_BDI_CODES = ("02", "05", "06", "07", "08", "09", "11")\n',
    'STANDARD_EQUITY_BDI_CODES = ("02", "05", "06", "07", "08", "09", "11")\n'
    '# BDI 58 (OUTROS) can still carry the same listed ON/PN share while B3 places\n'
    '# the instrument under special trading conditions. It is deliberately kept\n'
    '# separate so its acceptance remains conditional on share metadata below.\n'
    'SPECIAL_COMPANY_EQUITY_BDI_CODES = ("58",)\n'
    'COMPANY_EQUITY_BDI_CODES = STANDARD_EQUITY_BDI_CODES + SPECIAL_COMPANY_EQUITY_BDI_CODES\n'
    '_COMPANY_SHARE_TICKER_RE = re.compile(r"^[A-Z]{4}\\d{1,2}$")\n'
    '_COMPANY_SHARE_SPECIFICATIONS = ("ON", "PN")\n',
)
replace_once(
    "b3_strategy_lab/cotahist.py",
    "    bdi_codes: Iterable[str] = STANDARD_EQUITY_BDI_CODES,\n",
    "    bdi_codes: Iterable[str] = COMPANY_EQUITY_BDI_CODES,\n",
)
replace_once(
    "b3_strategy_lab/cotahist.py",
    "        bdi_code = line[10:12]\n        ticker = line[12:24].strip().upper()\n        market_type = line[24:27]\n        if bdi_code not in selected_bdi or market_type not in selected_markets:\n            continue\n",
    "        bdi_code = line[10:12]\n"
    "        ticker = line[12:24].strip().upper()\n"
    "        market_type = line[24:27]\n"
    "        specification = line[39:49].strip().upper()\n"
    "        if bdi_code not in selected_bdi or market_type not in selected_markets:\n"
    "            continue\n"
    "        # CODBDI 58 is not a blanket equity code. Keep it only when the raw B3\n"
    "        # record is still a standard cash-market ON/PN share with a normal listed\n"
    "        # share ticker. This preserves GOLL4/AZUL4 continuity without admitting\n"
    "        # unrelated instruments that also happen to use the generic BDI 58.\n"
    "        if bdi_code in SPECIAL_COMPANY_EQUITY_BDI_CODES and (\n"
    "            market_type != \"010\"\n"
    "            or not _COMPANY_SHARE_TICKER_RE.fullmatch(ticker)\n"
    "            or not specification.startswith(_COMPANY_SHARE_SPECIFICATIONS)\n"
    "        ):\n"
    "            continue\n",
)
replace_once(
    "b3_strategy_lab/point_in_time.py",
    "from .cotahist import STANDARD_EQUITY_BDI_CODES, parse_cotahist_lines\n",
    "from .cotahist import COMPANY_EQUITY_BDI_CODES, STANDARD_EQUITY_BDI_CODES, parse_cotahist_lines\n",
)
replace_once(
    "b3_strategy_lab/point_in_time.py",
    "STANDARD_BDI_CODES = STANDARD_EQUITY_BDI_CODES\n",
    "# Candidate BDI codes for company shares. BDI 58 is still filtered through\n"
    "# _mask_non_company_equity_records, so only market-010 ON/PN shares survive.\n"
    "STANDARD_BDI_CODES = COMPANY_EQUITY_BDI_CODES\n",
)
