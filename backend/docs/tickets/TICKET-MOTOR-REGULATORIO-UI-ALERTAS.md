# TICKET-MOTOR-REGULATORIO-UI-ALERTAS — tornar visível o motor regulatório no prescritor.html

> **Origem:** decisão arquitetural de 2026-05-27 (Fabiano + Arquiteto). Motor regulatório está 70-80% implementado mas **invisível ao usuário** — grep retornou zero matches de `classe_controle`/`grupo_regulatorio`/`tipo_retencao` em `prescritor.html`. O motor calcula, o oráculo valida, mas o prescritor não recebe sinal visual durante a prescrição.
> **Classe:** `module` (toca `prescritor.html` + endpoint novo de validação live + integração com IA DEF existente).
> **Ritmo:** Regra 2 estrita (~150-200 linhas previstas; classe `module` toca frontend + integração backend). Ticket rodada 0 → CODEX rodada 1 → Code impl → CODEX rodada 2.
> **Prazo:** após o TICKET-MOTOR-REGULATORIO-AUDITORIA-CATALOGO ter pelo menos 50% das substâncias auditadas (catálogo estável o suficiente para testar alertas com confiança). Estimativa: início em 2 semanas, fechamento em 1 semana de trabalho.
> **Predecessor:** Etapa 6 fechada (`5005271`); TICKET-MOTOR-REGULATORIO-AUDITORIA-CATALOGO em curso pelos extensionistas.

---

## §1 Contexto

O PicSaúde tem motor regulatório implementado (TICKET-15 + 18 + 20). Quando o prescritor adiciona um item à prescrição com `classe_controle = "B1"`, o backend roteia esse item para o grupo regulatório "Notificação Azul" e exige assinatura qualificada (ICP-Brasil A1/A3). O oráculo `catalogo_regulatorio.py` valida a declaração contra o catálogo seed.

**Mas o prescritor não vê nada disso na tela.** Hoje, ao digitar "amoxicilina" no formulário de prescrição, o sistema aceita silenciosamente sem `tipo_retencao` declarado. Quando a prescrição é emitida, o motor regulatório classifica como receita simples branca — porque o prescritor não declarou `tipo_retencao = antimicrobiano`. **Erro regulatório invisível.**

Este ticket torna o motor regulatório **visível**. Quando o prescritor adiciona "amoxicilina", a UI consulta o catálogo regulatório, sugere automaticamente `tipo_retencao = antimicrobiano`, e mostra alerta amarelo "esta substância exige retenção de receita (IN 83/2021)". O prescritor pode aceitar a sugestão (default) ou rejeitar com justificativa registrada. Tornar visível o que o sistema já sabe.

## §2 Escopo

### §2.1 Endpoint novo — `POST /ia/regulatorio/classificar`

Cria endpoint backend que recebe dados de um item de prescrição em edição e retorna a classificação regulatória sugerida + alertas:

**Request:**
```json
{
  "dcb": "amoxicilina",
  "classe_controle_declarada": null,
  "tipo_retencao_declarado": null
}
```

**Response:**
```json
{
  "classificacao_sugerida": {
    "classe_controle": null,
    "tipo_retencao": "antimicrobiano",
    "fonte": "in_83_2021",
    "dcb_encontrada": "Amoxicilina"
  },
  "alertas": [
    {
      "severidade": "warning",
      "codigo": "tipo_retencao_ausente",
      "mensagem": "Esta substância exige retenção de receita conforme IN 83/2021. Recomendado declarar tipo_retencao=antimicrobiano.",
      "campo_sugerido": "tipo_retencao",
      "valor_sugerido": "antimicrobiano"
    }
  ],
  "grupo_regulatorio_estimado": "branco_retencao",
  "tipo_receituario_estimado": "branca_retencao"
}
```

Quando o catálogo não conhece a substância: response com `classificacao_sugerida: null` + `alertas: []` (princípio de cautela do TICKET-20).

Quando a declaração do prescritor diverge do catálogo (`classe_controle_declarada="B1"` mas catálogo diz `"C1"`): response com alerta `severidade: "critical"`.

**Implementação backend:** wrapper sobre `catalogo_regulatorio.py` (já existe). Endpoint em `backend/app/routers/ia.py` (junto com IA DEF/CID/TUSS) ou em router próprio `backend/app/routers/ia_regulatorio.py`.

### §2.2 Integração IA DEF ↔ classificação regulatória

Quando o prescritor digita um medicamento no campo Fármaco em `prescritor.html` e a IA DEF retorna sugestão de forma/unidade (atual), também consultar `/ia/regulatorio/classificar` em paralelo. Resposta da IA DEF aumentada:

