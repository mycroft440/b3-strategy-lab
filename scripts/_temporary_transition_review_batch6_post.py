from pathlib import Path

path = Path("tests/test_instrument_transition_layer.py")
text = path.read_text(encoding="utf-8")
if "import math\n" not in text:
    anchor = "import unittest\n"
    if anchor not in text:
        raise SystemExit("unittest import anchor missing")
    text = text.replace(anchor, "import math\nimport unittest\n", 1)
    path.write_text(text, encoding="utf-8")
