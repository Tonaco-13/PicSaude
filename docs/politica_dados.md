# PicSaúde — Política de Dados, Retenção e Anonimização

> **RESSALVA JURÍDICA — LEITURA OBRIGATÓRIA**
>
> Este documento é **orientação técnica** destinada a desenvolvedores e gestores
> do PicSaúde. **Não é parecer jurídico vinculante.** Antes de qualquer uso em
> produção, o documento **deve ser revisado por advogado** com competência em
> LGPD e legislação sanitária. Bases legais específicas dependem do controlador,
> do contrato institucional e da finalidade concreta do tratamento.
>
> Prazos e disposições citadas de normas infralegais (Resolução CFM 1.821/2007,
> RDC Anvisa 1.000/2025, entre outras) podem ter sido alterados após a emissão
> deste texto — **verificar sempre o texto vigente** antes de tomar decisão
> operacional com base neles.

---

## 1. Objetivo e escopo

Formalizar a política de tratamento de dados pessoais e sensíveis no PicSaúde,
cobrindo:

- Inventário das categorias de dados tratadas.
- Referências legais aplicáveis (LGPD + legislação setorial de saúde).
- Prazos mínimos legais e retenção recomendada.
- Regras de exclusão e mediação do conflito LGPD × obrigações regulatórias.
- Anonimização, pseudonimização e risco de reidentificação.
- Matriz de decisão por tipo de dado.
- Riscos remanescentes e recomendações para tickets futuros.

**Fora do escopo deste ticket:** alterar banco, schema ou dados; implementar
jobs automáticos de exclusão; emitir parecer jurídico; alterar regras do
ledger ou máquina de estados (CLAUDE.md §§ 1–5).

---

## 2. Referências legais

### 2.1 LGPD — Lei nº 13.709/2018

| Artigo | Relevância para o PicSaúde |
|---|---|
| art. 5, I | Define **dado pessoal** (qualquer informação relativa a pessoa natural identificada/identificável). |
| art. 5, II | Define **dado pessoal sensível** — inclui expressamente **dado referente à saúde**. É a categoria predominante do PicSaúde. |
| art. 5, III | Define **dado anonimizado** — aquele que não permite reidentificação com meios técnicos razoáveis. |
| art. 7 | Hipóteses de base legal para tratamento de dados pessoais comuns. |
| art. 11 | Hipóteses específicas para dados sensíveis (saúde inclusive), mais restritas. |
| art. 16, I | Permite **conservação após o término** do tratamento para cumprimento de **obrigação legal ou regulatória**. Cláusula central para conciliar LGPD e Lei 13.787. |
| art. 16, II | Conservação para estudo por órgão de pesquisa (anonimização preferencial). |
| art. 18 | Direitos do titular — acesso, correção, anonimização, bloqueio, **eliminação** (VI), portabilidade, revogação de consentimento. |
| art. 37 | **Registro de Atividades de Tratamento (ROPA)** — obrigação do controlador. |
| art. 46–49 | Segurança, boas práticas, governança. |

### 2.2 Lei nº 13.787/2018 — Prontuário Eletrônico do Paciente

- Define prazo **mínimo de 20 (vinte) anos** de guarda do prontuário a partir
  do último registro do paciente.
- Documentos que compõem o registro clínico — **prescrições, laudos, pedidos
  de exame, trilhas de dispensação** — estão sujeitos a este prazo.
- Após o prazo mínimo, a norma permite eliminação ou guarda permanente,
  conforme política do controlador.
- É a **norma principal** que justifica retenção prolongada no PicSaúde,
  mesmo diante de solicitação de eliminação pelo titular (LGPD art. 18, VI).

### 2.3 Resolução CFM 1.821/2007

- Norma setorial do Conselho Federal de Medicina sobre **guarda de prontuários
  médicos** (meio físico e eletrônico).
- Complementa a Lei 13.787/2018 no que concerne à prática médica.
- **⚠️ Disposições específicas (prazos, procedimentos) devem ser conferidas
  no texto vigente antes de uso operacional** — este documento **não** afirma
  dispositivos dessa resolução como fato, apenas registra sua existência
  como referência setorial.

### 2.4 RDC Anvisa nº 1.000/2025 — Sistema Nacional de Controle de Receituários (SNCR)

- Regulamenta a rastreabilidade e o controle de receituários para
  **medicamentos sujeitos a controle especial** (psicotrópicos, antimicrobianos,
  etc. — mapeados no PicSaúde pelo campo `prescricao_itens.classe_controle`).
- Impõe numeração sequencial, guarda e rastreabilidade específicas.
- **Prazo de adequação das instituições: 1º de junho de 2026.**
- A política do PicSaúde deve contemplar os requisitos da RDC 1.000/2025
  para prescrições com `classe_controle` não nula (A1, A2, A3, B1, B2, C5,
  D1, D2). Um plano de adequação formal deve existir antes dessa data
  (ver § 11).

