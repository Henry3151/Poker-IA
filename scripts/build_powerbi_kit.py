"""Build derived Power BI kit files from powerbi/measures.dax (single source of truth).

Writes powerbi/measures_dax_query_view.dax: a DEFINE block for Power BI Desktop's
"DAX query view" -> CodeLens "Update model: Add new measures" (requires a table named _Medidas).

    python scripts/build_powerbi_kit.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "powerbi/measures.dax"
OUT = ROOT / "powerbi/measures_dax_query_view.dax"
FORMATS = {"%": "0.0%", "ROI": "0.0%", "Taxa": "0.0%"}


def parse(text: str) -> list[tuple[str, str]]:
    measures: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        code = re.sub(r"\s+--.*$", "", line).rstrip()
        if not code or code.lstrip().startswith("--"):
            continue
        if not line[0].isspace() and (" = " in code or code.endswith(" =")):
            name, expr = (code[:-2], "") if code.endswith(" =") else code.split(" = ", 1)
            measures.append((name.strip(), [expr] if expr else []))
        elif measures and line[0].isspace():
            measures[-1][1].append(code)
        else:
            raise ValueError(f"unparsed line: {line!r}")
    return [(n, "\n".join(e).strip()) for n, e in measures]


def main() -> None:
    ms = parse(SRC.read_text(encoding="utf-8"))
    names = [n for n, _ in ms]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate measure names")
    lines = ["// Gerado por scripts/build_powerbi_kit.py a partir de powerbi/measures.dax — não edite à mão.",
             "// Power BI Desktop > Exibição de consulta DAX > cole tudo > clique em 'Atualizar modelo: Adicionar novas medidas'.",
             "// Pré-requisito: uma tabela chamada _Medidas (Página Inicial > Inserir dados > tabela vazia > nome _Medidas).",
             "DEFINE"]
    for name, expr in ms:
        body = expr.replace("\n", "\n        ")
        lines.append(f"    MEASURE '_Medidas'[{name}] =\n        {body}")
    lines += ["", "EVALUATE", "    ROW ( \"Medidas definidas\", " + str(len(ms)) + " )", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(ms)} medidas -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
