# Regras Sanitárias Transparentes sobre uma Trilha Imutável de Eventos: Uma Arquitetura de Referência Auditável para Software de Saúde

*Rascunho v3 — CBEB 2026 (paper do sistema; os dois motores). Português. Formato IEEE (artigo completo, 4–8 pp). Prazo 30/06/2026. Substitui v1/v2: agora cobre os dois motores ancorados na tese central. A trilha do Biochallenge (equipe do Bruno) corre em paralelo.*

> **Notas de redação (remover antes de submeter):**
> - Este é o **paper do sistema**: motor de circulação (a trilha imutável) + motor regulatório (as regras transparentes), realizando a tese central.
> - O argumento **anti-mercantilização entra como COROLÁRIO** (afirmado, compacto). O desenvolvimento arquitetural aprofundado — defesa em três camadas, propriedade "sem egressão" — fica reservado ao trabalho companheiro (ICSA), que **cita este paper**. Não esmiuçar aqui, para preservar ineditismo.
> - Guardas de honestidade (narrativa canônica): assinatura/ICP-Brasil = *design declarado / em aberto* (nunca "validado"); bases = *subconjunto MVP sintético*; avaliação = *conformidade executável*, não validação de campo. Nunca "descentralizado/blockchain" — *centralizado, event-sourced internamente, stateless, determinístico*.
> - `[TODO]` = dados a inserir (autores/coautores, entrevistas, contagens de teste, referências).

---

**Autores:** `[TODO: inserir depois — linha de autores + bloco de afiliação IEEE de 5 linhas por autor, sem títulos.]`

Afiliação: Universidade Federal de Pernambuco (UFPE), Recife, Brasil.

---

## Resumo

O software de saúde tornou-se o meio pelo qual documentos clínicos são emitidos, transferidos e dispensados — e pelo qual regras clínicas e regulatórias são, na prática, aplicadas. Dois requisitos críticos de confiança, porém, costumam ser frágeis: a *rastreabilidade* do que aconteceu e a *explicabilidade* das regras que governaram cada ato. No modelo dominante de prescrição como PDF estático, ambos faltam; e a regra regulatória, quando existe, vive embutida em lógica opaca específica de cada fornecedor. Apresentamos uma arquitetura de referência na qual a auditabilidade é estrutural, ancorada na tese de que **regras sanitárias transparentes operando sobre uma trilha imutável de eventos produzem fluxos auditáveis por construção**. A arquitetura combina dois motores: um *motor de circulação* — máquina de estados sobre um livro-razão de eventos append-only, com cadeia de custódia explícita e suporte a dispensação parcial — e um *motor regulatório* de regras explícitas, verificáveis e explicáveis, no qual cada decisão de autorização é decomposta em verificações independentes, cada uma com justificativa estruturada e legível. Objetos clínicos são imutáveis após a emissão: correções e renovações são novos objetos derivados. Instanciamos a arquitetura no PicSaúde, implementação de referência aberta sobre dados sintéticos, e a avaliamos por conformidade executável sobre cenários alinhados à regulação farmacêutica brasileira. Posicionamo-la como implementação de referência auditável — não plataforma clínica em produção — e declaramos seus limites em aberto, incluindo a assinatura ICP-Brasil ponta a ponta.

*Palavras-chave—* arquitetura de software em saúde; trilha de auditoria imutável; prescrição digital; apoio à decisão clínica explicável; conformidade regulatória; informática em saúde

---

## I. Introdução

O software tornou-se o meio pelo qual os atos centrais do cuidado acontecem: prescrever, dispensar, laudar e auditar são, hoje, operações mediadas por sistemas. Com essa transição, regras clínicas e regulatórias que antes viviam em normas e no julgamento profissional passaram a ser *codificadas* — e a maneira como a indústria de software em saúde as codifica determina se elas podem ser verificadas, auditadas e confiadas. A prescrição é o caso exemplar: simultaneamente instrução clínica, documento legal e evento que precisa ser rastreável para farmacovigilância e auditoria.