### 2.5 Princípios LGPD aplicáveis ao PicSaúde (art. 6)

| Princípio | Aplicação no sistema |
|---|---|
| **Finalidade** | Dados tratados apenas para emissão, custódia, dispensação e auditoria de objetos sanitários. |
| **Adequação** | Cada campo coletado deve ter relação com um uso clínico concreto. |
| **Necessidade / minimização** | Não coletar campos extras sem justificativa — ex: `telefone` é nullable em `pacientes`, CPF é sentinela quando não identificado. |
| **Livre acesso / qualidade** | Titular deve ter meio de consulta (carteira digital já implementada). |
| **Transparência** | Este documento é insumo para políticas de privacidade públicas. |
| **Segurança e prevenção** | JWT, hash de senha com Argon2, headers de segurança, rate limiting. |
| **Não discriminação** | Dados clínicos não podem ser usados para fins discriminatórios. |
| **Responsabilização e prestação de contas** | Ledger imutável + ROPA futuro + trilha de custódia. |

### 2.6 Bases legais possivelmente aplicáveis (art. 7 e art. 11)

Para dados pessoais **comuns** (identificação, contato):

- art. 7, II — cumprimento de obrigação legal/regulatória;
- art. 7, III — execução de políticas públicas em saúde;
- art. 7, VI — exercício regular de direitos.

Para dados pessoais **sensíveis** (saúde):

- art. 11, II, "a" — cumprimento de obrigação legal do controlador;
- art. 11, II, "e" — exercício regular de direitos;
- art. 11, II, "f" — **tutela da saúde**, exclusivamente em procedimento realizado
  por profissionais de saúde ou por entidades sanitárias. É a base central
  candidata para o tratamento clínico no PicSaúde, mas depende do contexto
  institucional do operador.

> **A base legal definitiva não pode ser fixada neste documento.** Ela depende
> do contrato entre controlador e operador, do papel institucional (SUS,
> privado, convênio) e da finalidade específica de cada fluxo. Validação
> jurídica formal é **pré-requisito** de produção.

---

## 3. Inventário de dados tratados

Levantamento feito a partir dos models SQLAlchemy em
[backend/app/models/](../backend/app/models/). Apenas campos que o sistema
efetivamente trata estão listados.

### 3.1 Dados pessoais do paciente (LGPD art. 5, I)

| Tabela | Campos | Observações |
|---|---|---|
| `pacientes` | `cpf`, `nome`, `telefone`, `ativo` | `cpf` é indexado e único; `telefone` é opcional. CPF sentinela `00000000000` para emissão física sem identificação (CLAUDE.md § 6a). |
| `codigos_login` | `cpf`, `codigo` | OTP de 6 dígitos com expiração de 5 min. **CPF em texto plano** (não hashed) — justificado pelo fluxo curto de OTP, mas precisa de controle de acesso estrito. |
| `tokens_apresentacao` | `paciente_cpf`, `codigo_curto` | Token de apresentação em farmácia (Ticket 24). CPF em texto plano para vínculo e revogação. |
| `solicitacoes_renovacao` | `cpf_paciente`, `cns_prescritor` | Fluxo de renovação (Ticket 13 original). CPF/CNS em texto plano. |
| `circulacoes_diagnosticas` | `criado_por` (pode conter CPF) | Ticket 53. CPF em texto plano quando o paciente é originador. |
| `agendamentos` | `criado_por` (CPF ou CNS) | Ticket 29. |

### 3.2 Dados pessoais sensíveis — saúde (LGPD art. 5, II + art. 11)

| Tabela | Campos sensíveis | Observações |
|---|---|---|
| `prescricoes` | `indicacao_clinica` (texto livre), `codigo_cid` | Hipótese diagnóstica em texto livre é dado sensível clínico. |
| `prescricao_itens` | `nome_medicamento`, `concentracao`, `posologia`, `classe_controle` | Posologia é texto livre. `classe_controle` informa regime regulatório (A1–D2). |
| `pedidos_exame` | `indicacao_clinica` | Motivo clínico do pedido. |
| `pedido_exame_itens` | `nome_exame`, `resultado_resumo`, `resultado_url` | Resultado clínico pode conter diagnósticos. |
| `laudos` (via join em `laudo_itens`) | — | Laudo completo em `laudo_itens`. |
| `laudo_itens` | `nome_exame`, `resultado_resumo`, `conclusao`, `valor_referencia`, `resultado_url` | Conclusão (normal/alterado/indeterminado) + texto livre. |
| `solicitacoes_renovacao` | `motivo`, `observacao_resposta` | Textos clínicos livres. |
| `agendamentos` | `observacao` | Texto livre — pode conter contexto clínico. |
| `circulacoes_diagnosticas` | `instrucoes_preparo` | Texto clínico livre. |

### 3.3 Dados pessoais profissionais (LGPD art. 5, I)

