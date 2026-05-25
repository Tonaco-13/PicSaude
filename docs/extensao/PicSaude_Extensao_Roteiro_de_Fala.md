# PicSaúde — Roteiro de fala da primeira reunião de extensão

> Reunião: terça-feira, 26 de maio de 2026
> Apresentador: Fabiano Tonaco Borges
> Material visual: `PicSaude_Extensao_2026_05_26.pptx` (18 slides)
> Duração total prevista: **22-25 minutos** de fala + **30-45 minutos** de apresentações dos extensionistas + **5-10 minutos** de combinações
>
> Este roteiro é guia, não script. Adapte o tom à energia da sala. Pausas valem mais que pressa.

---

## Antes de começar (~2 min, informal)

Cumprimente cada um pelo nome quando entrarem. Espere todos sentarem. Beba água. Respire. Você está em casa — é seu projeto.

Quando começar formalmente: **"Obrigado por estarem aqui. Vou falar uns 20 minutos sobre o PicSaúde, depois quero ouvir vocês — formação, interesse, o que gostariam de fazer. No fim combinamos próximos passos. Pode interromper para pergunta a qualquer momento."**

---

## Slide 1 — Capa (45s)

**Fala sugerida:**

> "PicSaúde. Prescrição digital pública para o SUS.
>
> É o projeto que vocês estão entrando como extensionistas. Aprovado essa semana na CTG. Quero contar pra vocês o que é, onde está, e onde vocês entram. Em 20 minutos."

**Dica:** projete confiança. Esse projeto já tem registro INPI, código rodando, e agora extensão aprovada. Você não está pedindo permissão — está convidando para colaboração.

**Transição:** "Antes do projeto em si, vou me apresentar rapidamente."

---

## Slide 2 — Quem coordena (60s)

**Fala sugerida:**

> "Fabiano Tonaco Borges. Sanitarista de formação. Hoje professor de Engenharia Biomédica aqui no CTG.
>
> Por que essa origem importa? Porque o PicSaúde não é projeto de engenheiro de software que decidiu mexer com saúde. É o contrário: é sanitarista que precisou aprender a fazer software porque o que existia no mercado não servia o serviço público.
>
> Coordeno como pesquisa-ação. Cada decisão técnica responde a uma pergunta sanitária. Cada arquitetura tem uma motivação clínica ou regulatória atrás dela."

**Dica:** Aponte rapidamente para o card de propriedade intelectual: *"Tudo isso já tem registro no INPI, marca registrada, e licença AGPL. Não é prototipo de gaveta."*

**Transição:** "Mas antes de mostrar o projeto, deixa eu mostrar a frase que rege tudo."

---

## Slide 3 — Software à altura do SUS (30s)

**Fala sugerida:**

> "Essa frase está em todos os arquivos de configuração do projeto. É a primeira linha de cada documento.
>
> O SUS é o maior sistema universal de saúde do mundo. Atende 215 milhões de pessoas. Merece infraestrutura digital pública à altura.
>
> Hoje não tem. É isso que a gente está construindo."

**Dica:** Pausa de 3 segundos depois de falar a frase. Deixa ela aterrissar.

**Transição:** "Por que a gente acha que falta? Vou mostrar em três slides o problema."

---

## Slide 4 — Problema 1: prescrição em papel (90s)

**Fala sugerida:**

> "Hoje, no serviço público brasileiro, a receita médica ainda sai em papel. E isso custa caro em três frentes.
>
> **Rastreabilidade zero.** A receita sai da mão do médico e desaparece. Foi usada? Foi perdida? Foi falsificada? Foi jogada fora? Ninguém sabe. Não há ledger nenhum.
>
> **Fraude estrutural difícil de auditar.** Sem assinatura digital, sem trilha forense — identificar quem emitiu, quem alterou, quando, depende de inspeção manual. Em escala de Brasil, isso é inviável.
>
> **Adesão medicamentosa baixa.** Paciente não compra. Médico não fica sabendo. Sem feedback, a terapêutica não se ajusta. Resultado clínico pior."

**Dica:** Se algum extensionista é da farmácia/medicina, olhe para essa pessoa no slide da adesão — eles vivem isso.

**Transição:** "Tem soluções digitais privadas. Mas vou argumentar que elas não resolveram para o SUS."

---

## Slide 5 — Problema 2: privado não resolveu (90s)

**Fala sugerida:**

