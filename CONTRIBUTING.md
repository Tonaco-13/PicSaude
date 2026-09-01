# Como contribuir com o PicSaúde

Este guia é curto de propósito — para ser lido inteiro antes do primeiro café. Detalhes técnicos avançados ficam em `CLAUDE.md` (princípios arquiteturais) e em documentos específicos na pasta `docs/`.

---

## Como contribuir

1. Escolha uma issue com label `good-first-issue`
2. Comente "eu pego" na issue para evitar trabalho duplicado
3. Fork → crie branch com nome descritivo (ex: `feat/mascara-cpf`) → commit → abra um Pull Request
4. Rode `pytest` antes do PR — todos os testes devem passar

## Setup local

Veja `README.md` → seção "Quick Start (5 min)".

## Como a casa classifica uma mudança

Toda mudança no PicSaúde é classificada antes de ser implementada — a classe
determina o nível de revisão exigido (`AGENTS.md` §10, espelhado em
`CLAUDE.md` §10):

| Classe | O que é | Revisão |
|---|---|---|
| `core` | Ledger, custódia, máquina de estados, RBAC, documento canônico, protocolos públicos | Revisão central obrigatória |
| `module` | Novo objeto sanitário ou extensão de módulo existente | Checklist de `docs/NUCLEO_SANITARIO.md` + revisão |
| `adapter` | Integração externa — **nunca** escreve direto no banco clínico | Revisão de contrato de interface |
| `local-extension` | Customização que não altera semântica clínica | Revisão de isolamento |
| `docs` | Documentação sem impacto em código executável | Revisão de consistência |
| `ops` | Infraestrutura, empacotamento, CI/CD | Revisão de segurança operacional |

Mudanças `core` — ledger, custódia, assinatura, documento canônico — nascem de
um ticket (`docs/tickets/`) antes de virar código. Não são o lugar para um
primeiro PR: exigem entender o contrato inteiro do núcleo primeiro. Comece por
`good-first-issue` (abaixo).

## O rito de um PR

1. **Vermelho antes do verde** — se a mudança corrige um defeito, escreva o
   teste que reproduz o defeito primeiro, confirme que ele falha pelo motivo
   certo, só então corrija.
2. **Suíte completa, não só o escopo declarado** — `pytest tests/unit -q` e,
   se a mudança tocar telas, `pytest tests/browser -q`. Regressão fora do
   escopo declarado é achado, não desculpa.
3. **Um PR, uma mudança** — commits separados para código e para
   documentação/ticket relacionado.
4. **PRs `core`/`module` esperam revisão** antes do merge — não é bloqueio
   burocrático, é a mesma disciplina que mantém o ledger confiável.

## Convenções

- Type hints em todas as funções públicas
- Docstrings em português, no estilo Google ou reStructuredText
- Commits no padrão convencional: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Mensagens de commit em português

## O que é (e o que não é) `good-first-issue`

Issues `good-first-issue` cobrem: UI/frontend, validação simples, máscaras de input, mensagens de erro, testes adicionais, documentação de endpoints. **Não tocam** ledger imutável, cadeia de custódia, motor de assinatura digital ou documento canônico — essas áreas exigem revisão arquitetural e ficam fora do escopo de primeiro PR.

## Antes do primeiro commit

Leia e assine o Termo de Contribuição (`CONTRIBUTOR-LICENSE.md`). Sem assinatura, PRs não são merged.

## Dúvidas?

Abra uma issue com label `docs` no repositório, ou contate o coordenador: `fabianotonaco@gmail.com`.
