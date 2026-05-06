# Token de Apresentação — Integração com E-commerce Farmacêutico

> **Status:** Proposta arquitetural — pré-implementação
> **Fase do produto:** Fase 4 — Interoperabilidade com canais digitais de dispensação
> **Dependências:** Custódia digital (Fase 1–3) deve estar estável antes da implementação

---

## Sumário

| Seção | Conteúdo |
|---|---|
| 1 | Problema e motivação |
| 2 | Conceito: chave de apresentação |
| 3 | Distinção em relação ao protocolo de prescrição |
| 4 | Modelo de dados |
| 5 | Máquina de estados do token |
| 6 | Eventos no ledger |
| 7 | Endpoints propostos |
| 8 | Integração com o módulo de custódia existente |
| 9 | Modos de operação: token aberto vs. vinculado |
| 10 | Campo `escopo`: gradação de permissão |
| 11 | Restrições regulatórias |
| 12 | Invariantes de negócio |
| 13 | Riscos e salvaguardas |
| 14 | Estratégia de adoção em 4 níveis |
| 15 | Posicionamento no whitepaper |

---

## 1. Problema e motivação

O fluxo atual de dispensação digital pressupõe que o paciente está fisicamente presente no
balcão de uma farmácia credenciada. O farmacêutico (dispensador) faz login no PicSaúde,
localiza a prescrição pelo protocolo e registra a transferência de custódia.

E-commerces farmacêuticos não se encaixam nesse fluxo porque:

1. O pagamento ocorre antes da dispensação física (na entrega)
2. O paciente não está presente no momento do checkout
3. A farmácia online precisa validar a prescrição sem que o paciente envie um PDF ou foto
4. Não há mecanismo atual para reservar itens de uma prescrição durante o processo de compra

A solução é uma **chave de apresentação**: um token de uso único, com escopo e validade
controlados, que o paciente gera e entrega ao e-commerce para autorizar consulta, reserva
ou captura de custódia da prescrição.

---

## 2. Conceito: chave de apresentação

A chave de apresentação é uma **autorização temporária e delegada** sobre uma prescrição.

O paciente — detentor legítimo da custódia — gera um token que representa sua intenção de
apresentar aquela prescrição em um canal digital. O token não substitui a prescrição nem
altera a custódia por si só: apenas habilita que um dispensador credenciado execute as
operações autorizadas pelo escopo do token.

```
Paciente                PicSaúde              E-commerce
   |                       |                      |
   |-- POST /tokens -----→ |                      |
   |← token (UUID) ------  |                      |
   |                       |                      |
   |-- envia token ----------------------→        |
   |                       |                      |
   |            ← GET /tokens/{token} -----------|
   |                       |-- retorna resumo --→ |
   |                       |                      |
   |                       | ← POST /tokens/{token}/consumir
   |                       |-- transfere custódia |
   |                       |-- evento no ledger → |
```

---

## 3. Distinção em relação ao protocolo de prescrição

| Atributo | Protocolo de prescrição | Token de apresentação |
|---|---|---|
| Natureza | Identidade permanente do objeto sanitário | Autorização temporária de acesso |
| Validade | Permanente (ledger imutável) | TTL configurável (ex: 48h) |
| Geração | Sistema PicSaúde na emissão | Paciente sob demanda |
| Escopo | Prescrição inteira | Item específico, conjunto ou prescrição inteira |
| Destino | Qualquer ator autorizado | Dispensador credenciado (aberto ou CNPJ-bound) |
| Uso | Ilimitado para consulta | Uso único para operações de escrita |
| Cancelamento | Apenas via derivação (novo objeto) | Revogação direta pelo paciente |

O protocolo responde à pergunta: **"o que é este objeto?"**
O token responde à pergunta: **"quem está autorizado a agir sobre ele agora?"**

---

## 4. Modelo de dados

