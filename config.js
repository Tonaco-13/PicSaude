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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', aplicarMascarasCPFGlobais);
} else {
    aplicarMascarasCPFGlobais();
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
