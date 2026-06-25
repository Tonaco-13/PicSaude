# Um Motor Regulatório Transparente e Explicável para a Indústria de Software em Saúde: Autorização Auditável de Prescrições Digitais

*Rascunho v2 — CBEB 2026 (Trabalho B, recorte "motor regulatório"). Português. Formato IEEE (artigo completo, 4–8 pp). Prazo de submissão 30/06/2026. Substitui o foco em APS do v1 por foco na indústria de software em saúde.*

> **Notas de redação (remover antes de submeter):**
> - Contribuição = **motor regulatório** apenas. A trilha imutável / cadeia de custódia aparecem como *substrato*, nunca como contribuição reivindicada. O argumento de auditabilidade + anti-mercantilização fica reservado ao paper de arquitetura (ICSA) — aqui só um ponteiro de uma linha.
> - Guardas de honestidade (narrativa canônica): assinatura/ICP-Brasil = *design declarado / trabalho em aberto* (nunca "validado"); bases de referência = *subconjunto MVP sintético*; avaliação = *conformidade executável*, não validação clínica de campo. Nunca escrever "descentralizado/blockchain" — o motor é *stateless e determinístico*.
> - `[TODO]` marca onde a equipe deve inserir dados reais (bloco de autores, consentimento/citação das entrevistas, contagem de testes, lista final de referências).

---

**Autores:** `[TODO: linha de autores — Bruno Henrique Aragão Konig; Nicole Leise Andrade Serra; Heloisa Pessoa Tseng; Fabiano Tonaco Borges; + coautores. Bloco de afiliação IEEE de 5 linhas por autor. Sem títulos (Dr./Prof.).]`

Afiliação: Universidade Federal de Pernambuco (UFPE), Recife, Brasil.

---

## Resumo

O software de saúde codifica, de forma crescente, regras clínicas e regulatórias críticas — classes de substâncias controladas, exigências de assinatura, elegibilidade do prescritor — mas tipicamente as embute em lógica opaca, específica de cada fornecedor, que nem o profissional nem um auditor conseguem inspecionar. No caso das prescrições digitais, o modelo dominante de documento PDF estático agrava o quadro: não oferece autorização verificável por máquina, não explica quais regras foram aplicadas e não garante rastreabilidade do que ocorre com o documento. Apresentamos um motor regulatório transparente e explicável, concebido como componente de referência aberto para a indústria de software em saúde. O motor é stateless e determinístico: aplica seis camadas independentes de validação — estrutural, integridade, conformidade com o conselho profissional (Resolução CFM 2.299/2021), metadados de assinatura, verificação de certificado e cruzamento de identidade do prescritor contra o cadastro nacional de estabelecimentos de saúde (CNES) — e cada verificação devolve uma justificativa estruturada e legível, em vez de um veredito opaco. A terminologia clínica (medicamentos, diagnósticos, exames) é resolvida por um pipeline determinístico exato–alias–aproximado com limiares defensivos que expõem correspondências de baixa confiança como alertas explícitos. Instanciamos o motor no PicSaúde, uma implementação de referência aberta sobre dados sintéticos, e o avaliamos por conformidade executável sobre suítes de cenários alinhadas à regulação farmacêutica brasileira. Posicionamos o sistema como implementação de referência auditável, não como plataforma clínica em produção, e declaramos seus limites em aberto, incluindo a assinatura ICP-Brasil ponta a ponta.

*Palavras-chave—* prescrição digital; apoio à decisão clínica; validação explicável; conformidade regulatória; engenharia de software em saúde; informática em saúde

---

## I. Introdução

`[Parágrafo 1 — área ampla]` O software ocupou o centro da prestação de cuidados: prescrever, dispensar, laudar e auditar são hoje, na prática, operações mediadas por sistemas. Com isso, regras clínicas e regulatórias que antes viviam em normas e no julgamento profissional passaram a ser *codificadas* — e a forma como a indústria de software em saúde as codifica determina se elas podem ser verificadas, auditadas e confiáveis.

`[Parágrafo 2 — a lacuna]` Predomina, porém, um anti-padrão: cada fornecedor reimplementa as mesmas regras (classes de controle especial, exigências de assinatura, elegibilidade do prescritor) dentro de lógica de aplicação fechada, não inspecionável e não portável. Reguladores não conseguem auditar a regra que de fato roda; integradores não conseguem verificá-la; e a regra pode derivar silenciosamente da norma. No caso específico da prescrição, o modelo de PDF assinado estático reproduz o papel como artefato: não há autorização verificável por máquina (o prescritor estava habilitado a prescrever isto?), não há explicação de quais regras foram aplicadas, nem rastreabilidade embutida. Duas consequências concretas decorrem: o mesmo PDF pode ser apresentado em várias farmácias, viabilizando dispensação duplicada de controlados; e as regras que deveriam governar a prescrição ficam invisíveis ao profissional e ao auditor. Entrevistas semiestruturadas com profissionais de saúde `[TODO: formalizar — Danilo (UBS); Bianca Carvalho de Assis, médica de família, USF+ Vila Arraes]` confirmaram a dor concreta: risco de documento duplicado por compartilhamento de PDF e fragmentação persistente entre sistemas que não se comunicam.

