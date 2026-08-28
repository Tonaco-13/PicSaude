/**
 * config.js — PicSaúde
 *
 * Centraliza a URL do backend. Inclua este arquivo em todos os HTMLs
 * como primeiro <script> no <head>:
 *
 *   <script src="config.js"></script>
 *
 * Estratégia:
 *   - Se a página foi aberta via http(s) — backend é a mesma origem.
 *   - Se a página foi aberta via file:// — fallback para localhost:8000.
 *
 * O fallback 8000 alinha com o dev nativo (uvicorn default, subir-local.sh
 * e o Quick Start do CONTRIBUTING-EXTENSAO). No empacotamento Docker o
 * frontend é servido pelo próprio backend (StaticFiles na mesma origem),
 * então window.location.origin cobre a porta externa 8080 sem este fallback.
 */

const _isFileProtocol = window.location.protocol === 'file:';

const BACKEND_URL = _isFileProtocol
    ? 'http://127.0.0.1:8000'
    : window.location.origin;

// ─────────────────────────────────────────────────────────────────────────
// PicSaúde — Identidades canônicas da demo (FONTE ÚNICA)
// TICKET-DEMO-IDENTIDADES-FONTE-UNICA
//
// A circulação da vitrine tem de fechar num só cidadão: uma receita emitida
// no prescritor.html cai na carteira DESTE mesmo CPF no cidadao.html. Antes,
// cada tela chumbava o seu literal e os objetos não se encontravam — o valor
// certo existia, mas não era a ÚNICA verdade.
//
// A REGRA: nenhuma tela chumba CPF/CNPJ literal. Toda identidade de demo
// referencia `DEMO.*` daqui. Um guard-rail estático varre os HTMLs e falha se
// um literal de 11 (CPF) ou 14 (CNPJ) dígitos reaparecer solto — exceto o
// sentinela `00000000000` (§6a). Ver
// backend/tests/unit/test_guardrail_identidades_demo.py.
//
// Concordância provada: os mesmos valores vivem em `seed_demo.py` (lado
// servidor). Frontend em JS e seed em Python não compartilham arquivo, então a
// régua não é "importam do mesmo módulo" — é "os dois batem", travado no gate.
//
// Um cidadão; um estabelecimento por PAPEL (farmácia ≠ clínica: um CNPJ não
// pode ser as duas coisas). CPF/CNPJs verificados nos dígitos (módulo 11).
// ─────────────────────────────────────────────────────────────────────────

const DEMO = {
    prescritor: { cns: '980001112223334', nome: 'Dra. Demo Maria Souza' },
    // ENG-016 — o DESTINO da terceira circulação. Fonte única, como as demais:
    // a tela lê daqui, nunca literal (guard-rail estático no gate).
    prescritorDestino: { cns: '980001112223335', nome: 'Dr. Demo Carlos Andrade', especialidade: 'CARDIOLOGIA' },
    cidadao:  { cpf:  '12345678909',    nome: 'João Demo da Silva' },
    farmacia: { cnpj: '99999999000191', nome: 'Farmácia Demo Central' },
    clinica:  { cnpj: '11222333000181', nome: 'Clínica Demo' },
};

// Atalho de login em DEV_MODE (prescritor.html) — credencial de teste local,
// NÃO é identidade de circulação. Vive aqui só para não deixar um literal de 11
// dígitos solto na tela (o antigo '11111111111', CPF matematicamente inválido).
const DEV_LOGIN_CPF = '11111111111';

// ─────────────────────────────────────────────────────────────────────────
// PicSaúde — Utilitários de formatação
// Padronização: CPF SEMPRE exibido como 000.000.000-00; banco/API armazena
// e trafega 11 dígitos puros (sem máscara). Para enviar à API, strip via
// replace(/\D/g, '').
// ─────────────────────────────────────────────────────────────────────────

/** Formata 11 dígitos como 000.000.000-00. Aceita string com ou sem máscara. */
function formatarCPF(valor) {
    const d = String(valor || '').replace(/\D/g, '').slice(0, 11);
    if (d.length === 11) return `${d.slice(0,3)}.${d.slice(3,6)}.${d.slice(6,9)}-${d.slice(9)}`;
    return d;  // se inválido, retorna só os dígitos sem máscara
}

