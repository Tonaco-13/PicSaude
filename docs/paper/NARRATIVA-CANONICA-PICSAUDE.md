# PicSaúde — Narrativa Canônica (fonte única de verdade)

> **Para:** equipe Front Gear Health System (Bruno, Nicole, Heloisa) + autores dos papers
> **De:** coordenação de arquitetura do PicSaúde
> **Versão:** 1.0 · 2026-06-03
>
> Este documento é a **fonte única de verdade** sobre o que o PicSaúde é, como o descrevemos,
> e — igualmente importante — o que NÃO afirmamos sobre ele. Três artefatos herdam daqui:
> o pitch do Biochallenge, o resumo do CBEB (Trabalho B) e o paper de arquitetura (Trabalho A, ICSA).
> Se os três contam a mesma história, ganhamos credibilidade. Se um contradiz o outro diante da
> mesma banca (e a comunidade SBEB é a mesma para os três), perdemos. **Quando houver dúvida de
> como descrever algo, este documento decide.**

---

## 1. Como usar este documento (regra dos dois registros)

O mesmo sistema é descrito em **dois registros** diferentes, e os dois são honestos:

- **Registro de visão (pitch / Biochallenge):** pode falar do *futuro desejado* — "vamos integrar com o e-SUS", "o cidadão será soberano do seu dado". É legítimo, desde que esteja claro que é **visão/roadmap**, não algo pronto.
- **Registro de rigor (papers / banca científica):** descreve o **estado real** — o que já roda, o que é design declarado, e os limites em aberto.

**A única regra inviolável entre os dois:** *o pitch nunca pode afirmar como PRONTO aquilo que o paper declara como ROADMAP.* Dizer "nossa visão é integrar ao e-SUS" = ✅. Dizer "o PicSaúde integra ao e-SUS" (hoje) = ❌. Essa linha protege os três artefatos de uma vez.

---

## 2. A tese central (uma frase)

> **Regras sanitárias transparentes operando sobre uma trilha imutável de eventos produzem fluxos de saúde digital auditáveis por construção.**

Tudo no PicSaúde serve a essa frase. Os dois "motores" são as duas metades dela:

- **Motor sanitário (motor de circulação):** garante a *trilha imutável* — estados dos objetos clínicos, livro-razão de eventos (ledger) e cadeia de custódia.
- **Motor regulatório:** garante as *regras transparentes* — regras explícitas, verificáveis e explicáveis (alertas de dose, interação, inconsistência), nunca uma "caixa-preta".

### O corolário (a peça mais importante para a parte ética)

> **Auditável por construção é a mesma coisa que resistente à mercantilização encoberta — vista de outro ângulo.**

Por quê: vender/monetizar dado de paciente de forma encoberta exige um caminho de saída em massa, fora da trilha, sem rastro. Mas uma arquitetura auditável-por-construção é exatamente aquela onde **nada acontece fora do ledger** e **não existe porta de saída em massa**. Logo, a anti-mercantilização não é um "módulo" — é uma **consequência** da auditabilidade. *Não se vende o que a arquitetura não emite.*

---

## 3. Vocabulário canônico — o que dizer e o que NÃO dizer

Estes ajustes não são preciosismo: uma banca de engenharia biomédica que conhece o assunto vai cravar o termo errado, e a inconsistência entre o pitch e o paper fica visível.

