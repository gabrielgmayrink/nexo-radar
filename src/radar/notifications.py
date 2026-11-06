"""Small, deduplicated digests. Rule suggestions are never labelled AI-validated."""
import html
import re
from datetime import datetime,timedelta,timezone
from radar.mail import APP_URL,email_list,reserve,send_reserved
from radar.relevance import TZ
from radar.learning import apply_examples
from radar.verification import verify_shortlist,fetch_record


def future_deadline(card,now):
    if card.get('statusId')!=1 or card.get('instrumentId') not in (1,2):return None
    try:
        value=datetime.fromisoformat(card.get('proposalDeadline','').replace('Z','+00:00'))
        if value.tzinfo is None:value=value.replace(tzinfo=TZ)
        return value if value>now else None
    except (TypeError,ValueError):return None


def select_cards(rows,kind,now):
    selected=[]
    for card,offer,status in rows:
        if not card or offer in ('Nenhuma','Revisar') or status in ('Descartada','Ganhou','Perdeu') or card.get('learning',{}).get('label') in ('irrelevante','revisar'):continue
        approved=offer in ('Daltton','Gerico','Ambas') or card.get('learning',{}).get('label')=='relevante'
        if card.get('score',0)<60 and not approved:continue
        deadline=future_deadline(card,now)
        if not deadline or kind=='urgent' and deadline>now+timedelta(hours=48):continue
        if not re.fullmatch(r'https://pncp\.gov\.br/app/editais/\d{14}/\d{4}/\d+',card.get('pncpUrl','')):continue
        selected.append({**card,'effectiveOffer':offer or card.get('learning',{}).get('offer') or card['suggestedOffer'],'deadline':deadline})
    selected.sort(key=lambda c:(c['deadline'],-c.get('score',0)))
    return selected[:5 if kind=='urgent' else 15]


def render_onboarding():
    title='Conheça o Radar e ajude a melhorar as buscas'
    sections=[
        ('O que o Radar faz','O Radar consulta o PNCP para encontrar licitações relacionadas às empresas Daltton e Gerico. Ele reduz o volume de pesquisa, mas cada oportunidade ainda precisa ser conferida no edital oficial.'),
        ('1. Abra a lista certa','No radar mostra as oportunidades selecionadas. Mais compatíveis reúne objetos com sinais de aderência. Precisam de análise indica casos em que o escopo ainda precisa ser confirmado. Com prazo futuro reúne contratações ativas com encerramento adiante. Clique no indicador para abrir sua lista.'),
        ('2. Refine e confira','Filtre por produto, estado, prazo, modalidade e situação da avaliação. Combine palavras na busca. Abra Ver detalhes para ler o objeto completo e use Abrir edital no PNCP para conferir documentos, requisitos, valores e datas antes de decidir participar.'),
        ('3. Entre na equipe','No painel, clique em Entrar na equipe e informe o mesmo e-mail que recebeu esta mensagem. Você receberá um link pessoal, sem precisar criar uma senha. Confirme a entrada para compartilhar suas avaliações.'),
        ('4. Mostre o que serve — e o que não serve','Em cada oportunidade, escolha Faz sentido, Não tem relação ou Preciso analisar. Informe o produto, o motivo e, se possível, o que uma boa oportunidade deveria contratar. Exemplo: se é compra de equipamentos e pesquisa de preços aparece apenas como justificativa, marque Não tem relação e explique isso.'),
        ('5. Publique para ensinar o Radar','Clique em Publicar avaliação e ensinar o Radar. Sem esse passo, a anotação continua como rascunho no seu navegador. Os exemplos publicados aparecem em Aprendizado da equipe. Objetos idênticos já rejeitados vão para Descartadas; objetos apenas parecidos recebem um aviso para análise. Exemplos positivos também ajudam a reconhecer o produto certo. Se uma decisão estiver errada, corrija-a: o histórico é preservado.'),
        ('Como vocês podem ajudar','Avaliem os resultados úteis e os equivocados. Em vez de apenas dizer não serve, registrem por que não serve e o que deveria ser encontrado. Descrevam o serviço esperado e os limites de atendimento de cada empresa. Indiquem a empresa relacionada e se o objeto está dentro da sua capacidade de atendimento.'),
        ('Resumos e acompanhamento','Resumos e avisos dependem de configurar o envio e ativar o agendamento desta instalação. Avisos de oportunidades exigem uma coleta recente; o Radar evita enviar informações antigas. Usem Vou participar para acompanhar o que pretendem disputar.'),
    ]
    contents=''.join(f'<section style="margin-top:24px"><h2 style="font-size:17px;color:#315139;margin:0 0 8px">{html.escape(heading)}</h2><p style="margin:0;line-height:1.75;font-size:14px">{html.escape(text)}</p></section>' for heading,text in sections)
    body=f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"></head><body style="margin:0;background:#f3f6f0;font-family:Arial,sans-serif;color:#334a3b"><main style="max-width:640px;margin:24px auto;background:white;padding:28px;border-radius:16px"><p style="letter-spacing:2px;color:#64804c;font-size:12px;font-weight:bold">RADAR DE LICITAÇÕES</p><h1 style="font-size:26px;line-height:1.3">{title}</h1><p style="line-height:1.7">Olá! Este é o e-mail de apresentação e teste do Radar para a equipe Daltton e Gerico.</p><p><a href="{APP_URL}/" style="display:inline-block;background:#284d3c;color:white;padding:14px 22px;border-radius:9px;text-decoration:none">Abrir o Radar</a></p>{contents}<p style="margin-top:26px;padding-top:16px;border-top:1px solid #e1e8db;font-size:12px;line-height:1.7;color:#718067">A seleção usa regras e exemplos da equipe; não confirma elegibilidade nem substitui a leitura do edital. Este envio de apresentação é único. Para ajustar os avisos, responda este e-mail.</p></main></body></html>'
    text='Olá!\n\n'+title+'\n\nAbrir o Radar: '+APP_URL+'\n\n'+'\n\n'.join(heading+'\n'+content for heading,content in sections)
    return 'Radar de Licitações: como usar e melhorar as buscas',body,text


