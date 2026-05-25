# PicSaúde

[![Licença: AGPL v3](https://img.shields.io/badge/Licença-AGPL_v3-blue.svg)](LICENSE)
[![Testes](https://img.shields.io/badge/testes-1267%20passando-brightgreen.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Sistema brasileiro de prescrição digital com assinatura ICP-Brasil PAdES-B, motor regulatório RDC 1.000/2025 e ledger de auditoria imutável.

> **Status:** backend funcional (1267 testes passando). Modo demo público (`PICSAUDE_DEMO_MODE`) implementado — veja Quick Start abaixo. Deploy em URL pública em preparação. Roadmap em `docs/PLANO-PRODUCAO-V2.md`.

---

## Por que existe

A RDC 1.000/2025 da Anvisa exige prescrição digital com assinatura qualificada para receituários no Brasil. A MP 2.200-2/2001 estabelece a ICP-Brasil como infraestrutura de assinatura digital com validade jurídica. O SUS — maior sistema universal de saúde do mundo — precisa de uma alternativa livre, auditável e soberana aos softwares proprietários de prescrição que dominam o mercado privado.

O PicSaúde existe para resolver isso. Software livre, conformidade regulatória derivada da norma, arquitetura desenhada para auditoria.

## O que faz

Fluxo principal:

```
Prescritor emite ──► Motor regulatório valida ──► PDF gerado ──► Assinatura PAdES-B
                                                                       │
                                                                       ▼
            Ledger de auditoria ◄── Dispensação ◄── Paciente ◄── Custódia transferida
```

> **GIF do fluxo completo:** será adicionado após o deploy do demo público.

Funcionalidades implementadas:

- 6 tipos de receituário (RDC 1.000/2025)
- Catálogo de substâncias com alertas (info, warning, critical)
- Geração de PDF institucional (ReportLab)
- Assinatura digital PAdES-B com pyHanko
- Cofre AES-256-GCM para certificados `.pfx`
- Ledger de auditoria imutável e cadeia de custódia explícita
- Modo demo público com sessões pré-semeadas (`PICSAUDE_DEMO_MODE`) — isolado do banco de produção, reset horário
- 1267 testes (unitários + integração + E2E)

---

## Quick Start (5 min)

```bash
git clone https://github.com/Tonaco-13/PicSaude.git
cd PicSaude/backend

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Criar e popular o banco demo (3 personas pré-semeadas)
PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py

# 2) Subir o backend em modo demo
PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload --app-dir .
```

Abra `http://localhost:8000` no navegador — a tela inicial mostra o seletor de personas com banner amarelo **MODO DEMO**. O endpoint `/docs` continua disponível para explorar a API (Swagger).

Para rodar os testes:

```bash
cd backend && pytest -q
```

Pré-requisitos: Python 3.10+. Em produção, PostgreSQL 15+. Em demo, SQLite (sem configuração adicional).

### O que você verá no demo

- Banner amarelo no topo de todas as páginas: **MODO DEMO** com horário do próximo reset
- 3 cards de persona na tela inicial: **Prescritor** (Dra. Demo Maria Souza), **Dispensador** (Farmácia Demo Central), **Cidadão** (João Demo da Silva) — login real fica desabilitado em demo
- Marca d'água "DEMO" diagonal em todas as receitas PDF geradas (impede uso fraudulento)
- Banco demo é arquivo separado (`data/pix_saude_demo.db`) — fisicamente isolado do banco de produção
- Reset horário automático: a cada hora cheia o estado do demo volta ao inicial (cron entra na Etapa 8/deploy)

### Para extensionistas UFPE

Este projeto também é projeto de extensão do CTG/UFPE. Se você está chegando agora pela equipe de extensão, leia [`CONTRIBUTING-EXTENSAO.md`](CONTRIBUTING-EXTENSAO.md) primeiro — tem mapa do repo, primeiros tickets sugeridos (`good-first-issue`), explicação da convenção de naming híbrido pt-BR / en, e o roteiro de homologação manual para validar o demo.

---

## Arquitetura em um parágrafo

O PicSaúde trata cada prescrição como **objeto sanitário imutável**: uma vez emitida, nunca é editada — correções e renovações geram novos objetos derivados que apontam para o anterior. Toda ação relevante (emissão, impressão, transferência de custódia, dispensação, assinatura) gera evento append-only no **ledger de auditoria**, com hash, timestamp, ator e identificador de instância. A **cadeia de custódia** é rastreada explicitamente de prescritor → paciente → dispensador, com transições válidas declaradas no domínio. Detalhes completos em [`CLAUDE.md`](CLAUDE.md) (princípios arquiteturais) e em [`docs/`](docs/) (especificações por módulo).

## Stack técnica

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic
- **Banco:** PostgreSQL 15+ (produção), SQLite (demo)
- **Assinatura digital:** pyHanko 0.34.1 (PAdES-B com ICP-Brasil)
- **PDF:** ReportLab
- **Criptografia:** `cryptography` (PKCS#12, AES-256-GCM)
- **Testes:** pytest (146 passando)

---

## Como contribuir

Contribuições são bem-vindas. Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) primeiro — guia curto, ler antes do primeiro café. Todo contribuidor assina o Termo de Contribuição ([`CONTRIBUTOR-LICENSE.md`](CONTRIBUTOR-LICENSE.md)) antes do primeiro PR.

Issues marcadas com `good-first-issue` são pontos de entrada para quem está começando. Áreas core (ledger, custódia, assinatura digital) exigem revisão arquitetural — não são para primeiro PR.

## Licença

Distribuído sob a **GNU Affero General Public License v3.0** ([`LICENSE`](LICENSE)). Toda derivação que interaja com usuários via rede deve disponibilizar o código-fonte sob a mesma licença.

Licenciamento comercial alternativo (código fechado) está disponível mediante contrato — veja [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md).

O uso do software está sujeito à [Política de Proteção de Dados](DATA-PROTECTION.md) e ao [Disclaimer de Responsabilidade](DISCLAIMER.md).

## Propriedade intelectual

- **Registro de Programa de Computador:** INPI BR 51 2026 002267-3 (RPI 2883, 07/04/2026)
- **Marca PicSaúde — classe 9 (software):** pedido INPI 943014573, depositado em 12/03/2026
- **Marca PicSaúde — classe 44 (serviços médicos):** pedido INPI 943014883, depositado em 12/03/2026
- **Titular:** Fabiano Tonaco Borges

## Equipe

- **Coordenador:** Fabiano Tonaco Borges (`fabianotonaco@gmail.com`)
- **Contribuidores:** veja `CONTRIBUTORS.md` (criado quando o primeiro PR for merged)

---

> *"O SUS é o maior sistema universal de saúde do mundo. Merece software à altura."*