/** Formata 14 dígitos como 00.000.000/0000-00. Aceita string com ou sem máscara. */
function formatarCNPJ(valor) {
    const d = String(valor || '').replace(/\D/g, '').slice(0, 14);
    if (d.length === 14) return `${d.slice(0,2)}.${d.slice(2,5)}.${d.slice(5,8)}/${d.slice(8,12)}-${d.slice(12)}`;
    return d;  // se inválido, retorna só os dígitos sem máscara
}

/** Formata CNS (15 dígitos) como 980.0011.1222.3334. Aceita string com ou sem máscara. */
function formatarCNS(valor) {
    const d = String(valor || '').replace(/\D/g, '').slice(0, 15);
    if (d.length === 15) return `${d.slice(0,3)}.${d.slice(3,7)}.${d.slice(7,11)}.${d.slice(11,15)}`;
    return d;  // se inválido, retorna só os dígitos sem máscara
}

/** Aplica máscara automática enquanto o usuário digita CPF num <input>. */
function aplicarMascaraCPF(input) {
    if (!input || input.dataset.cpfMaskApplied) return;
    input.dataset.cpfMaskApplied = '1';
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('maxlength', '14');  // 11 dígitos + 3 separadores
    input.setAttribute('placeholder', '000.000.000-00');
    input.addEventListener('input', function(e) {
        let v = e.target.value.replace(/\D/g, '').slice(0, 11);
        if (v.length > 9)      v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2}).*/, '$1.$2.$3-$4');
        else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3}).*/, '$1.$2.$3');
        else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3}).*/, '$1.$2');
        e.target.value = v;
    });
}

/** Aplica a máscara em todos os <input class="cpf-input"> da página. */
function aplicarMascarasCPFGlobais() {
    document.querySelectorAll('.cpf-input, input[data-tipo="cpf"]').forEach(aplicarMascaraCPF);
}

/** Aplica máscara automática enquanto o usuário digita CEP num <input>. */
function aplicarMascaraCEP(input) {
    if (!input || input.dataset.cepMaskApplied) return;
    input.dataset.cepMaskApplied = '1';
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('maxlength', '9');  // 8 dígitos + 1 separador
    input.setAttribute('placeholder', '00000-000');
    input.addEventListener('input', function(e) {
        let v = e.target.value.replace(/\D/g, '').slice(0, 8);
        if (v.length > 5) v = v.replace(/(\d{5})(\d{1,3}).*/, '$1-$2');
        e.target.value = v;
    });
}

/** Aplica a máscara em todos os <input class="cep-input"> da página. */
function aplicarMascarasCEPGlobais() {
    document.querySelectorAll('.cep-input, input[data-tipo="cep"]').forEach(aplicarMascaraCEP);
}

/** TICKET FILA-VIVA A2 (Júlia, 26/08) — bloqueia não-dígitos em campos
 * numéricos sem máscara de separador (ex.: Idade). */
function aplicarRestricaoNumerica(input) {
    if (!input || input.dataset.numericoApplied) return;
    input.dataset.numericoApplied = '1';
    input.setAttribute('inputmode', 'numeric');
    input.addEventListener('input', function(e) {
        e.target.value = e.target.value.replace(/\D/g, '').slice(0, e.target.maxLength > 0 ? e.target.maxLength : undefined);
    });
}

/** Aplica a restrição numérica em todos os <input class="numerico-input"> da página. */
function aplicarRestricoesNumericasGlobais() {
    document.querySelectorAll('.numerico-input, input[data-tipo="numerico"]').forEach(aplicarRestricaoNumerica);
}

function _inicializarMascarasEntradaGlobais() {
    aplicarMascarasCPFGlobais();
    aplicarMascarasCEPGlobais();
    aplicarRestricoesNumericasGlobais();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _inicializarMascarasEntradaGlobais);
} else {
    _inicializarMascarasEntradaGlobais();
}

