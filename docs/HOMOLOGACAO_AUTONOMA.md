# Homologação autônoma · 12 de novembro de 2026

## Resumo executivo

Versão implementada e testada na branch de revisão, com preview Vercel. **Ainda não liberada para produção**: faltam Supabase independente de homologação, validação de Auth/MFA nesse provedor e destino de backup externo. O login do preview informa indisponibilidade enquanto suas variáveis próprias não existirem. O teste local usa rotas e PostgreSQL reais com provedor de identidade fictício, declaradamente.

Public mantém o nome confirmado pelo titular e os quatro grupos de serviços informados, sem TI. Gerico não recebeu segmentos inventados. Critérios, avaliações, anotações, responsáveis, checklist e histórico comercial são privados por empresa; os dados públicos são centrais.

Não houve merge, promoção de deploy, alteração de configuração nem migração produtiva. A produção permanece no commit `d10525f`. Conexão ao banco existente somente de leitura. SMTP autenticado sem enviar mensagem. Nenhum serviço pago, WhatsApp ou fonte restrita foi ativado.

## Conferência dos 16 itens da solicitação

| Pedido | Entrega / evidência | Limite ou pendência |
|---|---|---|
| 1. Continuidade | Branch e arquitetura preservadas | Sem reconstrução do projeto |
| 2. Execução autônoma | Implementações, testes, documentação, commits e preview | Dependências externas abaixo |
| 3. Integrações reais | PNCP e Compras consultados; matriz de fontes | Amostra não equivale a varredura nacional completa |
| 4. Confiabilidade | Recibos antes do parse, quarentena, retomada, idempotência, conferência por ID/versão | Fonte em movimento não recebe cobertura artificial |
| 5. Empresas e perfis | Produtos, serviços, termos, sinônimos, exclusões, UF/cidade, modalidade, valor, órgãos e notificações editáveis | Nome Public preservado por sua confirmação; mais empresas exigem provisionamento |
| 6. Busca | Filtros SQL, paginação, itens, acentos, frases, exclusões, sinônimos e recuperação de descartes | Itens precisam de enriquecimento; triagem não garante elegibilidade |
| 7. Interface | Login, painel, filtros, detalhes, avaliação, histórico, critérios e monitoramento examinados | Mobile em quadro 390×844, não aparelho físico |
| 8. Acompanhamento | Vou participar, descarte/motivo, notas, responsável, checklist, mudanças e histórico | SMTP verificado sem envio; entrega completa a destinatário de teste pendente |
| 9. Backup | Cifra, integridade e restauração real isolada; upload e agenda preparados | Destino externo/credenciais/retenção não provisionados |
| 10. Segurança | Autorização, sessões, limites, URLs fixas, PDF isolado, TLS e auditorias | Papéis restritos parcialmente conectados; Auth/MFA real pendente |
| 11. Testes | 250 Python aprovados, PostgreSQL real, verificações frontend e build | E2E local com Auth fictício |
| 12. Desempenho | Paginação, índices, debounce, cancelamento, cache por consulta/empresa e lotes | Sem benchmark em milhões de registros nesta homologação |
| 13. Produção | GitHub/Vercel compatíveis; preview protegido | Publicação definitiva depende das etapas críticas e aprovação posterior |
| 14. Git e documentos | README, instalação, fontes, segurança, evidências e capturas atualizados | Branch de revisão, sem force push |
| 15. Relatório | Este documento e arquivos relacionados | Resultado e ações abaixo |
| 16. Critérios finais | Evidências reais/locais diferenciadas e recuperação demonstrada | Sem declarar prontidão produtiva antes das etapas externas |

## Alterações realizadas

- Coleta nacional sem filtro comercial, UF ou modalidade; seleção depois da captura. Duas passagens completas devem coincidir em IDs e hashes para confirmar consistência; contagens iguais não bastam.
- Incremental diário por publicação e atualização, sobreposição de dois dias, janelas de retomada, timeout/retry/backoff e cursor preservado em falhas.
- Corpo original preservado antes de interpretar; quarentena de linha inválida sem perder vizinhas; identidade oficial evita duplicidade entre fontes.
- Histórico oficial de prazo, objeto, situação, valor e link separado da avaliação da equipe. Arquivamento preserva acompanhamentos e histórico.
- Busca paginada e combinada por objeto, itens, UF, cidade, órgão, modalidade, fonte, valor, período, situação, prazo e relevância; frases, exclusões, acentos, maiúsculas, flexões e sinônimos. Busca fora da seleção recupera até pontuação zero.
- Triagem por intenção principal: obra em auditório e tratamento acústico de sala de aulas não viram contratação de capacitação/EAD. Escopos mistos vão para revisão; regra não é probabilidade.
- Perfis versionados e auditados; produtos/órgãos configuráveis, resumo semanal e alerta urgente por empresa. Preferências regionais também conferidas após consulta individual da fonte.
- Detalhes com itens, arquivos, trechos/páginas e limitações. Histórico privado das avaliações agora visível; responsável e checklist persistem no reload.
- Diagnóstico de fontes para responsáveis/administradores; endpoint somente de leitura. Reprocessamento administrativo continua por job autenticado, não por botão público.
- Sessão corrigida no PostgreSQL real, revogação e contexto de credencial reforçados. Migração 015 expira sessões antigas quando aplicada.
- TLS `verify-full`, CA pública oficial incluída no pacote Python. Conexão de leitura ao Supabase existente validada, sem downgrade.
- Restauração recusa banco não vazio; falha de descriptografia não apaga destino preexistente. Migração exige arquivo de ambiente e projeto explícitos.

