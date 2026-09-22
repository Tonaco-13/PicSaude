# AGENDA-WEEKEND — 05 e 06/09/2026 (arquiteto, rodadas automáticas)

| Campo | Valor |
|---|---|
| **Autorização** | Fabiano, 04/09: *"Monte uma agenda automática para o fim de semana"* + **"sinal verde I10 estrito"** |
| **Executor** | Z, arquiteto — em rodadas automáticas (auto-resgate) |
| **Log** | este arquivo (uma seção por rodada) |

## Mapa das rodadas

| Quando | Rodada | Trabalho |
|---|---|---|
| Sáb 09:00 | R1 | **I10 v2 estrito** (ver sementes abaixo) |
| Sáb 15:00 | R2 | Auto-resgate R1 + sanidade vitrine/repo |
| Sáb 18:00 | R3 | Registro do dia + FILA-VIVA |
| Dom 09:00 | R4 | Levantura J44 (DPOC) + I50 (IC) do corpus |
| Dom 15:00 | R5 | Sanidade + self-check dos rascunhos |
| Dom 18:00 | R6 | FECHO + handoff segunda |

## Sementes da R1 (head-start do arquiteto, 04/09)

**Decisão assinada:** Fabiano, 04/09: *"sinal verde I10 estrito"* — 🟢 passa a
significar *reconhecido E disponível no SUS* em todas as condições.

**Sobreviventes na RENAME 2024 (17, com páginas):** hidroclorotiazida p.45,138 ·
furosemida p.44,137 · espironolactona p.44,135 · captopril p.42,128 · enalapril
p.45,140 · losartana p.45,140 · valsartana p.46,212 · anlodipino p.41,127 ·
nifedipino p.45,141 · verapamil p.43,133 · atenolol p.41,126 · propranolol
p.43,133 · metoprolol p.46,144 · carvedilol p.42,128 · metildopa p.45,141 ·
hidralazina p.43,131 · doxazosina p.45,141.

**Excomungadas (44, viram 🟡 "não consta da RENAME 2024"):** lista completa na
varredura de 04/09 (clortalidona, indapamida, bumetanida, piretanida,
eplerenona, amilorida, triantereno, ramipril, lisinopril, benazepril, fosinopril,
perindopril, trandolapril, cilazapril, delapril, quinapril, candesartana,
olmesartana, telmisartana, irbesartana, azilsartana, alisquireno, levanlodipino,
felodipino, lercanidipino, manidipino, nitrendipino, isradipino, lacidipino,
nisoldipino, diltiazem, bisoprolol, nebivolol, nadolol, pindolol, acebutolol,
esmolol, clonidina, moxonidina, rilmenidina, guanabenzo, minoxidil, prazosina,
terazosina).

**Posologia I10:** clortalidona (row atual) **sai** (ausente da RENAME); as
outras 5 constam.

**Casos de demo preservados:** I10×sinvastatina segue 🟡 (não é do elenco, nunca
foi); I10×dapagliflozina segue 🟡. Sinvastatina ∈ RENAME (p.46,143) — nota para
o futuro E78.

**Execução:** padrão #233/#249 — worktree de origin/main, transformação dos
CSVs, guarda nova `test_semaforo_flip_i10_v2.py` (17×🟢 com página na fonte;
ramipril/cortalidona 🟡 com causa; posologia sem clortalidona; demo cases),
suíte unit, commit, push, PR [curadoria]. **NÃO mergeia** — martelo do Fabiano.

## Sementes da R4

Corpus: `data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/pcdt-da-doenca-pulmonar-obstrutiva-cronica.pdf`
e `pcdt-de-insuficiencia-cardiaca.pdf`. Padrão: E11/J45 (extração com páginas,
exclusões citadas, posologia citável, rascunho para assinatura — sem flip).

---

*Rodadas registram-se abaixo.*

## Rodada 1 — sáb 05/09, 09:00

- ✅ Cron disparou no horário (o desenho multi-rodada venceu o fantasma do tiro único de 30/08).
- ✅ Sanidade: `/health` ok · repo público 200.
- ✅ **I10 v2 ESTRITO executado e entregue: PR #256** (branch `curadoria/i10-v2-estrito-fabiano`).
  - CSV: 110→66 (I10 61→17, fonte por row com página da RENAME + SBC coadjuvante); posologia 28→27 (clortalidona fora).
  - Guarda nova `test_semaforo_flip_i10_v2.py` (7 testes); suíte completa **650 passed**.
  - Sinal verde verbatim citado na PR; as 44 excomungadas listadas no corpo.
  - **Aguarda martelo do Fabiano.**
- ⚠️ Pendência para o engenheiro: o `backend/.venv` do clone novo está **quebrado** (symlink para `miniforge3` que não resolve). Rodei com o venv do backup. Recriar com o python do sistema.
- ✅ #255 verificada MERGED (atribuição institucional fechada).