```sql
CREATE TABLE prescricao_tokens_apresentacao (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo_prescricao TEXT    NOT NULL REFERENCES prescricoes(protocolo),
    item_ids            TEXT    NULL,        -- JSON array de IDs; NULL = prescrição inteira
    token               TEXT    NOT NULL UNIQUE,  -- UUID v4
    escopo              TEXT    NOT NULL,    -- 'consulta' | 'reserva' | 'custodia'
    cnpj_destino        TEXT    NULL,        -- NULL = token aberto; CNPJ = token vinculado
    criado_por_cpf      TEXT    NOT NULL,
    criado_em           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_em           DATETIME NOT NULL,
    consumido_em        DATETIME NULL,
    consumido_por_cnpj  TEXT    NULL,
    status              TEXT    NOT NULL DEFAULT 'ativo',
                        -- 'ativo' | 'consumido' | 'expirado' | 'revogado'
    CHECK (escopo IN ('consulta', 'reserva', 'custodia')),
    CHECK (status IN ('ativo', 'consumido', 'expirado', 'revogado'))
);

CREATE INDEX idx_tokens_protocolo ON prescricao_tokens_apresentacao(protocolo_prescricao);
CREATE INDEX idx_tokens_status    ON prescricao_tokens_apresentacao(status, expira_em);
```

---

## 5. Máquina de estados do token

```
         [geração pelo paciente]
                  ↓
               ativo
              / | \
             /  |  \
            ↓   ↓   ↓
      consumido  expirado  revogado
      (terminal) (terminal) (terminal)
```

### Transições

| De | Para | Gatilho |
|---|---|---|
| `ativo` | `consumido` | `POST /tokens/{token}/consumir` (validação OK) |
| `ativo` | `expirado` | `expira_em` ultrapassado (verificação lazy ou job) |
| `ativo` | `revogado` | `DELETE /tokens/{token}` pelo paciente |

Todos os estados exceto `ativo` são **terminais**. Nenhuma transição parte de um estado terminal.

---

## 6. Eventos no ledger

Três novos valores para `prescricao_eventos.tipo_evento`:

| Evento | Quando ocorre | Dados mínimos |
|---|---|---|
| `token_apresentacao_emitido` | Criação do token | token (hash), cnpj_destino, escopo, expira_em, item_ids |
| `token_apresentacao_consumido` | Consumo bem-sucedido | token (hash), cnpj_destino, consumido_em |
| `token_apresentacao_revogado` | Revogação pelo paciente | token (hash), motivo |

**Nota de segurança:** o UUID completo do token nunca é gravado no ledger — apenas seu
hash SHA-256 de 8 caracteres. Isso preserva rastreabilidade sem expor o segredo.

Esses eventos **precedem** os eventos de custódia existentes: após
`token_apresentacao_consumido`, o sistema emite normalmente `custodia_transferida`.

---

## 7. Endpoints propostos

### `POST /prescricoes/{proto}/tokens`
Gera um novo token de apresentação.

```
Auth:    paciente (role com CPF correspondente ao cpf_paciente da prescrição)
Body:    {
           "escopo": "consulta" | "reserva" | "custodia",
           "cnpj_destino": "12345678000195" | null,
           "item_ids": [1, 2] | null,
           "ttl_minutos": 1440
         }
Retorno: { "token": "uuid-v4", "expira_em": "2026-03-18T14:00:00" }
Regras:
  - Prescrição deve estar em status compatível com dispensação digital
  - Gerar novo token para o mesmo item revoga automaticamente o token ativo anterior
  - MAX 1 token ativo por item (invariante — ver seção 12)
```

### `GET /tokens/{token}`
Consulta o token e retorna o resumo da prescrição autorizada.

```
Auth:    dispensador credenciado (qualquer, se token aberto; CNPJ matching, se vinculado)
Retorno: {
           "status": "ativo",
           "escopo": "custodia",
           "expira_em": "...",
           "prescricao": { protocolo, status, tipo_emissao },
           "itens": [ { id, nome_medicamento, quantidade, status_item } ]
         }
Nota:    Não consome o token. Pode ser chamado múltiplas vezes (leitura pura).
```

### `POST /tokens/{token}/consumir`
Consome o token e executa a operação autorizada pelo escopo.

```
Auth:    dispensador credenciado
Body:    { "cnpj_estabelecimento": "12345678000195" }
Retorno: { "ok": true, "custodia_transferida": true | false }
Regras:
  - Idempotente por token: segunda chamada retorna HTTP 409
  - Se cnpj_destino IS NOT NULL e cnpj_chamador != cnpj_destino → HTTP 403
  - Escopo 'consulta': retorna 200 sem alterar custódia
  - Escopo 'reserva': marca itens como 'em_custodia' sem evento de dispensação
  - Escopo 'custodia': transfere custódia (paciente → dispensador) normalmente
  - Transação atômica: UPDATE status='consumido' WHERE status='ativo' + verifica rows_affected
```

