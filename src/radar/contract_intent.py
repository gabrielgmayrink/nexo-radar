"""Auditable service roles, distinct from retrieval and legal eligibility.

Rules identify evidence and uncertainty, never a probability. Mixed/ambiguous
objects remain reviewable; no rule deletes source records or original evidence.
"""
from __future__ import annotations
import re
import unicodedata

SERVICE_RULES = {
    'administrative_support': re.compile(r'\b(?:apoio (?:administrativo|as? rotinas administrativas)|suporte administrativo|servicos (?:combinados )?de escritorio|rotinas administrativas)\b'),
    'document_preparation': re.compile(r'\b(?:preparacao(?: e organizacao)? de documentos|assessoria documental|organizacao de documentos)\b'),
    'business_advice': re.compile(r'\b(?:assessoria|consultoria)(?: tecnica)?(?: e (?:assessoria|consultoria))?\b'),
    'lecture': re.compile(r'\b(?:palestras?|palestrantes?)\b'),
    'training': re.compile(r'\b(?:treinamentos?|capacitac(?:ao|oes)|aperfeicoamento|formacao (?:profissional|continuada)|instrutoria|instrucao)\b'),
    'education': re.compile(r'\b(?:cursos?|ensino|educacao (?:a distancia|na modalidade a distancia))\b'),
}
OTHER_OBJECT = re.compile(
    r'\b(?:equipamentos?|material|materiais|mobiliario|moveis|cadeiras|uniformes|brindes|'
    r'insumos|reagentes|kits?|generos? alimenticios?|lanches|coffee break|buffet|alimentacao|'
    r'seguros?|apostilas|confeccao|passagens|transporte|hospedagem|softwares?|'
    r'licenciamento|licencas?|plataformas?|sistemas? (?:integrados?|informatizados?|de digitalizacao|de gestao publica)|'
    r'construcao|reformas?|(?<!mao de )obras?|pavimentacao|modernizacao|auditorios?|'
    r'auditoria|quimica|engenharia|tratamento de agua|analises laboratoriais|responsabilidade tecnica|'
    r'exames|consultas medicas|procedimentos cirurgicos|unidade movel|traducao|interpretacao|interpretes|'
    r'tradutores|filmagem|fotografia|sonorizacao|iluminacao|transmissao|gravacao|organizacao de eventos|producao de eventos)\b'
)
SECONDARY = re.compile(
    r'\b(?:com vistas a|onde (?:sao|e|serao|se|ocorrem)|a exemplo de|tais como|destinad[oa]s? (?:a|ao|aos|as)|'
    r'a ser(?:em)? utilizad[oa]s?|para (?:uso|utilizacao|atendimento)|visando (?:atender|o atendimento)|'
    r'com o objetivo de|a fim de|conforme|nos termos|incluindo|inclus[oa]s?|contemplando|abrangendo|compreendendo|bem como)\b'
)
NEGATION = re.compile(r'\b(?:nao (?:inclui|incluem|contempla|contemplam|abrange|abrangem|compreende|compreendem|contrata|envolve)|sem|excluid[oa]s?|exceto|vedad[oa]s?)\b')
ORGANIZATION = re.compile(r'\b(?:area|unidade|setor|departamento|centro|nucleo|escola) (?:de|do|da) (?:apoio administrativo|ensino|treinamento)\b')
COORDINATED_SERVICE = re.compile(r'\b(?:e|bem como|alem de)\s+(?:(?:a|de|da|do|ainda)\s+)*(?:realizacao|ministracao|execucao|oferta|prestacao|ministrar|realizar|oferecer|executar)\b')
COORDINATED_OTHER = re.compile(r'\b(?:e|bem como|alem de)\s+(?:(?:a|de|da|do|ainda)\s+)*(?:locacao|aquisicao|fornecimento|instalacao|reforma|construcao)\b')
ACQUISITION = re.compile(r'\b(?:aquisicao|compra|locacao)\b')
SERVICE_PURCHASE = re.compile(r'^\s+(?:de|do|da|dos|das)\s+(?:\d+\s+)?(?:servicos?|cursos?|vagas|inscricoes|palestras?|treinamentos?|capacitacao|bolsas|mao de obra)\b')
EAD = re.compile(r'\b(?:ead|(?:a|na modalidade a|na modalidade de ensino a|pela modalidade a) distancia|ensino remoto|educacao remota|cursos? on ?line)\b')
PRESENTIAL = re.compile(r'\b(?:presencial|presenciais)\b')
DEGREE = re.compile(r'\b(?:graduacao|pos graduacao|mestrado|doutorado|cursos? tecnicos?|cursos? profissionalizantes?)\b')
PROFESSIONAL = re.compile(r'\b(?:profissional|profissionais|gerencial|gerenciais|servidores|gestores|equipes?|pessoal|funcionarios|empregados|colaboradores)\b')
ADMINISTRATIVE = re.compile(r'\b(?:administrativ[oa]|empresarial|gestao (?:publica|privada|empresarial)|recursos humanos|preparacao de documentos)\b')


def normalized_with_offsets(value: str) -> tuple[str, list[int]]:
    chars, offsets = [], []
    for position, character in enumerate(value):
        for plain in unicodedata.normalize('NFKD', character.lower()):
            if unicodedata.combining(plain):
                continue
            plain = plain if plain.isascii() and plain.isalnum() else ' '
            if plain == ' ' and (not chars or chars[-1] == ' '):
                continue
            chars.append(plain)
            offsets.append(position)
    if chars and chars[-1] == ' ':
        chars.pop()
        offsets.pop()
    return ''.join(chars), offsets