```javascript
// Hoje (DEF apenas):
{
  forma: "comprimido",
  unidade: "comprimido",
  fonte: "DEF/BASE_LOCAL",
  confianca: "alta"
}

// Proposto (DEF + regulatório):
{
  forma: "comprimido",
  unidade: "comprimido",
  fonte: "DEF/BASE_LOCAL",
  confianca: "alta",
  regulatorio: {
    classe_controle_sugerida: null,
    tipo_retencao_sugerido: "antimicrobiano",
    fonte_regulatoria: "in_83_2021",
    alertas: [...]
  }
}
```

**Decisão arquitetural:** o endpoint backend `/ia/medicamentos/sugerir` (atual da IA DEF) pode chamar internamente `catalogo_regulatorio.classificar()` e devolver tudo em uma única resposta — economiza round-trip. **OU** o frontend faz duas chamadas em paralelo (`/ia/medicamentos/sugerir` + `/ia/regulatorio/classificar`). Decisão fica para a rodada 1 do CODEX — preferência inicial pela primeira opção (menos round-trips, contrato mais coeso), mas validar se não viola separação de responsabilidades.

### §2.3 UI dos alertas no `prescritor.html`

Quando a sugestão regulatória vem com alertas, mostrar bloco visual abaixo do campo Fármaco. Espelha o padrão atual de `.ia-bloco-neutro` / `.ia-bloco-sugestao` que já existe no `prescritor.html` (TICKET-6.1 P1#1 estabeleceu esse padrão visual).

Três níveis visuais:

- **info** (azul) — informativo. Ex: "Esta substância está no anexo X da Portaria 344/1998 (subcategoria C5 — antirretrovirais)." Não exige ação.
- **warning** (amber) — divergência leve. Ex: "Esta substância exige retenção de receita conforme IN 83/2021. Recomendado declarar `tipo_retencao=antimicrobiano`." Sugere ação; aceitar a sugestão é o caminho default.
- **critical** (vermelho) — divergência grave. Ex: "Atenção: substância controlada (classe C1) declarada como livre. Conferir Portaria 344/1998." Exige justificativa explícita do prescritor antes de continuar a emissão.

Cada alerta tem botão "Aplicar sugestão" que preenche os campos `classe_controle` e `tipo_retencao` no item de prescrição. Botão "Manter como está" mantém a declaração do prescritor + registra evento no ledger (`alerta_regulatorio_rejeitado`).

### §2.4 Indicador de tipo de receituário no formulário

No topo do formulário de prescrição, junto com o seletor de "Validade: 30 dias", adicionar indicador dinâmico: **"Tipo de receituário: [Branco simples / Branco retenção / Amarelo Notificação A / Azul Notificação B / Especial]"**.

Calculado em tempo real conforme itens são adicionados. Quando muda (ex: prescritor adiciona um item B1 e o receituário muda de "branco simples" para "azul notificação B"), animar a mudança visualmente (fade + cor por 300ms) para o prescritor perceber.

Backend: pode-se reusar o endpoint atual `POST /prescricoes/{proto}/receituarios/gerar` em modo "preview" (sem persistência), ou criar `POST /receituarios/preview` que recebe lista de itens em edição e retorna tipo de receituário previsto.

### §2.5 Override pelo prescritor (registro no ledger)

Quando o prescritor rejeita uma sugestão regulatória (clica "Manter como está" em um alerta `warning` ou `critical`), registrar evento no ledger:

```sql
INSERT INTO prescricao_eventos (
  prescricao_id, evento, ator_cns, dados_json, criado_em
) VALUES (
  NULL,  -- prescrição ainda em edição, evento avulso
  'alerta_regulatorio_rejeitado',
  ?,
  '{"item_dcb": "amoxicilina", "alerta_codigo": "tipo_retencao_ausente", "severidade": "warning", "justificativa_prescritor": "..."}',
  NOW()
);
```

Justificativa do prescritor é campo livre — para `warning` é opcional (textarea pequeno); para `critical` é obrigatório (textarea com mínimo 20 caracteres). Permite auditoria posterior de divergências entre declaração do prescritor e oráculo do catálogo.

**Nota arquitetural:** este evento é avulso (sem `prescricao_id`) porque acontece em tempo de edição, antes da emissão. Não bloqueia emissão; apenas registra para auditoria. Em produção real (não demo), esses eventos viram input para análises agregadas — quais substâncias são mais frequentemente "ignoradas" pelos prescritores? Sinal de problema regulatório real ou problema do catálogo?

## §3 Critérios de aceite

1. **Endpoint `POST /ia/regulatorio/classificar`** existe, retorna classificação sugerida + alertas, cobre os 3 cenários (substância conhecida sem divergência / substância conhecida com divergência / substância desconhecida).
2. **IA DEF aumentada** (decisão de §2.2): quando prescritor digita medicamento, a sugestão visual inclui informação regulatória + alertas.
3. **UI dos alertas** no `prescritor.html` exibe info/warning/critical com cores apropriadas, botões "Aplicar sugestão" / "Manter como está" funcionais.
4. **Indicador de tipo de receituário** no topo do formulário atualiza dinamicamente conforme itens são adicionados/removidos.
5. **Override registra evento no ledger** com justificativa do prescritor.
6. **Testes:**
   - Unit do endpoint `/ia/regulatorio/classificar` para 3 substâncias (1 antimicrobiano, 1 controlado classe B1, 1 desconhecida).
   - Integração: emitir prescrição com amoxicilina, confirmar que `tipo_retencao` foi preenchido via sugestão (não via declaração manual do prescritor).
   - Integração: rejeitar sugestão warning, confirmar que evento `alerta_regulatorio_rejeitado` aparece no ledger.
7. **Smoke completo:** `cd backend && pytest tests/ -x --tb=short` zero regressões.

## §4 Verificação automatizada

```bash
# Endpoint
curl -X POST http://127.0.0.1:8000/ia/regulatorio/classificar \
  -H "Content-Type: application/json" \
  -d '{"dcb": "amoxicilina", "classe_controle_declarada": null, "tipo_retencao_declarado": null}' \
  | jq

# Esperado: tipo_retencao_sugerido = "antimicrobiano" + 1 alerta warning

# Smoke completo
cd backend && pytest tests/ -x --tb=short
```

Verificação visual manual (paralela ao Fix C do TICKET-6.2):

1. Subir demo (`PICSAUDE_DEMO_MODE=true` + `PICSAUDE_ENV=dev`).
2. Entrar como prescritor (Dra. Demo Maria Souza).
3. Adicionar item "Amoxicilina 500mg" → confirmar que alerta amber "exige retenção" aparece.
4. Clicar "Aplicar sugestão" → confirmar que `tipo_retencao` foi preenchido no item.
5. Indicador no topo do formulário deve mostrar "Tipo de receituário: Branco retenção".
6. Adicionar item "Clonazepam" (B1) → indicador muda para "Azul Notificação B".
7. Tentar rejeitar a sugestão de classe controlada → confirmar que textarea obrigatório aparece com mínimo 20 caracteres.

## §5 Predecessoras

- HEAD pré-impl: TBD na hora.
- TICKET-MOTOR-REGULATORIO-AUDITORIA-CATALOGO com pelo menos 50% das 55 substâncias auditadas (catálogo estável para testar alertas).
- Etapa 5C-bis em curso ou fechada — não bloqueia este ticket porque domínios não colidem (5C-bis toca routers de autorização; este ticket toca `prescritor.html` + `routers/ia.py`).

## §6 Anti-escopo

- **NÃO bloquear emissão** mesmo em alertas `critical`. O prescritor pode sempre proceder com justificativa registrada — princípio do PicSaúde é apoiar decisão clínica, não substituí-la.
- **NÃO sugerir interação medicamentosa** ou contraindicações neste ticket. Foco estrito em classificação regulatória da substância individual. Interações ficam para v1.1+.
- **NÃO alterar o motor regulatório (`motor_regulatorio.py`) ou o oráculo (`catalogo_regulatorio.py`).** Eles ficam intocados — este ticket os **consume**, não os **modifica**.
- **NÃO expandir o catálogo** neste ticket. Expansão fica para TICKET-MOTOR-REGULATORIO-EXPANSAO-CATALOGO pós-MVP.
- **NÃO refatorar o padrão visual** de `.ia-bloco-*` existente. Reusar exatamente como está (definido no TICKET-6.1 P1#1).

## §7 Classe, volume, ritmo

- **Classe:** `module` (frontend + endpoint novo + integração com IA existente).
- **Volume estimado:** ~50-80 linhas backend + ~80-120 linhas frontend = ~150-200 total.
- **Ritmo:** Regra 2 estrita (>100 linhas, classe `module`). Rodada 0 (este ticket) → CODEX rodada 1 → Code impl → CODEX rodada 2.
- **Participação de extensionistas:** 1-2 extensionistas com perfil técnico (informática biomédica) ajudam na implementação sob **mentoria sincronizada** — Arquiteto + Code revisam JUNTOS antes do CODEX. Especificamente: extensionista pode pegar §2.3 (UI dos alertas) e §2.4 (indicador de tipo de receituário) — escopo de frontend bem definido. §2.1 (endpoint backend) e §2.5 (override no ledger) ficam com Code.

## §8 Prompt sugerido ao Code (preenchido após CODEX rodada 1)

*A ser preenchido após CODEX rodada 1 sobre este ticket integrada em §10.*

---

## §9 Reservado — CODEX rodada 1 sobre este ticket

*Será preenchido quando CODEX revisar esta spec.*

## §10 Reservado — output do Code pós-impl

*Preenchido pelo Code ao terminar a implementação.*

## §11 Reservado — CODEX rodada 2 pós-impl

*Preenchido após CODEX rodada 2 sobre o commit final.*