| Tabela | Campos | Observações |
|---|---|---|
| `prescritores` | `cns`, `nome`, `telefone_vinculado`, `email`, `ativo` | CNS é identificador único; telefone/email opcionais. |
| `prestadores` | `org_id`, `nome`, `cnpj`, `tipo`, `ativo` | Entidade jurídica (farmácia, hospital, USF). CNPJ é dado público mas associado à operação. |
| `unidades` | `unidade_id`, `nome`, `tipo`, `prestador_id` | Unidade operacional dentro de um prestador. |
| `estabelecimentos_proprios` | `cnpj`, `nome_fantasia`, `razao_social`, `telefone_vinculado` | Cadastro de estabelecimentos próprios. |
| `prescricao_custodia` | `detentor_tipo`, `detentor_id` | `detentor_id` pode ser CPF, CNS ou CNPJ (dependendo do papel). |
| `dispensacoes` | `cnpj_estabelecimento`, `dispensado_por` (nome/CRF) | Identifica o farmacêutico responsável. |

### 3.4 Dados técnicos e de credenciais

| Tabela / artefato | Campos / conteúdo | Observações |
|---|---|---|
| `usuarios` | `role`, `identificador`, `nome`, `senha_hash`, `ativo` | **Senha hasheada com Argon2** (`backend/app/auth/jwt.py`). Identificador é CNS, CNPJ ou email conforme perfil. |
| `api_keys` | `chave_hash`, `org_id`, `nome`, `ativo` | **Chave nunca em claro** — armazenado apenas SHA-256 (G4B). |
| `codigos_login` | `cpf`, `codigo`, `expiracao`, `usado` | OTP em texto plano (válido por 5 min). Registrar apenas códigos curtos e invalidar após uso (já implementado). |
| `tokens_apresentacao` | `codigo_curto` (Crockford 8 chars), TTL curto | Token de apresentação do paciente à farmácia. |
| `tokens_apresentacao_usos` | `cnpj_estabelecimento`, `usado_em` | Rastro de uso (auditoria). |
| `prescricao_assinatura` | `dados_assinatura_b64` (PKCS#7/CAdES), `serial_certificado`, `hash_documento`, `emissor` | **Artefato criptográfico inline.** Tratar como dado sensível: contém material que permite verificação da autoria clínica. |
| `prescricoes.string_validacao_prescritor` | Formato `CPF|CONSELHO|CNS|STATUS_NOME|HASH_CERT|TIMESTAMP` | String auditável — contém **CPF e CNS do prescritor em claro**. Acesso restrito. |
| JWT (access + refresh) | Em memória / armazenamento do cliente | Access token: `JWT_ACCESS_TTL_MINUTES`. Refresh: `JWT_REFRESH_TTL_MINUTES`. Não persistidos no banco. |
| Logs de aplicação | Stdout / arquivo operacional | Devem usar CPF mascarado ou ID interno (CLAUDE.md — ver `_cpf_mascarado` em `auth.py`). |
| Métricas de observabilidade | `/metrics` (localhost only) | Agregadas, sem dados pessoais. |
| Backups | Dump PostgreSQL (pg_dump) | Contêm **todos** os dados — mesma classificação do banco original. |

### 3.5 Dados de auditoria — ledger e custódia

| Tabela | Campos relevantes | Observações |
|---|---|---|
| `prescricao_eventos` | `tipo_evento`, `ator_tipo`, `ator_id`, `payload_json`, `created_at` | **Imutável** (CLAUDE.md § 2). `payload_json` pode carregar CPF, CNS, hash de certificado, CNES, score de confiança. |
| `pedido_exame_eventos` | idem | Ledger de pedidos de exame. |
| `laudo_eventos` | idem | Ledger de laudos. |
| `agendamento_eventos` | idem | Ledger de agendamentos. |
| `circulacao_diagnostica_eventos` | idem | Ledger de circulação diagnóstica. |
| `prescricao_custodia` | `detentor_tipo`, `detentor_id`, `transferida_em`, `encerrada_em`, `contexto_operacional`, `unidade_id` | Cadeia de custódia — CLAUDE.md § 3. |
| `laudo_custodia`, `pedido_exame_custodia` | idem | Custódias dos outros objetos sanitários. |
| `dispensacoes`, `dispensacoes_hospitalares` | `prescricao_item_id`, `cnpj_estabelecimento`, `quantidade_dispensada`, `dispensado_por`, `lote`, `fabricante` | Trilha de dispensação. |
| `eventos_publicacao` | `envelope_json` | Outbox G4A para publicação externa de eventos. Contém os mesmos dados do ledger serializados. |

**Resumo quantitativo:** ~30 tabelas operacionais. Cinco categorias de dados:

1. Dados pessoais comuns (paciente/profissional) — 7 tabelas principais.
2. Dados pessoais **sensíveis** de saúde — 9 tabelas principais.
3. Dados profissionais (prescritor / prestador) — 6 tabelas principais.
4. Dados técnicos (credenciais, tokens, logs, backups) — 5 tabelas + artefatos.
5. Ledger e auditoria — 8 tabelas de eventos/custódia/dispensação.

---

## 4. Política de retenção

Para cada categoria são distinguidos **(a) prazo mínimo legal** e
**(b) retenção recomendada operacionalmente**.

### 4.1 Dados clínicos — prescrições, laudos, pedidos, ledger, custódia, dispensações

- **Prazo mínimo legal:** **20 anos** a partir do último registro do paciente
  (Lei 13.787/2018). Resolução CFM 1.821/2007 como norma setorial complementar
  (verificar texto vigente).
- **Prescrições com `classe_controle` não nulo:** submetidas também aos prazos
  específicos da **RDC Anvisa 1.000/2025** — confirmar o prazo vigente na
  norma antes de definir rotina de expurgo.
- **Recomendação operacional:** **guarda permanente** enquanto o sistema estiver
  ativo. Não há ganho operacional relevante em expurgo automático.
- **Ledger (`*_eventos`):** **NUNCA excluir, NUNCA alterar** (CLAUDE.md § 2).
  Mesmo após expiração do prazo da Lei 13.787, a preservação do ledger é
  recomendada enquanto a prescrição/laudo referenciados existirem.

### 4.2 Dados pessoais do paciente (CPF, nome, telefone, CNS)

- **Prazo mínimo legal:** vinculado ao prazo do prontuário (20 anos — Lei
  13.787). Enquanto houver qualquer objeto sanitário (prescrição, laudo, pedido)
  referenciando o paciente dentro do prazo, **não excluir**.
- **Após expiração:** **pseudonimização preferível à exclusão**, pois preserva
  a integridade referencial do ledger e de relatórios agregados. Anonimização
  pode ser considerada para dados muito antigos.
- **Telefone:** coletado apenas quando necessário; não é obrigatório em
  `pacientes`. Minimizar.

### 4.3 Dados profissionais (prescritor, prestador, estabelecimento)

- **Prazo:** vinculado à vida útil dos documentos clínicos que os referenciam.
- **Enquanto houver prescrição, laudo ou dispensação vinculada:** não excluir.
- Cadastros inativos podem ter o flag `ativo=false` (deleção lógica) mantendo
  o vínculo para auditoria.

### 4.4 Credenciais e tokens

| Artefato | Retenção |
|---|---|
| `usuarios.senha_hash` | Enquanto o usuário estiver ativo. Revogar hash em caso de saída. |
| `codigos_login` | 5 minutos (TTL). Após uso/expiração, exclusão automática aceitável (GDPR/LGPD: minimização). |
| `tokens_apresentacao` | TTL ≤ 120 min (Ticket 44). Após expiração: manter registro para auditoria de tentativa de uso (não a chave, apenas metadados). |
| JWT access | TTL curto (JWT_ACCESS_TTL_MINUTES). Não persistido. |
| JWT refresh | TTL mais longo (JWT_REFRESH_TTL_MINUTES). Não persistido. |
| `api_keys.chave_hash` | Enquanto a integração for válida. Revogar via `ativo=false`; não remover o registro para preservar trilha G4B. |

### 4.5 Logs de aplicação

- **Prazo mínimo legal:** não definido especificamente.
- **Recomendação operacional:** **90 dias** (suficiente para troubleshooting e
  análise forense de curto prazo).
- **Requisito:** logs **não devem conter dados pessoais sensíveis** (CID,
  diagnóstico, medicamento associado a pessoa). CPF deve aparecer mascarado.
- **Exclusão automática aceitável** após o prazo.

### 4.6 Backups

- **Prazo:** definido por política operacional — **sugestão: 90 dias** para
  backups incrementais e **3 anos** para snapshots anuais auditáveis.
- **Requisitos:** em produção, backups **devem ser criptografados em repouso**
  e **em trânsito**. Ver [backup_restore.md](backup_restore.md).
- Sujeitos à **mesma política de dados** que o banco original — um backup
  vazado é um vazamento equivalente.
- Antes de destruir um backup, verificar que não há obrigação de retenção
  ativa sobre os dados que ele contém.

### 4.7 Dados CNES (referência externa)

- Base pública do Ministério da Saúde — política própria de atualização.
- Não contém dados pessoais de pacientes.
- Snapshot mensal: manter ao menos a versão corrente em uso + 1 anterior.

### 4.8 Métricas de observabilidade

- **Prazo:** 30 a 90 dias (operacional).
- Devem ser **agregadas e anônimas**; não devem conter CPF, CNS, nome.
- Exclusão automática aceitável.

---

## 5. Exclusão e conflito LGPD × legislação de saúde

Esta é a seção operacionalmente mais delicada. O direito do titular à
**eliminação** (LGPD art. 18, VI) **não é absoluto**.

### 5.1 Hipóteses de conservação apesar do pedido

- **LGPD art. 16, I** — cumprimento de obrigação legal/regulatória pelo
  controlador.
- **LGPD art. 16, II** — estudo por órgão de pesquisa (anonimização preferida).
- **Lei 13.787/2018** — guarda mínima de 20 anos do prontuário.
- **CFM 1.821/2007** — referência setorial sobre guarda (verificar vigente).
- **RDC Anvisa 1.000/2025** — rastreabilidade de receituários controlados.
- **Defesa em processo judicial, administrativo ou arbitral** (LGPD art. 7, VI).

### 5.2 Orientações operacionais

**a) Pedido de exclusão de dados clínicos (prescrição, laudo, pedido):**

