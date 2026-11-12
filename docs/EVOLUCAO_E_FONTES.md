# Nexo Radar · evolução e fontes

Revisão: 11/11/2026. Implementação em branch para revisão; não publicada nesta etapa.
O painel mantém **Public**. Gerico continua sem critérios comerciais confirmados.

## Cobertura demonstrável

A meta é percorrer os registros disponíveis e medir perdas, não atingir uma quantidade
arbitrária. Um milhão por semana não é uma premissa comprovada. Recebidos, identificadores
distintos, duplicatas, páginas, quarentena e indexação são medidas diferentes.

A varredura nacional consulta propostas abertas sem filtro de empresa/UF/modalidade.
Duas passagens completas precisam ter os mesmos identificadores e versões para
declarar consistência. Se a fonte mudar durante a leitura, os dados capturados continuam
disponíveis com cobertura não confirmada. Isso não prova um retrato transacional do
Brasil nem cobre registros que o órgão ainda não enviou ao PNCP.

O incremental diário consulta publicação e atualização com sobreposição de dois dias;
intervalos longos são retomados em janelas. Segunda às 07h de Brasília continua a
reconciliação nacional; domingo às 23h a manutenção arquiva registros, preservando
histórico e decisões. Agendamentos GitHub podem atrasar: monitoramento não substitui
capacidade de infraestrutura e acompanhamento de pendências.

## Matriz de fontes

| Fonte | Evidência conferida | Situação desta versão | Limite |
|---|---|---|---|
| [PNCP Consulta](https://pncp.gov.br/api/consulta/swagger-ui/index.html) | Consulta individual HTTP200 e coleta existente | Conector principal e recibos brutos implementados; testes locais | Publicação depende do órgão; consistência explicitamente medida |
| [PNCP itens/documentos](https://pncp.gov.br/manual/pt-br/latest/singlehtml/index.html) | Amostra real: 3 itens e 2 anexos para um identificador oficial | Enriquecimento paginado por itens e manifesto de anexos implementado | PDFs grandes, cifrados, digitalizados ou externos ficam pendentes |
| [Compras.gov.br](https://dadosabertos.compras.gov.br/swagger-ui/index.html) | Lista histórica, consulta por ID e itens HTTP200; identidade oficial conferida | Complemento estruturado implementado, pendente implantação | Não representa todos os municípios nem substitui a cobertura PNCP |
| [Querido Diário](https://docs.queridodiario.ok.org.br/pt-br/latest/utilizando/api-publica.html) | Documentação pública disponível; acesso de API sem sucesso neste ambiente | Conector preparado e desativado, pendente validação real | Diário não equivale a edital; associação requer identidade oficial |
| [INLABS](https://github.com/Imprensa-Nacional/inlabs/tree/master/public/python) | Scripts oficiais exigem login e senha | Depende de autorização e credencial própria; não integrado | Não usar credenciais de terceiros nem presumir acesso anônimo |
| [Dados MG](https://dados.mg.gov.br/pt_BR/dataset/portal_licitacoes_mg) | Catálogo público de licitações e itens por ano | Viável para avaliação de lacunas; não integrado | Medir atualidade, campos e sobreposição antes de habilitar |
| [TCE-MG](https://dadosabertos.tce.mg.gov.br/) | Sem API validada nesta avaliação | Sem acesso técnico validado; não integrado | Não inventar endpoint ou cobertura |
| Outros portais de disputa | Sem contrato de API validado nesta etapa | Não integrados | Avaliar lacuna e autorização individualmente |

A amostra Compras utilizada foi `00394502000144-1-010615/2025`: três itens retornaram
o mesmo controle PNCP. A amostra é histórica e não é apresentada como oportunidade
atual. Códigos de modalidade Compras e PNCP são campos diferentes.

## Referência ConLicitação

Foram consultadas [ferramentas públicas](https://conlicitacao.com.br/tutorial-ferramentas-plataforma/)
e os fluxos anunciados de busca, boletins e acompanhamento. O login autorizado retornou
usuário ou senha inválidos; a área interna não foi avaliada. Nenhuma identidade visual,
base privada, código proprietário ou API privada foi copiada.

Aplicações no Nexo: filtros nacionais no servidor, perfil versionado por empresa,
fila para revisar descartes, documentos com fonte/página, histórico oficial separado
do andamento interno, responsável e checklist. Análise jurídica por IA, concorrentes,
robô de lances e novas fontes não são anunciados como entregues.

## Qualidade e operação

O classificador diferencia objeto principal, contexto, exclusões e escopo misto.
Obra em auditório onde ocorrem palestras e seguro de participantes de cursos não
viram contratação de treinamento. Apoio às rotinas administrativas e ensino EAD
continuam detectáveis. Resultados de regras são explicáveis, não probabilidades.
Casos fora da seleção podem ser recuperados com decisão privada auditada.

Corpos PNCP são preservados antes da classificação; linhas inválidas seguem para
quarentena sem bloquear vizinhas válidas. Enriquecimento tem fila com tentativas,
retomada, token de posse e bloqueios explícitos. PDF roda em processo separado,
com limite de bytes, páginas, tempo e memória no Linux. Não executa conteúdo nem
contorna restrições. A extração é textual; OCR e análise jurídica não estão ativos.

Há limites atuais de armazenamento: captura para em 450MiB e documentos em 420MiB,
mantendo pendências. Uma base nacional com versões e PDFs exige dimensionamento,
retenção aprovada e armazenamento de objetos; o plano gratuito não garante essa
escala indefinidamente. Documentos excessivos permanecem identificados para revisão.

## Liberação

Aplicar primeiro em ambiente separado as migrações014–023, sem reexecutar as antigas.
Testar autenticação com o provedor real, MFA, TLS, escopos e envio simulado. O banco
temporário validou sintaxe e fluxos SQL; ele não substitui a homologação Supabase.
O código de backup foi preparado, mas cópia externa, agenda e restauração real
dependem de configuração própria. Consultar [operação de segurança](SECURITY_OPERATIONS.md).

Produção exige aprovação posterior ao resultado revisável; esta etapa não altera
senhas, dispara mensagens, habilita serviços pagos nem modifica dados publicados.