> "Existem receitas digitais privadas no Brasil há mais de 5 anos. Memed, MV, Tasy. Funcionam. Mas falharam no SUS por três razões.
>
> **Proprietárias e fragmentadas.** Cada fornecedor controla um silo de dado clínico. Hospital A não fala com farmácia B porque usa software diferente.
>
> **Sem controle público do dado.** Estado paga, empresa privada guarda. O município contratante não tem soberania nem sobre o próprio dado clínico do próprio cidadão.
>
> **Vendor lock-in.** Trocar de sistema custa anos e milhões. O Estado vira refém comercial.
>
> O PicSaúde propõe o oposto: aberto, auditável, o dado clínico fica com o serviço público, integrável sem prender ninguém."

**Dica:** A coluna direita do slide cresce em peso visual. Aponte para "Dado clínico fica com o serviço público" — é o argumento sanitarista mais forte.

**Transição:** "Mas então qual é o gap exato que ninguém preencheu?"

---

## Slide 6 — Problema 3: o gap (60s)

**Fala sugerida:**

> "O SUS precisa de prescrição digital com quatro características simultâneas. E hoje, essas quatro não existem juntas em lugar nenhum.
>
> **Pública** — operada pelo Estado, código aberto.
>
> **Auditável** — ledger imutável, instance_id forense, assinatura ICP-Brasil. Cada ação registrada.
>
> **Integrável** — padrões abertos, sem vendor lock-in.
>
> **Centrada na saúde** — fluxo desenhado da norma sanitária, não da preferência técnica.
>
> Esse é o gap. É isso que o PicSaúde preenche."

**Transição:** "Vou mostrar agora a solução em quatro slides — arquitetura, princípios, fluxo, proteção."

---

## Slide 7 — Solução: arquitetura 3 camadas (90s)

**Fala sugerida:**

> "Três camadas. Cada uma com uma responsabilidade clara.
>
> **Interface** — HTML simples. Frontend que roda em qualquer navegador, sem framework pesado. Prescritor, dispensador, cidadão, validador — cada um tem sua tela.
>
> **Aplicação** — FastAPI em Python. Mais de 30 endpoints REST com controle fino de quem pode fazer o quê. Cobertura de testes alta.
>
> **Persistência + auditoria** — PostgreSQL em produção, ledger imutável append-only, assinatura ICP-Brasil padrão PAdES-B. Cada evento clínico vira linha permanente no ledger.
>
> A separação é proposital. Cidadão troca de interface? Frontend muda, backend não. Município quer trocar de banco? Banco muda, regulação fica. A arquitetura permite evolução sem reforma estrutural."

**Transição:** "Por trás dessa arquitetura, há seis princípios que guiam toda decisão."

---

## Slide 8 — 6 princípios (120s)

**Fala sugerida:**

> "Esses seis princípios estão escritos no arquivo CLAUDE.md do projeto. Toda decisão técnica responde a um deles. Quando o time discute alguma coisa, a gente volta aqui.
>
> **1. Regulação é especificação.** As features saem da norma sanitária, não da preferência do programador. A RDC 1.000 vira código.
>
> **2. Auditoria é arquitetura.** Ledger não é log — é coluna vertebral. Tudo é evento append-only.
>
> **3. Backend é fonte de verdade.** Nunca confiamos no frontend para afirmar estado clínico. Frontend pode mentir, ser hackeado, perder conexão. Backend valida tudo.
>
> **4. Proteção é estrutural.** LGPD não é PDF jurídico — é propriedade do código. instance_id, sem export em massa, append-only.
>
> **5. Cada clique custa um paciente.** UX mínima é saúde pública. Não é estética — é vida. Médico cansado num posto de saúde precisa de 3 cliques, não 15.
>
> **6. Código público porque SUS é público.** AGPL não é ideologia, é estratégia. Qualquer município pode auditar, contribuir, adaptar."

**Dica:** Esse slide é o coração da fala. Não corre. Se algum princípio chamar atenção, abre espaço para pergunta.

**Transição:** "Vou mostrar agora como esses princípios aparecem no fluxo clínico real."

---

## Slide 9 — Fluxo clínico (75s)

**Fala sugerida:**

> "Esse é o fluxo principal. Quatro atores, três transições.
>
> O **prescritor** emite — digital com assinatura ICP, ou física registrada localmente.
>
> A **custódia** é explícita: a cada momento, alguém é o detentor do documento. Médico, paciente, ou farmácia. Nada fica ambíguo.
>
> O **paciente** recebe via carteira digital. Leva ao balcão.
>
> O **dispensador** valida a assinatura, dispensa (pode ser parcial), e encerra.
>
> Cada uma dessas transições emite um evento imutável no ledger. É essa trilha que permite auditoria forense, prestação de contas, ajuste de política sanitária."

**Transição:** "Mas o que protege o cidadão nesse fluxo?"

---

## Slide 10 — Proteção (75s)