1. **NÃO** excluir automaticamente — em nenhuma hipótese.
2. Registrar a solicitação formalmente (futuro: tabela `solicitacoes_titular`).
3. Analisar se há obrigação legal de conservação (quase sempre há, por 20 anos).
4. Se há obrigação: **negar exclusão** com fundamentação legal citada, informar
   o titular da base legal e o prazo de guarda.
5. Se não há obrigação: avaliar **pseudonimização** antes de exclusão.
6. **NUNCA destruir o ledger** (`*_eventos`) — sua imutabilidade é invariante
   arquitetural (CLAUDE.md § 2).

**b) Pedido de exclusão de dados cadastrais (nome, telefone):**

1. Se o paciente tem objetos sanitários dentro do prazo legal: preferir
   **restrição de acesso** ou pseudonimização à exclusão.
2. Se não há vínculo clínico: exclusão possível após análise.

**c) Resposta ao titular (LGPD art. 18, § 6):**

- Toda solicitação deve ser registrada e respondida.
- Prazo de confirmação: **15 dias** (LGPD art. 19, § 1).
- Quando negar, fundamentar a negativa (base legal específica).

### 5.3 Hierarquia de preferência

Do menos intrusivo ao mais intrusivo:

```
1. Restrição de acesso        ← primeiro recurso
2. Pseudonimização            ← preserva integridade, reversível sob controle
3. Anonimização               ← irreversível
4. Exclusão                   ← último recurso, apenas sem conflito legal
```