Arquivos principais: `src/radar/` (captura, catálogo, relevância, perfis, notificações, autenticação, TLS, papéis, backup e fontes); `api/{index,detail,profile,team,health}.py`; `web/src/{Dashboard,OpportunityDetails,CompanyProfileEditor,SourceHealthPanel,ReviewForm}.tsx`; scripts de migração, backup e aceite; workflows. O diff da branch traz a relação completa.

Migrações entregues: **014–017 e 019–027**; não existe arquivo 018. Cobrem recibos, segurança, reclassificação, operação do catálogo, eventos, enriquecimento, perfis, papéis, posse da fila, visibilidade inicial, busca de itens, normalização Unicode e escopo Public. Aplicadas no banco descartável; **não na produção**. Nunca reaplicar migração antiga com recibo existente.

## Integrações reais e cobertura

Evidência sanitizada: [validation/2026-11-12.json](validation/2026-11-12.json). Requisições em 11/11 Brasília, algumas já em 12/11 UTC.

| Fonte | Resultado observado | Limite / estado |
|---|---|---|
| PNCP propostas abertas | Páginas 1 e 2 com 50 registros cada; fonte informou **38.138 registros / 763 páginas** | Não reexecutada toda a varredura nesta homologação |
| PNCP publicações | Janela 01–07/11/2025, modalidade 6: 50 de 9.192 | Amostra histórica de período/paginação |
| PNCP atualizações | Sete dias excederam 15s; janela de 01/11/2025 retornou 23/23 em 3.906ms | Falha lenta registrada, seguida de sucesso |
| PNCP detalhes | Quatro IDs de PR/MG/RS/SP, identidade, órgão, cidade, UF e versão conferidos | Sem caso natural de suspensão/retificação nessas quatro amostras |
| PNCP modalidades | Catálogo oficial 1–19 | Coleta não limitada a algumas modalidades |
| PNCP itens/anexos | ID `00394502000144-1-010615/2025`: 3 itens e 2 documentos | Manifesto único; itens paginados |
| PDF oficial PNCP | Brumado `14105704000133-1-000067/2026`: 1 item, 1 arquivo e texto extraído exibido | Até 30 trechos na tela; não representa a contagem total de páginas |
| Compras.gov.br | Mesmo ID histórico: 1 contratação, 3 itens, 3 resultados, identidade PNCP exata | Complemento da contratação existente, sem nova oportunidade duplicada |
| Querido Diário | Nova tentativa: `transport_unavailable` | Preparado/desativado, não operacional |
| Dados MG | API CKAN retornou 52 recursos CSV/JSON | Metadados validados; arquivos não importados, lacuna adicional não medida |

IDs individuais: `00394460000141-1-000224/2022`, `18715615000160-1-000225/2022`, `88349238000178-1-000001/2023`, `46634507000106-1-000144/2023`. Códigos de modalidade PNCP e Compras são domínios diferentes.

A [matriz de fontes](EVOLUCAO_E_FONTES.md) registra método, cobertura, evidência e autorização de cada fonte adicional. INLABS requer credenciais; portais de disputa não foram considerados integrados por possuírem páginas públicas. Nenhum CAPTCHA/API privada foi contornado. ConLicitação: referência pública; login autorizado não funcionou.

Campos nulos, prazo/situação alterados, ausência de anexos, HTTP inválido, resposta parcial, repetição de página e suspensão possuem testes determinísticos. **Não foram todos observados naturalmente na amostra real**. Ampliar esses casos em staging.

Não há fundamento para garantir um milhão por semana. O sistema mede o disponibilizado pelas fontes. Não fabrica volume nem considera cobertura completa apenas por terminar um job. Registros ausentes no PNCP exigem outra fonte autorizada.

## Segurança e desempenho