// ─────────────────────────────────────────────────────────────────────────
// PicSaúde — Feedback visível de ação (TICKET-FALHA-SILENCIOSA-FRONTEND)
//
// A REGRA: toda função disparada por CLIQUE do usuário termina em feedback
// visível — sucesso ou motivo da falha. Nada de `return` mudo em caminho de
// ação.
//
// Por que isto virou regra: três vezes na mesma semana uma guarda defensiva
// correta evitou o crash E escondeu o problema. A última foi o "Imprimir
// rascunho" — `window.open` bloqueado devolvia null, o código saía por um
// `if (!win) return;`, e o profissional clicava sem que nada acontecesse. Sem
// erro, sem pista. É a doutrina do R4 (CLAUDE.md §2a — falhar alto, nunca
// calar) aplicada à tela.
//
// A DISTINÇÃO QUE DEFINE O ESCOPO: guarda muda em código de RENDERIZAÇÃO é
// defensiva sadia — se o elemento não existe, não há o que desenhar. Guarda
// muda em AÇÃO DO USUÁRIO é defeito: o profissional clica em "Dispensar",
// nada acontece, e ele não sabe se dispensou.
//
// Esta função NASCEU em cidadao.html e foi promovida para cá sem mudar de
// nome nem de assinatura — os ~20 chamadores de lá continuam valendo. O que
// mudou: o elemento e o CSS passam a ser criados sob demanda, então qualquer
// tela que carregue o config.js ganha o toast sem precisar de markup próprio.
// ─────────────────────────────────────────────────────────────────────────

let _toastTimer = null;

/** Garante o elemento do toast e seu CSS. Idempotente. */
function _garantirToast() {
    let el = document.getElementById('picsaude-toast');
    if (el) return el;                      // cidadao.html já traz o seu
    if (!document.body) return null;        // chamada antes do DOM: sem onde pintar

    if (!document.getElementById('picsaude-toast-css')) {
        const css = document.createElement('style');
        css.id = 'picsaude-toast-css';
        css.textContent =
            '#picsaude-toast{position:fixed;bottom:24px;left:50%;' +
            'transform:translateX(-50%) translateY(20px);background:#0f172a;color:#fff;' +
            'padding:10px 20px;border-radius:8px;font-size:13px;font-weight:500;' +
            'box-shadow:0 4px 16px rgba(0,0,0,.25);opacity:0;pointer-events:none;' +
            'z-index:9999;transition:opacity .25s,transform .25s;max-width:90vw;' +
            'text-align:center;}' +
            '#picsaude-toast.show{opacity:1;transform:translateX(-50%) translateY(0);}' +
            '#picsaude-toast.success{background:#166534;}' +
            '#picsaude-toast.error{background:#991b1b;}' +
            '#picsaude-toast.info{background:#1e40af;}';
        document.head.appendChild(css);
    }

    el = document.createElement('div');
    el.id = 'picsaude-toast';
    // role=status + aria-live: quem não vê a tela também recebe o aviso. Um
    // erro que só existe em pixel continua sendo um erro silencioso.
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
    return el;
}

/**
 * Mostra um aviso visível ao usuário.
 *
 * @param {string} msg  — o que aconteceu E, quando for falha, o que fazer.
 *                        "Erro" sozinho não é feedback: não diz o próximo passo.
 * @param {string} type — 'info' (padrão) | 'success' | 'error'
 */
function showToast(msg, type = 'info') {
    const el = _garantirToast();
    if (!el) { console.warn('[toast]', msg); alert(msg); return; }
    el.textContent = msg;
    el.className = `show ${type}`;
    clearTimeout(_toastTimer);
    // Erro fica mais tempo: a mensagem diz o que fazer, e ler leva mais que
    // reconhecer um "pronto".
    _toastTimer = setTimeout(() => { el.className = ''; }, type === 'error' ? 7000 : 3500);
}

/**
 * Atalho para o caso deste ticket: a ação DESISTIU e o usuário precisa saber.
 * Existe para que o motivo da desistência nunca seja um `return` nu.
 */
function avisarFalha(msg) {
    showToast(msg, 'error');
}

// ─────────────────────────────────────────────────────────────────────────
// Barra superior "Demo: chaves" (KIMI3-006, ampliado pelo Fabiano 2026-08-06:
// "em todos os módulos é para constar em cima somentes as chaves demo").
//
// Substitui o antigo banner amarelo em TODAS as telas: uma barra discreta no
// topo com as 4 identidades canônicas (de DEMO.*, nunca literais), cada uma
// clicável para copiar o valor SEM máscara. O aviso "dados fictícios" não
// some — virou o rótulo da barra (ressalva nº 1 do conselheiro mantida).
//
// Uso (a tela já buscou /config/public e confirmou demo_mode):
//   renderizarBarraChavesDemo(cfg);
//   renderizarBarraChavesDemo(cfg, { rotulo: 'Demo — ...:' });
//   renderizarBarraChavesDemo(cfg, { nota: 'texto extra', link: {href, texto} });
// ─────────────────────────────────────────────────────────────────────────