### 5.4 Invariantes arquiteturais (não negociáveis)

- **Imutabilidade do objeto sanitário** (CLAUDE.md § 1) — correção gera novo
  objeto derivado, nunca UPDATE do original.
- **Imutabilidade do ledger** (§ 2) — sem UPDATE, sem DELETE.
- **Cadeia de custódia explícita** (§ 3) — transições apenas via endpoints
  oficiais.

Qualquer workflow de exclusão deve respeitar essas invariantes. Pedidos que
tentariam violá-las devem ser rejeitados pela análise jurídica antes de
chegar ao banco.

---

## 6. Anonimização e pseudonimização

### 6.1 Definições (LGPD art. 5)

- **Anonimização (III):** dado deixa de permitir identificação, considerando
  os meios técnicos razoáveis disponíveis. Deixa de ser dado pessoal e **sai
  do escopo da LGPD**.
- **Pseudonimização (XI):** dado é modificado de forma que só possa ser
  identificado mediante informação adicional mantida em separado. Continua
  sendo dado pessoal, **permanece sob a LGPD**.

### 6.2 Hash simples **NÃO é anonimização**

- CPF tem 11 dígitos = ~10¹¹ combinações.
- CNS tem 15 dígitos = ~10¹⁵ combinações.
- Um hash SHA-256 sem salt pode ser **revertido em horas** num dicionário
  completo de CPFs válidos. É **reversível** — portanto apenas
  pseudonimização fraca, não anonimização.

**Nunca** usar `sha256(cpf)` e chamar o resultado de "dado anonimizado".

### 6.3 Pseudonimização técnica adequada

- **HMAC-SHA-256 com segredo** armazenado **fora do código-fonte**
  (ex: AWS Secrets Manager, Vault, variável de ambiente protegida).
- **Salt forte** por registro ou por contexto.
- **Rotação periódica do segredo** documentada.
- O segredo deve ter **o mesmo nível de proteção do banco de dados**.
- Em memória: zerar o segredo após uso.

### 6.4 Anonimização para relatórios e analytics

Para liberação de dados agregados:

1. Remover identificadores diretos: CPF, CNS, nome, telefone, e-mail,
   string_validacao_prescritor, UUIDs globais (`protocolo`).
2. **Generalizar datas** — por mês ou trimestre em vez de dia/hora.
3. **Reduzir granularidade territorial** — estado ou região, em vez de
   município pequeno.
4. **Agregar medicamentos** por classe terapêutica em vez de apresentação
   específica.
5. Aplicar **k-anonymity ≥ 5** (cada combinação de atributos quase-identificadores
   deve corresponder a pelo menos 5 pessoas).

### 6.5 Risco de reidentificação — exemplo concreto do PicSaúde

O PicSaúde é projetado para rodar em Pernambuco, que possui **municípios de
baixa população** (dezenas de cidades abaixo de 10.000 habitantes).

**Cenário real:**