def render_digest(cards,kind,now):
    if kind=='test':return render_onboarding()
    title={'weekly':'Seu resumo semanal de oportunidades','urgent':'Prazos nos próximos dois dias','test':'O Radar está conectado ao seu e-mail'}[kind]
    intro='Sugestões por regras e exemplos da equipe para Daltton e Gerico, com situação conferida individualmente no PNCP. A coleta geral pode acrescentar outras oportunidades. Confira o objeto, os documentos e os requisitos antes de decidir participar.'
    if kind=='test':intro='A configuração de envio do Radar foi concluída. Você receberá resumos semanais e avisos de prazo das oportunidades selecionadas. Entre no painel com este e-mail para compartilhar avaliações com a equipe.'
    items=[];texts=[title,intro]
    for card in cards:
        deadline=card['deadline'].astimezone(TZ).strftime('%d/%m/%Y às %H:%M')
        obj=card.get('object','')[:900]
        label=card['effectiveOffer']
        items.append(f'<article style="padding:20px 0;border-bottom:1px solid #dde5ed"><p style="color:#5e45a8;font-weight:bold">{html.escape(label)}</p><h2 style="font-size:17px">{html.escape(card.get("organization",""))}</h2><p>{html.escape(obj)}</p><p><strong>Encerramento:</strong> {deadline} (Brasília)</p><p><a href="{html.escape(card["pncpUrl"],quote=True)}">Conferir edital no PNCP →</a></p></article>')
        texts.append(f'{label} | {card.get("organization","")}\n{obj}\nEncerramento: {deadline} (Brasília)\n{card["pncpUrl"]}')
    if not cards and kind=='weekly':
        items.append('<p>Nenhuma candidata com prazo futuro foi selecionada neste resumo. Consulte o painel para ampliar os filtros.</p>')
    body=f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"></head><body style="margin:0;background:#f3f6fa;font-family:Arial,sans-serif;color:#20344a"><main style="max-width:640px;margin:24px auto;background:white;padding:28px;border-radius:16px"><p style="letter-spacing:2px;color:#6852b5;font-weight:bold">RADAR DE LICITAÇÕES</p><h1 style="font-size:25px">{title}</h1><p style="line-height:1.6">{intro}</p>{"".join(items)}<p style="margin-top:26px"><a href="{APP_URL}/" style="background:#283e56;color:white;padding:13px 20px;border-radius:8px;display:inline-block;text-decoration:none">Abrir meu Radar</a></p><p style="font-size:12px;color:#62758a">IA desligada. Sugestões não confirmam elegibilidade. Situação e prazos podem mudar; confira sempre o PNCP. Para ajustar os avisos, responda este e-mail.</p></main></body></html>'
    return 'Radar · '+title,body,'\n\n'.join(texts)+'\n\nAbrir Radar: '+APP_URL