## Rodada 2 — sáb 05/09, 15:00

- ✅ Auto-resgate desnecessário: PR #256 existe, gates SUCCESS (smokes ausente é esperado — PR de dados, CI filtrado por path).
- ✅ Sanidade: `/health` ok · repo 200.
- ✅ Lente com objeto fresco: `1fc2f628…` (receita de enalapril — sobrevivente do I10 v2, a propósito) → `/public` neutro, forma correta.
- ✅ Linha institucional verificada AO VIVO nos três lugares: rodapé da abertura, rodapé do demo.html (decisão de estensão implementada na #255) e emenda do FAQ ("projeto de extensão da UFPE, em código aberto…").
- ✅ Página obras: linha de consentimento da lista de espera ao vivo.
- Nota: a instrução R2 do manual citava a linha institucional "no entrar.html" — imprecisão do prompt (a linha mora nos rodapés da abertura e do demo); corrigido na verificação, sem dano.

## Rodada 3 — sáb 05/09, 18:00

- ✅ Sanidade: `/health` ok · repo 200.
- ✅ FILA-VIVA atualizada: I10 v2 (#256, aguardando martelo) registrada no topo da seção curadoria.
- **Fecho do dia de sábado:** R1 entregou a PR #256 (I10 v2 estrito, 650✓); R2 validou tudo ao vivo (lente, linha institucional nos três lugares, consentimento da lista). Nenhum alarme. Nenhum resgate preciso.
- Amanhã (domingo): R4 09:00 — levantura J44 (DPOC) + I50 (IC) do corpus; R5 15:00 — self-check das citações; R6 18:00 — fecho.

## Rodada 4 — dom 06/09, 09:00

- ✅ Sanidade: `/health` ok · repo 200.
- ✅ **Levantura dupla lavrada** (padrão E11/J45, e pela primeira vez com o critério estrito NATIVO — PCDT ∩ RENAME 2024, páginas duplas):
  - `RASCUNHO-J44-DUPLO-PCDT-2026.md` — DPOC, Port. Conjunta SAES/SCTIE 29/2025: 7 chaves + combinação formoterol+budesonida; fluticasona/teofilina/roflumilaste/salmeterol fora (com razão e página); 1 ponto de decisão (fluticasona 🟡 vs 🟢-declarado).
  - `RASCUNHO-I50-DUPLO-PCDT-2026.md` — IC FEr, Port. Conjunta SAES/SECTICS 10/2024: 13 chaves (sacubitril+valsartana e dapagliflozina inclusos, ambos renomeados); bisoprolol e ivabradina fora por RENAME (ponto de decisão).
- Achado de época registrado: PCDT de IC é set/2024 — conferir atualização CONITEC antes da assinatura (nota no rascunho).
- Posologia de ambos: pendente de levantura na assinatura (não se inventa row — precedente F32).
- SEM flip, SEM PR, como mandava a rodada. Rascunhos na mesa do Fabiano.

## Rodada 5 — dom 06/09, 15:00

- ✅ Sanidade: `/health` ok · repo 200. Rascunhos da R4 no lugar (auto-resgate desnecessário).
- ✅ **SELF-CHECK 9/9**: portarias verbatim (SAES/SCTIE 29/2025 · SAES/SECTICS 10/2024); tiotrópio p.16, teofilina p.18 (DPOC); NYHA II p.8, digoxina p.32 (IC); RENAME: dapagliflozina p.29 (componente Especializado, não índice), sacubitril+valsartana p.46 e p.212.
- ✅ **Confirmação circular achada**: a RENAME p.212 lista sacubitril valsartana citando como documento norteador o PRÓPRIO PCDT de IC estagiado — PCDT e RENAME apontando um para o outro.
- ✅ **O self-check pagou a rodada**: achou os dois LAMAs irmãos que a primeira passada perdeu (p.16: glicopirrônio, tiotrópio, umeclidínio na mesma frase). Rascunho J44 EMENDADO: umeclidínio entra no elenco (RENAME p.107/174); glicopirrônio fora por ausência na RENAME (registrado no §2 com as duas opções de decisão).

## Encerramento póstumo (13/09, arquiteto Z — auditoria a pedido de "como foi a vigília?")

A **R6 (fecho, dom 06/09 18:00) falhou em silêncio** — o cron não disparou (5/6
execuções; próximo disparo recalculado para 05/09/2027). O mesmo defeito que este
prompt citava como lição de 30/08. Encerrada aqui por auditoria: o trabalho das
rodadas 1–5 está registrado acima e prosperou (I10 v2 estrito martelado; F32/N39.0
assinados 02/09, #249; o corpus seguiu alimentando a curadoria). Nada pendente
desta agenda além da recomendação de deletar a automação zumbi
(`automation-51ea8a52…`) — gesto do Fabiano.