| ❌ Não dizer | ✅ Dizer | Por quê |
|---|---|---|
| "descentralizado", "blockchain", "DLT" | "livro-razão imutável (ledger append-only)", "event-sourcing **interno**" | O PicSaúde é **centralizado** (banco único, ex. PostgreSQL). Imutabilidade vem do *append-only*, não de distribuição. Citar blockchain convida ataque e nos associa a hype de cripto — do qual nos afastamos de propósito. |
| "Event-Driven Architecture" | "event-sourced **internamente**" | Hoje somos event-sourced por dentro, mas **não** publicamos eventos para fora (não há camada de publicação — ver G4A nos limites). "Event-driven" promete uma porta que não existe. |
| "Integra com e-SUS / RNDS / HIS-LIS" (presente) | "Camada Adaptadora **projetada / roadmap**, condicionada ao G4A" | O Adapter Layer é **design declarado, não construído**. Adapter nunca escreve direto no banco clínico; ele consome endpoints/eventos oficiais. Sem a camada de publicação (G4A), não há onde conectar. |
| "PIX da saúde" como mecanismo técnico | "Inspirado na **transferência de custódia** do PIX (metáfora de UX)" | A metáfora do PIX para *passar a posse* é ótima e pode ficar — desde que como analogia de experiência, não como afirmação de que usamos a infraestrutura do PIX. |
| "Assinatura ICP-Brasil funcionando / validada" | "Fluxo de assinatura ICP-Brasil **projetado**; integridade por hash SHA-256 do documento canônico" | A assinatura ponta-a-ponta ainda não fecha (ver R6 nos limites). Descrever como contribuição de **design**, nunca como validada. |
| "Plataforma / produto / SaaS de saúde" | "Implementação de referência / prova de conceito auditável" | Não há piloto, não há dado real. Vender como produto pronto é o erro que derruba o trabalho. |
| "Elimina fraude / impede revenda" | "Torna a fraude/revenda **conspícua, juridicamente exposta e de alto atrito**" | Nenhum software *impede* um fork malicioso. Elevamos o piso e tornamos a violação visível. |

---

## 4. Os invariantes inegociáveis (nunca contradizer)

Estes são os pilares de identidade e confiança. Valem para os três artefatos.

1. **Objetos clínicos são imutáveis após emissão.** Correção, renovação ou ajuste = **novo objeto derivado** apontando para o anterior. Nunca "editar" uma prescrição emitida.
2. **O ledger é imutável.** A trilha de eventos só recebe inserções (append-only); nunca apaga nem altera evento.
3. **Custódia é explícita e rastreável.** Cada objeto tem um detentor a cada momento; transferências de posse são registradas (prescritor → paciente → dispensador, etc.).
4. **Dispensação parcial não invalida a prescrição.** Não conseguir pagar/retirar um item devolve aquele item ao estado pendente; ele pode ser dispensado em outra farmácia. A soma dispensada nunca supera a quantidade prescrita.
5. **Identidade soberana do paciente vs. proteção do prescritor.** O CPF do **paciente** é a chave soberana de custódia (o cidadão controla a transferência da posse). Já o CPF do **prescritor** é extraído **localmente** do certificado ICP-Brasil e **nunca é enviado ao servidor**. A validação do prescritor é feita **por NOME** (bases CNES/CFM), não por CPF.
6. **Soberania do dado ≠ centralização para lucro.** O cidadão é dono do seu dado; isso não cria nenhuma porta para terceiros monetizarem esse dado.

---

## 5. Fronteira de claims — o que afirmamos vs. o que nunca afirmamos

| ✅ Podemos afirmar (defensável) | ❌ Nunca afirmar (overclaim) |
|---|---|
| Cenários validados rodam verde: emissão digital, emissão física, transferência de custódia, dispensação parcial, autorização por dono. | "Validado em campo / com pacientes reais." |
| Dados **sintéticos**; DEMO_MODE garantido na arquitetura, não só no rótulo. | "Avaliado com dados clínicos reais." |
| Assinatura e Adapter Layer = **design declarado**. | "Assinatura/integração e-SUS funcionando." |
| Guard-rails (anti-monetização, anti-exportação) elevam o piso e tornam a violação visível. | "Guard-rails impedem fork malicioso / garantem que ninguém revende." |
| Implementação de referência aberta (AGPL), inspecionável por terceiros. | "Produto/plataforma em produção no SUS." |

---

## 6. Limites honestos (declarar, não esconder)

Declarar os limites é o que separa um trabalho sério de marketing — e fortalece a banca a nosso favor.

