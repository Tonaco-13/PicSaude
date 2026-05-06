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
 *   - Se a página foi aberta via file:// — fallback para localhost:8080.
 *
 * Antes este arquivo apontava para :8000, mas em desenvolvimento via
 * uvicorn nativo a porta padrão é 8080 (definida em .env). Como o
 * frontend agora é servido pelo próprio backend (StaticFiles mount),
 * usar window.location.origin é o mais correto.
 */

const _isFileProtocol = window.location.protocol === 'file:';

const BACKEND_URL = _isFileProtocol
    ? 'http://127.0.0.1:8080'
    : window.location.origin;

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
