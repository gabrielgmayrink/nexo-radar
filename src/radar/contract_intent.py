"""Conservative scope extraction for the Public service profile.

The input is normalized Portuguese. Service words in a venue's purpose,
an organization's name, course topics or a purchased product's onboarding
are not evidence that the corresponding service is being procured.
"""
import re

SERVICE = re.compile(
    r'\b(?:assessoria|consultoria|apoio administrativo|preparacao de documentos|'
    r'servicos de escritorio|palestras?|palestrantes?|treinamento|capacitacao|'
    r'aperfeicoamento|cursos?|ensino|educacao a distancia|instrutoria|instrucao|'
    r'formacao profissional|desenvolvimento (?:profissional|gerencial))\b'
)
SECONDARY = re.compile(
    r'\b(?:com vistas a|onde (?:sao|e|serao|se|ocorrem)|a exemplo de|tais como|'
    r'destinad[oa]s? (?:a|ao|aos|as)|a ser(?:em)? utilizad[oa]s?|'
    r'para (?:uso|utilizacao|atendimento|atender (?:a|as|o|os|aos) (?:necessidades|demandas))|'
    r'visando (?:atender|o atendimento)|com o objetivo de|a fim de|conforme|nos termos|'
    r'incluindo|inclus[oa]s?|contemplando|abrangendo|compreendendo|bem como)\b'
)
TOPIC = re.compile(r'\b(?:sobre|acerca de|com o tema|com temas|que aborda|que abordam)\b')
OTHER_OBJECT = re.compile(
    r'\b(?:equipamentos?|materiais?|mobiliario|moveis|cadeiras|uniformes|brindes|'
    r'insumos|reagentes|kits?|generos alimenticios|lanches|'
    r'coffee break|buffet|alimentacao|passagens|transporte|hospedagem|'
    r'softwares?|licenciamento|licencas?|plataformas?|'
    r'sistemas? (?:integrados?|informatizados?|de digitalizacao|de gestao publica)|'
    r'construcao|reformas?|obras?|pavimentacao|modernizacao|auditorios?|'
    r'auditoria|quimica|engenharia|tratamento de agua|analises laboratoriais|'
    r'responsabilidade tecnica|exames|consultas medicas|procedimentos cirurgicos|unidade movel|'
    r'traducao|interpretacao|interpretes|tradutores|filmagem|fotografia|sonorizacao|'
    r'iluminacao|transmissao|gravacao|organizacao de eventos|producao de eventos)\b'
)
ORGANIZATION_SERVICE = re.compile(
    r'\b(?:area|unidade|setor|departamento|centro) (?:de|do|da) '
    r'(?:apoio administrativo|ensino)\b'
)


def service_contract_focus(text: str) -> str:
    """Return the service-bearing main clause, or no matching service intent."""
    text = text.strip()
    service = SERVICE.search(text)
    if not service:
        return ''
    topic = TOPIC.search(text)
    if topic and service.start() < topic.start():
        text = text[:topic.start()]
    secondary = SECONDARY.search(text)
    if secondary:
        head = text[:secondary.start()]
        # Preserve genuine requests expressed after a neutral preamble, such as
        # "empresa destinada à prestação de apoio administrativo".
        if SERVICE.search(head) or OTHER_OBJECT.search(head):
            text = head
    service = SERVICE.search(text)
    if not service:
        return ''
    other = OTHER_OBJECT.search(text)
    if other and other.start() < service.start():
        return ''
    organization = ORGANIZATION_SERVICE.search(text)
    if organization and organization.start() < service.start():
        return ''
    return text


def exclusion_is_primary(text: str, phrases: list[str]) -> bool:
    """Do not reject a course merely because its subject is excluded IT work."""
    service = SERVICE.search(text)
    first_service = service.start() if service else len(text)
    return any(0 <= (position := text.find(phrase)) <= first_service + 1 for phrase in phrases)
