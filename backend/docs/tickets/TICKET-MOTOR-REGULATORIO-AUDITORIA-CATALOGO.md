# TICKET-MOTOR-REGULATORIO-AUDITORIA-CATALOGO — auditoria regulatória pelos extensionistas UFPE

> **Origem:** decisão arquitetural de 2026-05-27 (Fabiano + Arquiteto). Motor regulatório está 70-80% implementado em código; o trabalho restante de catálogo é domínio-específico e cabe aos 7 extensionistas sanitaristas/farmacêuticos/médicos/biomédicos.
> **Classe:** `local-extension` (revisão e expansão de catálogo regulatório; não altera semântica clínica do motor — atualiza dados auditados em `catalogo_seed.py`).
> **Ritmo:** trabalho contínuo dos extensionistas em PRs individuais; mentoria de cadência semanal pelo Arquiteto.
> **Prazo:** primeira leva de auditoria em 2 semanas (até 2026-06-10); auditoria completa das 55 substâncias em 3-4 semanas.
> **Predecessor:** Etapa 6 fechada (`5005271`); extensionistas onboarded como collaborators do repo.

---

## §1 Para quem este ticket fala

Este ticket é **para os 7 extensionistas UFPE** que entram no projeto PicSaúde a partir de 2026-05-27. Não é ticket técnico de programação — é ticket de **auditoria regulatória** que pede competência de domínio (farmácia, medicina, biomedicina, enfermagem, saúde pública).

Cada extensionista vai conferir a classificação de ~5-10 substâncias do catálogo regulatório do PicSaúde contra fontes primárias oficiais da Anvisa. Output esperado: PR individual atualizando o arquivo `backend/app/domain/catalogo_seed.py` com correções ou confirmações, e nota explicativa citando fonte primária.

**Pré-requisito:** ter conta GitHub, estar adicionado como collaborator do repo `Tonaco-13/PicSaude`, ter conseguido subir o PicSaúde local seguindo o `CONTRIBUTING-EXTENSAO.md`.

## §2 Contexto regulatório

O PicSaúde implementa um motor regulatório que classifica cada item de prescrição em um grupo regulatório (receituário branco simples / branco retenção / amarelo notificação A / azul notificação B / especial). Essa classificação é fonte da decisão sobre que tipo de receituário emitir, que assinatura digital exigir, e como o item é tratado na cadeia de custódia.

A classificação depende de dois campos declarados pelo prescritor no item de prescrição:

- `classe_controle` — listas A1/A2/A3/B1/B2/C1/C2/C3/C4/C5/D1/D2 da **Portaria SVS/MS nº 344/1998** (substâncias sob controle especial).
- `tipo_retencao` — valores `antimicrobiano` ou `glp1_agonista` da **RDC Anvisa nº 471/2021 + IN 83/2021 (antimicrobianos)** e **IN 360/2025 (agonistas de GLP-1)**.

O motor confia nesses valores. Se forem declarados incorretamente (ou omitidos), a classificação fica errada — e o sistema emite uma receita simples branca para um medicamento que exigiria notificação amarela. **Erro regulatório grave que expõe a plataforma a risco de autuação pela Anvisa em produção real.**

O catálogo de substâncias (`catalogo_seed.py`) serve como **oráculo de validação cruzada**: quando o prescritor declara `classe_controle = NULL` para amoxicilina, o catálogo responde "amoxicilina é antimicrobiano por IN 83/2021" e emite alerta. **A confiabilidade desse alerta depende da confiabilidade do catálogo.** Por isso este ticket existe — antes de qualquer uso clínico real, cada substância do seed precisa ser conferida contra a fonte primária.

## §3 O que cada extensionista vai fazer

### §3.1 Setup inicial (Day 1 dos extensionistas)

1. Criar conta no GitHub.com se ainda não tiver (gratuito, 2 minutos).
2. Mandar para Fabiano o handle GitHub + e-mail vinculado.
3. Esperar convite de collaborator do repo `Tonaco-13/PicSaude` chegar por e-mail.
4. Aceitar convite.
5. Seguir o `CONTRIBUTING-EXTENSAO.md` da raiz do repo para subir o PicSaúde local.
6. Confirmar que o demo está rodando localmente (banner amarelo "MODO DEMO" aparece no `http://127.0.0.1:8000/index.html`).

### §3.2 Distribuição das 55 substâncias

O arquivo `backend/app/domain/catalogo_seed.py` tem três blocos:

- **`SEED_GLP1`** — 5 substâncias (semaglutida, liraglutida, dulaglutida, tirzepatida, lixisenatida).
- **`SEED_ANTIMICROBIANOS`** — 30 substâncias (a confirmar exatamente quais ao abrir o arquivo).
- **`SEED_PORTARIA_344`** — 20 substâncias (a confirmar exatamente quais ao abrir o arquivo).

