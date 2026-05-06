# Política de Proteção de Dados — PicSaúde

> Este documento estabelece a política de proteção de dados aplicável a todas as instâncias do PicSaúde, independentemente da licença adotada (AGPL-3.0 ou comercial). Complementa, mas não modifica, os termos do `LICENSE` e do `DISCLAIMER.md`.

---

## Contexto regulatório

O PicSaúde processa **dados pessoais sensíveis** conforme definição do Art. 5º, II, da Lei 13.709/2018 (LGPD): dados sobre saúde, vida sexual, dados genéticos, biométricos, entre outros. O tratamento desses dados está sujeito a hipóteses legais específicas (Art. 11) e a salvaguardas reforçadas.

Identificadores oficiais:

- **Registro de Programa de Computador no INPI:** processo BR 51 2026 002267-3 (RPI 2883, 07/04/2026)
- **Titular do software:** Fabiano Tonaco Borges

---

## Regra de Ouro

> **Dados de pacientes, prescritores, dispensadores e prescrições processados pelo PicSaúde NÃO PODEM ser vendidos, comercializados, monetizados, cedidos ou transferidos a terceiros — sob nenhuma circunstância, por nenhum licenciado, em nenhuma modalidade.**

A violação desta regra:

- Configura **infração à LGPD**, sujeita às sanções administrativas do Art. 52 (advertência, multa simples até 2% do faturamento, multa diária, publicização da infração, bloqueio de dados, suspensão de atividade, proibição de tratamento)
- **Extingue automática e irrevogavelmente** qualquer licença comercial ativa concedida pelo titular do software (`COMMERCIAL-LICENSE.md`)
- Configura **violação contratual** sujeita às sanções civis cabíveis no foro da Comarca de Recife/PE
- Pode configurar crime contra a privacidade nos termos da legislação penal aplicável

---

## Distinção entre titular do software e controlador de dados

Para evitar confusão jurídica:

- **Titular do software:** Fabiano Tonaco Borges, autor e detentor dos direitos autorais sobre o código. **Não é controlador de dados** das instâncias operadas por terceiros.
- **Controlador de dados** (Art. 5º, VI, LGPD): é quem opera a instância do PicSaúde — clínica, hospital, secretaria de saúde, plataforma SaaS. Assume todas as obrigações da LGPD perante titulares de dados (pacientes e prescritores).
- **Operador de dados** (Art. 5º, VII, LGPD): pode ser empresa terceirizada que processa os dados em nome do controlador. Vincula-se via contrato específico.

O titular do software fornece a ferramenta; quem opera responde pelos dados.

---

## Mecanismos técnicos de proteção

A proteção técnica é **dissuasão (deterrence) e rastreabilidade**, não bloqueio absoluto. Nenhum mecanismo técnico impede exfiltração deliberada por quem tem acesso direto ao banco de dados. A proteção jurídica (contrato + LGPD) complementa, mas não substitui, a proteção técnica.

### 1. Sem exportação em massa

O motor PicSaúde **não oferece endpoints de dump nem exportação em lote** de dados individualizados. Consultas retornam prescrições individuais por protocolo (UUID). Relatórios estatísticos são **anonimizados e agregados**.

Qualquer modificação no código que adicione endpoints de exportação em massa é tecnicamente visível — a AGPL-3.0 obriga publicação de alterações para qualquer software derivado que interaja com usuários via rede. Em instâncias sob licença comercial, o operador aceita auditoria técnica sob demanda do titular.

### 2. Marca d'água (instance_id)

Cada instância do PicSaúde gera um identificador único (`instance_id`, UUID v4) no primeiro boot e o persiste localmente. Esse identificador é embutido em:

- Metadados de cada prescrição emitida
- Cada evento registrado no ledger de auditoria
- Metadados do PDF assinado
- Logs de operações sensíveis

Se dados desta instância aparecerem fora do sistema (por exemplo, em vazamentos), o `instance_id` permite identificar a instância de origem com precisão forense.

**A remoção, modificação ou ofuscação do `instance_id` viola os termos de licenciamento e extingue automaticamente qualquer licença comercial.**

### 3. Ledger de auditoria imutável

Toda ação no sistema (emissão, assinatura, transferência de custódia, dispensação, visualização autenticada, download de PDF) gera registro **append-only** no ledger de eventos, contendo:

