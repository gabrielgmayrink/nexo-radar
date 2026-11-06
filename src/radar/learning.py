"""Audited example memory. Similarity is a review cue, never a rejection rule."""
import hashlib
import json
import re
from collections import defaultdict
from radar.relevance import normalize

REASONS=('','produto_diferente','nao_contrata_sistema','mencao_incidental','escopo_fora',
         'edital_insuficiente','aderente','outro')
STOPWORDS=set('contratacao empresa especializada prestacao servicos aquisicao fornecimento para como que dos das uma com por nos seus suas conforme objeto municipal prefeitura licitacao servico incluindo mediante'.split())
OBJECT_REASONS={'produto_diferente','nao_contrata_sistema','mencao_incidental'}


def object_hash(obj,additional=''):
    values=[re.sub(r'\s+',' ',str(value or '').strip().casefold()) for value in (obj,additional)]
    return hashlib.sha256(json.dumps(values,ensure_ascii=False).encode()).hexdigest()


def tokens(obj):
    return {word for word in normalize(obj).split() if len(word)>3 and word not in STOPWORDS and not word.isdigit()}


def apply_examples(cards,examples):
    indexed=defaultdict(list)
    negatives=[]
    for example in examples:
        if example.get('object_hash'):
            indexed[example['object_hash']].append(example)
        if example.get('offer')=='Nenhuma':negatives.append((example,tokens(example.get('example_object') or '')))
    result=[]
    for card in cards:
        card=dict(card)
        signature=object_hash(card['object'],card.get('additionalInfo',''))
        same=indexed.get(signature,[])
        rejected=[e for e in same if e['offer']=='Nenhuma']
        object_rejections=[e for e in rejected if e.get('reason_code') in OBJECT_REASONS]
        approved=[e for e in same if e['offer'] in ('Daltton','Gerico','Ambas')]
        direct=[e for e in same if e['opportunity_id']==card['id']]
        if direct:
            example=direct[0]
            if example['offer']=='Nenhuma':
                card['learning']={'label':'irrelevante','match':'reviewed','reasonCode':example['reason_code'],'examples':1}
            elif example['offer'] in ('Daltton','Gerico','Ambas'):
                card['learning']={'label':'relevante','match':'reviewed','reasonCode':example['reason_code'],'examples':1,'offer':example['offer']}
            elif example['offer']=='Revisar':
                card['learning']={'label':'revisar','match':'reviewed','reasonCode':example['reason_code'],'examples':1}
        elif rejected and approved:
            card['learning']={'label':'revisar','match':'conflicting_examples','reasonCode':'','examples':len(same)}
        elif object_rejections and len(normalize(card['object']))>=80:
            card['learning']={'label':'irrelevante','match':'identical_object','reasonCode':object_rejections[0]['reason_code'],'examples':len(object_rejections)}
        elif rejected and len(normalize(card['object']))>=80:
            card['learning']={'label':'revisar','match':'identical_context','reasonCode':rejected[0]['reason_code'],'examples':len(rejected)}
        elif approved and len(normalize(card['object']))>=80:
            offers={example['offer'] for example in approved}
            card['learning']={'label':'relevante','match':'identical_object','reasonCode':'aderente','examples':len(approved),
                              'offer':next(iter(offers)) if len(offers)==1 else 'Ambas'}
        else:
            words=tokens(card['object'])
            similar=[example for example,known in negatives
                     if len(words&known)>=8 and len(words&known)/max(1,len(words|known))>=.85]
            if similar:
                card['learning']={'label':'revisar','match':'similar_negative','reasonCode':similar[0]['reason_code'],'examples':len(similar)}
        result.append(card)
    return result
