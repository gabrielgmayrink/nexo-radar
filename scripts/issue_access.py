"""Deliver one-time first-access links in a private, ignored local artifact."""
import html
import json
import os
from pathlib import Path
from runtime_env import load
load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
members=['gabrielmayrink07@gmail.com','publicgerencia9@gmail.com']
os.environ['RADAR_TEAM_EMAILS']=','.join(members)
from radar.postgres_store import PostgresStore
from radar.password_auth import create_invite

root=Path(__file__).resolve().parents[1]
target=root/'.local'/'primeiro-acesso.html'
target.parent.mkdir(exist_ok=True)
store=PostgresStore()
try:
    links=[]
    for email in members:
        token=create_invite(store.db,email)
        links.append('<article><p>'+html.escape(email)+'</p><a rel="noreferrer" href="https://nexo-radar-taupe.vercel.app/#setup='+token+'">Definir minha senha e acessar →</a></article>')
    document='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nexo Radar — primeiro acesso</title><style>body{font:15px/1.7 Segoe UI,Arial;background:#f1f5fc;color:#1c3559;padding:32px}main{max-width:650px;margin:auto;background:white;border-radius:20px;padding:32px}h1{font-size:28px}article{border:1px solid #d7e4f7;border-radius:14px;padding:18px;margin:18px 0}a{display:inline-block;background:#286bed;color:white;text-decoration:none;border-radius:9px;padding:12px 18px}p{color:#6780a4}small{color:#8c6c4a}</style><main><h1>Nexo Radar · Primeiro acesso</h1><p>Escolha o convite correspondente ao seu e-mail e defina sua própria senha no aplicativo. Cada convite só pode ser usado uma vez e expira em 24 horas.</p>'''+''.join(links)+'''<small>Este arquivo contém convites privados. Entregue o convite da Public apenas ao responsável pela empresa. Ele não é publicado no GitHub nem na Vercel.</small></main></html>'''
    target.write_text(document,encoding='utf-8')
    print(json.dumps({'invitesCreated':len(members),'privateArtifact':str(target),'validHours':24,'emailSent':False}))
finally:store.close()
