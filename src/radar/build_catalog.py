"""Replay stored PNCP records into a deduplicated searchable catalog."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from radar.relevance import classify, procurement_state, VERSION


def build(source: Path, output: Path, *, collection_date: str | None = None) -> dict:
    records = {}
    total = 0
    collected_dates = []
    with source.open(encoding="utf-8") as stream:
        for line in stream:
            wrapper = json.loads(line)
            if wrapper.get('coletado_em'):
                collected_dates.append(str(wrapper['coletado_em'])[:10])
            row = wrapper.get("registro", wrapper)
            key = row.get("numeroControlePNCP")
            if not key:
                continue
            total += 1
            previous = records.get(key)
            if previous is None or str(row.get("dataAtualizacaoGlobal", "")) >= str(previous.get("dataAtualizacaoGlobal", "")):
                records[key] = row
    candidates, counts = [], Counter()
    for key, row in records.items():
        decision = classify(row.get("objetoCompra") or "", row.get("informacaoComplementar") or "")
        counts[decision["suggestedOffer"]] += 1
        if decision["score"] < 40:
            continue
        org, unit = row.get("orgaoEntidade") or {}, row.get("unidadeOrgao") or {}
        candidates.append({
            "id": key, "organization": org.get("razaoSocial", ""), "state": unit.get("ufSigla", ""),
            "city": unit.get("municipioNome", ""), "modality": row.get("modalidadeNome", ""),
            "publishedAt": row.get("dataPublicacaoPncp", ""), "object": row.get("objetoCompra", ""),
            "additionalInfo": row.get("informacaoComplementar") or "", "estimatedValue": row.get("valorTotalEstimado"),
            "proposalDeadline": row.get("dataEncerramentoProposta") or "", "proposalStart": row.get("dataAberturaProposta") or "",
            "procurementState": procurement_state(row), "statusId": row.get("situacaoCompraId"),
            "instrumentId": row.get("tipoInstrumentoConvocatorioCodigo"),
            "pncpUrl": f"https://pncp.gov.br/app/editais/{org.get('cnpj')}/{row.get('anoCompra')}/{row.get('sequencialCompra')}",
            "sourceUrl": row.get("linkSistemaOrigem") or "", "sourceSystem": row.get("usuarioNome") or "",
            **decision,
        })
    candidates.sort(key=lambda r: (-r["score"], r["proposalDeadline"]))
    dates = [str(r.get('dataPublicacaoPncp'))[:10] for r in records.values() if r.get('dataPublicacaoPncp')]
    catalog = {"generatedAt": datetime.now(timezone.utc).isoformat(), "collectionDate": collection_date or max(collected_dates,default=None), "window": {"start": min(dates,default=''), "end": max(dates,default='')}, "historical": True,
        "rulesVersion": VERSION, "metrics": {"received": total, "unique": len(records), "candidates": len(candidates), "discarded": len(records) - len(candidates), "byOffer": dict(counts)}, "opportunities": candidates}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return catalog["metrics"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("work/phase0/records.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("web/public/catalog.json"))
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output), ensure_ascii=False))
