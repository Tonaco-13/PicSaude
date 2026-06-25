# Ratificação do contrato do Motor de Busca Clínica — checklist para o Chefe

> Objeto: `MOTOR_MS_definicao_ancora.md` (status PROPOSTA), classe `core`
> (contrato de domínio). Esta é a revisão central exigida antes de ratificar.
>
> Escopo da ratificação: verificar que o contrato **não viola invariante de
> núcleo** e que o comportamento MVP **não exige mudança de código core além de
> ordenação sourced**. NÃO é revisão do conteúdo clínico nem do roadmap A–F.

## A. Invariantes de núcleo intactos

- [ ] Motor permanece **Camada 3**: não bloqueia emissão, não altera estado de
  prescrição/item, não escreve em ledger nem custódia.
- [ ] Continua atrás da flag `PICSAUDE_DECISAO_CLINICA` (desligada por default);
  o contrato não implica ligá-la.
- [ ] **Não exige evento de ledger novo.** O comportamento MVP cabe no
  `decisao_clinica_avaliada` existente (sinal + versão da regra, só com
  `codigo_cid`). Se exigir evento novo → é mudança core separada, fora desta
  ratificação.

## B. Fronteira com `semaforo_decisao.py` (código core)

- [ ] Ordenação é **servida a partir de dado sourced** (`linha_terapia` /
  `ordem_fonte`); o motor **não computa** ranking. Fonte sem ordem → ordem
  neutra (alfabética).
- [ ] Nenhuma mudança MVP toca a lógica de decisão além de ordenar por esse
  campo. 🔴 e ranqueamento por evidência permanecem fora (Fase F).

## C. Documento canônico / assinatura (maior adjacência ao R6)

- [ ] Posologia é **referência ao lado do campo** — nunca pré-preenche o campo
  que vai ao payload assinado. Nada que o motor produz entra no documento
  canônico / ICP-Brasil sem ato explícito do prescritor.
- [ ] Confirmar que isso **não cria caminho do motor para `documento_canonico.py`
  / serialização** (R6 intocado).

## D. Régua da linha citável — executável

- [ ] A regra "destaque/ordem só com linha citável; senão ordem neutra" é
  **enforçável como guard/teste** (análoga ao `test_ingestao_canon`), não só
  prosa.

## E. Gate de autoridade de validação

- [ ] **Peça 1** (CODEOWNERS nos 2 CSVs + branch protection) ativa **antes** de
  qualquer estudante abrir PR.
- [ ] **Peça 2** robusta planejada: cruza `GITHUB_ACTOR` do `pull_request_review`
  (com `state == "approved"`) contra `validado_por`; só validador credenciado
  aprova linha `validado`.

## F. Fontes e determinismo

- [ ] Fontes de ordenação/seleção **só oficiais** (PCDT/CONITEC, RENAME,
  ANVISA/CMED); nunca PubMed/evidência/juízo do sistema. Coerente com
  "determinístico, sem LLM".
- [ ] Currency ("oficial ≠ vigente", caso ranitidina) é etapa **nomeada e
  obrigatória** da curadoria.

## G. Registro e taxonomia

- [ ] Classe `core` (contrato de domínio) confirmada.
- [ ] Ao aprovar: o documento vira `docs/MOTOR_BUSCA_CLINICA.md`; o ponteiro a
  ele no `CLAUDE.md` / `NUCLEO_SANITARIO.md` é **edição core à parte** (decisão
  do Chefe).

---

**Resultado:** aprovar · aprovar com condições · rejeitar.

**A ratificação NÃO autoriza ligar a flag** `PICSAUDE_DECISAO_CLINICA` com
paciente — isso depende do enquadramento SaMD/jurídico (RDC 751/2022 + 657/2022),
consulta paralela e separada, fora deste escopo.
