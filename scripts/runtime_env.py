"""Load a private Vercel env file without printing its contents."""
import json
import os
from pathlib import Path


def load(path='.env.production.local'):
    values={}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        if not key.replace('_','').isalnum():continue
        values[key]=json.loads(value) if value.startswith('"') else value.strip("'")
    for key,value in values.items():os.environ[key]=value
    return values