Predominam, contudo, dois anti-padrões complementares. Primeiro, a prescrição digital reproduz o papel como artefato estático — um PDF assinado, trafegado por e-mail ou aplicativos de mensagem — sem autorização verificável por máquina, sem explicação das regras aplicadas e sem rastreabilidade embutida; a mesma cópia pode ser apresentada em farmácias distintas, viabilizando a dispensação duplicada de medicamentos controlados. Segundo, quando as regras regulatórias são de fato codificadas, ficam presas em lógica de aplicação fechada, específica de cada fornecedor, que nem o profissional nem o auditor conseguem inspecionar e que pode divergir silenciosamente da norma. O resultado é uma carência estrutural: a auditabilidade, quando existe, é acoplada *a posteriori* — por logs e relatórios — em vez de garantida pela forma do sistema. Entrevistas semiestruturadas com profissionais da atenção primária `[TODO: formalizar — Danilo (UBS); Bianca Carvalho de Assis, médica de família]` confirmaram a expressão concreta do problema: risco de documento duplicado por compartilhamento de PDF e fragmentação persistente entre sistemas que não se comunicam.

Este trabalho propõe tornar a auditabilidade uma propriedade *estrutural* do sistema, e não um anexo posterior. A tese é que **regras sanitárias transparentes operando sobre uma trilha imutável de eventos produzem fluxos de saúde digital auditáveis por construção**. A arquitetura que a realiza acopla dois motores: um *motor de circulação*, que garante a trilha imutável (máquina de estados, livro-razão de eventos *append-only* e cadeia de custódia explícita), e um *motor regulatório*, que garante as regras transparentes (validação explícita, verificável e explicável, decomposta em verificações justificadas). Ela é instanciada no PicSaúde, uma implementação de referência aberta que opera integralmente sobre dados sintéticos. Posicionamo-la explicitamente como implementação de referência auditável — não plataforma clínica em produção — e declaramos seus limites em aberto.

**Objetivos.** O trabalho persegue três objetivos, formulados de modo a serem demonstráveis empiricamente: (i) tornar a auditabilidade uma propriedade *estrutural* — isto é, garantir que todo ato relevante seja um evento numa trilha imutável e que o estado do sistema seja integralmente reconstruível a partir dela; (ii) tornar a autorização da prescrição verificável por máquina e *explicável*, alinhada à regulação farmacêutica brasileira de forma inspecionável; e (iii) preservar, sob carga e sob estímulo adversarial, os invariantes do domínio — imutabilidade após emissão, soma dispensada não superior à prescrita e integridade do documento.

**Contribuições.** (1) Uma arquitetura de referência que acopla motor de circulação e motor regulatório, tornando a auditabilidade estrutural; (2) um modelo generalizável de objetos sanitários sob contrato comum (identidade, estados, ledger, custódia); (3) um motor de validação em seis camadas com justificativa estruturada por verificação, identidade do prescritor por nome e resolução de terminologia explicável; e (4) uma implementação de referência aberta, sobre dados sintéticos, avaliada por um experimento de conformidade reprodutível.

A Seção II revisa o contexto regulatório e os trabalhos relacionados; a III descreve a arquitetura e os dois motores; a IV apresenta o experimento de auditabilidade — objetivos, método e resultados; a V discute o corolário de auditabilidade e os limites; e a VI conclui.

## II. Contexto e Trabalhos Relacionados

`[TODO: comparação crítica; mirar ~12–15 referências reais com DOI.]`

**Contexto regulatório.** A prescrição digital brasileira é regida pela Resolução CFM 2.299/2021 e por um regime de controle em adensamento: Portaria SVS/MS 344/1998, RDC Anvisa 471/2021 e, mais recentemente, a RDC Anvisa 1.000/2025, que institui o Sistema Nacional de Controle de Receituários (SNCR), com horizonte de conformidade em 2026. A assinatura qualificada apoia-se na ICP-Brasil. Essa densidade normativa é o que um PDF opaco não expressa e o que uma arquitetura auditável pode tornar verificável.

**Trilhas de auditoria imutáveis e event sourcing.** `[TODO: 2–3 refs — event sourcing, logs append-only, registros clínicos rastreáveis. Posicionar event sourcing como técnica conhecida; nossa contribuição é o contrato integrado de objeto sanitário e seu acoplamento ao motor regulatório, não o event sourcing em si.]`

**Apoio à decisão clínica explicável.** `[TODO: 3–5 refs — regras vs. aprendizado de máquina; transparência/explicabilidade em software de saúde crítico; fadiga de alertas.]`