`[Parágrafo 3 — proposta]` Propomos tratar a lacuna de *autorização explicável* com um motor regulatório que valida a prescrição no momento da emissão e no ato da dispensação, operando sobre uma trilha imutável de eventos. O motor é transparente por construção: cada decisão é decomposta em verificações independentes, e cada verificação devolve uma justificativa estruturada. Ele é concebido não como funcionalidade de um produto fechado, mas como **componente de referência aberto** que a indústria pode inspecionar e adotar. É instanciado no PicSaúde, implementação de referência que roda integralmente sobre dados sintéticos. Posicionamo-lo explicitamente como implementação de referência auditável — não plataforma clínica em produção — e declaramos seus limites em aberto.

**Objetivos.**

- Tornar a *autorização* da prescrição verificável por máquina e *explicável*, em vez de implícita num documento estático.
- Alinhar as regras de validação à regulação farmacêutica brasileira vigente, de forma inspecionável.
- Resolver a terminologia clínica de modo robusto, expondo a incerteza como alertas explícitos e auditáveis.

**Contribuições.**

- Um **motor de validação em seis camadas**, stateless e determinístico, no qual cada verificação devolve uma justificativa estruturada e legível, tornando a decisão de autorização auditável em vez de opaca.
- Uma **validação de identidade do prescritor por nome** contra o cadastro nacional CNES (não pelo número de CPF), ancorada em uma string de identidade imutável, com falhas graduadas (dura/leve).
- Um **pipeline de resolução de terminologia explicável** (exato → alias → aproximado) com limiares defensivos e alertas estruturados de baixa confiança, incluindo uma correção de projeto motivada por falsos positivos.
- Uma **implementação de referência aberta** sobre dados sintéticos, avaliada por conformidade executável contra cenários alinhados à norma.

`[Parágrafo de organização]` A Seção II revisa o contexto regulatório e os trabalhos relacionados. A Seção III descreve o motor. A Seção IV reporta a avaliação por conformidade. A Seção V discute limitações e a Seção VI conclui.

## II. Contexto e Trabalhos Relacionados

`[TODO: expandir em comparação crítica; mirar ~10–15 referências reais com DOI.]`

**Contexto regulatório.** A prescrição digital brasileira é regida pela Resolução CFM 2.299/2021 (requisitos e níveis de assinatura) e por um regime de controle em adensamento: Portaria SVS/MS 344/1998 e suas listas, RDC Anvisa 471/2021 (retinoides sistêmicos) e, mais recentemente, a RDC Anvisa 1.000/2025, que institui o Sistema Nacional de Controle de Receituários (SNCR), com horizonte de conformidade em 2026. A assinatura eletrônica qualificada apoia-se na infraestrutura de chaves públicas ICP-Brasil. Essa densidade normativa é exatamente o que um PDF opaco não expressa e o que um motor explicável pode tornar verificável — um problema de engenharia que recai sobre toda a indústria, não sobre um único produto.

**Apoio à decisão clínica explicável.** `[TODO: 3–5 refs — sistemas baseados em regras vs. aprendizado de máquina; o caso da transparência/explicabilidade em software de saúde crítico; fadiga de alertas e o valor de alertas justificados.]`

**Resolução de terminologia.** `[TODO: 2–3 refs — casamento aproximado de strings em normalização de terminologia clínica; métodos da família Levenshtein/rapidfuzz; risco de falsos positivos.]`

**Registros clínicos baseados em eventos (substrato).** O motor opera sobre uma trilha de eventos append-only; o event sourcing como substrato de registros rastreáveis — e as propriedades de auditabilidade do sistema — são tratados em um trabalho companheiro sobre arquitetura. Aqui é pano de fundo, não contribuição. `[TODO: 1–2 refs sobre event sourcing / logs de auditoria imutáveis.]`

## III. Materiais e Métodos

### A. Contexto do sistema

