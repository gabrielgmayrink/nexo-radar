"""Evaluate against independent human labels; no network calls or fabricated targets."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from radar.relevance import classify,classification_version
from radar.company_access import COMPANIES

def evaluate(rows):
    counts={'tp':0,'fp':0,'tn':0,'fn':0,'retainedRelevant':0,'relevant':0,'review':0,'pendingDocuments':0}
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('company') not in COMPANIES or type(row.get('relevant')) is not bool or not isinstance(row.get('object'),str) or not row.get('id'):raise ValueError('Each label requires id, company, object, relevant:boolean')
        key=(row['id'],row['company'])
        if key in seen:raise ValueError('Duplicate labels must be resolved before evaluation')
        seen.add(key)
        decision=classify(row['object'],row.get('additionalInfo') or '')['decisionByCompany'][COMPANIES[row['company']]]
        selected=decision['status']=='selected';relevant=row['relevant']
        counts['tp' if relevant and selected else 'fp' if selected else 'fn' if relevant else 'tn']+=1
        counts['relevant']+=int(relevant)
        counts['retainedRelevant']+=int(relevant and decision['status'] in ('selected','review','pending_documents'))
        counts['review']+=int(decision['status']=='review');counts['pendingDocuments']+=int(decision['status']=='pending_documents')
    ratio=lambda a,b:round(a/b,6) if b else None
    return {'labels':len(seen),'classificationVersion':classification_version(),'confusion':{key:counts[key] for key in ('tp','fp','tn','fn')},
            'automaticPrecision':ratio(counts['tp'],counts['tp']+counts['fp']),
            'automaticRecall':ratio(counts['tp'],counts['relevant']),
            'retainedRecall':ratio(counts['retainedRelevant'],counts['relevant']),
            'manualReview':counts['review'],'pendingDocuments':counts['pendingDocuments'],
            'limitation':'Metrics apply only to supplied independently labeled examples; they do not measure national source coverage.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='JSONL: id,company,object,additionalInfo,relevant (human label).');parser.add_argument('labels',type=Path)
    args=parser.parse_args()
    with args.labels.open(encoding='utf-8') as stream:result=evaluate(json.loads(line) for line in stream if line.strip())
    print(json.dumps(result,ensure_ascii=False,indent=2))
