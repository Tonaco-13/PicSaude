# RESUMO TÉCNICO — REQUISITOS SNCR PARA TICKET 16

## Status: Levantamento concluído em 24/04/2026
## Autor: Engenheiro chefe (Claude Opus)
## Fontes: Web search (fontes oficiais e secundárias)

---

## 1. O QUE É O SNCR

O Sistema Nacional de Controle de Receituários (SNCR) é a plataforma da Anvisa que centraliza a numeração, emissão e rastreabilidade de receituários de medicamentos controlados em todo o território nacional. Foi criado pela RDC 873/2024 e expandido pela RDC 1.000/2025.

**Prazo crítico:** 1º de junho de 2026 — Anvisa deve disponibilizar o SNCR completo para requisição de numeração e registro de utilização de receituários eletrônicos.

**Período de tolerância:** 30 dias após a disponibilização — receituários sem numeração SNCR ainda são aceitos.

---

## 2. FLUXOS IDENTIFICADOS

### 2.1 — Fluxo de Emissão (Prescritor → SNCR)

```
[Prescritor no sistema]
        ↓
[Sistema prescritor requisita numeração ao SNCR via API]
  → Autenticação: assinatura eletrônica qualificada (ICP-Brasil)
  → Requisição vinculada ao CPF do prescritor
        ↓
[SNCR retorna numeração individualizada]
  → Número sequencial único por receituário
  → Vinculado ao prescritor autorizado
        ↓
[Sistema insere numeração no receituário]
  → Receituário é nato-digital (não digitalização de papel)
  → Assinado eletronicamente pelo prescritor
        ↓
[Receituário disponibilizado ao paciente]
  → Paciente pode apresentar em qualquer farmácia
```

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**
Fonte: RDC 1.000/2025, art. sobre integração via API.

### 2.2 — Fluxo de Dispensação (Farmácia → SNCR)

```
[Paciente apresenta receituário na farmácia]
        ↓
[Farmácia verifica no SNCR:]
  1. Autenticidade da assinatura do prescritor
  2. Integridade do documento
  3. Validade da numeração SNCR
        ↓
[Farmácia registra utilização no SNCR]
  → Preenchimento dos campos exigidos
  → Registro tem valor legal de retenção
  → Substitui anotação manual e arquivo físico
        ↓
[Receituário marcado como utilizado]
  → Uso único — não pode ser reutilizado
```

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**
Fonte: RDC 1.000/2025 + fontes secundárias (CFF, Vigilância SC).

### 2.3 — Fluxo SNGPC (Farmácia → Anvisa)

O SNGPC (Sistema Nacional de Gerenciamento de Produtos Controlados) já pode receber a numeração completa das Notificações de Receita emitidas pelo SNCR. O SNCR fornece a numeração, o SNGPC faz o gerenciamento pós-dispensação.

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO** (mas fora do escopo do PicSaúde — escopo da farmácia)

---

## 3. API DO SNCR — STATUS DA DOCUMENTAÇÃO

### 3.1 — O que está confirmado

| Item | Status | Fonte |
|------|--------|-------|
| Integração obrigatória via API | ✅ Confirmado | RDC 1.000/2025 |
| API = Interface de Programação de Aplicações | ✅ Confirmado | Texto da RDC |
| Vedada emissão por sistemas não integrados | ✅ Confirmado | RDC 1.000/2025 |
| Requisitos técnicos serão definidos pela Anvisa | ✅ Confirmado | RDC 1.000/2025 |
| Requisitos serão publicados no site da Anvisa | ✅ Confirmado | RDC 1.000/2025 |
| Memed já está integrada ao SNCR | ✅ Confirmado | Fontes secundárias (dez/2025) |
| Memed captura numeração automaticamente do SNCR | ✅ Confirmado | Healthcare Management |

### 3.2 — O que NÃO está publicamente documentado

