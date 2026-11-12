"""Conservative, explainable product matching. Scores are not probabilities."""
from __future__ import annotations

import re
import unicodedata
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import lru_cache

VERSION = "2026-11-11.1"
TZ = ZoneInfo("America/Sao_Paulo")


def normalize(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


@lru_cache(maxsize=512)
def phrase(term):
    return ' '+normalize(term)+' '


def classification_version(profiles=None):
    from radar.profiles import load_profiles
    profiles=load_profiles() if profiles is None else profiles
    fingerprint=hashlib.sha256(json.dumps(profiles,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:16]
    return VERSION+':'+fingerprint


def classify(obj: str, additional: str = "", *, profiles=None) -> dict:
    from radar.profiles import load_profiles
    profiles = load_profiles() if profiles is None else profiles
    text = " " + normalize(obj) + " "
    extra = " " + normalize(additional) + " "
    scores = {"Public": 0, "Gerico": 0}
    reasons = []
    decisions={company['name']:{'status':'unconfigured','reasonCodes':['profile_unconfigured'],'evidence':[]} for company in profiles}
    active = [company for company in profiles if company["enabled"] and company["terms"]]
    for company in active:
        scoped=text
        intent=company.get('requireServiceIntent',False)
        exclusions=[phrase(term) for term in company['excludeTerms']]
        if intent:
            from radar.contract_intent import analyze_service_intent,exclusion_is_primary,exclusion_evidence
            decision=analyze_service_intent(obj,additional)
            decisions[company['name']]=decision
            if decision['status']!='review' and exclusion_is_primary(text,exclusions):
                decisions[company['name']]={**decision,'status':'excluded','reasonCodes':['profile_exclusion'],
                                          'evidence':exclusion_evidence(obj,company['excludeTerms'])}
                continue
            focus=decision['focus']
            if decision['status']=='excluded':continue
            if decision['status']=='pending_documents':
                scores[company['name']]=20
                continue
            scoped=' '+focus+' '
            if decision['status']!='review' and exclusion_is_primary(scoped,exclusions):
                decisions[company['name']]={**decision,'status':'excluded','reasonCodes':['profile_exclusion']}
                continue
        elif any(term in text for term in exclusions):
            from radar.contract_intent import exclusion_evidence
            decisions[company['name']]={'status':'excluded','reasonCodes':['profile_exclusion'],'evidence':exclusion_evidence(obj,company['excludeTerms'])}
            continue
        terms=[*company['terms'],*(alias for alternatives in company.get('synonyms',{}).values() for alias in alternatives)]
        evidence = list({normalize(term):term for term in terms if phrase(term) in scoped}.values())
        incidental = [term for term in terms if phrase(term) in extra]
        review_groups = []
        for group in company.get('reviewGroups', []):
            subjects = [term for term in group['subjects'] if phrase(term) in scoped]
            # Training recipients may follow "destinada a". Advisory scope must
            # be in the main clause, rather than incidental reports/documents.
            training = any(normalize(term) in {'capacitacao', 'treinamento', 'aperfeicoamento', 'curso', 'cursos'} for term in subjects)
            context = text if training else scoped
            if subjects and any(phrase(term) in context for term in group['contexts']):
                review_groups.append(group['label'])
        score=min(90, 60 + 10 * len(evidence)) if evidence else 45 if review_groups else 20 if incidental else 0
        if intent:
            services=decisions[company['name']].get('services',[])
            if decisions[company['name']]['status']=='review':score=45
            elif not evidence and any(service in services for service in ('administrative_support','document_preparation','lecture')):score=70
            elif not evidence and 'education' in services and re.search(r'\b(ead|a distancia|ensino remoto|on ?line)\b',normalize(obj)):score=70
            elif not evidence and 'business_advice' in services:score=max(score,45)
            if score<40:
                decisions[company['name']]['status']='pending_documents'
                decisions[company['name']]['reasonCodes']=['scope_requires_confirmation']
            elif score<60:decisions[company['name']]['status']='review'
        else:
            decisions[company['name']]={'status':'selected' if score>=60 else 'review' if score>=40 else 'excluded',
                                      'reasonCodes':['profile_terms' if evidence else 'related_terms' if review_groups else 'no_profile_service'],
                                      'evidence':[]}
        scores[company["name"]] = score
        reasons.extend(company["name"] + ": " + ('Serviço no objeto principal: ' if intent else '') + term for term in evidence)
        if not evidence:reasons.extend(company['name']+': '+label for label in review_groups)
        if intent and scores[company['name']]>=40 and not evidence and not review_groups:
            reasons.extend(company['name']+': '+item['matchedText'] for item in decisions[company['name']]['evidence'] if item['role'] in ('primary','mixed'))
    matches = [name for name, score in scores.items() if score >= 60]
    offer = "Ambas" if len(matches) > 1 else matches[0] if matches else "Revisar" if max(scores.values()) else "Nenhuma"
    return {"suggestedOffer": offer, "score": max(scores.values()), "scores": scores,
            "evidence": reasons, "ruleVersion": VERSION, "classificationVersion":classification_version(profiles),
            "scoreBasis":"rules_not_probability","decisionByCompany":decisions,"configurationPending": not bool(active)}


def procurement_state(row: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    if row.get("situacaoCompraId") != 1:
        return "Inativa"
    if row.get("tipoInstrumentoConvocatorioCodigo") not in (1, 2, 4):
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
