# Busca, rolagem e desempenho

## Como pesquisar

- Palavras em qualquer ordem: `sistemas prefeitura`.
- Expressões exatas entre aspas: `"apoio administrativo"`.
- Exclusão de palavras ou frases: `sistemas -equipamentos` ou `TI -"material de consumo"`.
- `TI` também encontra referências explícitas a tecnologia da informação, informática e desenvolvimento de sistemas/software. `EAD` encontra ensino/educação a distância.
- A busca inclui objeto, informações complementares, órgão, município, UF e número PNCP, sem diferenciar acentos ou maiúsculas.
- `/`, `Ctrl+K` ou `Command+K` levam ao campo de busca. O atalho respeita campos de edição e diálogos abertos.

O painel permite escolher 12, 24 ou 48 itens por página. Quando uma lista não tem resultados, é possível ampliar para todas as oportunidades preservando o texto e os filtros.

## Mudanças de implementação

O painel passou a usar `/api/opportunities?bulk=1`: uma requisição lê o catálogo público completo, dentro do limite de 10 mil candidatas. Antes, cada página de 100 itens fazia uma nova leitura integral no servidor. A paginação da API continua disponível para outros consumidores.

O acesso ao Supabase seleciona apenas o card compacto, evitando transferir o registro bruto do PNCP. Parâmetros inválidos são recusados antes de consultar o banco.

O navegador prepara um índice normalizado e datas de ordenação uma vez por atualização da base. As consultas são compiladas uma vez por busca. `useDeferredValue` mantém a digitação responsiva, e as opções de UF/modalidade são memorizadas. Empates na ordenação usam o identificador PNCP para evitar saltos entre atualizações.

Um cache de memória de 20 segundos evita recarregamentos repetidos ao reabrir o painel. A atualização explícita ignora esse cache. Se a atualização falhar, o painel preserva os resultados válidos anteriores e informa que não foram atualizados. Requisições canceladas não atualizam o cache.

O avanço da coleta atualiza o catálogo durante a consulta periódica de situação, sem zerar a busca. A primeira consulta de situação e a atualização manual não disparam uma segunda leitura desnecessária.

As barras de rolagem usam recursos nativos de CSS, sem interceptar gestos ou eventos de roda. O espaço reservado evita deslocamentos de layout, e cores de alto contraste e movimento reduzido continuam respeitados.

## Verificações

`node scripts/test_catalog_search.mjs` verifica frases, exclusões, siglas, cache, cancelamento, carga integral e preservação de resultados após falha. `--benchmark` acrescenta uma medição sintética, sem usar esse tempo como condição de aprovação.

Na execução local de 06/11/2026, quatro consultas em 10 mil registros levaram aproximadamente 442 ms normalizando os dados repetidamente, contra 13 ms com o índice pronto. A construção inicial do índice levou 121 ms. Esses números são uma comparação local, não uma garantia de latência em produção.
