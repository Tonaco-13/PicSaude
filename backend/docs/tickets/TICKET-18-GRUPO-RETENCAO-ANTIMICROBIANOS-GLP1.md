# TICKET 18 — GRUPO RETENÇÃO: ANTIMICROBIANOS E GLP-1 (PICSAÚDE)

## Prompt para Claude Code

> Cole o texto abaixo no seu Claude Code.

---

```
=== TICKET 18 — GRUPO RETENÇÃO (ANTIMICROBIANOS / GLP-1) ===

CONTEXTO

O PicSaúde possui motor regulatório (Ticket 15) que classifica
itens de prescrição por grupo regulatório usando o campo
classe_controle (A1, A2, A3, B1, B2, C5, D1, D2).

Esse campo foi desenhado para a Portaria SVS/MS nº 344/1998,
que classifica substâncias por LISTAS regulatórias (A, B, C, D).

PORÉM, existem medicamentos que exigem retenção de receita mas
NÃO pertencem às listas da Portaria 344:

1. ANTIMICROBIANOS — regulados pela RDC 471/2021 (que substituiu
   a RDC 20/2011). Classificados por SUBSTÂNCIA (DCB), não por
   lista/classe. Código SNGPC = "1".

2. AGONISTAS DE GLP-1 — incluídos na RDC 471/2021 pela
   IN nº 360/2025 (vigente desde 23/06/2025). Substâncias:
   semaglutida, liraglutida, dulaglutida, tirzepatida,
   lixisenatida. Código SNGPC = "1" (referência documental,
   NÃO usar na lógica do motor neste ticket).
   NOTA: Exenatida é agonista GLP-1 mas NÃO entrou na lista
   da IN 360/2025 por não haver registro válido no Brasil.
   Monitorar em ticket futuro — não incluir como ativo.

O GRUPO_RETENCAO já está SCAFFOLDED no motor regulatório:
- Definido em motor_regulatorio.py com todos os atributos
  (assinatura_minima="avancada", vias=2, requer_sncr=False)
- MAS com classes=frozenset() — VAZIO
- status_implementacao="pendente_classificacao"
- Nenhuma classe_controle roteia para ele

PROBLEMA ARQUITETURAL:
O campo classe_controle (String(10)) foi feito para códigos da
Portaria 344 (A1, B1, C5, etc.). Antimicrobianos e GLP-1 são
de outro sistema regulatório (RDC 471/2021). Inventar códigos
falsos como "C6" ou "E1" conflitaria dois sistemas normativos
diferentes e geraria confusão regulatória.

SOLUÇÃO: Criar campo tipo_retencao separado no modelo de itens,
que identifica substâncias sujeitas a retenção FORA da Portaria
344. O motor regulatório passa a verificar DOIS campos:
tipo_retencao (prioridade) e classe_controle (fallback).

Este é um ticket de CLASSIFICAÇÃO + MOTOR.
O PDF e o SNCR stub já suportam "receita_retencao".

O diretório do projeto é:
/Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

Instruções de reconexão do PostgreSQL:
PGBIN=~/Library/Python/3.9/lib/python/site-packages/pgserver/pginstall/bin
$PGBIN/pg_ctl -D /tmp/picsaude-pgdata -l /tmp/picsaude-pgdata/pg.log start
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_dev

--------------------------------------------------
OBJETIVO
--------------------------------------------------

1. Criar campo tipo_retencao em prescricao_itens
2. Atualizar motor regulatório para rotear itens com
   tipo_retencao para GRUPO_RETENCAO
3. Ativar GRUPO_RETENCAO (status="ativo")
4. Corrigir discrepância de abreviação RTC vs RRT
5. Testes de integração do fluxo completo
6. Documentação

--------------------------------------------------
ESCOPO
--------------------------------------------------

ENTRA:
- Campo tipo_retencao em prescricao_itens (migration)
- Lógica de roteamento no motor regulatório
- Ativação do GRUPO_RETENCAO
- Correção de abreviação RTC→RRT (ou vice-versa)
- Testes de integração
- Documentação

NÃO ENTRA:
- Catálogo completo de substâncias antimicrobianas (seria um
  banco de dados inteiro — escopo de Ticket futuro)
- Integração com SNGPC (outro sistema, escopo futuro)
- Validação de prazo de validade diferenciado (10 vs 90 dias)
- Alteração no PDF de receituário (já suporta receita_retencao)
- Alteração no SNCR adapter (já suporta receita_retencao)
- Integração real com SNCR (Ticket 16B)

--------------------------------------------------
PASSO 1 — INVESTIGAÇÃO PRÉVIA (OBRIGATÓRIO)
--------------------------------------------------

ANTES de escrever código, ler e entender:

1. app/domain/motor_regulatorio.py
   - GRUPO_RETENCAO (definição, status, observacao)
   - MAPA_CLASSE_GRUPO — como funciona
   - grupo_regulatorio() — lógica de lookup
   - agrupar_por_receituario() — como agrupa

2. app/domain/medicamento.py
   - CLASSES_CONTROLE_ESPECIAL
   - eh_item_atomizavel()

3. app/models/prescricao_item.py
   - Campo classe_controle existente

4. app/adapters/sncr_stub.py
   - _ABREV_TIPO: verificar abreviação de "receita_retencao"
   - Deve ser "RTC" — confirmar

5. app/domain/pdf_receituario.py
   - CORES_RECEITUARIO["receita_retencao"]["tipo_abrev"]
   - Deve ser "RRT" — confirmar a DISCREPÂNCIA com sncr_stub

6. tests/integration/test_receituarios.py
   - test_validacao_assinatura_govbr_atende_avancada
   - Como testa GRUPO_RETENCAO hoje (bypass direto)

Reportar:
- Abreviação no sncr_stub.py vs pdf_receituario.py
- Status atual do GRUPO_RETENCAO
- Quais classes mapeiam para ele (deve ser nenhuma)

--------------------------------------------------
PASSO 2 — DECISÃO ARQUITETURAL (CAMPO tipo_retencao)
--------------------------------------------------

JUSTIFICATIVA REGULATÓRIA:

A Portaria 344/1998 classifica substâncias por LISTAS:
  A1 (entorpecentes), B1 (psicotrópicos), C5, D1, D2...
  → Campo: classe_controle

A RDC 471/2021 classifica substâncias por TIPO DE RETENÇÃO:
  antimicrobiano, glp1_agonista
  → Campo: tipo_retencao (NOVO)

São dois sistemas regulatórios INDEPENDENTES.
Um medicamento pode ter:
- classe_controle + tipo_retencao (raro mas possível)
- apenas classe_controle (A1, B1, etc.)
- apenas tipo_retencao (amoxicilina, semaglutida)
- nenhum dos dois (receita simples)

REGRA DE PRIORIDADE no motor:
1. Se tipo_retencao está preenchido → GRUPO_RETENCAO
   (independente de classe_controle)
2. Se classe_controle está preenchido → MAPA_CLASSE_GRUPO
3. Se nenhum → GRUPO_SIMPLES

EXCEÇÃO: Se um item tem AMBOS tipo_retencao E classe_controle
da Portaria 344 (caso raro — ex: talidomida é D1 e poderia
ter tipo_retencao), o classe_controle da Portaria 344 PREVALECE
porque a Portaria 344 tem regras MAIS restritivas (amarela >
retenção). Na prática:
- Se classe_controle ∈ {A1, A2, A3, B1, B2, C5, D1, D2}:
  usar classe_controle (Portaria 344 prevalece)
- Senão, se tipo_retencao preenchido: usar tipo_retencao
- Senão: GRUPO_SIMPLES

--------------------------------------------------
PASSO 3 — MIGRATION (NOVO CAMPO)
--------------------------------------------------

Criar migration Alembic:
alembic revision -m "add_tipo_retencao_to_prescricao_itens"

Adicionar à tabela prescricao_itens:

| Coluna | Tipo | Nullable | Default | Nota |
|--------|------|----------|---------|------|
| tipo_retencao | String(30) | Y | NULL | "antimicrobiano" ou "glp1_agonista" |

Valores aceitos (validar em business logic, não em schema):
- "antimicrobiano" — RDC 471/2021, IN 83/2021
- "glp1_agonista" — RDC 471/2021, IN 360/2025
- NULL — não sujeito a retenção por RDC 471

Também atualizar o modelo ORM:
app/models/prescricao_item.py

  tipo_retencao = Column(String(30), nullable=True)

NÃO alterar classe_controle — os dois campos coexistem.

Aplicar a migration em dev e test:
alembic upgrade head

--------------------------------------------------
PASSO 4 — ATUALIZAR MOTOR REGULATÓRIO
--------------------------------------------------

Arquivo: app/domain/motor_regulatorio.py

4.1 — Ativar GRUPO_RETENCAO:

Alterar:
  status_implementacao="pendente_classificacao"
Para:
  status_implementacao="ativo"

Atualizar observacao para refletir a implementação:
  observacao=(
      "Antimicrobianos (RDC 471/2021 + IN 83/2021) e agonistas "
      "de GLP-1 (IN 360/2025). Classificados por tipo_retencao, "
      "não por classe_controle da Portaria 344/1998. "
      "Ref. SNGPC código '1' (apenas documentação, não usado "
      "na lógica do motor). Exenatida excluída da IN 360 "
      "(sem registro válido no Brasil). "
      "requer_sncr=False é premissa provisória — confirmar "
      "quando ferramenta SNCR para retenção estiver disponível."
  )

4.2 — Atualizar grupo_regulatorio():

A função atualmente recebe apenas classe_controle.
Alterar para receber AMBOS os campos:

def grupo_regulatorio(
    classe_controle: str | None,
    tipo_retencao: str | None = None,
) -> GrupoRegulatorio:
    """
    Determina o grupo regulatório de um item de prescrição.

    Prioridade:
    1. classe_controle ∈ Portaria 344 → grupo da Portaria
       (mais restritivo, prevalece)
    2. tipo_retencao preenchido → GRUPO_RETENCAO
    3. Nenhum → GRUPO_SIMPLES
    """
    # Normalizar
    cc = (classe_controle or "").strip().upper() or None
    tr = (tipo_retencao or "").strip().lower() or None

    # 1. Portaria 344 prevalece (mais restritiva)
    if cc and cc in MAPA_CLASSE_GRUPO:
        return MAPA_CLASSE_GRUPO[cc]

    # 2. RDC 471 — retenção
    if tr:
        if tr in TIPOS_RETENCAO_VALIDOS:
            return GRUPO_RETENCAO
        # AJUSTE: valor inválido DEVE gerar erro, NÃO tratar
        # como simples. Classificar retenção inválida como
        # simples é risco regulatório.
        raise ValueError(
            f"tipo_retencao '{tr}' não reconhecido. "
            f"Valores válidos: {sorted(TIPOS_RETENCAO_VALIDOS)}"
        )

    # 3. classe_controle desconhecida (não é 344 nem retenção)
    if cc:
        raise ValueError(
            f"classe_controle '{cc}' não reconhecida. "
            f"Valores válidos: {sorted(MAPA_CLASSE_GRUPO.keys())}"
        )

    # 4. Nenhum → simples
    return GRUPO_SIMPLES

Importar constante de app/domain/retencao.py (ver PASSO 7):
from app.domain.retencao import TIPOS_RETENCAO_VALIDOS

4.3 — Atualizar agrupar_por_receituario():

Onde chama grupo_regulatorio(), passar o tipo_retencao:

  grupo = grupo_regulatorio(
      item.get("classe_controle"),
      tipo_retencao=item.get("tipo_retencao"),
  )

4.4 — Atualizar validar_assinatura_para_receituario():

Se necessário, verificar que a assinatura "avancada" é
aceita para GRUPO_RETENCAO (gov.br é suficiente).
Já funciona hoje — o teste existente confirma. Apenas
verificar que não quebrou.

--------------------------------------------------
PASSO 5 — ATUALIZAR ROUTERS
--------------------------------------------------

Arquivo: app/routers/receituarios.py

No endpoint POST /gerar, onde carrega itens da prescrição,
garantir que tipo_retencao é incluído no dict passado para
agrupar_por_receituario():

Onde faz o dict do item, adicionar:
  "tipo_retencao": row.tipo_retencao,
  (ou equivalente, dependendo de como Row → dict funciona)

Verificar em _carregar_itens() ou equivalente.

Se o endpoint POST de criação de prescrição já aceita
tipo_retencao no body, ótimo. Se não, ajustar:
- O schema de criação de PrescricaoItem deve aceitar
  tipo_retencao (nullable, opcional)
- Validar que tipo_retencao está em TIPOS_RETENCAO_VALIDOS
  se preenchido

--------------------------------------------------
PASSO 6 — CORRIGIR DISCREPÂNCIA DE ABREVIAÇÃO
--------------------------------------------------

ACHADO NA INVESTIGAÇÃO:
- sncr_stub.py usa "RTC" para "receita_retencao"
- pdf_receituario.py usa "RRT" para "receita_retencao"

PADRONIZAR para "RRT" (Receita Retenção):
- É mais semântico
- Já está no PDF (visível ao usuário)
- Alterar sncr_stub.py: "receita_retencao": "RRT"

Arquivo: app/adapters/sncr_stub.py
Alterar em _ABREV_TIPO:
  "receita_retencao": "RTC"  →  "receita_retencao": "RRT"

--------------------------------------------------
PASSO 7 — ATUALIZAR MEDICAMENTO.PY
--------------------------------------------------

Arquivo: app/domain/medicamento.py

A função eh_item_atomizavel() precisa considerar
tipo_retencao para decidir se um item é atomizável:

def eh_item_atomizavel(item: dict) -> bool:
    classe = (item.get("classe_controle") or "").strip().upper()
    tipo_ret = (item.get("tipo_retencao") or "").strip().lower()
    # Itens com controle especial OU retenção NÃO são atomizáveis
    if classe in CLASSES_CONTROLE_ESPECIAL:
        return False
    if tipo_ret in TIPOS_RETENCAO_VALIDOS:
        return False
    return True

IMPORTANTE: NÃO importar de motor_regulatorio.py — risco
de dependência circular (medicamento ↔ motor_regulatorio).

Criar módulo compartilhado:
  app/domain/retencao.py

Conteúdo:
  TIPOS_RETENCAO_VALIDOS: frozenset[str] = frozenset({
      "antimicrobiano",
      "glp1_agonista",
  })

  # Labels para documentação/display
  TIPOS_RETENCAO_LABELS: dict[str, str] = {
      "antimicrobiano": "Antimicrobiano (RDC 471/2021 + IN 83/2021)",
      "glp1_agonista": "Agonista GLP-1 (IN 360/2025)",
  }

  # Substâncias GLP-1 documentadas (referência, não validação)
  # Exenatida EXCLUÍDA: sem registro válido no Brasil (IN 360/2025)
  SUBSTANCIAS_GLP1_IN360: tuple[str, ...] = (
      "semaglutida",
      "liraglutida",
      "dulaglutida",
      "tirzepatida",
      "lixisenatida",
  )

Tanto motor_regulatorio.py quanto medicamento.py importam
de retencao.py — sem ciclo.

--------------------------------------------------
PASSO 8 — TESTES DE INTEGRAÇÃO
--------------------------------------------------

Criar: tests/integration/test_grupo_retencao.py

1. test_item_antimicrobiano_gera_receituario_retencao
   - Criar prescrição com item:
     nome_medicamento="AMOXICILINA",
     tipo_retencao="antimicrobiano",
     classe_controle=NULL
   - Chamar POST /gerar
   - Verificar: receituário gerado com tipo="receita_retencao"
   - Verificar: grupo_nome contém "Retenção"
   - Verificar: assinatura_minima="avancada"
   - Verificar: vias=2
   - Verificar: requer_sncr=False (premissa provisória —
     ver TODO_REGULATORIO abaixo)
   - Verificar: retencao_farmacia=True
   - Registrar TODO_REGULATORIO no ledger:
     motivo: "requer_sncr_retencao_provisorio"
     detalhe: "Confirmar se, quando a ferramenta SNCR para
     receitas sujeitas à retenção estiver disponível, haverá
     numeração SNCR no fluxo prescritor ou apenas registro
     eletrônico de uso pela farmácia."

2. test_item_glp1_gera_receituario_retencao
   - Criar prescrição com item:
     nome_medicamento="SEMAGLUTIDA",
     tipo_retencao="glp1_agonista",
     classe_controle=NULL
   - Chamar POST /gerar
   - Verificar: mesmo resultado que antimicrobiano
   - (ambos mapeiam para GRUPO_RETENCAO)

3. test_item_misto_controlado_e_retencao
   - Criar prescrição com 3 itens:
     Item 1: classe_controle="B1", tipo_retencao=NULL (psicotrópico)
     Item 2: tipo_retencao="antimicrobiano" (antimicrobiano)
     Item 3: classe_controle=NULL, tipo_retencao=NULL (simples)
   - Chamar POST /gerar
   - Verificar: 3 receituários distintos:
     * notificacao_receita_b (item B1)
     * receita_retencao (antimicrobiano)
     * receita_simples (item simples)

4. test_classe_controle_prevalece_sobre_tipo_retencao
   - Item com classe_controle="D1" E tipo_retencao="antimicrobiano"
   - Chamar grupo_regulatorio()
   - Resultado deve ser GRUPO_D (Portaria 344 prevalece)
   - NÃO deve ser GRUPO_RETENCAO

5. test_tipo_retencao_invalido_gera_erro
   - Item com tipo_retencao="valor_invalido"
   - Motor DEVE levantar ValueError
   - Endpoint DEVE retornar 422
   - NÃO tratar como GRUPO_SIMPLES — classificar retenção
     inválida como simples é risco regulatório
   - Justificativa: se alguém digitou "antimicrobianoo",
     melhor falhar do que emitir receita simples para
     antimicrobiano

6. test_assinatura_govbr_aceita_para_retencao
   - Prescrição com assinatura gov.br (avançada)
   - Item tipo_retencao="antimicrobiano"
   - Gerar receituário → assinatura_valida=True
   - (gov.br atende "avancada")

7. test_assinatura_icp_tambem_aceita_para_retencao
   - Prescrição com ICP-Brasil (qualificada)
   - Item tipo_retencao="glp1_agonista"
   - Gerar receituário → assinatura_valida=True
   - (qualificada > avancada, atende)

8. test_fluxo_completo_retencao_gerar_numerar_pdf
   - Prescrição com antimicrobiano
   - POST /gerar → receituário "receita_retencao"
   - POST /numerar → status "nao_requer_sncr"
     (requer_sncr=False para retenção)
   - GET /pdf → PDF válido, status "emitido"
   - Verificar evento no ledger

9. test_nao_atomiza_item_retencao
   - Item com tipo_retencao="antimicrobiano"
   - eh_item_atomizavel() deve retornar False

10. test_grupo_retencao_ativo
    - GRUPO_RETENCAO.status_implementacao deve ser "ativo"
    - NÃO mais "pendente_classificacao"

Executar:
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend
pytest tests/integration/test_grupo_retencao.py -v

Também rodar todos os testes existentes para não-regressão:
pytest tests/integration/ -v

--------------------------------------------------
PASSO 9 — DOCUMENTAÇÃO
--------------------------------------------------

Criar: docs/grupo_retencao.md

Conteúdo:
1. Justificativa regulatória
   - Portaria 344/1998 vs RDC 471/2021
   - Por que campos separados (classe_controle vs tipo_retencao)
   - Antimicrobianos: RDC 471/2021 + IN 83/2021
   - GLP-1: IN 360/2025 (semaglutida, liraglutida, etc.)
   - Código SNGPC: "1" (vs "2" para Portaria 344)

2. Decisão arquitetural
   - tipo_retencao vs estender classe_controle
   - Regra de prioridade (Portaria 344 > RDC 471 > simples)
   - Por que Portaria 344 prevalece

3. Valores aceitos de tipo_retencao
   - "antimicrobiano" — escopo RDC 471/2021
   - "glp1_agonista" — escopo IN 360/2025
   - NULL — sem retenção por RDC 471

4. Fluxo no motor regulatório
   - Diagrama textual da prioridade
   - Exemplos: amoxicilina, semaglutida, diazepam+amoxicilina

5. Diferenças em relação aos outros grupos
   - requer_sncr=False (diferente de A, B, C, D)
   - assinatura_minima="avancada" (gov.br basta)
   - vias=2

6. Escopo futuro
   - Catálogo de substâncias antimicrobianas (DCB)
   - Integração SNGPC
   - Validação de prazo diferenciado (10 vs 90 dias)

Atualizar: docs/adapter_sncr.md
- Mencionar correção RTC→RRT
- Grupo Retenção agora ativo

--------------------------------------------------
SALVAGUARDAS
--------------------------------------------------

1. NÃO alterar tabela receituarios (já suporta receita_retencao)
2. NÃO alterar pdf_receituario.py (já tem cores/layout)
3. NÃO alterar sncr_interface.py (contrato inalterado)
4. NÃO inventar códigos de classe_controle para antimicrobianos
   (são de sistema regulatório diferente)
5. NÃO remover a observacao do GRUPO_RETENCAO — atualizar
6. NÃO alterar o endpoint /numerar
7. NÃO alterar o endpoint de PDF
8. Manter compatibilidade: tipo_retencao=NULL continua
   funcionando como antes (GRUPO_SIMPLES)
9. Testes existentes NÃO devem quebrar — grupo_regulatorio()
   com tipo_retencao=None deve ter mesmo comportamento anterior
10. Rollback explícito em caso de falha (usar get_tx)
11. Se algum teste existente quebrar, parar e reportar
12. Corrigir abreviação RTC→RRT no sncr_stub.py

--------------------------------------------------
DEFINIÇÃO DE PRONTO
--------------------------------------------------

Responder com:

1. Migration criada: tipo_retencao adicionado a prescricao_itens
   - Tipo do campo
   - Nullable
   - Aplicada em dev e test

2. Módulo retencao.py criado: app/domain/retencao.py
   - TIPOS_RETENCAO_VALIDOS ✓
   - TIPOS_RETENCAO_LABELS ✓
   - SUBSTANCIAS_GLP1_IN360 (sem exenatida) ✓

3. Motor regulatório atualizado:
   - GRUPO_RETENCAO.status_implementacao="ativo" ✓
   - grupo_regulatorio() aceita tipo_retencao ✓
   - Regra de prioridade implementada ✓
   - tipo_retencao inválido → ValueError (NÃO simples) ✓
   - Importa de retencao.py (sem ciclo) ✓

4. Abreviação padronizada:
   - sncr_stub.py: "receita_retencao" → "RRT" ✓
   - pdf_receituario.py: já era "RRT" ✓

5. eh_item_atomizavel() atualizado:
   - Considera tipo_retencao ✓
   - Importa de retencao.py (sem ciclo) ✓

6. Router atualizado:
   - tipo_retencao passado para motor regulatório ✓
   - Schema aceita tipo_retencao no body ✓
   - tipo_retencao inválido → 422 no endpoint ✓

7. Nº de testes criados e resultado do pytest -v
8. Testes existentes continuam passando (total geral)
9. Documentação criada: docs/grupo_retencao.md
10. TODO_REGULATORIO registrado:
    - requer_sncr provisório para retenção ✓
    - Exenatida como monitoramento futuro ✓

11. Exemplo de execução:
   - Prescrição com amoxicilina (antimicrobiano)
   - Prescrição com semaglutida (GLP-1)
   - Prescrição mista (B1 + antimicrobiano + simples)
   - Mostrar receituários gerados para cada cenário

12. Confirmação: Portaria 344 prevalece sobre RDC 471
    quando ambos preenchidos

Frase final obrigatória:

"GRUPO RETENÇÃO ATIVO (ANTIMICROBIANOS + GLP-1)"
```