Cookie produtivo `__Host-`/HttpOnly/Secure/SameSite Strict; identidade e empresa resolvidas no servidor. Endpoints negam acesso a outra empresa. SQL parametrizado; React não executa texto dos documentos como HTML. Downloads fixados ao host e ID oficial, sem redirecionamento; URLs externas permanecem links.

PDF: até 3MiB, 80 páginas e 20s em subprocesso; Linux limita memória a 512MiB e CPU a 15s. Digitalizados, protegidos e falhos exigem conferência. Tela limita itens/trechos/fontes e informa recortes. Não há OCR, análise jurídica automática nem execução de conteúdo recebido.

Migração 022 prepara papéis NOLOGIN/NOBYPASSRLS. Contexto restrito testado localmente e conectado a perfil/avaliações. Outras rotas ainda dependem da autorização explícita do servidor. **Credencial administrativa pode ultrapassar RLS**; `RADAR_DB_ENFORCE_ROLES=0` até provisionar credenciais distintas e homologar o fluxo inteiro.

Página de 12/24/48 itens, filtros SQL, cache por empresa/consulta, cancelamento e debounce; fila e lotes para enriquecimento. Sem benchmark de carga nacional. Armazenamento interrompe captura em 450MiB e documentos em 420MiB com pendências explícitas; plano gratuito não garante escala ilimitada.

## Validação visual

Navegador: login Public, logout, login Gerico, painel, busca com acentos/UF, detalhes, itens/PDF, avaliação, Vou participar, responsável, checklist, histórico privado, edição auditada de critérios e diagnóstico. Gerico com estado vazio e somente sua navegação, sem avaliações Public. Console conferido sem erros/avisos capturados.

O servidor local usa handlers reais e PostgreSQL 18. Só o provedor Auth é fictício. Cookie HTTP local tem nome próprio, sem alterar o cookie seguro produtivo. Ferramentas de teste recusam banco remoto e não carregam dotenv.

Mobile: quadro 390×844, área útil 380px pela rolagem, sem excesso horizontal medido; menu móvel abriu. O controle de viewport disponível não aplicou a dimensão, por isso foi usado iframe local. Não se afirma teste físico ou de todos os tamanhos possíveis.

[Capturas](screenshots/2026-11-11/): login, painel, busca, avaliação, perfil, Gerico, monitoramento, documentos, histórico e menu móvel. Dados públicos com contas fictícias.

## Testes e falhas corrigidas

- **250 testes Python aprovados, zero ignorados** com PostgreSQL 18 configurado: migrações, busca SQL, isolamento, quarentena, IDs/versões, eventos, autorização, perfis, notificações, bootstrap e backup.
- Ruff aprovado para sintaxe/nomes indefinidos (`E9,F821,F822,F823`); não equivale a toda regra de estilo e nenhum verificador existente foi desligado.
- TypeScript + build Vite aprovados; verificações frontend de busca, token, cache e isolamento aprovadas.
- npm e Python sem vulnerabilidades conhecidas na auditoria. Setuptools atualizado de 80.9.0 para 84.1.0 após os avisos encontrados. Isso não certifica ausência de toda falha.
- Wheel gerado com CA pública incluída; scanner de padrões de segredos aprovado, sem imprimir valores. Não substitui auditoria integral do histórico Git.
- Restauração PostgreSQL e consultas HTTP reais, além de testes determinísticos.
- **Não executados:** E2E Supabase Auth/MFA, entrega completa de e-mail de teste e carga nacional, por ausência de staging/credenciais ou por limites do ensaio. Nenhuma mensagem a clientes reais.

Falhas corrigidas na homologação: conjunto Python como parâmetro SQL na sessão; incremental invisível antes do primeiro fechamento; responsável/checklist incompletos no reload; acentos maiúsculos em locale C; parâmetros excedentes com perfil desativado; acompanhamentos encerrados ocultos; falso positivo de acústica; destino de descriptografia preexistente; manifesto/URL alternativos oficiais; página complementar repetida; histórico privado retornado pela API sem aparecer na tela.

## Backup e recuperação

Arquivo final AES-GCM: **2.139.225 bytes**, SHA256 `95966ada2bbbb2738a3b10a3788f41748d0963e9e7fbbeb193e730688260f7e9`. Validado e restaurado em banco local vazio diferente: **33 tabelas / 73 registros**, mesmas contagens e hashes de conteúdo. Fixtures de Auth e amostras públicas; não é cópia da produção.

Arquivo fora do Git: `../nexo-backup-validation/final-acceptance.nexo-backup`. Chave efêmera do ensaio não retida; não usar como cópia operacional. Origem/destino descartáveis `radar_restore_test_*` em loopback.