O PicSaúde modela documentos clínicos como *objetos sanitários* com identificador global, máquina de estados explícita, livro-razão de eventos append-only e cadeia de custódia. Os objetos são imutáveis após a emissão; correções e renovações são novos objetos derivados. O motor regulatório aqui descrito consome esse substrato sem modificá-lo: lê a prescrição e sua representação canônica e devolve um relatório de validação. A implementação é em Python (FastAPI, SQLAlchemy); todos os dados são sintéticos e o sistema opera em modo de demonstração imposto pela arquitetura.

### B. O motor de validação em seis camadas

Uma prescrição é validada por seis camadas independentes; cada camada produz um conjunto de verificações, e cada verificação é um registro da forma `(ok, detalhe, aplicável)`, em que *detalhe* é uma justificativa legível e *aplicável* marca verificações que não se aplicam a um dado tipo de prescrição (p.ex., integridade em emissão exclusivamente física). O motor é stateless e determinístico: entradas idênticas produzem relatórios idênticos.

1. **Estrutural** — existência da prescrição, estados reconhecidos de prescrição e itens, presença de ao menos um item.
2. **Integridade** — recomputação do hash SHA-256 do *documento canônico* e comparação com o hash armazenado (apenas emissões digitais).
3. **Conformidade com o conselho profissional (CFM 2.299/2021)** — identificador real do paciente (não sentinela), campos obrigatórios por item (quantidade, unidade, posologia) e modo de assinatura admissível pela norma.
4. **Metadados de assinatura** — presença e coerência dos registros de assinatura e de seu hash de documento.
5. **Verificação de certificado (ICP-Brasil)** — *design declarado; limite em aberto.* Esta camada é especificada, mas ainda não integrada ponta a ponta (ver Seção V); é reportada de forma transparente, não afirmada como funcional.
6. **Identidade do prescritor (cruzamento CNES)** — descrita em §III-D.

O relatório agrega as camadas em um resultado geral graduado (p.ex., válido estrutural, válido com identidade CNES confirmada, inválido por falha dura), tornando explícito o *nível* de garantia em vez de reduzir a validação a um único bit passa/não-passa.

### C. Resolução de terminologia explicável

Entradas em texto livre de medicamento, diagnóstico (CID-10) e exame são resolvidas por um pipeline determinístico: (i) casamento exato sobre índice normalizado; (ii) casamento por alias; (iii) casamento aproximado por escore difuso ponderado (`rapidfuzz`) acima de um limiar; caso contrário (iv) sem correspondência. Correspondências aproximadas nunca são aplicadas silenciosamente — retornam como alertas estruturados pedindo confirmação do prescritor.

Os limiares são deliberadamente conservadores. Reportamos uma correção concreta de projeto: o limiar difuso de medicamentos foi elevado de 0,82 para 0,88 após tokens curtos de dosagem (p.ex., "N mg") gerarem correspondências espúrias de alta confiança, e adicionou-se uma guarda de comprimento mínimo para consultas curtas. Isso ilustra a postura do motor: quando a resolução de terminologia é incerta, o sistema torna a incerteza visível, em vez de escondê-la sob uma correspondência aparentemente confiante.

### D. Identidade do prescritor por nome, não por CPF

A elegibilidade do prescritor é verificada contra um *snapshot* do cadastro nacional CNES **por nome**, não pelo número de CPF. A identidade é ancorada em uma string de validação imutável composta pelo identificador derivado do certificado, pelo registro no conselho profissional com a respectiva UF e pelo cartão nacional de saúde; o CPF do prescritor é extraído localmente e nunca é transmitido ao servidor. A camada CNES realiza verificações graduadas: consistência de nome (similaridade de strings acima de um limiar fixo), código de ocupação prescritiva, conselho profissional habilitado e ao menos um vínculo institucional ativo. Uma divergência de nome/ocupação/conselho é falha *dura* (possível uso indevido de credenciais de terceiro); uma ausência no cadastro é falha *leve*, atribuída à defasagem do snapshot, não ao prescritor.

### E. Agrupamento regulatório de controlados

O motor mapeia medicamentos a grupos de controle derivados da Portaria 344/1998, da RDC 471/2021 e do regime do SNCR (RDC 1.000/2025), determinando número de vias, retenção e tratamento de controle especial. Esses mapeamentos são expressos em código inspecionável, não em configuração oculta, em coerência com o objetivo de transparência.

### F. Bases de referência (MVP, sintéticas)

As bases de referência atuais são deliberadamente subconjuntos MVP, não as tabelas oficiais completas: 81 medicamentos (tabela curada de formulário), um subconjunto de CID-10 da ordem de 240 códigos (reportado como cobrindo a maioria dos casos de atenção primária) e 35 procedimentos diagnósticos. Reportamos esses tamanhos honestamente; a expansão e a sincronização com fontes oficiais são trabalho futuro.