**Fala sugerida:**

> "Quatro mecanismos. Todos estruturais — quer dizer, não dependem de boa vontade de operador.
>
> **Assinatura ICP-Brasil.** Padrão PAdES sobre documento canônico. Validação por hash e cadeia oficial.
>
> **Sem export em massa.** A API recusa consultas amplas. Cada acesso é singular e logado. Não dá pra baixar 'todas as prescrições de um município' num CSV.
>
> **instance_id forense.** Cada instalação física tem uma marca d'água única. Se vazar dado, dá pra rastrear de qual servidor saiu.
>
> **RBAC autorizativo.** Onze endpoints clínicos centrais com owner check explícito. Médico A não lê paciente do médico B. Isso a gente fechou semana passada com auditoria de segurança."

**Transição:** "É isso o que o sistema faz. Agora deixa eu mostrar onde a gente está."

---

## Slide 11 — Estado: o que está pronto (75s)

**Fala sugerida:**

> "Hoje, maio de 2026, esses são os números.
>
> **Cinco etapas técnicas fechadas.** Identidade da instância, carteira digital, OTP seguro, autenticação por papel, autorização mínima. Cada uma com ticket formal, revisão por agente externo, e teste regressional.
>
> **Mais de 140 testes automatizados.** Cobertura focal em fluxo crítico. Suite roda em segundos.
>
> **Onze vulnerabilidades de segurança fechadas** com três ciclos de revisão. Auditoria séria, não de fachada.
>
> **Três ciclos de revisão por ticket.** Eu redijo, agente revisor critica, eu integro, código entra, agente revisor confere. Não é solo — é cadeia.
>
> Mas tem um problema."

**Dica:** Pausa de 2 segundos antes do "Mas tem um problema." Cria curiosidade.

**Transição:** Aponte para a frase embaixo do slide. *"O motor funciona — localmente. Falta torná-lo público."*

---

## Slide 12 — Estado: o que falta (60s)

**Fala sugerida:**

> "Próximas duas, três semanas. Marcos curtos e conhecidos.
>
> **Esta semana**, DEMO_MODE — um modo demo público com personas pré-semeadas, sem precisar login real. Permite vocês e a comunidade testar sem cadastro.
>
> **Próxima**, Dockerfile — container que roda em qualquer cloud.
>
> **Mais uma semana**, deploy em provedor público (Render) + frontend em Cloudflare. URL pública na rua.
>
> **Depois**, vou abrir doze 'good-first-issues' no GitHub — tarefas pequenas, ideais para quem quer dar primeiro PR num projeto open source.
>
> Demo pública até início de junho. Comunidade pode testar antes de qualquer município ouvir falar."

**Transição:** "E é exatamente por isso que extensão importa agora."

---

## Slide 13 — Por que extensão agora (90s)

**Fala sugerida:**

> "O sistema funciona. Mas ninguém usa em ambiente real ainda.
>
> Tem uma janela rara aqui. O motor está pronto. A apresentação para os municípios ainda não foi feita. As decisões de UX clínica ainda podem ser ajustadas. A estratégia de chegada nos secretários ainda está aberta.
>
> Eu sozinho não dou conta. E não devo — extensão é sobre coletivo.
>
> Precisa de **olhos clínicos** para validar fluxo — vocês de medicina, enfermagem, farmácia.
>
> Precisa de **voz sanitarista** para acessar SMS — vocês de saúde coletiva.
>
> Precisa de **mãos técnicas** para deploy e issues — vocês de informática, engenharia.
>
> Precisa de **comunicação** para chegar no município — vocês de direito, comunicação, design."

**Dica:** Esse é o slide que justifica vocês estarem aqui. Olha cada um na cara enquanto fala "vocês de X".

**Transição:** "Então vou propor quatro frentes. São negociáveis hoje."

---

## Slide 14 — 4 frentes propostas (90s)

**Fala sugerida:**

> "Quatro frentes. Vocês escolhem.
>
> **Clínico-regulatória.** Validar fluxo de prescrição-dispensação com olho clínico. Traduzir regulamentação da Anvisa para casos de uso. Médicos, enfermeiros, farmacêuticos.
>
> **Técnica.** Contribuir código via issues abertas. Testar. Ajudar com Dockerfile e deploy. Informática, engenharia biomédica, engenharia de software.
>
> **Sanitarista / saúde coletiva.** Mapear municípios alvo de Pernambuco. Entender contexto local — indicadores de saúde, perfil político, gatekeepers nas Secretarias Municipais. Saúde coletiva, saúde pública.
>
> **Comunicação / jurídica.** Pacote para SMS — material institucional. Modelo de parceria com município (comodato, doação, contrato). Website, design, materiais. Direito, comunicação, design.
>
> Se nenhuma encaixa exatamente no que vocês querem, a gente conversa. Frentes são meio negociáveis."

