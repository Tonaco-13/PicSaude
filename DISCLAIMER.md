# Disclaimer de Responsabilidade — PicSaúde

> Este documento complementa, mas não modifica, os termos da licença sob a qual o software é distribuído (`LICENSE`, GNU Affero General Public License v3.0, e/ou `COMMERCIAL-LICENSE.md`).

---

## Natureza do software

O PicSaúde é um motor de prescrição digital que implementa regras regulatórias brasileiras (RDC 1.000/2025 da Anvisa, Portaria 344/98 do MS, Lei 13.709/2018 — LGPD, entre outras) e assinatura digital qualificada via ICP-Brasil (MP 2.200-2/2001).

O software é uma **ferramenta de apoio ao profissional de saúde habilitado**. **NÃO é um substituto do julgamento clínico** do prescritor, do farmacêutico dispensador ou de qualquer outro profissional de saúde envolvido no ciclo da prescrição.

Identificadores oficiais:

- **Registro de Programa de Computador no INPI:** processo BR 51 2026 002267-3 (RPI 2883, 07/04/2026)
- **Titular:** Fabiano Tonaco Borges

---

## Limitação de responsabilidade

O titular do software e os contribuidores:

### 1. Não se responsabilizam por erros clínicos, diagnósticos ou terapêuticos

A responsabilidade pela prescrição é **exclusivamente** do profissional de saúde habilitado que a emitiu, devidamente registrado no respectivo conselho de classe (CRM, CRO, CRMV, CRBM, conforme aplicável). Erros de dose, posologia, interação medicamentosa, contraindicação, alergia, indicação ou diagnóstico são de responsabilidade do prescritor, não do software.

### 2. Não garantem ausência de erros, bugs ou vulnerabilidades

O software é fornecido **"como está"** (*as-is*), sem garantias de qualquer tipo, expressas ou implícitas, incluindo — mas não se limitando a — garantias de comerciabilidade, adequação a um propósito específico, ausência de erros, ou não violação. O esforço de testes (146 testes automatizados na versão atual) reduz a probabilidade de defeitos, mas não a elimina.

### 3. Não se responsabilizam por danos

Em nenhuma hipótese o titular ou os contribuidores serão responsáveis por **danos diretos, indiretos, incidentais, especiais, exemplares ou consequenciais** decorrentes do uso ou da impossibilidade de uso do software, incluindo perda de dados, perda de receita, interrupção de atividade ou erros de prescrição, mesmo se avisados da possibilidade de tais danos.

### 4. Não se responsabilizam por interpretações regulatórias

O catálogo de substâncias, as regras dos 6 tipos de receituário e os mecanismos de validação implementados refletem o **entendimento do autor sobre a legislação vigente** no momento da implementação. Esses elementos **não constituem aconselhamento jurídico ou regulatório**. Mudanças na legislação podem tornar partes do software desatualizadas até que sejam corrigidas. O operador do sistema é responsável por monitorar a legislação aplicável.

### 5. Não se responsabilizam por uso em desacordo com a legislação local

O software foi desenhado para conformidade com a legislação brasileira federal. **O operador do sistema é o responsável por garantir conformidade regulatória na sua jurisdição** — incluindo regulamentações estaduais, municipais e setoriais (CFM, CRM, conselhos profissionais), bem como uso em jurisdições estrangeiras, que pode exigir adaptações específicas.

---

## Responsabilidade do operador

Quem instala, hospeda, opera ou integra o PicSaúde é o **operador do sistema** e assume integralmente:

- **Conformidade com a LGPD** (Lei 13.709/2018) na qualidade de controlador de dados pessoais sensíveis (dados de saúde)
- Conformidade com normas sanitárias aplicáveis ao seu contexto operacional
- **Segurança da infraestrutura** onde o sistema é hospedado (servidores, banco de dados, certificados ICP-Brasil, chaves de criptografia)
- **Backup, disponibilidade e integridade** dos dados
- **Treinamento** dos profissionais que utilizam o sistema
- Auditoria interna periódica de conformidade
- Notificação de incidentes de segurança às autoridades competentes (ANPD, CFM, CRM, conforme aplicável)

A obrigação contratual de proteção de dados está descrita em `DATA-PROTECTION.md`.

---

## Uso acadêmico e de pesquisa

Em ambiente acadêmico ou de pesquisa, o software pode ser usado livremente nos termos da AGPL-3.0. Os pesquisadores são responsáveis por:

- Aprovação ética em **Comitê de Ética em Pesquisa (CEP)** e, quando aplicável, **INAEP**, sempre que dados reais de pacientes forem envolvidos
- Adequação ao Termo de Consentimento Livre e Esclarecido (TCLE) de cada participante
- Anonimização de dados antes da publicação de resultados
- Conformidade com as resoluções CNS 466/2012 e 510/2016 (pesquisa com seres humanos)

O titular não se responsabiliza por aprovações éticas, autorizações regulatórias ou consequências de seu eventual descumprimento.

---

## Foro

Eventuais disputas relacionadas a este disclaimer ou ao uso do software serão dirimidas no foro da Comarca de Recife/PE, salvo se contrato comercial específico (`COMMERCIAL-LICENSE.md`) estabelecer foro diverso.

---

## Vigência e atualização

Este disclaimer é válido para a versão atual do software e para todas as suas derivações. Atualizações deste documento são publicadas no repositório oficial do projeto e entram em vigor a partir da data do commit correspondente. O operador é responsável por acompanhar atualizações.

**Data desta versão:** 2026-05-06