/**
 * Renderiza a barra de chaves demo no topo do body. Idempotente.
 * @param {object} _cfg    — resposta de /config/public (reservado p/ usos futuros).
 * @param {object} [opcoes]— { rotulo, nota, link:{href,texto} }
 */
function renderizarBarraChavesDemo(_cfg, opcoes = {}) {
    if (document.getElementById('demo-keys-bar')) return;   // idempotente
    if (!document.body) return;

    if (!document.getElementById('demo-keys-bar-css')) {
        const css = document.createElement('style');
        css.id = 'demo-keys-bar-css';
        css.textContent =
            '.demo-keys-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;' +
            'gap:6px 14px;' +
            'background:#ffffff;border-bottom:1px solid #e2e8f0;padding:8px 20px;' +
            'font-size:12px;color:#475569;}' +
            '.demo-keys-bar .rotulo{font-weight:600;color:#92400e;white-space:nowrap;}' +
            '.demo-keys-bar .chip{display:inline-flex;align-items:center;gap:5px;' +
            'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:3px 8px;' +
            'cursor:pointer;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;' +
            'color:#0f172a;white-space:nowrap;}' +
            '.demo-keys-bar .chip:hover{background:#f1f5f9;border-color:#cbd5e1;}' +
            '.demo-keys-bar .chip .tipo{font-family:inherit;font-weight:700;color:#64748b;}' +
            '.demo-keys-bar .nota{color:#94a3b8;font-style:italic;}' +
            '.demo-keys-bar a{color:#1e3a8a;font-weight:600;text-decoration:none;' +
            'white-space:nowrap;}' +
            '.demo-keys-bar a:hover{text-decoration:underline;}';
        document.head.appendChild(css);
    }

    const CHAVES = [
        { icone: '🩺', tipo: 'CNS',  valor: formatarCNS(DEMO.prescritor.cns), bruto: DEMO.prescritor.cns,  modulo: 'Consultório' },
        { icone: '👤', tipo: 'CPF',  valor: formatarCPF(DEMO.cidadao.cpf),    bruto: DEMO.cidadao.cpf,     modulo: 'Carteira Cidadã' },
        { icone: '💊', tipo: 'CNPJ', valor: formatarCNPJ(DEMO.farmacia.cnpj), bruto: DEMO.farmacia.cnpj,   modulo: 'Farmácia' },
        { icone: '🏥', tipo: 'CNPJ', valor: formatarCNPJ(DEMO.clinica.cnpj),  bruto: DEMO.clinica.cnpj,    modulo: 'Clínica/Laboratório' },
    ];

    const barra = document.createElement('div');
    barra.className = 'demo-keys-bar';
    barra.id = 'demo-keys-bar';
    barra.setAttribute('role', 'note');
    barra.setAttribute('aria-label', 'Chaves de acesso da demo');

    const rotulo = document.createElement('span');
    rotulo.className = 'rotulo';
    rotulo.textContent = opcoes.rotulo || 'Demo — dados fictícios:';
    barra.appendChild(rotulo);

    CHAVES.forEach(c => {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.setAttribute('role', 'button');
        chip.setAttribute('tabindex', '0');
        chip.title = `Copiar ${c.tipo} do ${c.modulo} (sem máscara)`;
        chip.setAttribute('aria-label', chip.title);

        const icone = document.createElement('span');
        icone.setAttribute('aria-hidden', 'true');
        icone.textContent = c.icone;
        const tipo = document.createElement('span');
        tipo.className = 'tipo';
        tipo.textContent = c.tipo;
        const valor = document.createElement('span');
        valor.textContent = c.valor;
        chip.append(icone, tipo, valor);

        const copiar = async () => {
            try {
                await navigator.clipboard.writeText(c.bruto);
                showToast(`${c.tipo} do ${c.modulo} copiado`, 'success');
            } catch (err) {
                showToast(`Não consegui copiar — anote: ${c.bruto}`, 'error');
            }
        };
        chip.addEventListener('click', copiar);
        chip.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); copiar(); }
        });
        barra.appendChild(chip);
    });

    if (opcoes.nota) {
        const nota = document.createElement('span');
        nota.className = 'nota';
        nota.textContent = opcoes.nota;
        barra.appendChild(nota);
    }
    if (opcoes.link) {
        const a = document.createElement('a');
        a.href = opcoes.link.href;
        a.textContent = opcoes.link.texto;
        barra.appendChild(a);
    }

    document.body.insertBefore(barra, document.body.firstChild);
}

