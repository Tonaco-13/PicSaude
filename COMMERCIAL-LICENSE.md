# Licença Comercial PicSaúde (código fechado)

> **Aviso:** este documento é um *term sheet* — modelo de termos e condições para licenciamento comercial. **Não é, por si só, contrato vinculante.** O licenciamento comercial efetivo exige contrato formal assinado por ambas as partes, com qualificação completa do licenciado, cláusulas de adesão e termos negociados em documento separado.

---

## Titular dos direitos

| Campo | Dado |
|---|---|
| **Nome** | Fabiano Tonaco Borges |
| **CPF** | *(a ser preenchido em contrato formal)* |
| **E-mail** | fabianotonaco@gmail.com |
| **Endereço** | *(a ser preenchido em contrato formal)* |

**Identificadores oficiais da propriedade intelectual:**

- **Registro de Programa de Computador no INPI:** processo **BR 51 2026 002267-3** (RPI nº 2883, 07/04/2026), título oficial *"PicSaúde: Plataforma de Gestão de Objetos Sanitários com Ledger e Máquina de Estados"*
- **Pedido de Registro de Marca — Classe NCL(13) 9 (software, hardware, aplicativos):** processo INPI **943014573**, depositado em 12/03/2026
- **Pedido de Registro de Marca — Classe NCL(13) 44 (assistência médica, telemedicina, serviços de saúde):** processo INPI **943014883**, depositado em 12/03/2026

---

## Quem precisa desta licença

**Apenas quem deseja integrar o motor PicSaúde em software proprietário (código fechado) sem cumprir a obrigação da AGPL-3.0 de publicar o código-fonte das derivações que interajam com usuários via rede.**

Se a sua organização **publica o código-fonte** do sistema derivado sob AGPL-3.0, **não precisa desta licença comercial** — use a `LICENSE` (AGPL-3.0) gratuitamente, respeitando suas obrigações.

---

## Modalidades de preço

O licenciado escolhe entre uma das duas opções abaixo, declarada em contrato:

### Opção A — Licença anual fixa

| Porte do licenciado | Valor anual |
|---|---|
| Startup ou pequena empresa (até 50 funcionários) | **R$ 15.000,00/ano** |
| Média empresa (51 a 500 funcionários) | **R$ 50.000,00/ano** |
| Grande empresa (acima de 500 funcionários) | **Sob consulta** |

O porte é declarado no momento da contratação e revisado anualmente. Mudança de porte durante a vigência implica reajuste proporcional.

### Opção B — Royalties sobre faturamento

**1% (um por cento) do faturamento bruto anual da empresa licenciada** (não apenas do produto que integra o motor), sujeito às seguintes condições, todas cumulativas:

#### B.1 Piso

**R$ 15.000,00 por ano**, devido independentemente do faturamento — inclusive em caso de faturamento zero ou negativo no exercício. O piso cobre o custo administrativo do titular para gerenciar a licença, alinha-se ao valor mínimo da Opção A (pequena empresa) e impede que a Opção B fique abaixo do custo operacional de manutenção do contrato.

#### B.2 Teto

**R$ 600.000,00 por ano**. Faturamento bruto anual acima de **R$ 60.000.000,00** dispara cláusula obrigatória de **"Sob consulta"** — o licenciado deve contatar o titular para acordo específico antes do início da vigência. Esta cláusula impede que royalties sobre faturamento muito alto inviabilizem comercialmente a relação e força negociação direta com grandes empresas.

#### B.3 Sem isenção

**Não há isenção por baixo faturamento.** Empresa que não puder ou não quiser pagar o piso desta Opção B deve adotar a AGPL-3.0 (`LICENSE`), que é gratuita e exige apenas a publicação do código-fonte das derivações que interajam com usuários via rede.

#### B.4 Pagamento trimestral

Pagamento em **4 parcelas trimestrais iguais**, vencendo no último dia útil de cada trimestre civil (março, junho, setembro, dezembro). Cada parcela corresponde a 25% do royalty estimado para o ano, calculado com base no faturamento do exercício anterior. **Ajuste anual em março**, com base no faturamento real do exercício encerrado, gerando crédito ou débito a ser compensado nas parcelas subsequentes.

