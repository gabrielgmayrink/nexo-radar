# Nexo Radar · evolução e fontes

Revisão: 12/11/2026. Branch de revisão com preview; produção não promovida.
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
| [PNCP Consulta](https://pncp.gov.br/api/consulta/swagger-ui/index.html) | Propostas, publicações, atualizações, quatro detalhes e modalidades reais HTTP200 | Conector principal e recibos brutos implementados; testes locais e amostras HTTP reais | Publicação depende do órgão; consistência explicitamente medida |
| [PNCP itens/documentos](https://pncp.gov.br/manual/pt-br/latest/singlehtml/index.html) | Amostra real: 3 itens e 2 anexos para um identificador oficial | Enriquecimento paginado por itens e manifesto de anexos implementado | PDFs grandes, cifrados, digitalizados ou externos ficam pendentes |
| [Compras.gov.br](https://dadosabertos.compras.gov.br/swagger-ui/index.html) | Consulta por ID, 3 itens e 3 resultados HTTP200; identidade oficial conferida | Complemento estruturado implementado, pendente implantação | Não representa todos os municípios nem substitui a cobertura PNCP |
| [Querido Diário](https://docs.queridodiario.ok.org.br/pt-br/latest/utilizando/api-publica.html) | Documentação pública disponível; acesso de API sem sucesso neste ambiente | Conector preparado e desativado, pendente validação real | Diário não equivale a edital; associação requer identidade oficial |
| [INLABS](https://github.com/Imprensa-Nacional/inlabs/tree/master/public/python) | Scripts oficiais exigem login e senha | Depende de autorização e credencial própria; não integrado | Não usar credenciais de terceiros nem presumir acesso anônimo |
| [Dados MG](https://dados.mg.gov.br/pt_BR/dataset/portal_licitacoes_mg) | API CKAN respondeu com 52 recursos CSV/JSON por ano | Viável para avaliação de lacunas; não integrado | Medir atualidade, campos e sobreposição antes de habilitar |
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

Aplicar primeiro em ambiente separado as migrações014–017 e019–027, sem reexecutar as antigas.
Testar autenticação com o provedor real, MFA, TLS, escopos e envio simulado. O banco
temporário validou sintaxe e fluxos SQL; ele não substitui a homologação Supabase.
Backup e restauração real foram validados em PostgreSQL local descartável; cópia externa e agenda dependem de configuração própria. Consultar [operação de segurança](SECURITY_OPERATIONS.md).

Produção exige aprovação posterior ao resultado revisável; esta etapa não altera
senhas, dispara mensagens, habilita serviços pagos nem modifica dados publicados.

## Reavaliação individual dos portais

| Fonte | Método identificado / tipo de dado | Estado e próxima ação |
|---|---|---|
| [Portal de Compras Públicas](https://www.portaldecompraspublicas.com.br/parceiros) | API de parceiros com token/aprovação; documentação anuncia escopo de processos finalizados | Novas solicitações informadas como temporariamente suspensas na página consultada. Não integrada; solicitar acesso autorizado quando reabrir e verificar escopo de abertas |
| [BLL Compras](https://bll.org.br/) | Portal anuncia integração PNCP; acesso técnico via suporte | Sem API pública de leitura validada; não integrada; solicitar contrato técnico antes de implementar |
| [BNC](https://bnc.org.br/) | Portal anuncia integração PNCP | Sem API pública autorizada validada; não integrada; verificar autorização e lacuna antes de desenvolver |
| [BBMNET](https://bbmnet.com.br/cadastro-formulario-de-acesso-manual-de-integracao/) | Manual técnico condicionado a solicitação de acesso | Solicitação não enviada; não integrada; titular pode obter autorização/manual |
| [Licitanet](https://licita-sso.licitanet.com.br/) | Acesso autenticado para contas autorizadas | Não há API pública de leitura validada nesta pesquisa; não integrada |
| Licitar Digital | Nenhum contrato de leitura autorizado confirmado | Não integrada; confirmar interface oficial e escopo |
| Licitações-e | Nenhum contrato de leitura autorizado confirmado | Não integrada; confirmar interface oficial e escopo |
| TCE-MG | Catálogo de dados públicos, sem endpoint de coleta de abertas validado aqui | Não integrado; avaliar datasets e campos com evidência antes de implementar |
| Portais municipais/estaduais | Avaliação individual; sem conector genérico anunciado | Não integrados indiscriminadamente; medir lacuna, acesso e identidade oficial por portal |

As afirmações sobre interfaces acima refletem a documentação consultada, não ausência
universal de uma API. Não foram usadas credenciais de terceiros, scraping de login
ou endpoints privados. Publicação dos mesmos processos no PNCP não prova cobertura
integral do portal: a lacuna deve ser medida, não presumida.

Dados MG: metadados reais em
[package_show](https://dados.mg.gov.br/api/3/action/package_show?id=portal_licitacoes_mg).
Arquivos CSV foram identificados, mas não importados: falta medir atualidade, IDs,
volume e ganho efetivo além do PNCP. Querido Diário continua desativado após nova
falha de transporte. Nenhuma dessas fontes conta como cobertura operacional adicional.