// ─────────────────────────────────────────────────────────────────────────
// Painel "Chaves de acesso (demo)" — formato cartão (nascido no index.html,
// promovido para cá em 2026-08-12 para ficar na borda superior de TODOS os
// módulos, no mesmo formato em que aparecia na parte inferior do índice).
//
// Diferença para a barra slim acima: mesmo conteúdo (as 4 identidades de
// DEMO.*, cópia sem máscara), apresentação em cartão com grade — um item por
// perfil, com rótulo, valor mono e botão "📋 Copiar" dedicado.
//
// Uso (a tela já buscou /config/public e confirmou demo_mode):
//   renderizarPainelChavesDemo(cfg);
//   renderizarPainelChavesDemo(cfg, { aviso: 'texto', nota: 'extra',
//                                     link: {href, texto} });
// ─────────────────────────────────────────────────────────────────────────

/**
 * Renderiza o painel-cartão de chaves demo na borda superior do body.
 * Idempotente.
 * @param {object} _cfg    — resposta de /config/public (reservado p/ usos futuros).
 * @param {object} [opcoes]— { aviso, nota, link:{href,texto} }
 */
function renderizarPainelChavesDemo(_cfg, opcoes = {}) {
    if (document.getElementById('chaves-demo-panel')) return;  // idempotente
    if (!document.body) return;

    if (!document.getElementById('chaves-demo-panel-css')) {
        const css = document.createElement('style');
        css.id = 'chaves-demo-panel-css';
        css.textContent =
            /* Espelha a estética do .status-block do portal: cartão branco,
               borda sutil, sem amarelo. Posicionado na borda superior. */
            '.chaves-demo-panel{background:#ffffff;border:1px solid #e2e8f0;' +
            'border-radius:12px;padding:16px 24px;box-sizing:border-box;' +
            'width:calc(100% - 24px);max-width:1080px;margin:12px auto 0;}' +
            '.chaves-demo-title{font-size:11px;text-transform:uppercase;' +
            'letter-spacing:1.2px;color:#94a3b8;font-weight:700;margin-bottom:12px;}' +
            '.chaves-demo-grid{display:grid;' +
            'grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px 20px;}' +
            /* Item em DUAS linhas: cabeçalho (ícone + rótulo) e corpo
               (valor mono à esquerda, botão Copiar à direita). Assim o
               valor nunca é espremido pelo botão — defeito visto na 1ª
               versão (CNS/CNPJ cortados em 4 colunas). */
            '.chaves-demo-item{display:flex;flex-direction:column;gap:6px;' +
            'padding:8px 10px;border-radius:8px;background:#f8fafc;' +
            'border:1px solid #eef2f7;}' +
            '.chaves-demo-item .cabec{display:flex;align-items:center;gap:8px;}' +
            '.chaves-demo-item .corpo{display:flex;align-items:center;' +
            'justify-content:space-between;gap:8px;}' +
            '.chaves-demo-item .icone{font-size:16px;}' +
            '.chaves-demo-item .rotulo{font-size:11px;color:#64748b;font-weight:600;' +
            'text-transform:uppercase;letter-spacing:.4px;}' +
            '.chaves-demo-item .valor{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;' +
            'font-size:13px;color:#0f172a;font-weight:600;white-space:nowrap;}' +
            '.chaves-demo-copiar{border:1px solid #cbd5e1;background:#fff;color:#334155;' +
            'font-size:11px;padding:3px 7px;border-radius:6px;cursor:pointer;' +
            'white-space:nowrap;}' +
            '.chaves-demo-copiar:hover{background:#f1f5f9;}' +
            '.chaves-demo-aviso{margin-top:12px;font-size:12px;color:#94a3b8;font-style:italic;}' +
            '.chaves-demo-aviso a{color:#1e3a8a;font-weight:600;text-decoration:none;' +
            'font-style:normal;white-space:nowrap;}' +
            '.chaves-demo-aviso a:hover{text-decoration:underline;}';
        document.head.appendChild(css);
    }

    const CHAVES = [
        { icone: '🩺', modulo: 'Consultório',         chave: 'CNS',
          valor: formatarCNS(DEMO.prescritor.cns),    bruto: DEMO.prescritor.cns },
        { icone: '👤', modulo: 'Carteira Cidadã',     chave: 'CPF',
          valor: formatarCPF(DEMO.cidadao.cpf),       bruto: DEMO.cidadao.cpf },
        { icone: '💊', modulo: 'Farmácia',            chave: 'CNPJ',
          valor: formatarCNPJ(DEMO.farmacia.cnpj),    bruto: DEMO.farmacia.cnpj },
        { icone: '🏥', modulo: 'Clínica/Laboratório', chave: 'CNPJ',
          valor: formatarCNPJ(DEMO.clinica.cnpj),     bruto: DEMO.clinica.cnpj },
    ];

    const painel = document.createElement('section');
    painel.className = 'chaves-demo-panel';
    painel.id = 'chaves-demo-panel';
    painel.setAttribute('aria-label', 'Chaves de acesso da demo');

    const titulo = document.createElement('div');
    titulo.className = 'chaves-demo-title';
    titulo.textContent = 'Chaves de acesso (demo)';
    painel.appendChild(titulo);

    const grid = document.createElement('div');
    grid.className = 'chaves-demo-grid';
    CHAVES.forEach(c => {
        const item = document.createElement('div');
        item.className = 'chaves-demo-item';

        const cabec = document.createElement('div');
        cabec.className = 'cabec';
        const icone = document.createElement('span');
        icone.className = 'icone';
        icone.setAttribute('aria-hidden', 'true');
        icone.textContent = c.icone;
        const rotulo = document.createElement('span');
        rotulo.className = 'rotulo';
        rotulo.textContent = `${c.modulo} · ${c.chave}`;
        cabec.appendChild(icone);
        cabec.appendChild(rotulo);

        const corpo = document.createElement('div');
        corpo.className = 'corpo';
        const valor = document.createElement('span');
        valor.className = 'valor';
        valor.textContent = c.valor;

        const copiar = document.createElement('button');
        copiar.type = 'button';
        copiar.className = 'chaves-demo-copiar';
        copiar.textContent = '📋 Copiar';
        copiar.setAttribute('aria-label', `Copiar ${c.chave} do ${c.modulo}`);
        copiar.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(c.bruto);  // sem máscara
                showToast(`${c.chave} do ${c.modulo} copiado`, 'success');
            } catch (err) {
                showToast(`Não consegui copiar — anote: ${c.bruto}`, 'error');
            }
        });

        corpo.appendChild(valor);
        corpo.appendChild(copiar);
        item.appendChild(cabec);
        item.appendChild(corpo);
        grid.appendChild(item);
    });
    painel.appendChild(grid);

    const aviso = document.createElement('div');
    aviso.className = 'chaves-demo-aviso';
    aviso.textContent = opcoes.aviso || 'Demo — dados fictícios, nenhuma prescrição é real.';
    if (opcoes.nota) aviso.textContent += ' ' + opcoes.nota;
    if (opcoes.link) {
        aviso.appendChild(document.createTextNode(' '));
        const a = document.createElement('a');
        a.href = opcoes.link.href;
        a.textContent = opcoes.link.texto;
        aviso.appendChild(a);
    }
    painel.appendChild(aviso);

    document.body.insertBefore(painel, document.body.firstChild);
}