Total: 55 substâncias. A distribuição entre os 7 extensionistas será definida na reunião de 2026-05-27 com base nas formações. Sugestão inicial:

| Formação preferencial | Bloco | Volume |
|---|---|---|
| Farmácia / Endocrinologia | SEED_GLP1 | 5 substâncias |
| Farmácia / Medicina / Infectologia | SEED_ANTIMICROBIANOS | 30 substâncias (divididas em 3-4 lotes de ~7-10) |
| Psiquiatria / Farmácia / Medicina | SEED_PORTARIA_344 | 20 substâncias (divididas em 2-3 lotes de ~7-10) |
| Apoio geral (saúde coletiva / enfermagem) | revisão cruzada | qualquer bloco que precise de segundo olhar |

A divisão exata fica para acordo direto entre os 7 e o Fabiano. **Princípio:** ninguém audita uma substância de área que desconhece. Se preciso, dividir consultando especialista da equipe.

### §3.3 Para cada substância atribuída

Para cada substância no seu lote, o extensionista deve:

1. **Abrir o arquivo `backend/app/domain/catalogo_seed.py`** no editor e localizar a entrada da substância (formato `(dcb_display, classe_controle, tipo_retencao, fonte, observacao)`).

2. **Conferir a classificação contra a fonte primária declarada.** A `fonte` no seed indica qual instrumento foi referenciado:
   - `in_360_2025` → IN Anvisa nº 360/2025 (agonistas de GLP-1)
   - `in_83_2021` → IN Anvisa nº 83/2021 (antimicrobianos)
   - `portaria_344_1998` → Portaria SVS/MS nº 344/1998 (com atualizações por RDCs)
   - Outras fontes possíveis: RDC 20/2011, RDC 471/2021

3. **Buscar a fonte primária online** (DOU, site Anvisa, base oficial). Confirmar:
   - A substância está realmente listada nessa fonte?
   - A classificação (`classe_controle` ou `tipo_retencao`) está correta?
   - A fonte ainda está vigente (não foi revogada)?

4. **Decidir uma de três ações:**
   - ✅ **Confirmado** — classificação correta. Adicionar comentário inline no seed com: data da conferência, link da fonte primária, e suas iniciais. Exemplo: `# Confirmado 2026-06-03 por F.S. — DOU 2025-06-23, IN 360/2025 art. 2º`.
   - 🔄 **Correção** — classificação errada. Alterar o campo no seed + comentário explicativo + link da fonte.
   - ⚠️ **Marcar para revisão** — algum detalhe não está claro. Manter classificação atual mas adicionar comentário com a dúvida específica. Outro extensionista (ou Fabiano) revisa.

5. **Abrir Pull Request individual** no GitHub:
   - Branch: `audit-catalogo-{seu-handle}-{lote}` (ex: `audit-catalogo-mariaufpe-glp1`).
   - Mensagem do PR: "Auditoria regulatória — [BLOCO] — [substâncias auditadas]".
   - Corpo do PR: lista das substâncias revisadas + decisão de cada uma (✅/🔄/⚠️) + fontes consultadas.
   - Solicitar review do Fabiano (@tonaco-13).

### §3.4 Como pesquisar a fonte primária

Recursos oficiais:

- **DOU (Diário Oficial da União)** — `https://www.in.gov.br` — busque o número da IN ou RDC.
- **Site Anvisa** — `https://www.gov.br/anvisa/pt-br` — seção "Legislação".
- **Anvisa Legis** — `https://antigo.anvisa.gov.br/legislacao` (base histórica).
- **Portaria 344/1998 consolidada** — busque "Portaria 344 1998 consolidada com atualizações" para versão atual com todas as RDCs incorporadas.

Princípio: nunca aceitar resumo de blog, Wikipedia, ou bula como fonte primária. **Sempre verificar o documento oficial da Anvisa ou do Ministério da Saúde.**

### §3.5 Formato do comentário no seed

Padrão de comentário inline em `catalogo_seed.py`:

```python
# Confirmado YYYY-MM-DD por INICIAIS — [Fonte primária com URL ou referência completa]
("Semaglutida",   None, "glp1_agonista", "in_360_2025", None),

# Corrigido YYYY-MM-DD por INICIAIS — classe_controle alterada de NULL para C1
# Fonte: Portaria SVS/MS 344/1998 art. X, consolidada por RDC 47/2023
# URL: https://www.gov.br/anvisa/pt-br/...
("Substância-X", "C1", None, "portaria_344_1998", None),

# REVISAR YYYY-MM-DD por INICIAIS — substância não localizada na IN 83/2021;
# pode estar na IN 360/2025 (não verificado)? Pedido segundo olhar de especialista.
("Substância-Y", None, "antimicrobiano", "in_83_2021", None),
```