### `DELETE /tokens/{token}`
Revoga um token ativo.

```
Auth:    paciente (criador do token)
Retorno: { "ok": true }
Regra:   Apenas tokens com status='ativo' podem ser revogados
```

---

## 8. Integração com o módulo de custódia existente

O `POST /tokens/{token}/consumir` com `escopo='custodia'` é uma **fachada** sobre a lógica
existente em `routers/custodia.py`.

```
tokens.py                          custodia.py
    |                                   |
    |-- valida token ----------------→  |
    |-- verifica CNPJ ---------------→  |
    |-- verifica escopo -------------→  |
    |                                   |
    |-- chama transferir_custodia() --→ |
    |                                   |
    |← custódia transferida ----------  |
    |                                   |
    |-- registra token_consumido ----→ ledger
```

O módulo `custodia.py` **não precisa saber que tokens existem**. Essa separação garante:
- Zero acoplamento entre os módulos
- Testes unitários de custódia continuam válidos sem modificação
- O token é uma camada de autorização, não uma mudança no modelo de custódia

---

## 9. Modos de operação: token aberto vs. vinculado

### Token aberto (`cnpj_destino = NULL`)
- Qualquer dispensador credenciado pode consultar e consumir
- Útil para: comparação de preços, marketplaces farmacêuticos, portais de convênio
- Risco adicional: token interceptado pode ser consumido por farmácia não-intencional
- Mitigação: o paciente vê qual CNPJ consumiu o token (`consumido_por_cnpj` no ledger)

### Token vinculado (`cnpj_destino = CNPJ_X`)
- Apenas a farmácia especificada pode consumir
- Útil para: checkout em e-commerce específico, compra recorrente em farmácia de preferência
- `GET /tokens/{token}` por CNPJ diferente retorna HTTP 403

A escolha é do paciente no momento da geração. O MVP deve suportar ambos os modos.

---

## 10. Campo `escopo`: gradação de permissão

O campo `escopo` define o que o dispensador pode fazer com o token:

| Escopo | `GET /tokens/{token}` | `POST /tokens/{token}/consumir` |
|---|---|---|
| `consulta` | Retorna dados completos | Registra visualização; sem alteração de custódia |
| `reserva` | Retorna dados completos | Marca itens como `em_custodia`; sem dispensação |
| `custodia` | Retorna dados completos | Transfere custódia `paciente → dispensador` |

**Por que isso importa:**
- Um e-commerce pode solicitar escopo `consulta` apenas para verificar elegibilidade antes de
  exibir o produto
- O escopo `reserva` bloqueia o item temporariamente enquanto o pagamento é processado
- O escopo `custodia` efetiva a transação sanitária — só deve ser chamado após pagamento
  confirmado

O escopo é **imutável após a geração** do token. Para escalar de `consulta` para `custodia`,
o paciente deve gerar um novo token.

---

## 11. Restrições regulatórias

### Medicamentos elegíveis para escopo `custodia` remoto

| Categoria | Elegível | Observação |
|---|---|---|
| Sem tarja | Sim | Sem restrição |
| Tarja vermelha sem retenção | Sim | Verificação de identidade na entrega responsabilidade do e-commerce |
| Antibióticos (RDC 20/2011) | Parcialmente | Token válido para reserva; retenção física ocorre na entrega |
| Tarja preta (psicotrópicos) | Não | Exige presença física e notificação de receita retida |
| Entorpecentes (Portaria 344) | Não | Fluxo físico obrigatório |

**Princípio:** o token não substitui obrigações regulatórias. Para categorias que exigem
retenção física, o token autoriza `reserva` — a custódia digital só é efetivada após
confirmação da retenção presencial na entrega.

### Responsabilidade do dispensador credenciado
O e-commerce que consome um token com `escopo='custodia'` assume formalmente a responsabilidade
de verificar a identidade do paciente na entrega e reter a receita quando exigido. Isso deve
constar no contrato de credenciamento com a plataforma.

---

## 12. Invariantes de negócio

