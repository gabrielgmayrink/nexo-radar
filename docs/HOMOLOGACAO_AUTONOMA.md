# Homologação autônoma · 11 de novembro de 2026

O painel mantém Public, com o escopo confirmado e sem serviços de TI. Gerico
permanece sem segmentos inventados. Produção não foi modificada nesta execução.

## Evidência já obtida

- APIs reais: duas páginas de propostas abertas, publicações, quatro detalhes
  individuais de UFs diferentes, modalidades1–19, itens e anexos PNCP; consulta
  por ID, itens e resultados do Compras.gov.br. A amostra não equivale a varredura
  nacional completa. A rota de atualização excedeu15s e ficou registrada como falha.
- A fonte de propostas informou38138 registros e763 páginas na consulta realizada.
  Não se fabricam registros para atingir um milhão por semana.
- TLS do banco existente: conexão de leitura com `verify-full` validada após incluir
  o certificado público indicado no próprio painel Supabase. Nenhum ajuste do banco
  ou credencial produtiva foi feito. Certificado distribuído em `radar/certificates`,
  SHA256`700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7`.
- PostgreSQL18 nativo local: migrações e oito testes de integração executados;
  suíte completa238 testes aprovada, sem ignorados quando o banco está configurado.
- Auditorias: npm sem vulnerabilidades conhecidas; Python sem avisos conhecidos
  após atualizar setuptools80.9.0 para84.1.0. Isso não certifica ausência de toda falha.
- Backup: arquivo AES-GCM de121556 bytes restaurado em outro banco local vazio;
  contagens e hashes das32 tabelas daquele snapshot, total52 linhas, coincidiram.
  O teste contém contas fictícias e amostras públicas; não é backup da produção.

## Correções encontradas pela homologação

1. Sessão falhava no PostgreSQL real porque recebia um conjunto Python em parâmetro
   SQL; agora recebe lista ordenada. Teste de regressão acrescentado.
2. O primeiro incremental ficava invisível antes de existir um fechamento nacional;
   migração024 permite consultar registros já capturados sem afirmar cobertura total.
3. Responsável/checklist não voltavam completos após recarregar o catálogo; corrigido.
4. Busca em banco de locale C não normalizava capitais acentuadas; migração026corrige.
5. Perfil desativado com busca preenchida enviava parâmetros excedentes; corrigido.
6. Acompanhamentos encerrados sumiam do catálogo recente; agora preservados por
   vínculo privado da empresa, com situação oficial separada da etapa interna.
7. Tratamento acústico de sala de aulas era classificado como contratação EAD;
   foi corrigido com evidência de contexto, mantendo objetos mistos em revisão.
8. Falha ao abrir destino existente na descriptografia podia apagar esse destino;
   corrigido e coberto por teste. Restauração agora recusa banco não vazio.

## Interface efetivamente testada

Servidor local usa as rotas de aplicação e PostgreSQL reais. Somente o provedor de
identidade é fictício; ele não prova autenticação Supabase nem entrega de mensagens.
O servidor rejeita bancos remotos e não carrega dotenv. O cookie HTTP de teste tem
nome próprio e não modifica o cookie `__Host-`/Secure de produção.

Fluxos: login Public, logout, login Gerico, busca com acentos e UF, detalhes,
avaliação publicada, etapa Vou participar, responsável, checklist e edição auditada
do perfil Public. Gerico apresentou estado vazio e não recebeu as avaliações Public.
Console das telas conferidas sem erros/avisos capturados.

Responsividade foi examinada em quadro real de390×844px; área útil380px devido à
barra de rolagem, sem excesso horizontal medido. Menu móvel abriu corretamente.
O controle de viewport do navegador não aplicou a dimensão; por isso o teste usa
iframe de homologação local, não simulação de integração nem aparelho físico.

Capturas em [screenshots/2026-11-11](screenshots/2026-11-11/): login, painel,
busca, avaliação, perfil, Gerico e navegação móvel. São dados de homologação.

## Configuração ainda necessária

O terminal Vercel está sem sessão válida e a autorização por dispositivo apresentou
botão desabilitado. O navegador tem acesso ao painel pessoal correto. Não foram
copiados segredos produtivos para preview nem desabilitadas proteções.

Faltam banco e credenciais próprios de homologação para validar Supabase Auth/MFA
com o provedor real. A criação/configuração não pode reutilizar o banco de produção.
Aplicar024–026 junto com014–023 ainda não liberadas; jamais reexecutar migrações
antigas que já tenham recibo. Produção exige autorização posterior.

Backup externo: mecanismo local e upload S3 privado preparados, agenda desativada.
É necessário fornecer bucket privado autorizado, chave de criptografia separada,
credencial restrita ao prefixo e política de retenção. Nenhum serviço foi contratado.

Próximas evidências e os resultados da CI/preview serão acrescentados nesta branch.