// ─────────────────────────────────────────────────────────────────────────
// TICKET-J.3 — Login invisível na demo (re-login transparente)
//
// O PROBLEMA (parecer da excursão de 14/08, §3): `JWT_ACCESS_TTL_MINUTES = 15`.
// Passou de 15 minutos de uso, o próximo request leva 401, e os módulos mostravam
// "Sessão expirada. Faça login novamente." + `sair()` → tela de acesso. O
// auto-login demo existe nos 4 módulos, mas só roda no CARREGAMENTO da página —
// não socorre sessão que expira no meio da visita.
//
// O QUE **NÃO** MUDA: JWT e RBAC continuam de pé. `/demo/login` emite JWT real e
// o `require_role` nem sabe que é demo — esse é o desenho correto e é `core`.
// O que sai é o ATRITO: em modo demo a sessão nasce sozinha e RENASCE sozinha.
//
// POR QUE ENVOLVER `window.fetch`: são 91 chamadas de fetch nos 4 módulos.
// "Interceptador único" só existe de verdade num ponto que todas atravessam.
// Envolver aqui, no arquivo que os 4 já carregam, evita 91 pontos de edição —
// e evita que o próximo `fetch` escrito amanhã nasça desprotegido.
// ─────────────────────────────────────────────────────────────────────────

