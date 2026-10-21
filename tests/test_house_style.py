"""House style: no em or en dashes in the library source.

dome-core text reaches the model in every tool (the schema hint in
ClaudeProvider.generate_structured), and a dash there nudges the model into
writing dashes users then read. The tools strip any that still come back.
"""

from pathlib import Path

EM = "\N{EM DASH}"
EN = "\N{EN DASH}"

SRC = Path(__file__).resolve().parents[1] / "src"


def test_no_dashes_in_library_source() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in sorted(SRC.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if EM in line or EN in line
    ]
    assert not offenders, "Em or en dash found (house style):\n" + "\n".join(offenders)