#### B.5 Comprovação proporcional ao porte do licenciado

- **MEI, ME e EPP** (Lei Complementar 123/2006): apresentação da **DEFIS** (Declaração de Informações Socioeconômicas e Fiscais) do Simples Nacional, ou documento equivalente para o regime tributário aplicável
- **Demais empresas** (Lucro Presumido, Lucro Real, regimes especiais): apresentação de **DRE assinada por contador registrado no CRC**, acompanhada das demonstrações financeiras consolidadas do exercício

A documentação é entregue ao titular até **31 de março** de cada ano, referente ao exercício anterior. Atraso superior a 30 dias suspende automaticamente o licenciamento até regularização.

#### B.6 Auditoria periódica e direito de fiscalização

O titular reserva-se o direito de conduzir **auditoria técnica e contábil a cada 24 (vinte e quatro) meses**, com aviso prévio mínimo de **30 (trinta) dias**, em horário comercial, sem interromper a operação do licenciado. O escopo da auditoria abrange:

- Verificação do faturamento bruto declarado
- Verificação da integridade do `instance_id` (cláusula 4 abaixo)
- Verificação do cumprimento da política de proteção de dados (`DATA-PROTECTION.md`)

**Custo da auditoria:**

- **Do titular**, se a apuração confirmar o faturamento declarado ou identificar subdeclaração de até 5% (cinco por cento) do valor real
- **Do licenciado**, se a subdeclaração for superior a 5% do valor real apurado, acrescido de **juros de 1% ao mês** e **multa contratual de 10%** sobre a diferença, sem prejuízo de outras sanções civis cabíveis

#### B.7 Anti-arbitragem entre Opções A e B

A opção escolhida no contrato (A ou B) tem **permanência mínima de 24 (vinte e quatro) meses**. Migração entre opções está sujeita a:

- **Aviso prévio escrito de 90 (noventa) dias** ao titular
- **Apuração retroativa**: se a opção de destino teria gerado valor maior do que a opção de origem no período de permanência mínima, o licenciado paga a diferença integralmente no momento da migração, como condição da migração
- Migrações superiores a 1 (uma) a cada 36 (trinta e seis) meses configuram **comportamento abusivo** e dão ao titular direito de denúncia contratual com efeitos imediatos, sem multa rescisória ao licenciado

Esta cláusula impede que o licenciado migre oportunisticamente entre opções A e B conforme a conveniência momentânea.

---

## Cláusulas contratuais obrigatórias

As cláusulas abaixo são **inegociáveis** — fazem parte de qualquer contrato comercial PicSaúde, em qualquer modalidade de preço.

### 1. Atribuição "Powered by PicSaúde"

O licenciado deve exibir, em toda interface derivada visível ao usuário final, o texto **"Powered by PicSaúde"** ou **"Movido pelo PicSaúde"**, com hyperlink para `https://picsaude.com.br` (ou domínio sucessor indicado pelo titular). A marca gráfica oficial deve ser usada conforme guia de identidade visual fornecido pelo titular.

### 2. Proteção de dados

É **proibida a venda, comercialização, monetização, cessão ou transferência a terceiros** de dados de pacientes, prescritores, dispensadores ou prescrições processados por instâncias do PicSaúde — em qualquer modalidade, sob qualquer forma, sob qualquer pretexto. A violação desta cláusula:

- **Extingue a licença automática e irrevogavelmente**, sem necessidade de notificação prévia
- Configura infração à LGPD, sujeitando o licenciado às sanções do Art. 52
- Configura violação contratual sujeita a indenização por perdas e danos
- Está detalhada em `DATA-PROTECTION.md`

### 3. Marca

O licenciado **não adquire qualquer direito sobre a marca PicSaúde** (pedidos INPI 943014573 e 943014883). Uso comercial do nome, logotipo ou variantes em derivações não autorizadas é vedado e sujeito às sanções da Lei 9.279/96.

### 4. Marca d'água de rastreabilidade (`instance_id`)

O licenciado aceita a presença permanente do `instance_id` em metadados de prescrições, eventos do ledger e PDFs assinados, conforme `DATA-PROTECTION.md` §4. **Remoção, modificação ou ofuscação do `instance_id` extingue a licença automaticamente.**

