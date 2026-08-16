# Ticket H — Demo end-to-end + verificação

| Campo | Valor |
|---|---|
| Classe | `ops`/test |
| Depende de | A–G (todos) |
| Esforço | Médio |

## Contexto

Último ticket: costurar tudo num roteiro clicável e validar com `web-gui-tester`. O objetivo é
mostrar a visão completa — do recebimento da custódia ao encerramento do ciclo com o laudo em posse
do cidadão.

## Pré-requisitos

- Tickets A–G concluídos e `pytest` verde (gates-browser).
- Backend de dev rodando (`uvicorn` / script do projeto). DB de demo com: um prescritor, um
  cidadão (paciente), um laboratório (dispensador com CNPJ), e o RT do laboratório (CNS).
- Credenciais demo acessíveis (painel "Chaves de acesso demo" no `index.html`/módulos).

## Roteiro da demo (passo a passo)

1. **Prescritor emite pedido de exame** (`prescritor.html`):
   - Itens com `codigo_tuss` **e** `codigo_sigtap` (para exercitar ambos no faturamento).
   - Ex.: "Hemograma Completo", "Glicemia de Jejum".
2. **Cidadão transfere custódia ao laboratório** (`cidadao.html`):
   - Cria **circulação diagnóstica** (a chave "pix") para o CNPJ da clínica, ou transfere custódia
     do pedido ao laboratório.
3. **Laboratório recebe e processa** (`clinica.html`, login dispensador/CNPJ):
   - **Fila de Exames** mostra o pedido; abre.
   - Confirma/realiza o **agendamento** (ou realiza direto).
   - **Coleta** o material (item → `coletado`).
   - **Enviar à bancada** (item → `em_analise`) — Ticket F.
   - **🔬 Produzir laudo** (editor) → preencher conclusão/valor-referência/resumo → **assinar** →
     **liberar ao cidadão** — Ticket G. Itens → `resultado_disponivel`.
4. **Cidadão recebe o laudo** (`cidadao.html`):
   - Laudo aparece na carteira de laudos.
   - **Baixar PDF** do laudo.
   - **Dar ciência** → laudo → `encerrado`.
5. **Laboratório fecha o ciclo** (`clinica.html`):
   - Vê o laudo progredir para ciência/encerrado.
   - **Faturamento**: `?agrupar_por=tuss` e `?agrupar_por=sigtap` mostram agregações distintas
     (Ticket D) — particular/TUSS/SUS na mesma narrativa.

## Validação automatizada (web-gui-tester)

Usar a skill `web-gui-tester` para um passe preto de caixa pelo menos do trecho do `clinica.html`:

- Login como dispensador → localizar pedido na fila → coletar → enviar à bancada → produzir laudo
  → liberar.
- (Se o `web-gui-tester` cobrir múltiplos perfis numa sessão, validar também o `cidadao.html`
  recebendo e dando ciência.)

## Pontos de atenção na demo

- **RT declarado:** a produção do laudo sempre atribui ao RT (CNS). Na demo, deixar o RT
  pré-preenchido para não virar atrito.
- **Faturamento sem transmissão:** deixar claro na narração que TUSS/SIGTAP são **classificação/
  contagem interna** — a transmissão a operadora/SUS é o futuro G4A.
- **Custódia clínica do cidadão:** ao liberar, frisar que o laudo vai à **custódia do cidadão**; o
  lab reteve rastro (hash + ledger + custódia). É a política do Ticket A.

## Critérios de aceite

- [ ] Roteiro 1→5 executa sem erros manuais.
- [ ] Laudo aparece no `cidadao.html` após liberação pelo `clinica.html`.
- [ ] Ciência do cidadão reflui no `clinica.html` (status → encerrado).
- [ ] Faturamento TUSS e SIGTAP retornam agregações diferentes e corretas.
- [ ] `pytest` verde; `web-gui-tester` aprova o fluxo crítico do clínica.

## Entrega final

- Branch `feat/demo-lab-laudo-cidadao` com commits por ticket (ou agrupados por dia).
- Atualizar o diário de sessões (padrão do repo: `docs/sessoes-*`) registrando a demo.