| Item | Status | Implicação |
|------|--------|------------|
| Especificação REST/SOAP da API | ❌ Não encontrada | Não sabemos se é REST, SOAP, ou outro |
| Endpoints específicos | ❌ Não encontrados | Não temos paths, métodos, payloads |
| Formato de autenticação da API | ❌ Não encontrado | Sabemos que exige ICP-Brasil, mas não o mecanismo (mTLS? token?) |
| Schema de request/response | ❌ Não encontrado | Não temos campos exatos da requisição de numeração |
| Processo de credenciamento | ❌ Não encontrado | Não sabemos como registrar o PicSaúde como plataforma integrada |
| Ambiente de homologação/sandbox | ❌ Não encontrado | Não sabemos se existe ambiente de teste |
| SDK ou biblioteca cliente | ❌ Não encontrada | — |
| Swagger/OpenAPI da API SNCR | ❌ Não encontrado | — |

### 3.3 — Inferência técnica

A Memed (plataforma de prescrição digital líder no Brasil) já integrou ao SNCR em dezembro de 2025, antes da publicação oficial dos requisitos técnicos. Isso sugere que:

1. A API existe e está funcional para parceiros selecionados
2. O processo de credenciamento pode envolver contato direto com a Anvisa
3. A documentação técnica pode estar disponível apenas para plataformas credenciadas (não pública)
4. Pode haver um programa de early access / homologação

**CLASSIFICAÇÃO: INFERÊNCIA TÉCNICA** — não confirmada por fonte oficial.

---

## 4. REQUISITOS NORMATIVOS CONFIRMADOS PARA O SISTEMA PRESCRITOR

### 4.1 — Numeração SNCR

- Cada receituário eletrônico DEVE ter numeração individualizada
- Numeração concedida PREVIAMENTE pelo SNCR (antes da emissão)
- Numeração vinculada ao CPF do prescritor previamente autorizado
- Requisição de numeração exige assinatura eletrônica qualificada (ICP-Brasil)

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.2 — Tipo de Receituário

Tipos definidos pela RDC 1.000/2025 + Portaria 344/1998:

| Tipo | Listas | Assinatura exigida | Modelo |
|------|--------|-------------------|--------|
| Notificação de Receita A (amarela) | A1, A2, A3 | Qualificada (ICP-Brasil) | Versão 2 (obrigatória desde 18/05/2026) |
| Notificação de Receita B (azul) | B1 | Qualificada (ICP-Brasil) | Versão 2 |
| Notificação de Receita B2 | B2 | Qualificada (ICP-Brasil) | Versão 2 |
| Receita de Controle Especial | C1, C5, adendos A1/A2/B1 | Qualificada (ICP-Brasil) | Versão 2 |
| Notificação Especial (retinoides/talidomida) | D1, D2 | Qualificada (ICP-Brasil) | Versão 2 |
| Receita com retenção | Antimicrobianos, GLP-1 | Avançada (gov.br) OU qualificada | Versão 2 |

Modelos atualizados (Versão 2) publicados em 16/03/2026, obrigatórios desde 18/05/2026.

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.3 — Assinatura Digital

| Grupo | Nível mínimo | Mecanismo |
|-------|-------------|-----------|
| Controle especial (A, B, C, D) | Qualificada | Certificado ICP-Brasil (A1 ou A3) |
| Retenção (antimicrobianos, GLP-1) | Avançada | gov.br OU ICP-Brasil |
| Requisição de numeração ao SNCR | Qualificada | ICP-Brasil |

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.4 — Documento Nato-Digital

- Receituário eletrônico DEVE ser nato-digital
- Não é aceita digitalização de documento físico
- Mesmo que assinado eletronicamente após digitalização, não vale
- O PicSaúde já atende: prescrições são criadas digitalmente no sistema

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.5 — CPF do Paciente