- Timestamp em UTC
- Ator (CNS do prescritor, CPF do paciente quando aplicável, CNES do estabelecimento)
- Tipo de evento (vocabulário fechado, declarado em código)
- Hash criptográfico
- `instance_id`

O ledger não recebe `UPDATE` nem `DELETE`. Serve como **prova forense** em caso de investigação interna, auditoria regulatória ou processo judicial.

### 4. AGPL-3.0 como transparência forçada

Toda derivação que interaja com usuários via rede — incluindo SaaS, plataformas em nuvem e serviços públicos — deve **publicar o código-fonte** sob a AGPL-3.0. Funcionalidades ocultas de exportação, APIs de vazamento, integrações não documentadas com sistemas de marketing/CRM, ou backdoors de dados ficam **visíveis para auditoria pública**.

Operadores que adotem licença comercial (código fechado) **aceitam contratualmente auditoria técnica sob demanda do titular**, conforme `COMMERCIAL-LICENSE.md`.

### 5. Criptografia em repouso para artefatos sensíveis

Certificados ICP-Brasil (`.pfx`) ficam armazenados em **cofre AES-256-GCM** com chave separada do banco principal. Em produção, sugestões transitórias da camada de IA (quando ativada) ficam criptografadas em repouso e expurgadas por TTL configurável (ver `docs/TICKET-70-SPEC.md`).

---

## Roadmap de proteção (em desenvolvimento)

Itens previstos para versões futuras, em ordem de prioridade:

- **Rate limiting por usuário autenticado** — detecta scraping silencioso via API legítima
- **Watermark invisível no PDF** — além do `instance_id` nos metadados, marca d'água esteganográfica no documento renderizado
- **Hashing encadeado no ledger** — cadeia de integridade tipo "blockchain leve", em que cada evento contém hash do anterior, tornando manipulação retroativa detectável
- **Detecção de comportamento anômalo** — alertas automáticos para padrões de acesso suspeitos (muitos protocolos consultados em curto intervalo, acessos fora de horário de expediente, etc.)
- **Pseudonimização nativa para relatórios** — exportação de dados para análise epidemiológica sempre com chave de pseudonimização rotativa

Estes itens são **dissuasão e rastreabilidade adicionais**, não substituem as obrigações da LGPD nem o controle físico do banco de dados pelo operador.

---

## Limites honestos da proteção técnica

Para que ninguém se iluda:

- Quem tem **acesso administrativo ao banco de dados** pode exfiltrar dados sem passar pela API. A proteção contra esse vetor é **organizacional** (controle de acesso, segregação de funções, auditoria interna), não técnica.
- Quem tem **acesso ao servidor de aplicação** pode ler memória e capturar dados em trânsito. A proteção é **infra** (hardening, IDS, SIEM).
- Quem **bifurca o código** sob AGPL pode remover o `instance_id` antes de operar. A proteção contra isso é **jurídica** — operação sem `instance_id` viola licenciamento, e a marca registrada PicSaúde (pedidos INPI 943014573 e 943014883) impede uso comercial do nome em derivações.

A proteção técnica é **necessária e suficiente para detectar abuso**, não para impedi-lo de modo absoluto. Por isso a regra de ouro está em texto, em contrato e em código.

---

## Direitos dos titulares de dados

Em consonância com a LGPD (Arts. 17–22), todo paciente, prescritor ou dispensador cujos dados sejam tratados pelo PicSaúde tem direito a:

- **Confirmação** da existência de tratamento
- **Acesso** aos dados
- **Correção** de dados incompletos, inexatos ou desatualizados
- **Anonimização, bloqueio ou eliminação** de dados desnecessários, excessivos ou tratados em desconformidade com a LGPD
- **Portabilidade** dos dados a outro fornecedor de serviço
- **Eliminação** dos dados tratados com consentimento
- **Informação** sobre entidades públicas e privadas com as quais o controlador compartilhou dados
- **Revogação do consentimento**

O exercício desses direitos é responsabilidade do **operador** (controlador de dados), não do titular do software. O operador deve disponibilizar canal acessível para que titulares de dados exerçam seus direitos.

---

## Vigência e atualização

Esta política é válida para todas as instâncias do PicSaúde a partir da data desta versão. Atualizações são publicadas no repositório oficial e entram em vigor a partir da data do commit correspondente.

**Data desta versão:** 2026-05-06

**Foro:** Comarca de Recife/PE, conforme `DISCLAIMER.md` e `COMMERCIAL-LICENSE.md`.
