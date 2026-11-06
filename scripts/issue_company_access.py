"""Create separate private first-access artifacts; never print invite tokens."""
import html,json,os
from pathlib import Path
from runtime_env import load
load()
os.environ['RADAR_SUPABASE_PROJECT_REF']='hxngkmrsthyjycxaellk'
members={'public':('Public','publicgerencia9@gmail.com'),'gerico':('Gerico','gericomayrink@gmail.com')}
os.environ['RADAR_TEAM_EMAILS']=','.join(email for _,email in members.values())
from radar.postgres_store import PostgresStore
from radar.password_auth import create_invite
store=PostgresStore()
try:
 files=[]
 for company,(name,email) in members.items():
  existing=store.db.execute("select exists(select 1 from auth.users where lower(email)=%s and coalesce(encrypted_password,'')<>'')",(email,)).fetchone()[0]
  link='https://nexo-radar-taupe.vercel.app/'
  if not existing:link+='#setup='+create_invite(store.db,email)
  target=Path('.local')/('acesso-'+company+'.html')
  target.write_text('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Acesso '+name+' · Nexo Radar</title><style>body{font:16px/1.7 Segoe UI,Arial;background:#f5f5f2;color:#202923;padding:24px}main{max-width:560px;margin:40px auto;padding:30px;background:white;border:1px solid #dbe0da;border-radius:14px}a{display:inline-block;background:#315c43;color:white;padding:12px 20px;text-decoration:none;border-radius:8px}small{display:block;margin-top:24px;color:#606c64}</style><main><h1>Nexo Radar · '+html.escape(name)+'</h1><p>'+html.escape(email)+'</p><p>Este acesso é exclusivo para a sua empresa. As oportunidades e avaliações da outra empresa não ficam disponíveis nesta conta.</p><a rel="noreferrer" href="'+html.escape(link,quote=True)+'">'+('Entrar na minha conta' if existing else 'Criar minha senha e entrar')+'</a><small>'+('Use a senha já cadastrada.' if existing else 'Convite pessoal válido por 24 horas e utilizável uma única vez. Defina uma senha com pelo menos 12 caracteres.')+' Entregue este arquivo somente ao responsável pela empresa.</small></main></html>',encoding='utf-8')
  files.append({'company':name,'firstAccessNeeded':not existing,'privateArtifact':str(target.resolve())})
 print(json.dumps({'accessFiles':files,'emailSent':False}))
finally:store.close()