## IV. Resultados: Avaliação por Conformidade Executável

Avaliamos o motor por *conformidade executável*, não por métricas clínicas de campo: o sistema não possui classificador e não fazemos alegação de acurácia/F1. A validação consiste em suítes de cenários que exercitam cada camada e o agrupamento regulatório sobre prescrições sintéticas `[TODO: reportar contagens/arquivos exatos de teste — suíte de receituários, suíte de validação, suíte de catálogo CNES; indicar status de aprovação a partir de uma execução limpa].`

`[Tabela I — TODO]` *Cenário → verificações exercitadas → relatório esperado → status do teste.* Linhas sugeridas: emissão digital com metadados de assinatura válidos; emissão exclusivamente física (verificações de integridade marcadas como não aplicáveis); violação de campo obrigatório CFM; agrupamento de controlado; divergência de nome CNES (falha dura); ausência no cadastro CNES (falha leve); correspondência de terminologia de baixa confiança (alerta estruturado).

O que isso estabelece e o que não estabelece: a suíte demonstra que as decisões do motor são *reprodutíveis, em camadas e individualmente justificadas*, e que os agrupamentos regulatórios se comportam conforme especificado. **Não** estabelece eficácia clínica nem segurança em uso real, o que exigiria estudo de campo.

## V. Discussão e Limitações

O valor do motor é tornar a autorização inspecionável: um auditor ou profissional pode ver não apenas *que* uma prescrição foi aceita ou recusada, mas *por quê*, verificação a verificação. Para a indústria de software em saúde, isso desloca a regra regulatória de uma caixa-preta por fornecedor para um componente de referência verificável e reutilizável. Vários limites são declarados explicitamente e por projeto.

- **A assinatura ICP-Brasil ponta a ponta é design declarado, não validada.** A integridade da assinatura é ancorada no hash SHA-256 do documento canônico, mas a serialização canônica entre ambientes e a verificação completa da cadeia de certificados permanecem em aberto; por isso reportamos a camada de certificado como especificada-mas-não-integrada, não como funcional.
- **As bases de referência são subconjuntos MVP** sobre dados sintéticos; nenhum dado real de paciente ou prescritor é usado, e o sistema opera em modo de demonstração imposto.
- **Sem validação clínica de campo.** A avaliação é por conformidade.
- As propriedades mais amplas de **auditabilidade e de resistência à mercantilização** — decorrentes da trilha imutável e da ausência de egressão em massa — são objeto de um trabalho companheiro sobre arquitetura e ficam, intencionalmente, fora do escopo aqui.

## VI. Conclusão

Apresentamos um motor regulatório transparente e explicável que autoriza prescrições digitais sobre uma trilha imutável de eventos, decompondo cada decisão em verificações independentemente justificadas e alinhadas à regulação farmacêutica brasileira, verificando a identidade do prescritor por nome contra o cadastro nacional e resolvendo terminologia clínica com limiares defensivos que expõem a incerteza. Instanciado em uma implementação de referência aberta sobre dados sintéticos e avaliado por conformidade executável, ele mostra que a autorização de prescrições pode ser tornada auditável em vez de opaca — um padrão reutilizável para a indústria de software em saúde. Trabalho futuro inclui a integração da assinatura ICP-Brasil ponta a ponta, a expansão e sincronização das bases de referência com fontes oficiais e um piloto de campo em unidade municipal de atenção primária.

## Referências

`[TODO: completar em estilo numérico IEEE — nomes completos de autores (et al. apenas para 6+), DOIs/URLs. Âncoras iniciais abaixo.]`

- [ ] CFM, Resolução nº 2.299/2021 (prescrição digital).
- [ ] Anvisa, RDC nº 1.000/2025 (SNCR — Sistema Nacional de Controle de Receituários).
- [ ] Brasil, Portaria SVS/MS nº 344/1998 (substâncias sob controle especial).
- [ ] Anvisa, RDC nº 471/2021 (retinoides sistêmicos).
- [ ] ICP-Brasil / MP 2.200-2/2001 (infraestrutura de chaves públicas).
- [ ] Lei nº 13.787/2018 (digitalização e guarda de prontuário).
- [ ] Biblioteca rapidfuzz — casamento aproximado de strings `[citar software]`.
- [ ] `[3–5 refs]` apoio à decisão clínica explicável / transparência em software de saúde crítico.
- [ ] `[2–3 refs]` casamento aproximado de strings para normalização de terminologia clínica.
- [ ] `[1–2 refs]` event sourcing / logs de auditoria imutáveis (substrato).