**Resolução de terminologia.** `[TODO: 2–3 refs — casamento aproximado de strings; risco de falsos positivos.]`

## III. Arquitetura e Métodos

A implementação é em Python (FastAPI, SQLAlchemy), com persistência relacional **centralizada**; todos os dados são sintéticos e o sistema opera em modo de demonstração imposto pela arquitetura. O código é aberto.

### A. Objetos sanitários: um contrato comum

Todo documento clínico é modelado como um *objeto sanitário* com quatro elementos: identidade global (UUID), máquina de estados explícita, livro-razão de eventos append-only e cadeia de custódia. Prescrições, laudos e pedidos de exame compartilham esse contrato, em vez de cada tipo ter lógica própria. Objetos são **imutáveis após a emissão**: correção, renovação ou ajuste geram um novo objeto derivado que aponta para o anterior; nunca há edição destrutiva.

### B. Motor de circulação (a trilha imutável)

O motor de circulação garante a metade "trilha imutável" da tese.

- **Máquina de estados.** Fluxo digital (p.ex., *pendente → transferida ao paciente → em custódia → parcial/totalmente dispensada*) e fluxo físico (*impressa → encerrada localmente*) são explícitos e disjuntos; estados terminais são declarados. A semântica separa revogação clínica (cancelamento) de emissão exclusivamente física, evitando ambiguidade.
- **Livro-razão de eventos.** Todo ato relevante (emissão, impressão, transferência de custódia, dispensação total/parcial, devolução) é um *insert* numa tabela de eventos append-only; não há caminho de `UPDATE`/`DELETE`. Essa é a trilha imutável.
- **Cadeia de custódia.** A posse do objeto a cada instante é registrada e transferível (prescritor → paciente → dispensador, e devoluções), com granularidade por prescrição ou por item.
- **Dispensação parcial.** Não conseguir retirar um item não invalida a prescrição: o item volta a *pendente* e pode ser dispensado em outra farmácia, com a invariante de que a soma dispensada nunca excede a quantidade prescrita.

### C. Motor regulatório (as regras transparentes)

O motor regulatório garante a metade "regras transparentes". É stateless e determinístico; cada verificação é um registro `(ok, detalhe, aplicável)`, em que *detalhe* é uma justificativa legível. Valida a prescrição em **seis camadas independentes**:

1. **Estrutural** — existência, estados reconhecidos, presença de itens.
2. **Integridade** — recomputa o hash SHA-256 do *documento canônico* e compara com o armazenado (emissões digitais).
3. **Conformidade CFM 2.299/2021** — identificador real do paciente, campos obrigatórios por item, modo de assinatura admissível.
4. **Metadados de assinatura** — presença e coerência dos registros e seu hash.
5. **Verificação de certificado (ICP-Brasil)** — *design declarado; limite em aberto* (ver Seção V); reportada como especificada-mas-não-integrada, não como funcional.
6. **Identidade do prescritor (CNES)** — §III-E.

O relatório agrega as camadas em um resultado **graduado** (válido estrutural, válido com identidade CNES confirmada, inválido por falha dura), tornando o *nível* de garantia explícito.

**Resolução de terminologia explicável.** Medicamentos, diagnósticos (CID-10) e exames são resolvidos por pipeline determinístico exato → alias → aproximado (`rapidfuzz`, escore ponderado acima de limiar); correspondências aproximadas retornam como **alertas estruturados** pedindo confirmação. Reportamos uma correção concreta: o limiar difuso de medicamentos foi elevado de 0,82 para 0,88 após tokens curtos de dosagem ("N mg") gerarem falsos positivos de alta confiança, com guarda adicional de comprimento mínimo — a postura é tornar a incerteza *visível*, não escondê-la.

### D. Identidade do prescritor por nome, não por CPF

A elegibilidade é verificada contra um *snapshot* do cadastro nacional CNES **por nome**, não por CPF. A identidade é ancorada em uma string de validação imutável (identificador derivado do certificado + registro no conselho com UF + cartão nacional de saúde); o CPF do prescritor é extraído localmente e **nunca transmitido ao servidor**. As verificações são graduadas (similaridade de nome acima de limiar fixo, ocupação prescritiva, conselho habilitado, vínculo institucional ativo): divergência de nome/ocupação/conselho é falha *dura*; ausência no cadastro é falha *leve*, atribuída à defasagem do snapshot.