### 5. Auditoria sob demanda

O licenciado aceita **auditoria técnica sob demanda do titular** para verificação de conformidade com a proteção de dados (cláusula 2) e com a integridade do `instance_id` (cláusula 4). A auditoria é realizada com aviso prévio mínimo de 15 dias, em horário comercial, sem interromper a operação. O custo da auditoria é do titular, salvo se houver não conformidade comprovada — neste caso, o custo é do licenciado.

### 6. Foro

Eventuais disputas são dirimidas no foro da **Comarca de Recife/PE**, com renúncia expressa a qualquer outro foro, por mais privilegiado que seja.

### 7. Vigência e renovação

Contrato com vigência de **12 (doze) meses**, com **renovação automática por iguais períodos**, salvo denúncia escrita de qualquer das partes com antecedência mínima de **60 (sessenta) dias** do término do período em curso.

### 8. Disclaimer

O titular não se responsabiliza por erros clínicos, diagnósticos, terapêuticos, regulatórios ou de prescrição decorrentes do uso do software, conforme `DISCLAIMER.md`. O licenciado, na qualidade de operador do sistema, assume integralmente as obrigações da LGPD como controlador de dados.

### 9. Sublicenciamento

A licença é **pessoal e intransferível**. O licenciado não pode sublicenciar, ceder, alugar ou transferir a terceiros os direitos concedidos, salvo mediante autorização prévia, expressa e por escrito do titular.

### 10. Conformidade regulatória

O licenciado é responsável por garantir que sua operação esteja em conformidade com a regulamentação setorial aplicável — Anvisa, conselhos profissionais (CFM, CRM, CRO, CRMV, CRBM), normas de telemedicina, normas locais. O titular fornece motor regulatório baseado no entendimento da legislação federal vigente; mudanças regulatórias subsequentes são responsabilidade do licenciado acompanhar.

---

## Direitos do licenciado

Sob esta licença comercial, o licenciado obtém:

- Direito de **integrar o motor PicSaúde em software proprietário** (código fechado) sem obrigação de publicar o código derivado
- Direito de **modificar o código** do motor para adequação ao seu produto, **mantendo as cláusulas obrigatórias acima** (notadamente as cláusulas 1, 4, 5)
- **Suporte técnico** conforme nível contratado (definido em contrato específico)
- **Atualizações de versão** do motor durante a vigência, conforme cronograma público
- Direito de **uso da marca "Powered by PicSaúde"** exclusivamente nos termos da cláusula 1

---

## O que o licenciado **não** obtém

- Direitos sobre o código-fonte original do PicSaúde (que permanece de titularidade exclusiva de Fabiano Tonaco Borges)
- Direitos sobre a marca PicSaúde
- Direito de redistribuir o motor a terceiros
- Direito de operar o software como provedor de SaaS multi-tenant para terceiros não licenciados (este uso exige contrato específico)

---

## Contato para licenciamento

Negociações e propostas de licenciamento comercial:

**E-mail:** `fabianotonaco@gmail.com`
**Assunto sugerido:** *Proposta de licenciamento comercial PicSaúde — [nome da organização]*

Por favor, inclua na proposta:

1. Razão social e CNPJ da empresa interessada
2. Descrição sumária do produto ou serviço que integrará o motor
3. Modalidade de preço pretendida (Opção A ou B)
4. Estimativa de porte (número de funcionários) ou faturamento bruto anual projetado
5. Prazo desejado para início da operação

---

## Base legal

Esta licença comercial fundamenta-se em:

- **Lei 9.609/1998** — proteção da propriedade intelectual de programa de computador
- **Lei 9.279/1996** — propriedade industrial (marcas e patentes)
- **Lei 9.610/1998** — direitos autorais
- **Lei 13.709/2018 (LGPD)** — proteção de dados pessoais
- **Lei 10.406/2002 (Código Civil)** — relações contratuais
- **Registro INPI BR 51 2026 002267-3** — Programa de Computador
- **Pedidos INPI 943014573 e 943014883** — Marca

---

**Data desta versão:** 2026-05-06
