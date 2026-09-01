# Documentação do PicSaúde — índice

Porta de entrada para quem chega de fora. Não é um catálogo exaustivo — `docs/`
acumula anos de trabalho de sessão (roteiros de demo, pareceres pontuais,
consultas a outras IAs) que não valem navegação própria. O que segue é o que
vale.

---

## Comece pelo contrato

**[`NUCLEO_SANITARIO.md`](NUCLEO_SANITARIO.md)** — o contrato que **todo** objeto
sanitário cumpre: protocolo imutável, itens com estado próprio, máquina de
estados declarada, custódia explícita, ledger append-only, documento canônico
com hash, PDF institucional, QR de validação pública. Qualquer objeto novo
(exame, laudo, agendamento…) satisfaz este contrato antes de existir.

A regra-mestra que tudo serve — [`CLAUDE.md`](../CLAUDE.md) §7 — está na raiz
do repositório, não aqui: é a constituição, lida a cada sessão.

---

## Arquitetura por objeto sanitário

Cada objeto tem sua própria máquina de estados (`backend/app/domain/states*.py`)
e seu documento de arquitetura:

| Objeto | Arquitetura |
|---|---|
| Prescrição / receita | [`ARQUITETURA.md`](ARQUITETURA.md) |
| Pedido de exame | [`ARQUITETURA_EXAMES.md`](ARQUITETURA_EXAMES.md) |
| Laudo | [`ARQUITETURA_LAUDO.md`](ARQUITETURA_LAUDO.md) |
| Atestado | [`ARQUITETURA_ATESTADO.md`](ARQUITETURA_ATESTADO.md) |
| Agendamento | [`ARQUITETURA_AGENDAMENTO.md`](ARQUITETURA_AGENDAMENTO.md) · [atomizado por exame](ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md) |
| Farmácia hospitalar | [`ARQUITETURA_FARMACIA_HOSPITALAR.md`](ARQUITETURA_FARMACIA_HOSPITALAR.md) |
| Custódia (todos os objetos) | [`MAQUINA_ESTADOS_CUSTODIA.md`](MAQUINA_ESTADOS_CUSTODIA.md) |
| Circulação diagnóstica | [`CIRCULACAO_ATOMIZADA.md`](CIRCULACAO_ATOMIZADA.md) · [ocorrências](CIRCULACAO_E_OCORRENCIAS.md) |
| Semáforo de decisão clínica (apoio, não-bloqueante) | [`ARQUITETURA_DECISAO_CLINICA.md`](ARQUITETURA_DECISAO_CLINICA.md) · [explicabilidade](EXPLICABILIDADE_DECISAO_CLINICA.md) |
| Publicação de eventos (G4, pré-adapter) | [`ARQUITETURA_G4A.md`](ARQUITETURA_G4A.md) · [`ARQUITETURA_G4B.md`](ARQUITETURA_G4B.md) |
| Talão digital SNCR (adapter) | [`adapter_sncr.md`](adapter_sncr.md) |

---

## Operação e produção

| Tópico | Documento |
|---|---|
| Deploy (Render) | [`DEPLOY-RENDER.md`](DEPLOY-RENDER.md) |
| Empacotamento / distribuição | [`EMPACOTAMENTO_DISTRIBUICAO.md`](EMPACOTAMENTO_DISTRIBUICAO.md) |
| Checklist de hardening para produção | [`HARDENING_MVP.md`](HARDENING_MVP.md) |
| Backup e restore | [`backup_restore.md`](backup_restore.md) |
| Observabilidade | [`observabilidade.md`](observabilidade.md) |
| Política de dados (LGPD) | [`politica_dados.md`](politica_dados.md) — ver também [`DATA-PROTECTION.md`](../DATA-PROTECTION.md) na raiz |
| Dois dialetos de banco (PG/SQLite) | [`arquitetura_dual_bancos.md`](arquitetura_dual_bancos.md) |
| Carga nacional de CNES | [`CNES-NACIONAL-CARGA.md`](CNES-NACIONAL-CARGA.md) |

---

## Tickets — a história técnica

**[`tickets/`](tickets/)** é o log cronológico de decisões: cada mudança de
classe `core` ou `module` nasceu de um ticket, foi implementada, e o ticket
ficou. É público por decisão (GP-3/B2, 31/08) — não é ruído a esconder, é a
prova de que cada regra do `CLAUDE.md` teve um motivo e um autor.

Não há índice próprio por dentro de `tickets/` — são ~130 arquivos, cada um
nomeado pelo assunto (`TICKET-*`, `DESPACHO-*`, `SESSAO-*`). Para achar algo
específico, busque por palavra-chave (`grep -ril "<termo>" docs/tickets/`) ou
comece por **[`tickets/FILA-VIVA.md`](tickets/FILA-VIVA.md)** — a lista viva
de pendências e decisões recentes, o ponto mais atual do arquivo.

---

## Panorama e planejamento

- [`PANORAMA_TECNICO_CONSOLIDADO_PICSAUDE.md`](PANORAMA_TECNICO_CONSOLIDADO_PICSAUDE.md) — visão consolidada do sistema
- [`PLANO-PRODUCAO-V2.md`](PLANO-PRODUCAO-V2.md) — plano mestre de produção
- [`LEARNINGS.md`](LEARNINGS.md) — lições registradas ao longo do projeto
- [`ORGANIZACAO_AGENTES.md`](ORGANIZACAO_AGENTES.md) — como a equipe de IAs se organiza

---

## O resto de `docs/`

Roteiros de demo, briefings, pareceres pontuais e consultas a outras IAs
(`ROTEIRO-DEMO-V27.md`, `BRIEFING_P05_DEMO.md`, `PARECER_PR76_T1.md`,
`CONSULTA-CODEX-MIGRATION-CIRCULACAO.md`, entre outros) continuam no
repositório como registro, mas não têm porta própria aqui — são material de
sessão, não referência viva. Subpastas (`gp3/`, `revisoes/`, `relatorios/`,
`dividas/`, `issues/`, `extensao/`, `review-tickets/`) seguem a mesma régua.