### E. Documento canônico e assinatura (design declarado)

Para assinatura e integridade, monta-se uma representação canônica determinística da prescrição (ordem fixa de campos, serialização compacta) sobre a qual se calcula o hash SHA-256. O fluxo de assinatura ICP-Brasil é descrito como contribuição de **design**; a verificação completa de cadeia de certificados e a serialização canônica idêntica entre ambientes (cliente/servidor) permanecem em aberto (Seção V).

## IV. Experimento: Auditabilidade por Construção sobre Dados Sintéticos

Avaliamos *propriedades de sistema e de engenharia* sobre dados sintéticos — não eficácia clínica nem acurácia diagnóstica. O experimento (E1) exercita diretamente a lógica que *impõe* os invariantes do sistema: o contrato da máquina de estados e o mecanismo de documento canônico/integridade. O corpus é gerado com semente fixa (reprodutível) e o experimento é executado contra os módulos de domínio reais da implementação de referência.

> **Escopo (declarado).** Os resultados abaixo são de uma execução **preliminar de nível-domínio**: exercitam a lógica de domínio que garante os invariantes, não o stack completo de persistência/endpoints. A execução **autoritativa** — corpus gerado pelos endpoints oficiais e *replay* do ledger persistido — é trabalho de engenharia no ambiente de dev e será reportada na versão final. `[TODO: substituir/complementar com a execução full-stack.]`

**Objetivo do experimento.** Verificar empiricamente que a auditabilidade do sistema é *estrutural*, operacionalizada em quatro propriedades mensuráveis: (a) a máquina de estados é total e fechada — nenhuma transição ilegal é aceita; (b) o estado é integralmente reconstruível a partir da trilha de eventos (*replay*); (c) a invariante de dispensação parcial (Σ dispensado ≤ prescrito) nunca é violada; e (d) o documento canônico é determinístico e detecta adulteração de conteúdo.

**Geração de dados.** O corpus é sintético e gerado com semente fixa (reprodutível), sem qualquer dado real de paciente ou prescritor. Cada prescrição recebe de um a quatro itens amostrados de um formulário sintético, com modos de emissão (digital/físico) e tipos (nova/correção/renovação) variados.

**Medições.** Para o *motor de circulação*: (i) enumeração de fechamento sobre o produto cartesiano completo de estados — a transição só é aceita se está declarada na tabela de transições; (ii) 5.000 percursos legais aleatórios, da emissão a um estado terminal, com *replay* (reconstrução do estado final a partir da trilha) comparado ao estado acompanhado; (iii) 10.000 transições adversariais uniformes, em que nenhuma transição não declarada pode ser aceita; e (iv) 20.000 ensaios da invariante de dispensação parcial sob retiradas sucessivas. Para o *documento canônico*: geração de 10.000 prescrições, teste de determinismo (independência da ordem de chaves), detecção de adulteração por mutação de um único campo canônico e contagem de colisões de hash.

**Execução preliminar e autoritativa.** Os resultados abaixo provêm de uma execução **preliminar de nível-domínio**, que exercita diretamente os módulos que impõem os invariantes (a máquina de estados e a canonicalização), sem o stack completo de persistência. A execução **autoritativa** — corpus gerado pelos endpoints oficiais e *replay* do ledger persistido — é conduzida no ambiente de integração e reportada na versão final. `[TODO: substituir/complementar com a execução full-stack.]`

**Resultados (E1, semente = 42).**

| Métrica | Resultado |
|---|---|
| Pares de estado verificados (fechamento) | 128 |
| Transições ilegais aceitas | **0** (rejeição 100%) |
| Transições legais bloqueadas indevidamente | 0 |
| Percursos legais / passos | 5.000 / 7.722 |
| Passos ilegais em percursos legais | 0 |
| Saídas de estado terminal encontradas | 0 |
| *Replays* inconsistentes (estado a partir da trilha) | **0** (consistência 100%) |
| Transições adversariais testadas / ilegais aceitas | 10.000 / **0** |
| Ensaios de dispensação parcial / violações (Σ disp. > prescrito) | 20.000 / **0** |
| Prescrições canônicas geradas (hash) | 10.000 (~57k/s) |
| Hashes não determinísticos (ordem de chaves) | **0** (determinismo 100%) |
| Adulterações detectadas | **10.000 / 10.000** (100%) |
| Hashes distintos / colisões | 10.000 / **0** |