def notify(db,kind,*,now=None,sender=send_reserved,fetcher=fetch_record,writer=None,dry_run=False):
    if kind not in ('weekly','urgent','test'):raise ValueError('Invalid notification')
    live_clock=now is None
    now=now or datetime.now(timezone.utc)
    recipients=email_list('RADAR_NOTIFY_EMAILS')
    if not recipients or not recipients<=email_list('RADAR_TEAM_EMAILS'):raise ValueError('Invalid team configuration')
    period=now.astimezone(TZ).strftime('%G-W%V') if kind=='weekly' else 'onboarding-v2' if kind=='test' else now.astimezone(TZ).date().isoformat()
    keys=[f'{kind}:{period}:{recipient}' for recipient in recipients]
    handled=db.execute('select count(*) from radar_mail_outbox where dedupe_key=any(%s)',(keys,)).fetchone()[0]
    if not dry_run and handled==len(recipients):return {'sent':0,'skipped':handled,'candidates':0,'kind':kind,'verified':0}
    cards=[];verified=0;check_errors=0
    if kind!='test':
        state=db.execute("select content from radar_catalog_state where id='publications'").fetchone()
        completed=datetime.fromisoformat(state[0]['completedAt'].replace('Z','+00:00')) if state else None
        if completed and completed.tzinfo is None:completed=completed.replace(tzinfo=TZ)
        stale=not completed or now-completed>timedelta(hours=72)
        rows=db.execute('''select o.card,r.offer,r.status from radar_opportunities o
            left join radar_review_state r on r.opportunity_id=o.id
              and r.example_object=o.payload->>'objetoCompra'
              and r.example_additional=coalesce(o.payload->>'informacaoComplementar','')
            where o.score>=40 and o.card is not null
              and o.payload->>'situacaoCompraId'='1'
              and o.payload->>'tipoInstrumentoConvocatorioCodigo' in ('1','2')
              and left(coalesce(o.payload->>'dataEncerramentoProposta',''),10)>=%s
            order by o.score desc limit 1001''',(now.astimezone(TZ).date().isoformat(),)).fetchall()
        if len(rows)>1000:raise ValueError('Candidate budget exceeded')
        examples=db.execute('select opportunity_id,offer,reason_code,object_hash,example_object,example_additional from radar_learning_examples').fetchall()
        if len(examples)>1000:raise ValueError('Learning example budget exceeded')
        examples=[dict(zip(('opportunity_id','offer','reason_code','object_hash','example_object','example_additional'),row)) for row in examples]
        learned=apply_examples([row[0] for row in rows],examples)
        rows=[(card,row[1],row[2]) for card,row in zip(learned,rows)]
        cards=select_cards(rows,kind,now)
        if cards:
            if writer is None:raise ValueError('Verified storage writer required')
            reviews={row[0]['id']:(row[1],row[2]) for row in rows}
            fresh,changed,check_errors=verify_shortlist(cards,reviews,fetcher=fetcher,writer=writer,now=now)
            verified=len(fresh)
            usable=[example for example in examples if example['opportunity_id'] not in changed]
            learned=apply_examples([row[0] for row in fresh],usable)
            decision_time=datetime.now(timezone.utc) if live_clock else now
            cards=select_cards([(card,row[1],row[2]) for card,row in zip(learned,fresh)],kind,decision_time)
        elif stale:
            # Never turn missing coverage into a reassuring empty weekly summary.
            raise ValueError('Collection is stale and no verified candidates are available')
        if kind=='urgent' and not cards:return {'sent':0,'skipped':len(recipients),'reason':'no_urgent_candidates'}
    subject,body,text=render_digest(cards,kind,now)
    if dry_run:return {'sent':0,'candidates':len(cards),'kind':kind,'verified':verified,'verificationErrors':check_errors,'dryRun':True}
    sent,skipped=0,0
    for recipient in sorted(recipients):
        # Urgent digest deduplicates each day; a deadline may appear on two consecutive days.
        identifier=reserve(db,recipient,kind,f'{kind}:{period}:{recipient}')
        if not identifier:skipped+=1;continue
        sender(db,identifier,recipient,subject,body,text);sent+=1
    return {'sent':sent,'skipped':skipped,'candidates':len(cards),'kind':kind,'verified':verified,'verificationErrors':check_errors}