- CPF do paciente é OBRIGATÓRIO em receituários controlados
- Para estrangeiros: passaporte
- Para uso veterinário: CPF do tutor
- Se paciente não tem CPF: registrar "não possui"
- O PicSaúde já tem CPF na tabela pacientes

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.6 — Rastreabilidade

- Numeração única e sequencial por receituário
- Vinculação: prescritor → numeração → receituário → dispensação
- Registro de utilização na dispensação
- Uso único (receituário não reutilizável)

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.7 — Responsabilidades do Serviço de Prescrição Eletrônica

O serviço de prescrição eletrônica DEVE:

1. Requisitar ao SNCR a numeração necessária, mediante assinatura qualificada
2. Assegurar a liberação e vinculação da numeração ao prescritor autorizado
3. Garantir a disponibilização do receituário ao paciente
4. Paciente deve poder apresentar em qualquer estabelecimento dispensador
5. Assegurar a rastreabilidade das informações de emissão

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

### 4.8 — Modelos de Receituário

- Versão 1: publicada em 13/02/2026, válida até 17/05/2026
- Versão 2: publicada em 16/03/2026, obrigatória desde 18/05/2026
- Modelos disponíveis na página do SNCR
- Principais mudanças: campos padronizados, CPF substitui endereço do paciente
- Modelos para: Receita Controle Especial, Notificação A, B, B2, Retinoides, Talidomida

**CLASSIFICAÇÃO: REQUISITO NORMATIVO CONFIRMADO**

---

## 5. ESTADOS DE SINCRONIZAÇÃO (INFERIDOS)

Com base nos fluxos confirmados, os estados do receituário eletrônico são:

```
gerado (local, sem numeração)
    ↓
numerado (numeração SNCR obtida)
    ↓
emitido (assinado e disponibilizado ao paciente)
    ↓
dispensado (registro de utilização feito pela farmácia)
    ↓
expirado (prazo de validade ultrapassado sem dispensação)
```

**CLASSIFICAÇÃO: INFERÊNCIA TÉCNICA**
Os estados "gerado" e "numerado" são inferidos da arquitetura.
"Emitido", "dispensado" e "expirado" derivam dos fluxos normativos.
A terminologia exata do SNCR pode ser diferente.

---

## 6. MAPEAMENTO PARA O PICSAÚDE

### 6.1 — O que o PicSaúde JÁ TEM

| Requisito | Status PicSaúde | Implementação |
|-----------|----------------|---------------|
| Prescrição nato-digital | ✅ | Criação via API |
| CPF do paciente | ✅ | tabela pacientes |
| classe_controle por item | ✅ | prescricao_itens.classe_controle |
| Assinatura ICP-Brasil | ✅ | assinatura_icp.py + icp_identity.py |
| Assinatura gov.br | ✅ | assinatura_modo='gov_br_nuvem' |
| Ledger imutável | ✅ | prescricao_eventos |
| Motor regulatório (Ticket 15) | ✅ | motor_regulatorio.py |
| Tabela receituarios | ✅ | Ticket 15 |
| Agrupamento por tipo | ✅ | agrupar_por_receituario() |
| Validação de assinatura por grupo | ✅ | validar_assinatura_para_receituario() |
| Campo numeracao_sncr | ✅ | receituarios.numeracao_sncr (NULL) |

### 6.2 — O que FALTA

| Requisito | Status | Bloqueador |
|-----------|--------|------------|
| Integração API SNCR (numeração) | ❌ | SIM — sem documentação pública |
| Credenciamento como plataforma | ❌ | SIM — processo desconhecido |
| Requisição de numeração via ICP-Brasil | ❌ | Parcial — temos ICP, não temos endpoint |
| Registro de utilização (dispensação) | ❌ | Escopo farmácia, não prescritor |
| PDF conforme modelo Versão 2 | ❌ | NÃO — pode ser feito localmente |
| Grupo 5 (antimicrobianos/GLP-1) | ❌ | NÃO — motor funciona sem ele |

---

