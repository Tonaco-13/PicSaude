# Despacho de copy travada — Atribuição institucional (partes 1 e 4)

> Convenção em vigor desde 04/09: **copy travada viaja no repo, nunca só no
> chat.** Este arquivo é a **fonte canônica** das partes (1) rodapé e (4) FAQ.
> Nasceu porque o chat perdeu um texto travado uma vez (a entrega do FAQ da
> abertura parou pedindo a copy de volta). O arquivo não perde.

Classe: `module` + `docs`. Ver o fecho no `FILA-VIVA.md`.

---

## 1. Rodapé do `index.html`

**Lugar (decisão do arquiteto, 04/09):** a linha institucional substitui a
**ocorrência pessoal** no bloco `.footer-legal`. A frase
"Responsável técnico: Dr. Fabiano Tonaco Borges." sai do rodapé da vitrine.

As outras duas linhas examinadas **ficam intactas**:

- a dedicação `.footer-sign p.sub` ("Feito com carinho…") é **voz da casa**,
  não nomeação pessoal;
- a descrição `.footer-ded` não muda.

**Justificativa registrada:** a responsabilidade pessoal continua existindo,
nos lugares onde ela é exigível e verificável. O responsável pela ação está na
certidão institucional (PJ324-2026). O titular está no README. O assinante das
curadorias clínicas está em cada row (`validado_por`). **A fachada fala pela
instituição; o documento fala pela pessoa.**

### Copy travada (texto âncora integral, com link)

```html
<a href="https://github.com/Tonaco-13/PicSaude/blob/main/docs/institucional/PJ324-2026.md">Um projeto de extensão da Engenharia Biomédica do CTG, Universidade Federal de Pernambuco.</a>
```

O restante do bloco `.footer-legal` (licença, avisos) permanece como está.

**Régua de pontuação:** zero travessão, ponto final, nada de emenda de palavra.

### Ratificação de 04/09 — dois acréscimos de uma linha

Na ratificação da #255 o arquiteto acrescentou:

1. **A substituição vale nas DUAS fachadas.** `demo.html` tinha a mesma linha
   pessoal no rodapé e recebe a mesma linha institucional, com o mesmo href.
   **Decisão pelo princípio da fachada:** onde a vitrine se apresenta, quem
   assina é a instituição — o princípio não é de uma página, é da fachada.
2. **O âncora ganha `target="_blank" rel="noopener noreferrer"`**, paridade
   com o link do repositório. A casa não deixa a aba nova controlar a
   original.

Os atributos valem para as duas cópias da linha: "mesma linha institucional"
é literal, e duas fachadas com atributos diferentes seriam divergência sem
motivo. Cada página estiliza no seu próprio idiom — `index.html` pela regra
`.footer-legal a`, `demo.html` pelo `style` inline que já usa no mailto —
porque isso é formatação, não copy.

### Extensão às ESTAÇÕES (04/09)

A linha passa a valer também nas quatro telas de trabalho: **prescritor,
dispensador, cidadão e clínica**. Não é mais só da fachada — quem **opera** a
plataforma também vê de quem é a casa.

Onde a linha vive hoje, com a mesma copy, o mesmo href e os mesmos atributos:

| Tela | Rodapé antes | O que mudou |
|---|---|---|
| `index.html` | `.footer-legal` | linha pessoal → institucional |
| `demo.html` | `.footer-brand` | linha pessoal → institucional |
| `prescritor.html` | copyright + AGPL | ganhou a linha |
| `dispensador.html` | copyright + AGPL | ganhou a linha |
| `cidadao.html` | copyright + AGPL | ganhou a linha |
| `clinica.html` | **nenhum** | ganhou rodapé com a forma das irmãs |

A clínica era a única estação **sem rodapé nenhum**. Recebeu um com a mesma
forma das outras três (aviso de licença + linha institucional), posicionado
depois das telas e antes dos modais, que são sobreposições. A alternativa —
um rodapé só com a linha institucional — deixaria a clínica como a única
tela servida sem o aviso de AGPL, num projeto cuja licença é AGPL.

**Não há rodapé compartilhado no repositório** (`submodulos.js` não injeta
rodapé, e só duas telas o carregam), então as seis cópias são inevitáveis
hoje sem construir um componente — obra maior que esta. O que impede as
cópias de divergirem é a guarda parametrizada em
`tests/browser/test_atribuicao_institucional.py`: a copy travada mora em UMA
constante, e todas as telas são conferidas contra ela.

---

## 2. FAQ — resposta "Quem faz? Como sei que posso confiar?"

### Copy travada (substitui a resposta atual inteira)

> É um projeto de extensão da UFPE, em código aberto, com licença AGPL e
> repositório público. Qualquer pessoa pode ler, auditar, usar e contribuir.
> As regras clínicas citam a fonte oficial, com página.

Texto simples, **sem link** (o rodapé já leva à certidão).

---

## 3. Guardas que acompanham

- `test_link_codigo_fonte_fachada.py` passa a declarar **dois alvos externos
  nomeados**: o repositório e a certidão (planejado pelo engenheiro,
  ratificado). O teste continua fechando a porta a um terceiro alvo entrar de
  carona — o que ele guarda é a **lista fechada**, não o número um.
- Verbatim das duas cópias conferido por script na revisão, como no FAQ.

---

## Proveniência

- Certidão institucional: `docs/institucional/PJ324-2026.md`
- PDF do SIGAA: **não versionado** (lista dez nomes de participantes que não
  consentiram com republicação); proveniência local com sha256 em
  `data/fontes-oficiais/ufpe/MANIFEST.md`