Upload S3 privado com SHA256, metadados e conferência por download preparado em `scripts/backup_upload.py`; workflow diário 03h41 Brasília preparado e **desativado**. Sem bucket/credenciais não se afirma upload externo nem backup produtivo ativo. Retenção via lifecycle no bucket; script não elimina backups. [Procedimento completo](SECURITY_OPERATIONS.md).

## Git, CI e preview

Branch `codex/seguranca-cobertura-qualidade`, repositório privado [gabrielgmayrink/nexo-radar](https://github.com/gabrielgmayrink/nexo-radar). Commits anteriores: `ee7db18`, `8325c9c`; entrega final consultável no histórico da branch. Sem force push nem transferência de código corporativo externo ao escopo.

[CI de 8325c9c](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43142323747) aprovada com PostgreSQL real. [SMTP](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43143283406): `smtpAuthenticated=true`, `emailSent=false`; agenda existente não alterada.

[Preview inicial](https://nexo-radar-61bijcc9p-gabriels-projects-6ec97526.vercel.app/) Ready, protegido pela Vercel. Titular alcançou o login; aplicação informa indisponibilidade sem banco/Auth próprios de staging. HTTP401 da proteção Vercel não valida autorização da aplicação. Git gera preview automaticamente; proteção mantida, segredos produtivos não copiados. Resultados da entrega final serão registrados no encerramento abaixo.

## Pendências e ações do titular

### Críticas para produção

1. **Staging independente:** criar Supabase separado na sua conta, em plano autorizado. Provisionar variáveis próprias de `.env.example` e Vercel → nexo-radar → Settings → Environment Variables → Preview desta branch. Guardar segredos nos provedores, sem enviá-los ao chat. Não apontar Preview à produção.
2. **Migrações/identidade:** bootstrap com arquivo staging/ref explícitos; testar contas Public/Gerico, acesso negado cruzado, senha, revogação, convite/link, MFA e recuperação. Provisionar papéis próprios e completar validação antes de exigir MFA ou ativar privilégios restritos.
3. **Backup externo:** fornecer bucket privado autorizado, credencial restrita ao prefixo, chave AES separada e retenção. Executar upload/download e restauração isolada; só então habilitar agenda.
4. **Liberação:** revisar CI/preview completo, dimensionar armazenamento e executar varredura nacional com relatório de páginas/IDs/versões/quarentena. Aprovar versão exata antes de merge/migração/promoção. Volume real pode ser muito menor que um milhão.

### Dependem de credenciais ou confirmação

- Alterar no provedor as credenciais anteriormente expostas no chat e atualizar ambientes autorizados. Não reproduzir senhas em mensagens/Git.
- Confirmar destinatário de teste para ensaio de entrega. Autenticar SMTP não garante recebimento na caixa de entrada.
- Informar produtos/serviços Gerico antes de ativar sua seleção.
- Fornecer autorização/credencial específica para fontes restritas desejadas.

### Opcionais / posteriores

OCR, fontes adicionais após medir lacunas reais, WhatsApp com infraestrutura autorizada, monitor independente dos provedores atuais, armazenamento de objetos, benchmark em escala, mais empresas e testes físicos em mais dispositivos. Não anunciados como operacionais nem contratados nesta versão.

## Encerramento da entrega

- Código final: `79c463a39532bbb70581caa5bd2a9f8600a1a53a`, enviado à mesma branch privada.
- [CI final do código aprovada](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43148277835), incluindo PostgreSQL18, testes, Ruff, auditorias e build.
- [Preview final do código](https://nexo-radar-bxbxtpklf-gabriels-projects-6ec97526.vercel.app/): Vercel Ready; login visual alcançado, com indisponibilidade de Auth por falta do ambiente de staging documentado.
- [PR #1 em rascunho](https://github.com/gabrielgmayrink/nexo-radar/pull/1), sem merge. `main` conferida em `d10525f5c5e5ef763b2f937f797dc6e5aaa453ae`.
- Instalação das migrações e carga dos três snapshots públicos reproduzidas em um segundo banco local vazio, com sucesso e zero mensagens externas.
- Servidor HTTP e PostgreSQL temporários encerrados. Binários e dados descartáveis removidos depois dos testes; arquivos de código, capturas e evidências preservados.
- Documentação/capturas finais serão enviadas no commit seguinte, sem alteração do código já aprovado. Estado do workspace e sincronismo remoto conferidos na entrega.

Precisões adicionais da conferência: a lista privada “Vou participar” registra interesse/acompanhamento; não foi criada uma estrela de favorito independente. Alternância entre empresas para usuário vinculado às duas existe, mas não foi exercitada visualmente nesta rodada; foram conferidos os logins separados e o isolamento. Reprocessamento de integrações permanece em rotinas autenticadas, sem botão administrativo de mutação no painel. Esses limites não são apresentados como recursos adicionais validados.