---

## Notas para o time de revisão

### Por que campo separado (tipo_retencao)?

| Abordagem | Problema |
|-----------|----------|
| Inventar classe "C6" para antimicrobianos | Conflita dois sistemas normativos (Portaria 344 ≠ RDC 471). "C6" não existe na legislação. |
| Inventar classe "E1" para GLP-1 | Mesmo problema. Cria ficção regulatória. |
| Campo tipo_retencao separado | ✅ Respeita que são sistemas regulatórios independentes com lógica própria. |

### Comparação dos dois sistemas regulatórios

| Aspecto | Portaria 344/1998 | RDC 471/2021 |
|---------|-------------------|--------------|
| Classificação | Por LISTA (A, B, C, D) | Por SUBSTÂNCIA (DCB) |
| Campo no PicSaúde | classe_controle | tipo_retencao |
| Código SNGPC | "2" | "1" |
| SNCR obrigatório | Sim | Não |
| Assinatura mínima | Qualificada (ICP-Brasil) | Avançada (gov.br basta) |
| Receituário | Amarelo/Azul/Branco | Branco com retenção |
| Vias | 2 ou 3 | 2 |

### Substâncias GLP-1 (IN 360/2025)

| Substância | DCB | Vigência da retenção |
|------------|-----|---------------------|
| Semaglutida | 09417 | 23/06/2025 |
| Liraglutida | 08197 | 23/06/2025 |
| Dulaglutida | 10267 | 23/06/2025 |
| Tirzepatida | 12621 | 23/06/2025 |
| Lixisenatida | 10266 | 23/06/2025 |

### Discrepância corrigida

| Arquivo | Antes | Depois |
|---------|-------|--------|
| sncr_stub.py | "RTC" | "RRT" |
| pdf_receituario.py | "RRT" | "RRT" (mantido) |

### Sequência pós-Ticket 18

- **Ticket 16B**: Integração real SNCR (quando API disponível)
- **Ticket 19** (futuro): Catálogo de substâncias antimicrobianas (DCB)
- **Ticket 20** (futuro): Validação de prazos diferenciados (10 vs 90 dias)
- **Ticket 21** (futuro): Integração SNGPC