- **R6 — serialização canônica entre cliente e servidor (WebCrypto ↔ Python).** Ainda não fecha; por isso a assinatura ponta-a-ponta é design, não validada. É bloqueador absoluto de piloto, e está declarado como trabalho em aberto.
- **G4A — camada de publicação de eventos.** Não existe ainda. Sem ela, não há porta de saída controlada (e, portanto, nenhum adapter externo real, e nenhuma prevenção dura de revenda institucional). É o próximo controle a construir.
- **Somente dados sintéticos.** Nenhuma validação clínica de campo; nenhum dado real de paciente.
- **Guard-rails não prendem um fork malicioso.** A força jurídica está na licença AGPL; os guard-rails tornam a violação conspícua e auto-incriminante.

---

## 7. A equação anti-mercantilização (defesa em profundidade, com força declarada)

Três camadas, com força honestamente diferente em cada uma:

1. **Arquitetural (a mais forte e original):** ausência de porta de saída em massa; event-sourced internamente, sem egressão externa; CPF do prescritor nunca sobe. Vale para o próprio sistema rodando honestamente.
2. **Jurídica (a única coercitiva contra fork):** AGPL — quem roda versão modificada como serviço é obrigado a publicar o fonte; a modificação maliciosa fica à luz do dia.
3. **Normativa (eleva o piso):** carta de não-objetivos (ETHICS.md) + verificações automáticas (CI) que falham o build se um termo de monetização aparecer. Não trava o fork determinado, mas converte deriva por descuido em ato deliberado e rastreável.

Contra-argumento que **antecipamos** (e que fortalece): "abrir o código não ajuda o mau ator?" Resposta: (a) o motor não tem valor em dado — vem sem dado; (b) um fork que arranca as salvaguardas deixa de ser PicSaúde-conforme, e conformidade é **verificável**; (c) sem abertura não há auditoria por terceiros — e auditoria por terceiros é a proposta de confiança inteira.

---

## 8. Como cada artefato usa esta narrativa (e a regra de não-vazamento)

| Artefato | Líder | Unidade de análise | Herda daqui |
|---|---|---|---|
| **Pitch Biochallenge** | alunos | a solução para a APS, o problema do cidadão | tese + corolário + vocabulário; registro de **visão** |
| **Trabalho B — CBEB** | alunos (Fabiano co-autor) | o **problema clínico** e a **aplicação** à Atenção Primária (ancorado nas entrevistas) | tese + invariantes + limites; registro de **rigor**; usa a arquitetura como pano de fundo, **não** a reivindica como contribuição |
| **Trabalho A — ICSA** | Fabiano (alunos citados) | a **arquitetura** e suas propriedades (os dois motores) | tudo; registro de **rigor** máximo; cita a aplicação à APS, mas a contribuição é a arquitetura |

**Regra de não-vazamento (para não violar ineditismo entre B e A):** B contribui o *problema/aplicação*; A contribui a *arquitetura*. Um pode mencionar o outro como contexto, mas a **contribuição reivindicada** de cada um é distinta. Assim os dois podem ser submetidos (CBEB e ICSA) sem dupla submissão do mesmo trabalho.

---

## 9. Glossário rápido para a equipe

- **Objeto sanitário:** qualquer documento clínico rastreável (prescrição, laudo, pedido de exame, agendamento). Todos seguem o mesmo padrão: identidade (UUID), estados, ledger, custódia.
- **Ledger (livro-razão):** tabela de eventos só-de-inserção. É a "trilha imutável".
- **Custódia:** quem detém a posse do objeto a cada momento; transferências são registradas.
- **Documento canônico:** representação padronizada do conteúdo clínico sobre a qual se calcula o hash SHA-256 (base da integridade e da assinatura).
- **DEMO_MODE:** modo que garante, na arquitetura, que só há dados sintéticos.
- **G4A:** camada (futura) de publicação de eventos para o mundo externo. Hoje não existe.
- **R6:** divergência de serialização canônica cliente↔servidor; bloqueador em aberto da assinatura ponta-a-ponta.
- **Guard-rail:** verificação automática que falha o build se algo proibido (ex.: termo de monetização) aparecer no código.

---

*Dúvida sobre como descrever qualquer coisa do PicSaúde? Volte aqui primeiro. Se não estiver coberto, pergunte à coordenação antes de escrever — especialmente se tocar assinatura, serialização, ledger, custódia ou estados.*
