# PDF de Receituários — Ticket 17

> Geração de PDF compatível em estrutura e campos obrigatórios com os
> modelos Anvisa **Versão 2** (publicada em 16/03/2026, mandatória a
> partir de 18/05/2026).

## 1. Por que um PDF separado da prescrição

Existem **dois documentos distintos** com propósitos diferentes:

| Documento | Finalidade | Audiência | Regulação | Módulo |
|---|---|---|---|---|
| PDF Prescrição | Ato clínico completo | Prescritor / prontuário | CFM 2.299/2021 | `app/domain/pdf_prescricao.py` |
| PDF Receituário | Documento regulatório | Farmácia / paciente / Anvisa | RDC 1.000/2025 + Portaria 344/98 | `app/domain/pdf_receituario.py` |

Uma prescrição com 3 itens (ex.: `A1` + `B1` + sem classe) gera:
- 1 PDF de prescrição (ato clínico — todos os itens, documento operacional)
- 3 PDFs de receituário regulatório distintos (1 amarelo, 1 azul, 1 simples)

Este ticket **não altera** o PDF de prescrição existente.

## 2. Fluxo completo

```
Prescrição emitida (T1–T14)
  ↓
POST /prescricoes/{proto}/receituarios/gerar     (T15 — motor regulatório)
  → 1..N receituários (status: gerado)
  ↓
POST /prescricoes/{proto}/receituarios/numerar   (T16A — adapter SNCR)
  → status: numerado_stub | numerado | nao_requer_sncr
  ↓
GET  /prescricoes/{proto}/receituarios/{id}/pdf  (T17 — este ticket)
  → status: emitido
  → evento: receituario_emitido (1ª vez) ou receituario_pdf_acessado (re-acesso)
```

## 3. Endpoint

```
GET /prescricoes/{protocolo}/receituarios/{receituario_id}/pdf
```

| Atributo | Valor |
|---|---|
| Auth | `Bearer` JWT, role=`prescritor` |
| Posse | CNS do token = prescritor da prescrição |
| Content-Type | `application/pdf` |
| Disposition | `inline; filename="receituario-{ABREV}-{id}.pdf"` |

### Status codes

| Código | Causa |
|---|---|
| 200 | PDF gerado |
| 401 | Token ausente / inválido |
| 403 | Outro prescritor |
| 404 | Prescrição ou receituário inexistente |
| 410 | Receituário substituído por nova geração |
| 422 | Status `gerado` (não numerado) ou `cancelado` |

## 4. Tipos suportados