let _reloginEmVoo = null;   // mutex: N requests que expiram juntos renovam UMA vez
let _reloginCfg = null;     // {api, role, aoRenovar} — preenchido na instalação

/** Está em modo demo com re-login instalado? */
function emDemoComRelogin() { return _reloginCfg !== null; }

/**
 * Renova a sessão demo sob demanda. Usado pelos módulos quando um 401 escapa do
 * interceptador (ex.: `handleUnauthorized`) ou quando o visitante clica "Sair":
 * em demo não existe "ficar deslogado" — a sessão renasce.
 * @returns {Promise<object|null>} dados do /demo/login, ou null se falhou.
 */
async function renovarSessaoDemo() {
    if (!_reloginCfg) return null;
    return _reloginCfg.__renovar();
}

/**
 * Instala o re-login transparente. Só tem efeito em DEMO_MODE.
 *
 * @param {object}   opcoes
 * @param {string}   opcoes.api        base da API (ex.: BACKEND)
 * @param {string}   opcoes.role       papel demo deste módulo ('paciente'|'prescritor'|'dispensador')
 * @param {function} opcoes.aoRenovar  callback(data) — o módulo atualiza o token em memória
 */
function instalarReloginDemo({ api, role, aoRenovar }) {
    if (window.__picsaudeReloginInstalado) return;   // idempotente
    window.__picsaudeReloginInstalado = true;

    const fetchOriginal = window.fetch.bind(window);

    async function renovarSessao() {
        // Um único /demo/login por rajada de 401 — sem o mutex, dez requests
        // simultâneos disparariam dez logins e o último venceria a corrida.
        if (_reloginEmVoo) return _reloginEmVoo;
        _reloginEmVoo = (async () => {
            try {
                const resp = await fetchOriginal(`${api}/demo/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role }),
                });
                if (!resp.ok) return null;
                const data = await resp.json();
                sessionStorage.setItem('picsaude_demo_token', data.access_token);
                sessionStorage.setItem('picsaude_demo_role',  data.role);
                sessionStorage.setItem('picsaude_demo_sub',   data.sub);
                sessionStorage.setItem('picsaude_demo_nome',  data.nome);
                if (typeof aoRenovar === 'function') aoRenovar(data);
                return data;
            } catch (_e) {
                return null;
            } finally {
                _reloginEmVoo = null;
            }
        })();
        return _reloginEmVoo;
    }

    _reloginCfg = { api, role, aoRenovar, __renovar: renovarSessao };

    window.fetch = async function (entrada, init) {
        const resp = await fetchOriginal(entrada, init);
        if (resp.status !== 401) return resp;

        const url = typeof entrada === 'string' ? entrada : (entrada && entrada.url) || '';
        // Nunca interceptar a própria renovação: 401 ali é falha real e
        // recursão aqui seria laço infinito.
        if (url.indexOf('/demo/login') !== -1) return resp;
        // Uma tentativa por request. Se o retry também levar 401, o módulo
        // trata como sempre tratou — a rede de segurança não vira armadilha.
        if (init && init.__reloginTentado) return resp;
        // Sem `init` não dá para reemitir com o header novo (corpo de Request
        // já pode ter sido consumido); devolve o 401 em vez de arriscar.
        if (!init) return resp;

        const dados = await renovarSessao();
        if (!dados || !dados.access_token) return resp;
        const novoToken = dados.access_token;

        // O header velho carrega o token expirado — trocar é o ponto todo.
        const headers = Object.assign({}, init.headers || {});
        for (const k of Object.keys(headers)) {
            if (k.toLowerCase() === 'authorization') delete headers[k];
        }
        headers.Authorization = `Bearer ${novoToken}`;

        return fetchOriginal(entrada, Object.assign({}, init, {
            headers,
            __reloginTentado: true,
        }));
    };
}
