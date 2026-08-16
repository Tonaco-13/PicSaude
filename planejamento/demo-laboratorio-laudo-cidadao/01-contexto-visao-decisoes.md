# 01 — Contexto, Visão e Decisões (leia antes de qualquer ticket)

> Documento de contexto compartilhado por todos os tickets desta demo.
> Origem: sessão de arquitetura com Fabiano Tonaco (2026-08-13).

---

## 1. A visão

O laboratório é um **operador de trilha sanitária**, não um armazém clínico. A jornada:

```
1. recebe custódia sanitária do cidadão     (pedido de exame + circulação diagnóstica = o "pix")
2. agenda ou realiza                         (agendamento / circulação)
3. quando realiza → envia à BANCADA          (coletado → em_analise, evento leve de setor)
4. a bancada devolve o LAUDO (dado leve)     (laudo estruturado: conclusão + valor-ref + resumo)
5. finaliza faturamento + entrega laudo ao cidadão
   → o laudo fica em posse do cidadão (ciência) → a clínica encerra o ciclo
```

## 2. A peça que falta (e a que não falta)

- **Já existe, ponta a ponta:** o lado cidadão. `cidadao.html` já recebe laudo, baixa PDF e dá
  ciência (`cidadao.html:693-756`). Backend `GET /paciente/laudos` em `auth.py:512`. Lente de
  Auditoria em `index.html:695`. **Não mexer no lado cidadão.**
- **Já existe, completo:** o backend do laudo (`laudos.py`) — criar, assinar, liberar, ciência,
  encerrar, cancelar, pdf, qr. Estados íntegros (`states_laudo.py`).
- **Falta (a demo):** a **UI de laudo no `clinica.html`** (verde de obra), o **gesto bancada**
  (estado `em_analise` hoje é fantasma — nenhum endpoint o persiste), o **faturamento por SIGTAP**
  (hoje só TUSS), e a **política formal** de custódia clínica do cidadão.

## 3. O refinamento da custódia ("o lab não armazena dados")

A frase literal colide com a regulação (RDC 302/2005, CFM 2.052/2013, LGPD obrigam retenção mínima
do Responsável Técnico). A regra adotada, fiel à filosofia PicSaúde:

> **A custódia clínica do laudo é do cidadão. O laboratório guarda o rastro forense
> (protocolo, hash SHA-256, ledger imutável, cadeia de custódia) + o mínimo legal do RT.**

Isso **já é o que o backend faz**: `liberar` cria `laudo_custodia (prestador → paciente)`
(`laudos.py:682`) e o laudo passa ao cidadão; o lab reteve `assinatura_hash` + `laudo_eventos`
+ `laudo_custodia`. Faltava apenas (a) declarar como política e (b) dar a UI que opera. A demo
faz os dois.

## 4. A bancada e a fronteira LIMS

`em_analise` é o "enviou à bancada". O PicSaúde é a **trilha sanitária, não o LIMS** do laboratório:
roteamento interno (qual analisador/técnico/fila de equipamento) é sistema do lab, **nosso não**.
A versão saudável: transição `coletado → em_analise` + **um evento leve** (`pedido_em_analise` com
`setor` opcional em `dados_json`). O evento já existe no vocabulário (`states_exame.py:134`); falta
o endpoint que persiste o estado.

## 5. Regulação — o que cabe agora vs. G4A

Sem a camada de publicação de eventos (G4A), não há adapter para sistema externo (AGENTS.md §10):

| Pagador | Classificação (agora) | Transmissão de cobrança |
|---|---|---|
| Desembolso direto (particular) | ✓ ciclo completo | não há sistema externo — não depende de G4A |
| Planos de saúde (TUSS/TISS) | ✓ `codigo_tuss` + agregação | ✗ guia TISS = adapter → bloqueado em G4A |
| SUS (SIGTAP/APAC/BPA) | ✓ `codigo_sigtap` + agregação | ✗ submissão SUS = adapter → bloqueado em G4A |

Logo, "facilitar faturamento" = **automatizar classificação e contagem** (Ticket D). A transmissão
é futuro G4A — **não implementar**.

## 6. Decisão de RBAC (core, aprovada)

O laudo exige **Responsável Técnico** com CNS (patologista/bioquímico) — nunca o CNPJ da unidade.
Mas o operador do `clinica.html` entra como `dispensador` (CNPJ), e `POST /laudos` exige papel
`prescritor` e valida `ident == CNS_do_autor`. **Decisão:** estender os endpoints de laudo ao
`dispensador`, que produz/assina/libera **declarando o CNS do RT**; o RT continua sendo `autor_id`.

**Ownership do dispensador sem schema change:** o dispensador só opera laudo **vinculado a um pedido
sob sua custódia atual** (`pedido_exame_custodia`, `item_id IS NULL`, `MAX(id)`, `para = CNPJ`).
Laudo standalone (sem `pedido_id`) segue restrito a prescritor/admin. **Não criar coluna nova.**

## 7. Princípios invioláveis (não esquecer em nenhum ticket)

- Objetos sanitários são **imutáveis após emissão** (derivação gera novo objeto).
- Ledger (`*_eventos`) **nunca** recebe UPDATE/DELETE.
- `encerrado_fisico ≠ cancelado` (semântica distinta).
- CPF sentinela `'00000000000'` = físico sem identificação; excluir de queries analíticas.
- Query em contexto institucional **deve** trazer `WHERE org_id = ?` quando aplicável (AGENTS.md §6b).
- `esc()` anti-XSS em toda interpolação do frontend; `_extrairMsgErro` para erros do FastAPI.
