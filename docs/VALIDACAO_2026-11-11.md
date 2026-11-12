# Verificação desta versão

- Suite Python: 233 testes, sem falhas; quatro testes de integração ignorados nessa
  rodada e executados separadamente com sucesso no PostgreSQL temporário.
- Build React/TypeScript: aprovado. Script de busca/paginação/cache/isolamento: aprovado.
- Migrações001–023: sintaxe validada em PostgreSQL temporário (PGlite), sem produção.
- Filtros SQL de estado, órgão e valor; fila de descartes; resgate de pontuação zero;
  perfil Public e autorização de escrita entre empresas: conferidos com fixtures locais.
- Políticas RLS: papel restrito da Public não leu perfis/avaliações da Gerico.
- Coleta: linhas inválidas isoladas, corpo bruto preservado, conjuntos/versões diferentes
  com mesma contagem não declararam cobertura, eventos idempotentes e atualização antiga
  não substituiu a mais recente.
- Enriquecimento real de uma licitação histórica: PNCP e Compras retornaram três itens
  cada, dois anexos PNCP e quatro recibos brutos guardados apenas no banco temporário.
- Extração PDF: arquivo vazio sinalizou necessidade de OCR, conteúdo inválido foi rejeitado.
- Scanner de padrões de credenciais: sem achados. Isso não certifica ausência de todo
  tipo de segredo nem equivale a auditoria de histórico.

Ainda não verificados: interface visual em navegador desta revisão, implantação com
credenciais restritas reais, login/MFA com o Supabase real, certificado do banco real,
backup externo e restauração completa. Auditorias de dependências estão na CI; não
registrar sua execução remota como concluída antes de receber o resultado.

Esta versão não foi publicada em produção. A disponibilidade de uma fonte na amostra
não garante sua disponibilidade permanente ou cobertura integral.
