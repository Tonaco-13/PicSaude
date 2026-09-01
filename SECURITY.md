# Política de Segurança

## Reportar uma vulnerabilidade

Encontrou uma falha de segurança no PicSaúde — no núcleo (ledger, custódia,
assinatura), num endpoint, num adapter ou na infraestrutura de deploy?
Reporte diretamente para:

**[`contato@picsaude.com.br`](mailto:contato@picsaude.com.br)**

Não abra uma issue pública para vulnerabilidades ainda não corrigidas. Uma
falha real em produção envolve dados de saúde de pessoas reais — o relato
privado dá tempo de corrigir antes de o problema virar exposição.

Inclua, quando possível:

- Passos para reproduzir
- Impacto esperado (o que um atacante ganharia)
- Componente afetado (endpoint, tela, migração, dependência)

## O que esperar

Confirmamos o recebimento e investigamos. Não há SLA formal publicado — o
projeto é mantido por uma equipe pequena — mas achados de severidade alta
(vazamento de dado clínico, bypass de RBAC, quebra do ledger imutável) têm
prioridade sobre qualquer outro trabalho em andamento.

## Escopo

Cobre o código deste repositório e a instância de demonstração pública em
picsaude.com.br. Dados na demo são **fictícios** — reset periódico, sem PII
real — mas falhas que exponham a arquitetura ou permitam pivotar para uma
instância de produção real ainda são reportáveis aqui.

## Fora de escopo

Engenharia social, ataques físicos, e vulnerabilidades em dependências de
terceiros sem exploração demonstrável contra este código — reporte essas
diretamente ao projeto upstream correspondente.
