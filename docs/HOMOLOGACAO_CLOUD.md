# Homologação em nuvem · 12/11/2026

## Estado da entrega

Ambiente independente de homologação provisionado na conta pessoal Vercel, com Supabase Free em São Paulo, migrações e contas fictícias. Login real, segundo fator, isolamento entre empresas, avaliação persistida e backup externo restaurado foram efetivamente testados. O código está na branch `codex/seguranca-cobertura-qualidade`, no [PR #1 em rascunho](https://github.com/gabrielgmayrink/nexo-radar/pull/1).

[Abrir homologação](https://nexo-radar-git-codex-seguranc-bb7f58-gabriels-projects-6ec97526.vercel.app/). A sessão de teste do navegador é da Public. As contas desta prévia são fictícias; as credenciais dos clientes em produção não foram copiadas para ela. O alias da branch é o endereço canônico do ambiente; origens diferentes são recusadas nas operações de escrita.

**Produção ainda não liberada.** Nenhum merge, promoção, configuração ou migração produtiva foi realizado nesta etapa. O pedido de continuação reserva a publicação definitiva para aprovação posterior do titular. O commit produtivo de referência é `d10525f5c5e5ef763b2f937f797dc6e5aaa453ae`.

Public conserva o nome e os quatro grupos confirmados: apoio administrativo/documental, gestão empresarial pública/privada, palestras e desenvolvimento profissional/gerencial, EAD. TI foi removida. Gerico permanece sem seleção comercial ativa até receber seus serviços; nenhuma atividade foi inventada.

## Infraestrutura e configuração

- Projeto Supabase de homologação: `odntvxflshrwxhdqtepm`, PostgreSQL 17.11, Free, região São Paulo. Migrações 001–028 aplicadas somente nele; não existe migração 018.
- Prévia Vercel com 28 variáveis próprias da branch, incluindo as substituições das configurações da integração de banco. Chaves de servidor protegidas; identificadores públicos de Auth não são segredos.
- Contas QA exclusivas de Public, Gerico e administrador vinculado às duas. Criação confirmada pelo provedor sem envio de e-mail.
- E-mail, IA e agendamentos de coleta da prévia desabilitados. A coleta de teste foi iniciada explicitamente com conexão limitada ao projeto de homologação, sem usar o receptor produtivo.
- Blob **privado** dedicado `store_XOKlrw7kBJJ7KJcx`, sem arquivos públicos nem plano pago ativado.
- Após autorização específica do titular, três segredos exclusivos de homologação foram cadastrados no GitHub Actions: banco de teste, chave AES de backup e token do Blob privado. Não foram enviados segredos produtivos.

O funcionamento depende dos limites gratuitos: proteção do banco em 450MiB, enriquecimento em 420MiB e orçamento do script de backup em 512MiB. Ao atingir proteção, a rotina preserva os dados e informa pendência. O plano gratuito não comporta crescimento ilimitado de recibos e documentos.

## Autenticação, autorização e MFA reais

Testes contra Supabase Auth, sem provedor fictício:

1. Public e Gerico autenticam com senhas próprias de teste.
2. Acesso cruzado negado pelo servidor nos dois sentidos.
3. Administrador com exigência de MFA não entra apenas com senha.
4. Código de segundo fator incorreto é recusado; TOTP válido produz sessão `aal2`.
5. Administrador autenticado acessa suas duas empresas; alternância exercitada no painel.
6. Sessão revogada deixa de autorizar chamadas.
7. Acesso anônimo direto às tabelas de perfis, avaliações e vínculos é negado.

No navegador publicado foram exercitados login Public, busca, detalhes, avaliação, responsável/checklist, histórico, logout, MFA administrativo, alternância, login Gerico e negação cruzada nas rotas. A Gerico exibe exclusivamente sua própria navegação e estado de configuração pendente.

Correções encontradas na integração real:

- O Supabase retorna QR SVG com declaração XML e tamanho superior ao limite antigo. O código valida estrutura, tamanho e elementos perigosos antes de gerar a imagem; não executa SVG recebido como HTML.
- Uma inscrição MFA abandonada reservava o nome amigável. Novas inscrições recebem nome único, sem apagar fatores existentes.
- No PostgreSQL 17 do provedor, `postgres` tinha administração do papel sem permissão de `SET ROLE`. O vínculo foi corrigido **em homologação** e o contexto `radar_web` foi validado com leituras e escrita cruzadas negadas.

`RADAR_DB_ENFORCE_ROLES=1` está ativo na prévia para os caminhos conectados a `company_transaction`: perfis e avaliações. **Ainda há conexão administrativa no servidor e caminhos protegidos pela autorização explícita da aplicação.** Não se afirma que todas as consultas usam credenciais independentes de menor privilégio. Esse endurecimento e a troca das credenciais produtivas permanecem itens de liberação.

## Coleta nacional e qualidade

A rota oficial utilizada é `/v1/contratacoes/proposta`, com `dataFinal=99991231`, páginas de 50 e sem filtro de empresa, UF, modalidade ou publicação. O limite de 50 foi conferido no [schema oficial](https://pncp.gov.br/api/consulta/v3/api-docs). O PNCP informou aproximadamente 38,3 mil contratações abertas durante o ensaio; não há fundamento para prometer um milhão por semana.

O progresso e os totais finais desta execução são registrados na evidência sanitizada vinculada ao fim deste relatório. Há duas leituras completas: terminar a captura não basta para provar cobertura. Os conjuntos de identificadores e hashes precisam coincidir. Mudanças durante a leitura mantêm `coverageComplete=false`.

Foi corrigida uma perda de visibilidade: quando duas passagens divergem, a conclusão preserva a **união dos identificadores observados**, em vez de ocultar os encontrados apenas na primeira. A alteração tem regressão com PostgreSQL real, verificando os três identificadores do exemplo A/B → B/C no catálogo. Não se conclui que um registro foi encerrado apenas por não aparecer numa página móvel.

A retomada real foi exercitada no mesmo identificador de execução após paradas controladas. O cursor avançou apenas a partir do último lote confirmado. Originais e recibos são preservados antes da classificação; a quarentena não descarta os demais registros da página.

Falsos positivos identificados nos dados reais foram corrigidos: software com treinamento acessório, clipping que menciona um setor de assessoria, inventário de emissões com capacitação acessória e apresentação artística cujo fornecedor possui “assessoria e treinamento” no nome. Cursos e palestras efetivamente contratados sobre esses assuntos continuam elegíveis. Escopos mistos continuam sujeitos à revisão; pontuação não é probabilidade nem parecer jurídico.

As fontes adicionais e os ensaios de PNCP/Compras continuam documentados na [matriz de fontes](EVOLUCAO_E_FONTES.md) e no [relatório anterior](HOMOLOGACAO_AUTONOMA.md). Esta rodada não transforma consultas de metadados de outros portais em conectores operacionais. WhatsApp/Evolution, OCR e fontes restritas não foram ativados.

No banco em nuvem, o ID `46694121000181-1-000121/2026` teve 12 itens, dois documentos e trechos de um PDF oficial recuperados. A interface exibe fonte/página e o limite de 30 trechos, com extração parcial e segundo documento ainda pendente. Não se confunde esse recorte com edital integralmente analisado nem com conclusão de toda a fila de enriquecimento.

## Desempenho medido

A busca foi medida no Supabase de homologação com aproximadamente 38 mil registros enquanto a coleta continuava. O plano de execução mostrou repetição da normalização de texto sobre a base inteira.

A migração 028 prepara texto de busca, tamanho do objeto normalizado, município, órgão e datas no momento da gravação/alteração do payload. O gatilho também atualiza os campos nas retificações. Os dados oficiais e os critérios de pesquisa foram preservados. Teste real verifica que uma expressão antiga desaparece e a nova passa a ser encontrada após alteração do objeto; datas inválidas tornam-se nulas.

| Consulta | Antes | Depois |
|---|---:|---:|
| Lista da empresa | 8.812ms | 1.765ms |
| Texto “capacitação” | 10.125ms | 1.532ms |
| Estado MG | 2.078ms | 2.250ms |
| Outros objetos do acervo | 3.531ms | 2.031ms |

São observações pontuais, sem carga concorrente de usuários, com fonte e cache em movimento. Não representam percentis, garantia de latência ou benchmark de escala. O filtro de estado não apresentou melhora nesta amostra. Contagens podem variar por horário, encerramento e reclassificação. A tela continua paginada e não baixa a base nacional inteira.

## Backup externo e restauração

[Ensaio aprovado no GitHub Actions](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43232137572), somente na branch de revisão e com banco de homologação:

- Snapshot de origem **somente de leitura**, transacional e compartilhado com `pg_dump`.
- Cópia SQL completa de 73 tabelas dos schemas auth/public/realtime/storage/vault, somando **96.149 linhas** naquele snapshot. Linhas de tabelas não equivalem a licitações.
- Arquivo AES-256-GCM de **71.527.227 bytes**, carregado no Blob privado.
- Download independente, checksum conferido, descriptografia e restauração em banco local vazio e descartável no runner.
- Mesmas contagens e hashes de conteúdo em todas as tabelas verificadas.
- SHA256 do arquivo cifrado: `3692ba14fef75a42a36f4c1dc72eb7d71bbcc781112069178a825411a311fbf1`.

O teste encontrou e corrigiu dois problemas operacionais: uso da CLI que exigia identidade geral Vercel no runner, substituída pelo SDK com token limitado ao Blob; e falta de privilégios de restauração no banco descartável, corrigida com usuário administrativo **somente no destino local**. A origem permaneceu intacta. A dependência transitiva vulnerável do SDK foi atualizada e a auditoria passou sem alertas conhecidos.

O ensaio prova restauração dos dados SQL. Não prova recuperação da plataforma Supabase inteira: serviços Auth, chaves de assinatura/configuração, integrações e arquivos binários externos do Storage exigem seus próprios procedimentos. Não foi restaurado nada sobre produção.

O arquivo cifrado permanece no Blob. A chave de recuperação fica separada, nos segredos autorizados e na configuração local ignorada pelo Git. O titular deve manter sua cópia num gerenciador de senhas. Não é uma chave efêmera descartada.

O script usa caminhos imutáveis por hash, valida o host privado, rejeita texto puro e confere download. Retenção do código: mínimo de 7 dias, remoção optativa e preservação de pelo menos duas cópias mais novas. Não foi executada remoção. O limite de 512MiB pode impedir novos backups antes de completar sete cópias; nesse caso é preciso dimensionar retenção/destino, sem apagar silenciosamente nem contratar plano.

Após o sucesso, o gatilho automático do ensaio foi desligado para evitar novas cópias a cada commit. **Backup produtivo diário ainda desativado**. A rotina S3 preparada não foi anunciada como validada; o destino validado nesta etapa é Blob privado.

## Validação e arquivos

CI com PostgreSQL 18 real, migrações, testes de integração, Ruff de sintaxe/nomes indefinidos, auditorias Python/npm, scanner de credenciais, TypeScript, build Vite e verificações de busca/cache/token. Resultados finais e capturas são vinculados na evidência da entrega.

Arquivos novos principais: `migrations/028_catalog_search_projection.sql`, `scripts/backup_blob.py`, `scripts/blob_transport.mjs`, `scripts/verify_staging_backup.py`, dependências operacionais com lock e `.github/workflows/backup-staging.yml`. Também foram alterados MFA, triagem do objeto, catálogo SQL e texto do progresso. Não há segredos nos arquivos versionados.

[Capturas reais desta rodada](screenshots/2026-11-12/). Os testes responsivos locais em quadro 390×844 permanecem documentados no relatório anterior; não se afirma teste físico de todos os dispositivos.

## Pendências para liberação

1. Titular revisar versão exata e autorizar migração/merge/promoção produtiva. Fazer backup anterior à migração e conservar o deploy anterior.
2. Substituir credenciais que circularam no chat e completar credenciais independentes por serviço. Aplicar papéis, MFA e recuperação em produção somente após validar seu contexto.
3. Definir orçamento/capacidade para histórico bruto, documentos e retenção de backups; a coleta nacional não torna o plano gratuito ilimitado.
4. Provisionar destino e segredos **produtivos** de backup com aprovação específica; habilitar agenda e ensaio de recuperação periódico.
5. Confirmar destinatário de teste antes de qualquer e-mail. SMTP autenticado não comprova recebimento; não houve mensagens a clientes nesta etapa.
6. Informar serviços Gerico e infraestrutura autorizada para WhatsApp se ainda desejado.

Falhas de integração não foram disfarçadas: o histórico dos jobs conserva as tentativas malsucedidas anteriores ao ensaio aprovado. O estado atual deve ser avaliado pelas evidências de sucesso e pelos limites acima.