| Campo | Valor hipotético |
|---|---|
| Município | Pequeno (5.000 habitantes) |
| Medicamento | Uso exclusivo em doença rara (órfão) |
| Data de emissão | Específica (ex: 2026-03-14) |
| Prescritor | Único médico especialista do município |

**Resultado:** mesmo **removendo CPF, CNS, nome e telefone**, essa combinação
identifica **uma pessoa específica** — em alguns casos, a única pessoa do
município portadora da condição. O registro permanece **dado pessoal sensível**
mesmo "anonimizado" ingenuamente.

**Consequências para a política:**

- Relatórios territorializados só devem circular com **agregação mínima
  (k ≥ 5)** ou em nível de região/estado.
- Medicamentos órfãos ou de altíssimo custo requerem supressão adicional
  (não publicar nível de município).
- Dados clínicos de municípios pequenos **não devem ser tratados como
  anônimos** apenas porque identificadores diretos foram removidos.

---

## 7. Matriz de decisão

| Tipo de dado | Categoria | Prazo mínimo legal | Retenção recomendada | Pode excluir? | Pode anonimizar? | Base legal / justificativa | Observações |
|---|---|---|---|---|---|---|---|
| CPF do paciente | Pessoal (art. 5, I) | 20 anos — Lei 13.787 (vinculado ao prontuário) | Enquanto houver vínculo clínico ativo | **Não** durante prazo; após: pseudonimizar preferencial | Sim, após prazo | LGPD 16, I + Lei 13.787 | Sentinela `00000000000` para emissão física sem identificação |
| CNS do paciente | Pessoal (art. 5, I) | 20 anos — Lei 13.787 | Idem CPF | **Não** durante prazo | Sim, após prazo | LGPD 16, I + Lei 13.787 | — |
| Nome do paciente | Pessoal (art. 5, I) | 20 anos — Lei 13.787 | Idem | **Não** durante prazo | Sim, após prazo | LGPD 16, I + Lei 13.787 | — |
| Telefone do paciente | Pessoal (art. 5, I) | Vinculado ao prontuário | Enquanto necessário ao contato | Sim, se desnecessário | N/A | LGPD 6, III (necessidade) | Minimizar — campo nullable |
| Prescrição (cabeçalho) | Sensível — saúde (art. 5, II) | 20 anos — Lei 13.787 | Permanente (enquanto sistema ativo) | **Não** | Parcial (agregados) | LGPD 11, II, "f" + Lei 13.787 | Imutável (CLAUDE.md § 1) |
| Itens de prescrição (medicamento, posologia) | Sensível — saúde | 20 anos — Lei 13.787; RDC 1.000 para controlados | Permanente | **Não** | Parcial (agregados por classe) | LGPD 11 + Lei 13.787 + RDC 1.000 | `classe_controle` ≠ NULL → RDC 1.000 |
| CID / indicação clínica | Sensível — saúde | 20 anos — Lei 13.787 | Permanente | **Não** | Parcial | LGPD 11 + Lei 13.787 | Texto livre em `indicacao_clinica` |
| Laudo (incl. resultado_resumo, conclusão) | Sensível — saúde | 20 anos — Lei 13.787 | Permanente | **Não** | Parcial | LGPD 11 + Lei 13.787 | Resultados podem conter diagnósticos inteiros |
| Pedido de exame | Sensível — saúde | 20 anos — Lei 13.787 | Permanente | **Não** | Parcial | LGPD 11 + Lei 13.787 | — |
| `prescricao_eventos` (ledger) | Auditoria clínica | 20 anos — Lei 13.787 | Permanente | **Nunca** | Não aplicável | CLAUDE.md § 2 (invariante) | Imutável por design |
| `prescricao_custodia` (custódia) | Auditoria clínica | 20 anos — Lei 13.787 | Permanente | **Não** | Não aplicável | CLAUDE.md § 3 | Cadeia completa preservada |
| `dispensacoes` / `dispensacoes_hospitalares` | Sensível — saúde | 20 anos — Lei 13.787; RDC 1.000 para controlados | Permanente | **Não** | Parcial | LGPD 11 + Lei 13.787 + RDC 1.000 | — |
| CNS do prescritor | Pessoal profissional | Vinculado a documentos clínicos referenciantes | Enquanto houver vínculo | **Não** durante vínculo | Sim, após | LGPD 7, II/III | Em `prescritores` |
| Usuário / senha_hash | Credencial | Enquanto conta ativa | Revogar no desligamento | Sim, após desativação + auditoria | N/A | LGPD 7, VI | Argon2 (não reversível) |
| Access token (JWT) | Técnico | N/A (TTL curto) | Em memória | Sim (expira) | N/A | LGPD 6, III | Não persistido |
| Refresh token (JWT) | Técnico | N/A (TTL configurável) | Conforme política | Sim | N/A | LGPD 6, III | Não persistido |
| `codigos_login` (OTP) | Credencial | N/A (5 min) | TTL + limpeza | Sim, após expiração | N/A | LGPD 6, III (minimização) | CPF em texto plano — revisar futura |
| `tokens_apresentacao` | Técnico (apresentação) | N/A (120 min máx) | Expirar + manter metadados | Chave sim; registro mantido | N/A | LGPD 6 + auditoria | Contém `paciente_cpf` |
| `string_validacao_prescritor` | Auditoria + credencial | Vinculado à prescrição (20 anos) | Permanente | **Não** | **Não** (contém CPF em claro) | LGPD 11 + Lei 13.787 | Contém CPF do prescritor |
| `prescricao_assinatura` (PKCS#7) | Auditoria + criptográfico | Vinculado à prescrição (20 anos) | Permanente | **Não** | **Não** | LGPD 11 + Lei 13.787 | Artefato de integridade |
| Logs de aplicação | Técnico | Não fixado | 90 dias | Sim, após prazo | N/A | LGPD 6, III | Sem dados sensíveis; CPF mascarado |
| Backups | Espelho do banco | Igual ao banco; sugestão 90 d + snapshot anual | Política operacional | Apenas após verificação de obrigações ativas | Não aplicável | LGPD 46 (segurança) | Criptografar em produção |
| Dados CNES (referência) | Público externo | N/A | Versão corrente + 1 anterior | Sim (atualização) | N/A | LGPD 7, III | Não contém dados pessoais de paciente |
| Métricas de observabilidade | Técnico | N/A | 30–90 dias | Sim | N/A | LGPD 6, III | Agregadas, sem dados pessoais |

---

## 8. Regras operacionais — o que fazer, o que não fazer

### 8.1 O que **DEVE** ser feito

- Mascarar CPF em logs (exibir só os 4 últimos dígitos) — padrão já existente
  em `routers/auth.py` (`_cpf_mascarado`).
- Registrar formalmente qualquer solicitação de titular (via endpoint
  dedicado futuro ou canal documentado).
- Responder o titular em até 15 dias (LGPD art. 19).
- Manter backups criptografados em produção.
- Minimizar coleta: não adicionar campos novos sem finalidade clínica ou
  legal clara.
- Revisar trimestralmente a matriz da seção 7.
- Sempre que em dúvida sobre classificação: **tratar como sensível**.

### 8.2 O que **NÃO** deve ser feito

- ❌ `UPDATE`/`DELETE` em qualquer tabela `*_eventos` (ledger).
- ❌ `UPDATE` em `prescricoes`, `laudos`, `pedidos_exame` já emitidos — usar
  derivação via `origem_prescricao_id`/`origem_*_id`.
- ❌ Excluir paciente com prescrição vinculada dentro do prazo da Lei 13.787.
- ❌ Usar hash simples como "anonimização".
- ❌ Publicar relatórios com granularidade de município pequeno para
  medicamentos raros.
- ❌ Armazenar o segredo de HMAC junto com o banco ou no código-fonte.
- ❌ Logar CPF, CNS ou CID em texto plano.
- ❌ Responder "Sim" à exclusão sem verificar obrigação legal.
- ❌ Destruir backups antes de confirmar que a retenção legal foi atendida.

---

## 9. Riscos remanescentes

| # | Risco | Gravidade | Mitigação atual | Próximo passo |
|---|---|---|---|---|
| 1 | Hash sem salt usado como "anonimização" | Alta | Documentado como proibido (§ 6.2) | Implementar HMAC com segredo em Vault (§ 11) |
| 2 | Reidentificação por combinação em município pequeno | Alta | Documentado com exemplo (§ 6.5) | Regra explícita para relatórios territoriais |
| 3 | Retenção excessiva sem justificativa | Média | Matriz de decisão (§ 7) | Revisar trimestralmente |
| 4 | Exclusão indevida de dados com obrigação legal | Alta | Invariantes do ledger; § 5 | Workflow formal de titular antes de permitir qualquer exclusão |
| 5 | Conflito LGPD × saúde não resolvido caso a caso | Média | Orientação geral em § 5 | Revisão jurídica formal pré-produção |
| 6 | Vazamento de backup não criptografado | Alta | Documentado em backup_restore.md | Criptografar em repouso e em trânsito em produção |
| 7 | Uso secundário de dados sem base legal clara | Alta | Sem uso secundário no MVP | Tabela de consentimentos + política antes de liberar |
| 8 | Logs vazando dados sensíveis por regressão futura | Média | CPF mascarado no código atual | Teste automatizado verificando que logs não contêm CPF completo |
| 9 | Ausência de ROPA formal (LGPD art. 37) | Média | Recomendação no § 10 | Implementar ROPA antes de produção |
| 10 | Ausência de DPO/encarregado designado | Média | Ausência documentada | Designar encarregado antes de produção |
| 11 | RDC 1.000/2025 — prazo 01/06/2026 sem plano formal | **Alta** | `classe_controle` já modelado | Plano de adequação SNCR **antes de junho/2026** |
| 12 | `codigos_login` armazena CPF e código OTP em claro | Média | TTL curto (5 min); invalidação após uso | Avaliar HMAC no CPF da tabela OTP |
| 13 | `tokens_apresentacao` armazena `paciente_cpf` em claro | Baixa | TTL curto; acesso restrito via RBAC | Avaliar se pseudonimização é viável sem quebrar Ticket 24 |
| 14 | `string_validacao_prescritor` contém CPF em claro | Média | Acesso restrito ao prescritor/admin | Verificar regras de exposição em GET `/prescricoes/.../validacao` |

---

## 10. Recomendações para tickets futuros

Cada item abaixo deve virar um ticket formal, classificado conforme
CLAUDE.md § 10 (core / module / adapter / local-extension / docs / ops):

1. **[module]** Workflow de **solicitação de titular** (endpoint + tabela
   `solicitacoes_titular` + prazo de 15 dias + resposta fundamentada).
2. **[ops]** Política de **rotação automática de logs** (90 dias) e validação
   de que não contêm dados pessoais.
3. **[ops]** **Criptografia de backups** em repouso e em trânsito (produção).
4. **[ops]** Designação formal de **DPO/encarregado** e documentação do
   canal de contato.
5. **[module]** Avaliar necessidade de tabela de **consentimentos**
   (se aplicável ao modelo institucional).
6. **[module]** **Pseudonimização para analytics/relatórios** — HMAC com
   segredo externo, supressão territorial k ≥ 5.
7. **[docs]** **Revisão jurídica formal** deste documento por advogado
   especializado antes de produção.
8. **[docs]** **ROPA completo** (LGPD art. 37) — ver § 11.
9. **[core/ops]** **Plano de adequação à RDC 1.000/2025** (SNCR) antes
   de 01/06/2026 — incluir numeração sequencial se exigida, rastreabilidade
   específica dos controlados, retenção conforme a norma.
10. **[module]** Política de **destruição de dados após prazo legal** — job
    controlado manualmente, registrado no ledger, com fundamentação legal.
11. **[core]** Revisão do **controle de acesso granular por papel/função** —
    garantir que campos pessoais (ex: `string_validacao_prescritor`) só
    sejam expostos aos perfis adequados.
12. **[module]** Teste automatizado que garante **logs não contêm CPF
    completo** (regressão a cada release).
13. **[module]** Avaliar **pseudonimização de CPF em `codigos_login`**
    (HMAC) — preservar fluxo de OTP sem armazenar CPF em claro.

---

## 11. ROPA — Registro de Atividades de Tratamento (LGPD art. 37)

Este documento **recomenda** a criação de um ROPA formal antes da operação
em produção. A implementação é escopo futuro (Ticket 14+ em roadmap LGPD).

**Estrutura mínima sugerida por fluxo:**

- Finalidade específica do tratamento.
- Categorias de dados tratados (referenciar § 3 deste documento).
- Categorias de titulares (pacientes, prescritores, dispensadores, gestores).
- Destinatários (se houver compartilhamento — ex: CNES, SNCR, integradores
  via G4B).
- Transferências internacionais (se houver).
- Prazo de retenção por categoria (referenciar § 4).
- Medidas de segurança adotadas (referenciar backup_restore.md, HARDENING_MVP.md).
- Base legal aplicável (referenciar § 2.6).

O ROPA é **documento do controlador**, não do operador. A responsabilidade
formal pela sua manutenção deve ser definida contratualmente.

---

## 12. Histórico de revisões

| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 1.0 | 2026-04-24 | Ticket 14 | Versão inicial — inventário completo; referências LGPD + Lei 13.787 + CFM 1.821 + RDC 1.000; matriz de decisão (23 linhas); orientações operacionais; 14 riscos registrados; 13 recomendações futuras. |

---

## Apêndice A — Glossário

| Termo | Definição |
|---|---|
| **Anonimização** | Tratamento que torna impossível a identificação do titular com meios técnicos razoáveis. Dado sai do escopo da LGPD. |
| **Pseudonimização** | Tratamento que dificulta identificação, requerendo informação adicional. Dado continua sob LGPD. |
| **Controlador** | Entidade que decide a finalidade e os meios do tratamento. |
| **Operador** | Entidade que trata dados em nome do controlador. |
| **DPO / Encarregado** | Pessoa designada pelo controlador para mediar relação com titulares e ANPD. |
| **ROPA** | Registro de Atividades de Tratamento (LGPD art. 37). |
| **SNCR** | Sistema Nacional de Controle de Receituários (RDC Anvisa 1.000/2025). |
| **Ledger** | Tabelas `*_eventos` — trilha imutável de eventos do PicSaúde. |
| **Custódia** | Rastreabilidade explícita do detentor de um objeto sanitário ao longo do tempo (CLAUDE.md § 3). |
| **k-anonymity** | Propriedade em que cada combinação de quase-identificadores aparece em pelo menos *k* registros. |
