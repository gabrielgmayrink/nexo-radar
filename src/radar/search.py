"""Literal, accent-insensitive search with phrases, exclusions and known acronyms."""
import re
import unicodedata

ALIASES={'ti':('ti','tecnologia da informacao','informatica','desenvolvimento de sistemas','desenvolvimento de software','fabrica de software'),'ead':('ead','ensino a distancia','educacao a distancia')}


def normalize_search(value):
    value=''.join(c for c in unicodedata.normalize('NFD',value.lower()) if not unicodedata.combining(c))
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())


def parse_query(query):
    clauses=[]
    for match in re.finditer(r'(-?)"([^"]*)"|(-?)([^\s"]+)',query[:240]):
        value=normalize_search(match[2] if match[2] is not None else match[4])
        if value:clauses.append((value,(match[1] or match[3])=='-',match[2] is not None))
    return clauses


def matches_query(row,clauses):
    if not clauses:return True
    text=' '+normalize_search(' '.join(str(row.get(key) or '') for key in ('object','additionalInfo','organization','city','state','id')))+' '
    words=set(text.split())
    for value,excluded,phrase in clauses:
        candidates=(value,) if phrase else ALIASES.get(value,(value,))
        matched=any((' '+term+' ' in text) if phrase or ' ' in term else (term in words if len(term)<=2 else term in text) for term in candidates)
        if matched==excluded:return False
    return True
