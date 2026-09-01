# PicSaúde

**Infraestrutura de circulação sem atrito de objetos sanitários com custódia cidadã.**

[![Licença: AGPL v3](https://img.shields.io/badge/Licença-AGPL_v3-blue.svg)](LICENSE)
[![Testes](https://img.shields.io/badge/gate-1513%20testes-brightgreen.svg)](#os-números-deste-repositório)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Demo pública](https://img.shields.io/badge/demo-picsaude.com.br-1e3a8a.svg)](https://picsaude.com.br)

Receita, exame, laudo, atestado e encaminhamento como **objetos rastreáveis**:
imutáveis depois de emitidos, com **cadeia de custódia explícita** e **ledger
append-only**. O cidadão carrega os próprios documentos e é ele quem os
entrega — não um intermediário agindo em nome dele.

**[Veja a abertura pública →](https://picsaude.com.br)** — a mesma vitrine que
roda localmente, com a lente de auditoria consultando protocolos de verdade.

---

## Comece por aqui

| Se você quer... | Vá para |
|---|---|
| Ver o sistema rodando sem instalar nada | [picsaude.com.br](https://picsaude.com.br) |
| Rodar localmente em 5 minutos | [§ Rode local](#rode-local-em-5-minutos), abaixo |
| Entender o princípio arquitetural (o "porquê") | [`CLAUDE.md`](CLAUDE.md) — a constituição do projeto |
| Entender o contrato de qualquer objeto sanitário | [`docs/NUCLEO_SANITARIO.md`](docs/NUCLEO_SANITARIO.md) |
| Navegar a documentação por assunto | [`docs/README.md`](docs/README.md) — o índice da casa |
| Ver a história técnica de uma decisão | [`docs/tickets/`](docs/tickets/) — pública por desenho, não por acidente |
| Contribuir com um primeiro PR | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Reportar uma vulnerabilidade | [`SECURITY.md`](SECURITY.md) |

---

## A tese: Care Rails

O Pix não digitalizou o dinheiro. Ele criou **trilhos** — um protocolo público
onde qualquer instituição pluga, o valor se move em segundos e a posse é
inequívoca a cada instante. O que mudou não foi a interface: foi a **camada de
transporte** ter virado infraestrutura comum.

A saúde brasileira ainda não tem isso. Tem documentos que circulam como anexo
de e-mail, papel na mochila e PDF sem dono. Cada instituição guarda a sua
verdade, e o cidadão — que é quem atravessa todas elas — é o único sem cópia
confiável.

**O PicSaúde propõe os trilhos equivalentes para o cuidado:** um objeto
sanitário que se move entre instituições sem perder identidade, com posse
verificável a cada passo e trilha auditável do começo ao fim.

> A formulação completa da tese está no artigo submetido ao **CBEB 2026**
> (Congresso Brasileiro de Engenharia Biomédica). O link entra aqui quando
> publicado.

---

## A prova: três circulações completas

A tese não é slide. São **três percursos inteiros**, cada um com objeto,
custódia, ledger e telas — do consultório à mão do cidadão e de volta.

### 1 · Receita → farmácia

```
prescritor emite ─► carteira do cidadão ─► cidadão apresenta na farmácia
                                                      │
        ledger ◄── dispensação (total ou parcial) ◄────┘
                          │
                          └─► estorno = objeto DERIVADO; a dispensação original nunca muda
```

Dispensação parcial não invalida a receita. Item não pago volta a `pendente` e
segue dispensável em outra farmácia — porque **a receita é do cidadão**, não do
balcão.

### 2 · Exame → laudo → ciência

```
prescritor solicita ─► cidadão entrega ao laboratório ─► coleta ─► bancada
                                                                     │
cidadão dá ciência ◄── laudo liberado (custódia → cidadão) ◄──────────┘
```

Agendar é **compromisso**; entregar é **posse**. Um pedido `agendado` tanto pode
estar com o cidadão quanto no laboratório — quem responde *"onde está"* é a
custódia, nunca o estado.

### 3 · Encaminhamento ⇄ contrarreferência

```
origem emite ─► cidadão leva ao especialista ─► atendimento
                                                    │
origem dá ciência e encerra ◄── contrarreferência ◄──┘
```

O cidadão é o **carteiro clínico**: faz as duas viagens, e é o gesto dele que
move a posse nas duas pontas. A contrarreferência é objeto **derivado**, com
custódia própria.

**[Ver as três circulações rodando →](https://picsaude.com.br)** — demo pública,
dados fictícios, reset horário.

---

## O núcleo

Tudo acima é a mesma máquina, aplicada **oito vezes**. O contrato que todo objeto
sanitário cumpre está em **[`docs/NUCLEO_SANITARIO.md`](docs/NUCLEO_SANITARIO.md)**:

| Contrato | O que exige |
|---|---|
| **Objeto principal** | protocolo UUID, imutável após emissão; correção e renovação são objetos **derivados** |
| **Itens** | granularidade própria, com estado por item |
| **Máquina de estados** | transições declaradas em `domain/states_*.py`; nada de estado ad hoc |
| **Custódia** | quem detém, desde quando, por qual motivo — explícito, nunca inferido |
| **Ledger** | append-only; `UPDATE`/`DELETE` recusados **pelo banco** |
| **Documento canônico + hash** | SHA-256 do que o profissional confirmou — versionado, com a regra antiga preservada |
| **PDF institucional** | layout comum a todos os objetos |
| **QR + validação pública** | verificação anônima, sem vazar conteúdo clínico |
| **Emissão física** | caminho paralelo declarado, sem custódia digital |

Objetos implementados, cada um com máquina de estados própria em
`backend/app/domain/states*.py`: **prescrição · pedido de exame · laudo ·
atestado · agendamento · circulação diagnóstica · encaminhamento ·
contrarreferência**.

### Invariantes provados pelo banco, nos dois dialetos

Convenção de código não é invariante. O que a casa afirma como garantido, o
banco recusa — em **PostgreSQL e SQLite**, por migração e com teste em cada um:

- **posse única**: no máximo **uma** custódia ativa por objeto. Um documento em
  dois lugares ao mesmo tempo é alarme, não erro cosmético;
- **ledger imutável**: *triggers* que recusam `UPDATE` e `DELETE` — **16** (oito
  ledgers × dois), conferidos no gate;
- **unicidade de identificadores** nos relatórios regulatórios: duplicidade é
  tratada como sinal de fraude, com guarda no gate e no *nightly*.

### A Regra Zero

Primeira linha da constituição do projeto ([`CLAUDE.md`](CLAUDE.md) §7):

> A movimentação **sem atrito** do objeto sanitário, **ancorada ao CPF (chave)**,
> é a régua-mestra desta casa. Atrito percebido na circulação é defeito — mesmo
> que cada peça esteja correta isolada. O núcleo existe para servi-la; a última
> milha (telas) é onde ela mais se perde.

---

## Rode local em 5 minutos

A demo pública é vitrine. **O que vale é rodar na sua máquina** — sem conta, sem
cadastro, sem nuvem.

```bash
git clone https://github.com/Tonaco-13/PicSaude.git
cd PicSaude

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # o requirements.txt fica na RAIZ

cd backend
PICSAUDE_DEMO_MODE=true alembic upgrade head     # cria o schema
PICSAUDE_DEMO_MODE=true python3 seed_demo.py     # popula as personas
PICSAUDE_DEMO_MODE=true uvicorn app.main:app --app-dir .
```

Abra `http://localhost:8000`. A raiz serve a **abertura pública** — a mesma
vitrine de picsaude.com.br, com a lente de auditoria já consultando de
verdade. As **quatro estações** — Consultório · Carteira Cidadã · Farmácia ·
Laboratório — ficam em `http://localhost:8000/demo.html`, um clique em cada,
sem senha.

**Roteiro sugerido (≈3 minutos):** emita uma receita no Consultório → abra a
Carteira Cidadã e veja o documento chegar → transfira à Farmácia → dispense no
balcão → volte à carteira e abra a rastreabilidade do objeto.

Pré-requisitos: Python 3.10+. PostgreSQL 15+ só em produção; a demo usa SQLite
sem configuração.

### Rodar os testes

O `requirements.txt` traz só o que a aplicação precisa para **rodar**. As
ferramentas de teste são instaladas à parte — é a mesma separação que o CI faz,
e evita que quem só quer ver o sistema funcionando baixe o Playwright inteiro.

```bash
pip install pytest                          # unidade e integração
cd backend && pytest tests/unit -q          # 620

pip install -r ../requirements-browser.txt  # navegador (Playwright)
python3 -m playwright install chromium      # ~8 min na primeira vez
pytest tests/browser -q                     # 221
```

### Prefere Docker?

O caminho de contêiner, voltado a operadores institucionais, está em
[`README_instalacao.md`](README_instalacao.md) — `docker compose` com
PostgreSQL, healthcheck e volume persistente.

### Para extensionistas da UFPE

Projeto de extensão do CTG/UFPE. Comece por
[`CONTRIBUTING-EXTENSAO.md`](CONTRIBUTING-EXTENSAO.md) — mapa do repositório,
primeiros tickets (`good-first-issue`), a convenção de nomes pt-BR/en e o
roteiro de homologação manual.

---

## Conformidade

| Norma | O que significa aqui |
|---|---|
| **RDC 1.000/2025 (Anvisa)** | motor de classificação regulatória com os 6 tipos de receituário; catálogo de substâncias com alertas |
| **CFM 2.299/2021** | assinatura digital qualificada para validade legal da prescrição |
| **MP 2.200-2/2001** | ICP-Brasil como infraestrutura de assinatura — PAdES-B via pyHanko, cofre AES-256-GCM para os certificados |
| **LGPD** | ver [`DATA-PROTECTION.md`](DATA-PROTECTION.md) |

### Ética — uma restrição de desenho, não uma promessa

**Dados de pacientes nunca são monetizados.** Isso não está só no
[`ETHICS.md`](ETHICS.md): está em
`backend/tests/test_guardrail_sem_monetizacao.py`, um teste que roda no gate.

A diferença importa. Promessa em documento envelhece; guarda executável falha o
build de quem tentar.

---

## Os números deste repositório

Contagem única, verificável, sem arredondamento para cima:

| Suíte | Testes | Como conferir |
|---|---|---|
| unidade (sem banco) | **620** | `pytest tests/unit -q` |
| integração (PostgreSQL) | **672** | `pytest tests/integration --ignore=tests/integration/test_concorrencia.py -q` |
| navegador (Playwright, ponta a ponta) | **221** | `pytest tests/browser -q` |
| **total no gate** | **1.513** | os três acima, em todo PR |

O repositório contém outros testes fora do gate principal (suítes históricas em
`backend/tests/*.py`, parcialmente cobertas por passos específicos do CI). **O
badge conta o que o gate roda e aprova** — não o que o `--collect-only` soma.

O gate também executa: imutabilidade do ledger nos dois dialetos · *reset* do
banco demo em PostgreSQL · *smoke* de predeploy (migração + seed idempotente) ·
seed do catálogo DCB · **paridade de deploy** (builda a imagem e confere que
todo asset referenciado pelas telas existe dentro dela).

---

## Arquitetura em um parágrafo

Cada prescrição é um **objeto sanitário imutável**: emitida, nunca editada —
correções e renovações geram objetos derivados que apontam para o anterior. Toda
ação relevante gera evento **append-only** no ledger, com hash, timestamp, ator e
identificador de instância. A **cadeia de custódia** é rastreada explicitamente,
com transições válidas declaradas no domínio. Princípios completos em
[`CLAUDE.md`](CLAUDE.md); contrato do núcleo em
[`docs/NUCLEO_SANITARIO.md`](docs/NUCLEO_SANITARIO.md); especificações por módulo
em [`docs/`](docs/).

## Stack

**Backend:** Python 3.10+ · FastAPI · SQLAlchemy · Alembic
**Banco:** PostgreSQL 15+ (produção) · SQLite (demo e desenvolvimento)
**Assinatura:** pyHanko (PAdES-B, ICP-Brasil) · `cryptography` (PKCS#12, AES-256-GCM)
**PDF:** ReportLab
**Testes:** pytest · Playwright

---

## Contribuir

Leia [`CONTRIBUTING.md`](CONTRIBUTING.md) — guia curto. Todo contribuidor assina
o [Termo de Contribuição](CONTRIBUTOR-LICENSE.md) antes do primeiro PR.

Issues `good-first-issue` são a porta de entrada. Áreas de núcleo — ledger,
custódia, máquina de estados, assinatura — exigem revisão arquitetural e não são
para o primeiro PR.

## Licença

**GNU AGPL-3.0** ([`LICENSE`](LICENSE)). Toda derivação que interaja com usuários
via rede deve disponibilizar o código-fonte sob a mesma licença.

Licenciamento comercial alternativo (código fechado) disponível mediante
contrato — [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md). Uso sujeito à
[Política de Proteção de Dados](DATA-PROTECTION.md) e ao
[Disclaimer](DISCLAIMER.md).

## Propriedade intelectual

- **Programa de computador:** INPI BR 51 2026 002267-3 (RPI 2883, 07/04/2026)
- **Marca PicSaúde, classe 9** (software): INPI 943014573, depositada em 12/03/2026
- **Marca PicSaúde, classe 44** (serviços médicos): INPI 943014883, depositada em 12/03/2026
- **Titular:** Fabiano Tonaco Borges

## Contato

Fabiano Tonaco Borges — [`fabiano.borges@ufpe.br`](mailto:fabiano.borges@ufpe.br)

---

> *"O SUS é o maior sistema universal de saúde do mundo. Merece software à altura."*