```
1. MAX 1 token ativo por item
   Gerar novo token para item X revoga automaticamente o token ativo anterior de item X.
   Emite evento 'token_apresentacao_revogado' para o token revogado.

2. Token só é consumido uma vez
   UPDATE status='consumido' WHERE token=? AND status='ativo'
   Verificar rows_affected == 1 antes de qualquer operação de custódia.
   Se rows_affected == 0 → HTTP 409 (já consumido ou expirado).

3. Token não opera sobre itens terminais
   Item com status_item IN ('dispensado', 'cancelado', 'encerrado_fisico',
   'devolvido_prescritor', 'estornado') não pode ser incluído em novo token.

4. Token não opera sobre prescrições físicas
   Prescrição com tipo_emissao='fisica' ou status='encerrada_localmente' retorna HTTP 422.

5. Expiração é verificada na consulta (lazy)
   Se expira_em < NOW() e status='ativo': marcar como 'expirado' antes de retornar.
   Job periódico pode fazer limpeza em lote, mas não é necessário para correção.

6. cnpj_destino não pode ser alterado após geração
   Token vinculado permanece vinculado até ser consumido, revogado ou expirado.
```

---

## 13. Riscos e salvaguardas

| Risco | Nível | Mitigação |
|---|---|---|
| Token interceptado em trânsito | Médio | HTTPS obrigatório; token vinculado limita uso a CNPJ específico |
| Brute-force do UUID | Baixo | UUID v4: 2¹²² possibilidades; rate-limit no endpoint de consulta |
| Race condition no consumo | Alto | Transação atômica + verificação de rows_affected |
| Token gerado para prescrição revogada | Médio | Validar status da prescrição na geração do token |
| Paciente gera tokens para todos os itens antes de revogar a prescrição | Baixo | Revogação da prescrição deve invalidar todos os tokens ativos dela |
| E-commerce não executa retenção obrigatória | Alto | Responsabilidade contratual; PicSaúde registra `consumido_por_cnpj` para auditoria |
| Logs expondo UUID completo do token | Médio | Apenas hash SHA-256 de 8 chars no ledger e nos logs |

---

## 14. Estratégia de adoção em 4 níveis

### Nível 0 — Sem token (disponível hoje)
O paciente informa o protocolo de prescrição manualmente ao e-commerce.
O farmacêutico faz login no PicSaúde e registra a dispensação via interface web.
Sem integração técnica, mas rastreável.

### Nível 1 — Token de consulta
E-commerce integra `GET /tokens/{token}` para exibir resumo da prescrição no checkout.
Valida elegibilidade, exibe dados do medicamento, confirma quantidade disponível.
Dispensação ainda registrada manualmente pelo farmacêutico após entrega.

### Nível 2 — Token de reserva
E-commerce integra `POST /tokens/{token}/consumir` com `escopo='reserva'` no momento
do pagamento. Itens ficam `em_custodia` durante o prazo de entrega.
Farmacêutico confirma dispensação efetiva na entrega via interface web.

### Nível 3 — Token de custódia completo
E-commerce integra consumo com `escopo='custodia'` após confirmação de entrega.
Custódia transferida automaticamente pelo sistema do e-commerce via API.
Dispensação registrada sem intervenção manual do farmacêutico.

### Nível 4 — Webhooks e notificações push
PicSaúde envia webhook ao e-commerce quando:
- Prescrição é revogada (`cancelada`) com tokens ativos pendentes
- Prescrição expira com pedido em aberto
- Custódia é transferida por outro canal (duplicidade)

Permite cancelamento automático de pedidos em aberto e evita dispensação dupla.

---

## 15. Posicionamento no whitepaper

Esta funcionalidade posiciona o PicSaúde como **infraestrutura nacional de dispensação
digital** — não apenas uma plataforma de prescrição eletrônica.

A distinção estratégica:

| Sistema | Foco |
|---|---|
| Prontuário eletrônico (RES/PEP) | Registro clínico |
| BNAFAR / HÓRUS | Rastreamento de estoque |
| E-commerce farmacêutico atual | Venda sem rastreabilidade sanitária |
| **PicSaúde com token de apresentação** | **Cadeia de custódia transacional ponta a ponta** |

O token de apresentação resolve o elo faltante entre prescrição digital e dispensação no
canal online, mantendo a rastreabilidade que diferencia o PicSaúde de soluções baseadas
em PDF ou foto de receita.

**Seção sugerida no whitepaper:**
> 6. Interoperabilidade com canais digitais de dispensação
> 6.1 Apresentação delegada de prescrição
> 6.2 Gradação de escopo: consulta, reserva, custódia
> 6.3 Credenciamento de dispensadores digitais

---

*Documento gerado em 2026-03-16. Próximo passo: ticket de implementação após estabilização
dos testes de integração (Ticket 9).*
