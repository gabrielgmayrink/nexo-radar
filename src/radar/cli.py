"""Comandos para execução local do spike."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from radar.collector import collect_phase0
from radar.contract import contract_snapshot, fetch_openapi
from radar.report import render_markdown


def main() -> None:
    parser = argparse.ArgumentParser(prog="radar", description="Spike de coleta do PNCP")
    sub = parser.add_subparsers(dest="command", required=True)
    phase0 = sub.add_parser("fase0", help="coleta publicações dos últimos dias e retrato de abertas")
    phase0.add_argument("--dias", type=int, default=30)
    phase0.add_argument("--fim", type=date.fromisoformat, default=date.today())
    phase0.add_argument("--saida", type=Path, default=Path("work/phase0"))
    phase0.add_argument("--sem-registros", action="store_true", help="não gravar resposta integral em JSONL")
    contract = sub.add_parser("contrato-api", help="salva o contrato OpenAPI atual do PNCP")
    contract.add_argument("--saida", type=Path, default=Path("outputs/contrato-pncp.json"))
    args = parser.parse_args()

    if args.command == "contrato-api":
        result = contract_snapshot(fetch_openapi())
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    result = collect_phase0(
        days=args.dias, end_date=args.fim, output_dir=args.saida,
        save_records=not args.sem_registros,
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    report_path = args.saida / "metrics.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_json = Path("outputs/fase0-pncp-metrics.json")
    public_md = Path("outputs/fase0-pncp-report.md")
    public_json.parent.mkdir(parents=True, exist_ok=True)
    public_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_md.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Relatório salvo em {report_path}")


if __name__ == "__main__":
    main()
