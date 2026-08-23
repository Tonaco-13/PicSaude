# Parecer do arquiteto (Z) — J.11 (#167), revisão retroativa

| Campo | Valor |
|---|---|
| **Data** | 2026-08-23 (revisão retroativa — o PR mergeou em 16/08 sob ordem geral, com esta revisão prometida) |
| **Objeto** | PR #167 `feat(demo): selo de agendamento no cartão do exame + lente compartilhada [module]` |
| **Escopo despachado** | Parecer J7-PRS §2 (15/08): (a) selo de agendamento; (b) lente compartilhada |
| **Método** | Revisão por **consumo direto**: os helpers do J.11 foram as fontes únicas que o arquiteto usou ao construir o J.10 (#170) e a recepção (#175) em cima; leitura dirigida do código do selo e da lente no `cidadao.html`/`lente.js`; suíte de navegador verde ininterrupta desde o merge (85→94 testes, incluindo `test_j11_selo_e_lente.py`); comprovações ao vivo na vitrine (20/08 e 23/08: agendamento criado pela clínica chega ao cartão do cidadão). **Não** foi refeito diff linha a linha — o método está declarado porque é isso que o parecer vale. |
| **Veredito** | **APROVADO — sem achado que exija ticket** |

---

## §1 (a) Selo de agendamento — correto e envelhecido bem

1. **Fonte única no backend.** `agendamento_atual_do_pedido` decide "qual
   compromisso vale agora" (terminais fora; remarcação é derivação, o corrente
   é o não-terminal) e `resumo_agendamento_para_cartao` projeta o mínimo
   (`criado_por` e id interno não atravessam). A decisão de implementação
   registrada na época — enriquecer a carteira em vez de N+1 chamadas por
   cartão — foi a certa, e é a mesma razão que o J.7 usou para tirar posse do
   status: **uma resposta por pergunta, no backend**. O J.10 e a recepção
   consumiram esses helpers sem alterá-los — o melhor sinal de desenho que
   um módulo pode dar.
2. **Informação ≠ custódia, respeitado na veia.** Zero escrita, zero evento,
   zero transição: o pedido segue com o `prestador_exame` enquanto o cidadão
   lê a data. O corolário do J.7 aplicado sem deslize.
3. **Envelhecimento:** o teste do selo foi atualizado pelo #171 para exercitar
   o **ator real** (o laboratório remarcando) sem afrouxar asserção — e o selo
   reagiu. Teste que acompanha a realidade, não que congela o passado.
4. **Evidência de campo:** provado na vitrine três vezes (20/08 duas, 23/08
   uma) — cartão do cidadão carregando o agendamento criado pela clínica.

## §2 (b) Lente compartilhada — fronteira pública intacta

1. Extração para `lente.js` (`window.LenteAuditoria`) com o CSS junto; o
   `index.html` **permaneceu inalterado em função** — a lente pública é `core`
   de fronteira e não foi tocada. "Ver rastreabilidade" por cartão (receita em
   posse e em histórico, exame, atestado, laudo) via `/public/*`, sem login
   adicional — o princípio do portal neutro preservado.
2. O ajuste no smoke existente (`TestAtestadoNaCarteira` passou a nomear a
   função do botão) ganhou especificidade em vez de perdê-la — registrado na
   época como tal e confirmado pela suite desde então.

## §3 Ressalva única (não é achado do J.11)

A experiência de 23/08 mostrou que o selo sozinho não basta para a pergunta
"para onde eu vou amanhã?" — a seção **Agendamentos** da carteira entrou como
 demanda do Fabiano e está em desenho (junto com a reorganização das abas da
 clínica, à espera da consulta externa). É evolução por demanda de uso, não
 defeito do que foi entregue.

---

*Parecer do arquiteto (Z), 2026-08-23. Integra o PR docs da série 19–23/08
como a sexta peça. Martelos citados: nenhum novo — este parecer apenas fecha
a promessa de revisão retroativa do Adendo §10a-4 (16/08).*