**O que estabelece e o que não estabelece.** O experimento mostra empiricamente que: a máquina de estados é total e fechada (nenhuma transição ilegal é aceita, mesmo sob estímulo adversarial); o estado é integralmente reconstruível a partir da trilha de eventos (*replay* 100% consistente — a expressão operacional de "auditável por construção"); a invariante de dispensação parcial nunca é violada; e o documento canônico é determinístico e detecta 100% das adulterações de campo. **Não** estabelece eficácia clínica nem segurança em uso real, e não substitui a execução full-stack pelos endpoints oficiais. O harness é aberto e reprodutível (`docs/paper/experiments/e1_auditability.py`).

## V. Discussão: Auditabilidade e seus Limites

A propriedade central é que a auditabilidade é estrutural: cada ato é um evento na trilha imutável, e cada decisão regulatória é decomposta em verificações justificadas. Isso desloca a regra regulatória de uma caixa-preta por fornecedor para um componente de referência verificável.

**Corolário (auditabilidade ⟹ resistência à mercantilização encoberta).** Monetizar dado de paciente de forma encoberta exige, materialmente, um caminho de egressão em massa, fora da trilha. Mas uma arquitetura auditável por construção é justamente aquela em que nada ocorre fora do ledger e não há porta de egressão em massa; logo, a disciplina que a torna auditável a torna estruturalmente hostil à mercantilização — *não se vende o que a arquitetura não emite*. Reforça-o uma assimetria de projeto: **abre-se a regra, localiza-se a pessoa** (o mecanismo é inspecionável e aberto; o identificador do cidadão não circula nem é coletado centralmente). *Apresentamos este corolário de forma compacta; seu desenvolvimento arquitetural — a análise de defesa em profundidade e a propriedade de ausência de egressão — é objeto de um trabalho companheiro sobre arquitetura de software.* `[ref ao paper ICSA, quando existir]`

**Limites declarados.**

- **Assinatura ICP-Brasil ponta a ponta é design declarado, não validada** (serialização canônica entre ambientes e verificação de cadeia de certificados em aberto).
- **Bases de referência são subconjuntos MVP** sobre dados sintéticos (na ordem de 81 medicamentos, ~240 códigos CID-10, 35 procedimentos); expansão e sincronização com fontes oficiais são trabalho futuro.
- **Sem validação clínica de campo**; avaliação por conformidade.
- Salvaguardas como código elevam o piso, mas não prendem um fork malicioso; a força jurídica está na licença aberta.

## VI. Conclusão

Apresentamos uma arquitetura de referência na qual a auditabilidade é estrutural, realizando a tese de que regras sanitárias transparentes sobre uma trilha imutável de eventos produzem fluxos auditáveis por construção. O acoplamento de um motor de circulação (estados, ledger imutável, custódia, dispensação parcial) a um motor regulatório (validação explicável em camadas, identidade por nome, terminologia defensiva), instanciado em uma implementação de referência aberta sobre dados sintéticos e avaliado por conformidade executável, mostra que a confiança em software de saúde pode nascer da forma do sistema, não de promessas. Trabalho futuro inclui a integração da assinatura ICP-Brasil ponta a ponta, a expansão das bases de referência e um piloto de campo em unidade municipal.

## Referências

`[TODO: estilo numérico IEEE — nomes completos (et al. só para 6+), DOIs/URLs. Âncoras iniciais:]`

- [ ] CFM, Resolução nº 2.299/2021.
- [ ] Anvisa, RDC nº 1.000/2025 (SNCR).
- [ ] Brasil, Portaria SVS/MS nº 344/1998.
- [ ] Anvisa, RDC nº 471/2021.
- [ ] ICP-Brasil / MP 2.200-2/2001.
- [ ] Lei nº 13.787/2018.
- [ ] Biblioteca rapidfuzz (casamento aproximado de strings).
- [ ] `[2–3 refs]` event sourcing / logs de auditoria imutáveis.
- [ ] `[3–5 refs]` apoio à decisão clínica explicável / transparência em software crítico de saúde.
- [ ] `[2–3 refs]` casamento aproximado de strings para terminologia clínica.
