"""Компиляция .po → .mo для gettext."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "locales"


def main() -> None:
    for po in LOCALES.rglob("*.po"):
        mo = po.with_suffix(".mo")
        mo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["msgfmt", "-o", str(mo), str(po)],
            check=True,
        )
        print(f"Compiled {po} -> {mo}")


def compile_with_babel() -> None:
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    for po_path in LOCALES.rglob("*.po"):
        with open(po_path, "rb") as f:
            catalog = read_po(f)
        mo_path = po_path.with_suffix(".mo")
        with open(mo_path, "wb") as f:
            write_mo(f, catalog)
        print(f"Compiled {po_path} -> {mo_path}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError:
        compile_with_babel()
