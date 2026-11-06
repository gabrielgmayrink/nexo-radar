"""Conservative, explainable product matching. Scores are not probabilities."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

VERSION = "2026-11-06.5"
TZ = ZoneInfo("America/Sao_Paulo")


def normalize(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def classify(obj: str, additional: str = "", *, profiles=None) -> dict:
    from radar.profiles import load_profiles
    profiles = load_profiles() if profiles is None else profiles
    text = " " + normalize(obj) + " "
    extra = " " + normalize(additional) + " "
    scores = {"Public": 0, "Gerico": 0}
    reasons = []
    active = [company for company in profiles if company["enabled"] and company["terms"]]
    for company in active:
        if any(" " + normalize(term) + " " in text for term in company["excludeTerms"]):
            continue
        evidence = [term for term in company["terms"] if " " + normalize(term) + " " in text]
        incidental = [term for term in company["terms"] if " " + normalize(term) + " " in extra]
        review_groups = [group['label'] for group in company.get('reviewGroups',[]) if
                         any(' '+normalize(term)+' ' in text for term in group['subjects']) and
                         any(' '+normalize(term)+' ' in text for term in group['contexts'])]
        scores[company["name"]] = min(90, 60 + 10 * len(evidence)) if evidence else 45 if review_groups else 20 if incidental else 0
        reasons.extend(company["name"] + ": " + term for term in evidence)
        if not evidence:reasons.extend(company['name']+': '+label for label in review_groups)
    matches = [name for name, score in scores.items() if score >= 60]
    offer = "Ambas" if len(matches) > 1 else matches[0] if matches else "Revisar" if max(scores.values()) else "Nenhuma"
    return {"suggestedOffer": offer, "score": max(scores.values()), "scores": scores,
            "evidence": reasons, "ruleVersion": VERSION, "configurationPending": not bool(active)}


def procurement_state(row: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    if row.get("situacaoCompraId") != 1:
        return "Inativa"
    if row.get("tipoInstrumentoConvocatorioCodigo") not in (1, 2):
        return "Inteligência"
    value = row.get("dataEncerramentoProposta")
    if not value:
        return "Prazo não informado"
    try:
        end = datetime.fromisoformat(value)
        if end.tzinfo is None:
            end = end.replace(tzinfo=TZ)
        start = datetime.fromisoformat(row["dataAberturaProposta"]) if row.get("dataAberturaProposta") else None
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=TZ)
        return "Encerrada" if end <= now else "A receber propostas" if start and start > now else "Recebendo propostas"
    except ValueError:
        return "Prazo inválido"
