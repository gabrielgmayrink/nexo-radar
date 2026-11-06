"""Orquestra o spike de publicações (30 dias) e propostas atualmente abertas."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

from radar.pncp import (
    PAGE_SIZE,
    PUBLICATION_MODALITIES,
    CollectionMetrics,
    PNCPClient,
    PNCPError,
    date_range,
    page_count,
)

PUBLICATION = "/v1/contratacoes/publicacao"
OPEN_PROPOSALS = "/v1/contratacoes/proposta"


def collect_phase0(
    *,
    days: int = 30,
    end_date: date | None = None,
    output_dir: Path = Path("work/phase0"),
    client: PNCPClient | None = None,
    modalities: tuple[int, ...] = PUBLICATION_MODALITIES,
    save_records: bool = True,
    progress: Callable[[str], None] = print,
) -> dict[str, Any]:
    end_date = end_date or date.today()
    start_date, end_date = date_range(days, end_date)
    client = client or PNCPClient()
    run_started = time.monotonic()
    metrics = CollectionMetrics()
    results: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "window": {"start": start_date.isoformat(), "end": end_date.isoformat(), "days": days},
        "page_size": PAGE_SIZE,
        "modalities": list(modalities),
        "endpoints": {},
        "failures": [],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.jsonl"
    stream = records_path.open("w", encoding="utf-8") if save_records else None
    seen: dict[str, set[str]] = {"publicacao": set(), "proposta_aberta": set()}
    try:
        for endpoint_name, endpoint in (("publicacao", PUBLICATION), ("proposta_aberta", OPEN_PROPOSALS)):
            endpoint_summary: dict[str, Any] = {}
            results["endpoints"][endpoint_name] = endpoint_summary
            for modality in modalities:
                progress(f"{endpoint_name}: modalidade {modality}")
                query = _query_for(endpoint_name, modality, start_date, end_date)
                pages = 0
                seen_pages: set[str] = set()
                modality_keys: set[str] = set()
                modality_records = 0
                try:
                    while pages < 10000:
                        query["pagina"] = pages + 1
                        payload = client.get_page(
                            endpoint, query, modality=modality, page=pages + 1, metrics=metrics
                        )
                        rows = payload["data"]
                        pages += 1
                        modality_records += len(rows)
                        for row in rows:
                            key = _canonical_key(row)
                            if key:
                                seen[endpoint_name].add(key)
                                modality_keys.add(key)
                            if stream is not None:
                                stream.write(json.dumps({
                                    "fonte": endpoint_name,
                                    "modalidade_consultada": modality,
                                    "coletado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                    "registro": row,
                                }, ensure_ascii=False, separators=(",", ":")) + "\n")
                        fingerprint = json.dumps(rows, ensure_ascii=False, sort_keys=True)
                        if fingerprint in seen_pages and rows:
                            raise PNCPError("pagina_repetida_paginacao_sem_avanco")
                        seen_pages.add(fingerprint)
                        count = page_count(payload, len(rows), PAGE_SIZE)
                        if not rows or (count is not None and pages >= count):
                            break
                        if count is None and len(rows) < PAGE_SIZE:
                            break
                    else:
                        raise PNCPError("limite_de_10000_paginas")
                    endpoint_summary[str(modality)] = {
                        "status": "ok", "pages": pages, "records": modality_records,
                        "unique_numero_controle_pncp": len(modality_keys),
                    }
                except PNCPError as exc:
                    endpoint_summary[str(modality)] = {
                        "status": "partial", "pages": pages, "records": modality_records,
                        "error": str(exc),
                    }
                    results["failures"].append({
                        "endpoint": endpoint_name, "modality": modality, "page": pages + 1,
                        "error": str(exc),
                    })
    finally:
        if stream is not None:
            stream.close()
    results["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    results["elapsed_seconds"] = round(time.monotonic() - run_started, 2)
    results["metrics"] = metrics.summary()
    results["unique"] = {name: len(keys) for name, keys in seen.items()}
    results["records_file"] = str(records_path) if save_records else None
    results["requests_by_endpoint_modality"] = _group_metrics(metrics)
    return results


def _query_for(name: str, modality: int, start_date: date, end_date: date) -> dict[str, Any]:
    query: dict[str, Any] = {
        "codigoModalidadeContratacao": modality,
        "pagina": 1,
        "tamanhoPagina": PAGE_SIZE,
    }
    if name == "publicacao":
        query["dataInicial"] = start_date.strftime("%Y%m%d")
        query["dataFinal"] = end_date.strftime("%Y%m%d")
    else:
        # dataFinal is the upper bound on closing dates, not the collection date.
        from datetime import timedelta
        query["dataFinal"] = (end_date + timedelta(days=365)).strftime("%Y%m%d")
    return query


def _canonical_key(row: dict[str, Any]) -> str | None:
    key = row.get("numeroControlePNCP")
    return str(key) if key else None


def _group_metrics(metrics: CollectionMetrics) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for metric in metrics.requests:
        grouped[f"{metric.endpoint}|modalidade={metric.modality}"].append(metric)
    return {
        key: {
            "requests": len(items),
            "records": sum(item.records for item in items),
            "errors": sum(item.error is not None for item in items),
            "latency_mean_ms": round(sum(item.elapsed_ms for item in items) / len(items), 2),
            "latency_max_ms": round(max(item.elapsed_ms for item in items), 2),
            "http_statuses": {
                str(code): sum(item.status == code for item in items)
                for code in sorted({item.status for item in items if item.status is not None})
            },
        }
        for key, items in grouped.items()
    }
