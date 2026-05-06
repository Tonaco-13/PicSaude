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