## §4 Critérios de aceite

### Por substância auditada

1. Comentário inline no `catalogo_seed.py` com data + iniciais do auditor + fonte primária citada (URL ou referência completa).
2. Decisão explícita: ✅ Confirmado / 🔄 Corrigido / ⚠️ Revisar.
3. Se 🔄: alteração no campo do seed efetivamente aplicada.
4. Se ⚠️: descrição clara da dúvida no comentário.

### Por PR de extensionista

1. PR contém apenas mudanças no `catalogo_seed.py` (não tocar em outros arquivos).
2. Branch nomeada conforme convenção `audit-catalogo-{handle}-{lote}`.
3. Corpo do PR lista as substâncias auditadas + decisões + fontes.
4. Review aprovado pelo Fabiano antes do merge.

### Para o ticket fechar

1. 100% das 55 substâncias auditadas pelo menos uma vez.
2. Todas as marcadas com ⚠️ revisadas por segundo extensionista ou pelo Fabiano.
3. Zero classificações inconsistentes entre o catálogo e a Portaria 344/IN 83/IN 360 vigentes.

## §5 Anti-escopo

- **NÃO tocar em código Python além do `catalogo_seed.py`.** O motor regulatório (`motor_regulatorio.py`), o oráculo (`catalogo_regulatorio.py`) e o vocabulário (`retencao.py`) não são parte deste trabalho de auditoria.
- **NÃO expandir a lista de substâncias para mais de 55** neste ticket. Expansão (anti-hipertensivos, anticonvulsivantes, ansiolíticos, antidepressivos) vira **TICKET-MOTOR-REGULATORIO-EXPANSAO-CATALOGO** a abrir depois deste fechar.
- **NÃO sugerir mudanças arquiteturais ao motor.** A arquitetura do motor é decidida; este ticket só audita dados.
- **NÃO discutir UI dos alertas** neste ticket. UI fica no TICKET-MOTOR-REGULATORIO-UI-ALERTAS, paralelo a este.
- **NÃO consolidar PRs múltiplos em PR único.** Cada extensionista abre o seu — pedagógico (cada um aprende fluxo Git) e auditável (cada decisão tem autor claro).

## §6 Mentoria e ritmo

- **Encontro semanal de mentoria** (1h, online ou presencial) — Fabiano + Arquiteto + extensionistas. Tira dúvidas regulatórias, conferem fontes em conjunto, calibram decisões controversas.
- **Slack/Discord/grupo WhatsApp** da extensão para perguntas rápidas entre encontros.
- **Resposta a PRs em até 48h** pelo Fabiano. Pedido de mudança não trava trabalho — extensionista pode partir para a próxima substância enquanto a anterior é refinada.

## §7 Saída esperada do trabalho coletivo

Após 3-4 semanas, o `catalogo_seed.py` estará com:

- 55 substâncias auditadas individualmente, cada uma com comentário citando fonte primária verificada.
- Conjunto de correções aplicadas (esperado: 5-15% das classificações iniciais precisem de ajuste, dada a nota de "REVISÃO REGULATÓRIA NECESSÁRIA" do próprio arquivo).
- Marcadores ⚠️ resolvidos por segundo olhar.

Esse catálogo auditado se torna a base de confiança do motor regulatório do PicSaúde. Em paralelo, o TICKET-MOTOR-REGULATORIO-UI-ALERTAS torna essa confiança visível no `prescritor.html` para o usuário final do sistema. Os dois tickets juntos completam o motor regulatório demo-grade.

## §8 Para depois

O **TICKET-MOTOR-REGULATORIO-EXPANSAO-CATALOGO** (a abrir depois deste fechar) expande o catálogo de 55 para 200+ substâncias, cobrindo classes terapêuticas frequentes na atenção primária — anti-hipertensivos, anticonvulsivantes, ansiolíticos, antidepressivos, anti-inflamatórios, hormônios, anticoagulantes. Trabalho contínuo dos extensionistas pós-MVP.

---

## §9 Status do ticket

> **2026-05-27 — ticket criado, aguardando reunião com 7 extensionistas:**
> Origem: decisão arquitetural pré-reunião 14h ✅
> Investigação do motor regulatório ✅ (70-80% implementado)
> Spec por substância (§3.3) ✅
> Critérios de aceite (§4) ✅
> Anti-escopo (§5) ✅
> Ritmo de mentoria (§6) ✅
> Reunião 14h — distribuição das 55 substâncias entre os 7 conforme formações
> Pós-reunião — onboarding dos 7 como collaborators do repo + Day 1 (subir PicSaúde local)
> Auditoria começa quando primeiro extensionista subir o PicSaúde local com sucesso