**Transição:** "Como vocês contribuem na prática?"

---

## Slide 15 — Como contribuir (60s)

**Fala sugerida:**

> "Três canais.
>
> **GitHub.** O repositório se chama Tonaco-13/PicSaude. Hoje está privado — vou abrir para vocês como colaboradores. Issues, pull requests, code review — tudo lá. Quem nunca usou Git, eu ajudo no início.
>
> **Reuniões quinzenais.** Aqui, presencial ou online. Acompanhamento, decisões, distribuição de trabalho. Entre reuniões, vocês trabalham assíncrono.
>
> **Canal assíncrono.** Telegram ou Discord — a gente define hoje qual prefere. Para dúvidas rápidas, coordenação, combinar reunião extra se precisar."

**Transição:** "E o que se espera de cada um."

---

## Slide 16 — Compromisso (60s)

**Fala sugerida:**

> "**Carga horária:** vamos seguir o que a regulação da extensão UFPE define. Trabalho efetivo distribuído entre reunião e tarefas assíncronas. Não precisa heroísmo — precisa consistência.
>
> **Engajamento de fluxo:** participar das reuniões quinzenais. Manter as tarefas em andamento. Quando trancar, reportar cedo — quanto antes a gente sabe, mais rápido destrava.
>
> **Entrega e crédito:** um relatório curto por mês. Suas contribuições ficam registradas no GitHub — isso é histórico público, conta para crédito acadêmico, conta como portfolio para depois."

**Dica:** Reforça que erro não tem problema, silêncio sim. *"Eu prefiro saber que vocês tropeçaram do que descobrir num mês."*

**Transição:** "Próximos passos concretos."

---

## Slide 17 — Próximos passos (60s)

**Fala sugerida:**

> "Três coisas hoje.
>
> **Apresentações.** Daqui a pouco. Cada um conta formação, interesse, o que gostaria de fazer. Sem pressão — pode mudar depois.
>
> **Escolha de frente.** Até sexta. Cada um confirma por mensagem qual frente prefere. Pode ser combinação de duas se fizer sentido.
>
> **Próxima reunião.** A gente combina a data agora ao final. Sai de lá com primeiras tarefas distribuídas e tudo no GitHub."

**Transição:** "Pra fechar."

---

## Slide 18 — Convite (45s)

**Fala sugerida:**

> "O SUS é o maior sistema universal de saúde do mundo.
>
> Merece software à altura.
>
> Bem-vindos ao PicSaúde."

**Dica:** Pausa de 3-5 segundos antes do "Bem-vindos." Olha cada um na cara. Sorri.

---

## Depois da apresentação (30-45 min)

> "Agora quero ouvir vocês. Vamos passar a palavra um por um. Conta: nome, curso, semestre/período, e o que te chamou atenção no que falei — pode ser tema, frente, dúvida, ressalva. Sem cerimônia."

Anote tudo num caderno. Não interrompe. Se alguém ficar mudo, ajuda com pergunta: *"E o que você gostaria de fazer na extensão, mesmo que ainda não saiba direito?"*

Depois das apresentações:

> "Vou consolidar o que ouvi, mandar por escrito amanhã, e até sexta vocês me confirmam frente preferida. Combina?"

E para fechar: agendar a próxima reunião (sugestão: 2 semanas — terça **09/06**), definir canal assíncrono (votar Telegram x Discord), trocar emails/telefones se precisar.

---

## Anti-roteiros (coisas a NÃO fazer)

- **Não prometa adoção rápida pelos municípios.** O texto da extensão diz "testar e aprimorar", não "implantar". Mantenha a expectativa calibrada.
- **Não venda o sistema como pronto.** Faltam Etapas 7-8 (Dockerfile + deploy). Apresente como "motor pronto, despacho em construção".
- **Não use jargão técnico sem traduzir.** Se falar "RBAC", traduza imediatamente como "controle de quem pode fazer o quê". Se falar "ledger", diga "trilha imutável de eventos".
- **Não centralize o crédito.** Diga "o time" quando puder. Os extensionistas ainda não fizeram nada, mas a linguagem coletiva os inclui desde o primeiro dia.
- **Não improvise compromisso de carga horária.** Se algum extensionista perguntar quantas horas, diga: *"Vou confirmar com a PROEXC e mando até sexta."* (Você precisa mesmo confirmar — não chute na hora.)

---

*"O SUS é o maior sistema universal de saúde do mundo. Merece software à altura."*
