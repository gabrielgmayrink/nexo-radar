"""Gera um resumo Markdown reproduzível a partir do resultado da coleta."""

from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    window = result["window"]
    metrics = result["metrics"]
    latency = metrics["latency_ms"]
    lines = [
        "# Fase 0 — Resultado da coleta PNCP",
        "",
        f"Janela de publicações: **{window['start']} a {window['end']}** ({window['days']} dias).",
        f"Conjunto de modalidades: **{', '.join(str(code) for code in result['modalities'])}**.",
        "",
        "## Resumo de execução",
        "",
        f"- Duração total: {result.get('elapsed_seconds', 'n/d')} s",
        f"- Requisições HTTP (incluindo retentativas): {metrics['requests']}",
        f"- Retentativas: {metrics['retries']}",
        f"- Latência por requisição: média {latency.get('mean')} ms; p95 {latency.get('p95')} ms; máxima {latency.get('max')} ms",
        f"- Status HTTP: `{metrics.get('http_statuses', {})}`",
        f"- Erros registrados: `{metrics.get('errors', {})}`",
        f"- Respostas 429 recuperadas por retentativa: {result.get('observations', {}).get('http_429_retries_recovered', 0)}; respostas 204 vazias válidas: {result.get('observations', {}).get('empty_http_204_responses', 0)}; falhas terminais: {result.get('observations', {}).get('terminal_failures', len(result.get('failures', [])))}",
        "",
        "## Registros por rota e modalidade",
        "",
        "| Rota | Modalidade | Estado | Páginas | Registros | IDs PNCP distintos |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for endpoint, entries in result.get("endpoints", {}).items():
        for modality, item in entries.items():
            lines.append(
                f"| `{endpoint}` | {modality} | {item.get('status', 'partial')} | "
                f"{item.get('pages', 'n/d')} | {item.get('records', 0)} | "
                f"{item.get('unique_numero_controle_pncp', 'n/d')} |"
            )
    lines += [
        "",
        f"IDs PNCP distintos no total: `{result.get('unique', {})}`.",
        "",
        "## Parâmetros validados",
        "",
        "- Publicações: `dataInicial`, `dataFinal` no formato `yyyyMMdd`, modalidade obrigatória, `pagina` e `tamanhoPagina` de 10 a 50.",
        "- Propostas abertas: `dataFinal` e `pagina` obrigatórios; modalidade opcional no contrato, mas enviada pelo spike; `tamanhoPagina` de 10 a 50.",
        "- A resposta real observada inclui `data`, `totalRegistros`, `totalPaginas`, `numeroPagina`, `paginasRestantes` e `empty`.",
        "- HTTP 204 foi observado para modalidades sem resultados abertos e é tratado como coleção vazia válida.",
        "",
        "## Falhas e limitações",
        "",
    ]
    if result.get("failures"):
        lines.append("A execução terminou parcialmente nas seguintes partições:")
        lines.append("")
        for failure in result["failures"]:
            lines.append(
                f"- `{failure['endpoint']}`, modalidade {failure['modality']}, "
                f"página {failure['page']}: `{failure['error']}`"
            )
    else:
        lines.append("Nenhuma partição terminou com erro definitivo após as retentativas.")
    lines += [
        "",
        "A rota de propostas abertas é um retrato na data de corte e não reconstitui o estado histórico de cada dia. A janela de 30 dias aplica-se às publicações.",
        "",
        "Os registros completos permanecem em `work/phase0/records.jsonl`; este relatório contém apenas métricas agregadas.",
        "",
    ]
    return "\n".join(lines)