## 7. ANÁLISE DE RISCO E RECOMENDAÇÃO

### 7.1 — Risco principal

A especificação técnica da API do SNCR **não está publicamente disponível** (ou não foi encontrada em busca pública). Isso significa que não é possível implementar a integração completa sem:

a) Acesso à documentação técnica da Anvisa (possivelmente restrita a parceiros credenciados), OU
b) Contato direto com a Anvisa para processo de credenciamento

### 7.2 — Recomendação

**AÇÃO IMEDIATA (Fabiano):**

1. Acessar https://sncr.anvisa.gov.br/ e verificar se há área de desenvolvedor / credenciamento
2. Baixar e ler o Manual SNCR 6ª edição (PDF no site da Anvisa)
3. Verificar o Perguntas & Respostas RDC 1000-2025 (PDF)
4. Se não houver documentação técnica pública: entrar em contato com a Anvisa (GGIMP ou canal de atendimento) solicitando acesso à especificação da API para integração de sistema prescritor
5. Verificar se existe processo formal de credenciamento para plataformas

**AÇÃO TÉCNICA (enquanto aguarda):**

O Ticket 16 pode ser estruturado em duas partes:

**Ticket 16A — Adapter SNCR (Stub):**
- Criar a camada de integração com interface definida
- Implementar stub/mock que simula respostas do SNCR
- Testar o fluxo completo localmente (geração → numeração mock → emissão)
- Quando a documentação real chegar, trocar o stub pelo cliente real

**Ticket 16B — Integração Real SNCR:**
- Implementar com a API real quando documentação estiver disponível
- Credenciamento da plataforma
- Testes contra ambiente de homologação (se existir)

Essa abordagem permite avançar sem depender da Anvisa, e a integração real se torna uma troca de adaptador — não reescrever.

**TICKET PARALELO — Geração de PDF (Ticket 17):**
- Pode ser feito agora, independente do SNCR
- Implementar os modelos Versão 2 (obrigatórios desde 18/05/2026)
- Baixar templates do site da Anvisa: gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/modelos-de-receituarios

---

## 8. FONTES

### Oficiais
- [Anvisa — SNCR (página principal)](https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr)
- [RDC 1.000/2025 (texto)](https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&tipo=RDC&numeroAto=00001000&seqAto=000&valorAno=2025&orgao=RDC/DC/ANVISA/MS)
- [Manual SNCR 6ª ed. (PDF)](https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/medicamentos/controlados/manual-sncr-1-0.pdf)
- [Perguntas e Respostas RDC 1000-2025](https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/perguntas-e-respostas/perguntas-e-respostas-rdc-1000-2025-1-ed/view)
- [Modelos de Receituários](https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/modelos-de-receituarios)
- [Anvisa — novos modelos fev/2026](https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2026/anvisa-disponibiliza-novos-modelos-de-receituarios-controlados)

### Secundárias (análise / interpretação)
- [CFF — RDC receituário eletrônico](https://site.cff.org.br/noticia/Noticias-gerais/10/12/2025/anvisa-aprova-nova-rdc-que-regulamenta-o-receituario-eletronico-de-medicamentos-controlados)
- [Vigilância SC — alterações RDC 1.000](https://www.vigilanciasanitaria.sc.gov.br/index.php/component/content/article/novas-regras-para-prescricoes-eletronicas-de-medicamentos-com-a-rdc-n-1-000-2025-anvisa-entenda-as-principais-alteracoes.html)
- [SBIS — suporte técnico à RDC](https://sbis.org.br/noticia/anvisa-aprova-a-prescricao-eletronica-de-medicamentos-controlados-com-o-suporte-tecnico-da-sbis/)
- [Memed — integração SNCR](https://healthcare.grupomidia.com/memed-integra-a-prescricao-digital-do-receituario-azul-e-amarelo/)
- [Amplimed — RDC 1000/2025](https://www.amplimed.com.br/blog/rdc-1000-2025/)