| `tipo_receituario` | Abrev | Cor primária | Vias | Retém |
|---|---|---|---|---|
| `notificacao_receita_a` | NRA | Amarelo Anvisa (#F9A825) | 3 | Sim |
| `notificacao_receita_b` | NRB | Azul Anvisa (#1565C0) | 2 | Sim |
| `receita_controle_especial` | RCE | Cinza-escuro (#37474F) | 2 | Sim |
| `notificacao_receita_especial` | NRE | Roxo (#6A1B9A) | 2 | Sim |
| `receita_simples` | RSI | Verde PicSaúde (#2E7D32) | 1 | Não |
| `receita_retencao` (T18 — ativo) | RRT | Verde-azulado (#00695C) | 2 | Sim |

> As cores são aproximações dos modelos oficiais Anvisa. Não há
> documentação pública em hexadecimal exato — o amarelo (NRA) e o azul
> (NRB) são os regulatoricamente mais relevantes e foram calibrados
> para serem claramente identificáveis.

## 5. Estrutura do PDF

Layout vertical, A4, margens 20mm. Blocos (de cima para baixo):

```
┌──────────────────────────────────────────────────────┐
│ 1. Cabeçalho colorido por tipo + marca SNCR          │ ← cor distinta
├──────────────────────────────────────────────────────┤
│ 2. Faixa de alerta (apenas NRA, NRE)                 │ ← vermelho se aplicável
├──────────────────────────────────────────────────────┤
│ 3. Faixa SNCR (oculta em receita_simples)            │ ← Nº SNCR + DEV warning
├──────────────────────────────────────────────────────┤
│ 4. Faixa de número de vias                           │ ← centralizado
├──────────────────────────────────────────────────────┤
│ 5. Seção Prescritor (nome, CNS, modo assinatura)     │
├──────────────────────────────────────────────────────┤
│ 6. Seção Paciente (nome, CPF mascarado)              │ ← V2: CPF (não endereço)
├──────────────────────────────────────────────────────┤
│ 7. Seção Medicamentos (tabela + posologia)           │ ← classe ao lado do nome
├──────────────────────────────────────────────────────┤
│ 8. Seção Informações regulatórias (vias, retenção)   │
├──────────────────────────────────────────────────────┤
│ 9. Seção Rastreabilidade (protocolo, data, hash)     │
├───────────────────────────────────┬──────────────────┤
│ 10a. Linha de assinatura          │ 10b. QR Code     │ ← QR canto inf. dir.
├───────────────────────────────────┴──────────────────┤
│ 11. Rodapé (PicSaúde — SNCR | Modelo Anvisa V2)      │
└──────────────────────────────────────────────────────┘
```

### Campos obrigatórios (Anvisa V2)

- Identificação do tipo do receituário (cabeçalho colorido)
- Numeração SNCR (faixa, exceto receita simples)
- Prescritor: nome + CNS + modo de assinatura
- **Paciente: nome + CPF** (mudança V1→V2; substitui endereço)
- Medicamentos: nome, concentração, quantidade, posologia
- Vias e retenção pela farmácia
- Protocolo, data de emissão, validade, hash SHA-256
- QR de rastreabilidade

## 6. QR Code

- Posição: canto inferior direito, lado ~25mm
- Lib: `reportlab.graphics.barcode.qr.QrCodeWidget` (ReportLab nativo, sem dep extra)
- Conteúdo: `protocolo=...;sncr=...;hash=...;tipo=...;emitido=...`
- Label visível: **"QR — Rastreabilidade PicSaúde"**

> Importante: enquanto o SNCR real não estiver integrado, este QR é
> **rastreabilidade interna do PicSaúde**, NÃO validação SNCR oficial.

## 7. Mudanças Anvisa V1 → V2

| Aspecto | V1 (13/02/2026) | V2 (16/03/2026, mandatória 18/05/2026) |
|---|---|---|
| ID paciente | Endereço | **CPF / Passaporte** |
| Campo endereço | Presente | Removido |
| Obrigatoriedade | Transitório | Mandatório a partir de 18/05/2026 |

## 8. Modo stub vs. real

| Sinal | Stub (`adapter_usado="stub"`) | Real (futuro T16B) |
|---|---|---|
| Marca d'água diagonal | `"DOCUMENTO SEM VALIDADE REGULATORIA"` (cinza ~18% alpha, 45°) | Nenhuma |
| Faixa SNCR | `[DESENVOLVIMENTO — numeração não regulatória]` em vermelho | Numeração normal |
| Rodapé extra | `⚠ Numeração STUB — apenas para desenvolvimento e testes` | Nenhum |
| Numeração | Prefixo `STUB-` | Numeração SNCR oficial |

A redundância (marca d'água + faixa + rodapé) é proposital: dificulta
que um PDF de stub seja confundido com um PDF regulatório válido.

## 9. CPF do paciente no PDF

| Modo | Comportamento | Notas |
|---|---|---|
| Stub | Mascarado: `123.***.***-01` | Decisão conservadora de privacidade |
| Real (futuro) | Mascarado por padrão; TODO_REGULATORIO emitido | Confirmar com Anvisa se modelo final exige CPF completo ou aceita mascaramento |

Quando emissão em modo `real` ocorrer pela primeira vez, o ledger recebe
um evento `todo_regulatorio` com motivo `cpf_paciente_em_pdf_real` —
sinalizando que validação jurídica é necessária antes de produção.

## 10. Diferenças em relação a `pdf_prescricao.py`

| Aspecto | pdf_prescricao | pdf_receituario |
|---|---|---|
| Cabeçalho | Navy fixo | Colorido por tipo |
| Título | "RECEITA MÉDICA" | Tipo do receituário ("NOTIFICAÇÃO DE RECEITA A", etc.) |
| Itens | Todos da prescrição | Apenas os do grupo regulatório |
| QR Code | Não | Sim (rastreabilidade) |
| Campos regulatórios | Não | Vias, retenção, classe controle, SNCR |
| Marca d'água | Não | Sim (modo stub) |
| Helpers | Próprios | Importa `_fmt_cpf`, `_fmt_data`, `_truncar_hash` de pdf_prescricao |

## 11. Salvaguardas implementadas

- Não altera `pdf_prescricao.py` (é outro documento)
- Não altera `motor_regulatorio.py` (Ticket 15)
- Não altera adapter SNCR (Ticket 16A)
- Não altera endpoints existentes `/gerar` e `/numerar`
- Importa helpers de `pdf_prescricao.py` para garantir formatação coerente
- Usa `QrCodeWidget` do ReportLab (sem dependência adicional)
- Marca d'água obrigatória quando `adapter_usado="stub"`
- Rollback automático via `get_tx()` em caso de falha
- Testes existentes não-regridem (60/60 testes passam)

## 12. Cobertura de testes

[`backend/tests/integration/test_pdf_receituario.py`](../backend/tests/integration/test_pdf_receituario.py) — 15 testes.

```bash
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd backend && pytest tests/integration/test_pdf_receituario.py -v
```

## 13. Próximos tickets

- **T18**: Grupo Retenção (antimicrobianos / GLP-1) — `receita_retencao` já tem layout pronto, mas não há `classe_controle` que mapeie para ele hoje.
- **T16B**: Integração real com SNCR (quando API Anvisa estiver disponível) — basta trocar adapter; o PDF já distingue stub/real.
- **Futuro**: Assinatura PAdES/LTV embutida no PDF (hoje o PDF é apenas rastreado por hash externo).