def _evidence(obj, offsets, match, service, role, code):
    start, end = offsets[match.start()], offsets[match.end()-1]+1
    return {'code':code,'service':service,'role':role,'source':'object',
            'start':start,'end':end,'matchedText':obj[start:end],
            'excerpt':obj[max(0,start-80):min(len(obj),end+120)]}


def _negated(text, start):
    prefix = text[max(0,start-100):start]
    matches = list(NEGATION.finditer(prefix))
    if not matches:
        return False
    last = matches[-1]
    suffix = prefix[last.end():]
    if last.group() == 'sem' and re.match(r'\s+(?:fins lucrativos|prejuizo)',suffix):
        return False
    return len(suffix.split()) <= 7 and not re.search(r'\b(?:mas|porem)\b',suffix)


def analyze_service_intent(obj: str, additional: str = '') -> dict:
    text, offsets = normalized_with_offsets(obj)
    hits = sorted([(match,service) for service,pattern in SERVICE_RULES.items()
                   for match in pattern.finditer(text)],key=lambda hit:hit[0].start())
    evidence, active = [], []
    other = OTHER_OBJECT.search(text)
    mixed = False
    for match, service in hits:
        role, code = 'primary', 'service_contracted'
        before = text[:match.start()]
        organization = ORGANIZATION.search(text)
        if _negated(text,match.start()):
            role,code = 'negated','expressly_excluded'
        elif organization and organization.start() <= match.start() < organization.end():
            role,code = 'context','organization_name'
        elif other and other.start() < match.start():
            coordinated = COORDINATED_SERVICE.search(before[other.end():])
            if coordinated and len(before[other.end()+coordinated.end():].split()) <= 8:
                mixed = True
                role,code = 'mixed','mixed_object'
            else:
                role,code = 'context','accessory_or_purpose'
        else:
            acquisition = ACQUISITION.search(before)
            if acquisition and not SERVICE_PURCHASE.match(text[acquisition.end():]):
                role,code = 'context','purchase_for_service_context'
        if role in ('primary','mixed') and service == 'business_advice':
            end = SECONDARY.search(text,match.end())
            scope = text[match.start():end.start() if end else len(text)]
            if not ADMINISTRATIVE.search(scope):
                role,code = 'uncertain','advisory_scope_unconfirmed'
                if OTHER_OBJECT.search(scope):
                    role,code = 'context','advisory_outside_profile'
        record = _evidence(obj,offsets,match,service,role,code)
        evidence.append(record)
        if role in ('primary','mixed','uncertain'):
            active.append(record)
    if active:
        first = min(item['start'] for item in active)
        # Source offsets are only used to delimit a coordination, never to score.
        first_normalized = len(normalized_with_offsets(obj[:first])[0])
        if COORDINATED_OTHER.search(text,first_normalized):
            mixed = True
    codes = list(dict.fromkeys(item['code'] for item in evidence))
    if not active:
        if not evidence:
            extra,_ = normalized_with_offsets(additional)
            related = any(pattern.search(extra) for pattern in SERVICE_RULES.values())
            uncertain = not other and (related or len(text.split()) < 10)
            return {'status':'pending_documents' if uncertain else 'excluded',
                    'reasonCodes':['additional_requires_confirmation' if related else 'insufficient_object' if uncertain else 'no_profile_service'],
                    'evidence':evidence,'services':[],'focus':''}
        return {'status':'excluded','reasonCodes':codes,'evidence':evidence,'services':[],'focus':''}
    services = sorted({item['service'] for item in active})
    if mixed:
        return {'status':'review','reasonCodes':['mixed_object'],'evidence':evidence,'services':services,'focus':text}
    education = any(item['service']=='education' for item in active)
    if education and DEGREE.search(text):
        if PRESENTIAL.search(text) and not EAD.search(text):
            return {'status':'excluded','reasonCodes':['ead_required_presential'],'evidence':evidence,'services':services,'focus':text}
        if not EAD.search(text):
            return {'status':'review','reasonCodes':['ead_modality_unconfirmed'],'evidence':evidence,'services':services,'focus':text}
    return {'status':'selected' if any(item['role']=='primary' for item in active) else 'review',
            'reasonCodes':['service_contracted'] if any(item['role']=='primary' for item in active) else ['scope_requires_review'],
            'evidence':evidence,'services':services,'focus':text}


def service_contract_focus(text: str) -> str:
    return analyze_service_intent(text)['focus']


def exclusion_is_primary(text: str, phrases: list[str]) -> bool:
    positions = [match.start() for pattern in SERVICE_RULES.values() for match in pattern.finditer(text)]
    first = min(positions,default=len(text))
    return any(0 <= (position := (' '+text.strip()+' ').find(phrase)) <= first+1 for phrase in phrases)


def exclusion_evidence(obj: str,terms: list[str]) -> list[dict]:
    text,offsets=normalized_with_offsets(obj)
    result=[]
    for term in terms:
        normalized,_=normalized_with_offsets(term)
        if not normalized:continue
        match=re.search(r'\b'+re.escape(normalized)+r'\b',text)
        if match:result.append(_evidence(obj,offsets,match,'outside_profile','primary','profile_exclusion'))
    return result
