# Ticket E — Atualização da arquitetura de laudo

| Campo | Valor |
|---|---|
| Classe | `docs`/`module` |
| Depende de | C (documenta o modelo implementado no Ticket C) |
| Esforço | Pequeno |

## Contexto

O Ticket C introduz o modelo **dispensador-produz-sob-RT** e o Ticket B materializa o **fluxo
bancada**. Ambos precisam ficar registrados na arquitetura oficial do laudo para que o próximo
desenvolvedor não os trate como acidente.

## Arquivo

- `docs/ARQUITETURA_LAUDO.md` — adicionar seção; não reescrever o existente.

## Tarefa

Adicionar duas seções curtas a `docs/ARQUITETURA_LAUDO.md`:

### Seção "Produção do laudo pelo dispensador (unidade) em nome do RT"

- Contexto: o operador do laboratório entra como `dispensador` (CNPJ); o laudo exige RT com CNS.
- Modelo: o dispensador produz/assina/libera **declarando o CNS do RT**; o RT é sempre o `autor_id`.
- Ownership: derivado da **custódia ATUAL do pedido vinculado** (sem coluna nova).
- Laudo standalone (sem `pedido_id`): restrito a prescritor/admin.
- Auditoria: `produzido_por_cnpj` no evento `laudo_criado`; CNPJ da unidade em `laudo_custodia` na liberação.
- Referência cruzada: `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` (Ticket A) e ao Ticket C.

### Seção "Fluxo bancada — `em_analise`"

- O item percorre `coletado → em_analise → resultado_disponivel`.
- `em_analise` = "material na bancada do laboratório".
- Endpoint: `POST /pedidos-exame/{proto}/itens/{id}/em-analise` (evento `pedido_em_analise`, com
  `setor` opcional).
- **Fronteira LIMS:** PicSaúde é a trilha sanitária, não o LIMS. `setor` é leve (work-area); não
  modelar analisador/técnico/fila.
- Referência cruzada: `docs/ARQUITETURA_EXAMES.md` (máquina de estados do item).

### Atualização do mapa "Endpoints" (se houver tabela)

- Incluir `POST .../itens/{id}/em-analise` na arquitetura de exames (`ARQUITETURA_EXAMES.md`) se
  houver tabela de endpoints — manter consistência.

## Critérios de aceite

- [ ] `ARQUITETURA_LAUDO.md` tem a seção do modelo dispensador-produz-sob-RT.
- [ ] `ARQUITETURA_LAUDO.md` (ou `ARQUITETURA_EXAMES.md`) documenta o fluxo bancada.
- [ ] Cross-links para a política (Ticket A) e para os tickets B/C.
- [ ] Não contradiz o `NUCLEO_SANITARIO.md` (é documentação de exceção/modelo de módulo).

## Notas

- Nenhum código. É alinhamento de documentação com o que C e B implementaram.
- Se a alteração tocar a semântica de estados do `NUCLEO_SANITARIO.md`, **parar e escalar** —
  mudança no Núcleo é `core` e exige revisão central separada (não é o caso aqui: nenhum estado
  novo é criado).
