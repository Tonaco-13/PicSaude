#!/usr/bin/env python3
"""GP-3 — varredura de segredos e PII no histórico INTEIRO do repositório.

Reproduzível: lê todos os blobs de todas as refs via `git cat-file --batch`,
sem depender de checkout. Não corrige nada — só relata.

Uso:  python3 varredura.py <caminho-do-repo>
"""
from __future__ import annotations
import json, re, signal, subprocess, sys, collections
from itertools import islice
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()

def git(*a, binario=False):
    r = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True)
    return r.stdout if binario else r.stdout.decode("utf-8", "replace")

# ── padrões de SEGREDO ────────────────────────────────────────────────────
SEGREDOS = {
    "github_pat":        re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,}"),
    "openai_key":        re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    "anthropic_key":     re.compile(rb"sk-ant-[A-Za-z0-9\-_]{20,}"),
    "aws_access_key":    re.compile(rb"AKIA[0-9A-Z]{16}"),
    "google_api_key":    re.compile(rb"AIza[0-9A-Za-z\-_]{35}"),
    "slack_token":       re.compile(rb"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    "private_key_block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "jwt_hardcoded":     re.compile(rb"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    "url_com_senha":     re.compile(rb"(?:postgres(?:ql)?|mysql|mongodb|redis|amqp)://[^\s:/@]+:[^\s:/@]{3,}@"),
    "senha_atribuida":   re.compile(rb"(?i)\b(?:password|senha|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
}
# Ruído conhecido: placeholders e exemplos que NÃO são segredo.
INOCENTE = re.compile(rb"(?i)(xxx|placeholder|exemplo|example|dummy|fake|your[_-]|<[a-z_]+>|\bchangeme\b|senha_?aqui|user:senha|user:pass)")

# ── padrões de PII ────────────────────────────────────────────────────────
CPF   = re.compile(rb"(?<!\d)(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")
CNPJ  = re.compile(rb"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")
CNS   = re.compile(rb"(?<!\d)(\d{15})(?!\d)")
EMAIL = re.compile(rb"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Telefone SÓ com formatação humana — parênteses ou hífen. A versão sem isso
# casava coluna numérica de catálogo (a CMED tem 5 MB de números) e a varredura
# não terminava. Telefone digitado por gente vem formatado; sequência crua de
# 11 dígitos num CSV de medicamento é código de barras, não contato.
FONE  = re.compile(rb"(?:\+55\s?)?\(\d{2}\)\s?9?\d{4}[-\s]?\d{4}|(?<!\d)\d{2}\s9\d{4}-\d{4}(?!\d)")

def so_digitos(b): return re.sub(rb"\D", b"", b)

def cpf_valido(d: bytes) -> bool:
    s = d.decode()
    if len(s) != 11 or len(set(s)) == 1: return False
    for n in (9, 10):
        soma = sum(int(s[i]) * ((n + 1) - i) for i in range(n))
        dv = (soma * 10) % 11 % 10
        if dv != int(s[n]): return False
    return True

def cnpj_valido(d: bytes) -> bool:
    s = d.decode()
    if len(s) != 14 or len(set(s)) == 1: return False
    for pesos in ([5,4,3,2,9,8,7,6,5,4,3,2], [6,5,4,3,2,9,8,7,6,5,4,3,2]):
        n = len(pesos)
        soma = sum(int(s[i]) * pesos[i] for i in range(n))
        dv = 0 if soma % 11 < 2 else 11 - soma % 11
        if dv != int(s[n]): return False
    return True

# ── inventário de blobs de TODAS as refs ─────────────────────────────────
print("[gp3] listando objetos de todas as refs…", file=sys.stderr)
objetos = git("rev-list", "--objects", "--all").splitlines()
blobs = {}
for linha in objetos:
    partes = linha.split(" ", 1)
    if len(partes) == 2 and partes[1]:
        blobs.setdefault(partes[0], set()).add(partes[1])
print(f"[gp3] {len(blobs)} blobs únicos", file=sys.stderr)

BIN = re.compile(rb"\.(png|jpg|jpeg|gif|ico|pdf|zip|whl|so|dylib|db|docx|xlsx)$", re.I)

achados_seg, pulados, nao_varridos = [], [], []
TETO, TETO_SEG = 400, 50
pii = {"cpf": collections.Counter(), "cnpj": collections.Counter(),
       "cns": collections.Counter(), "email": collections.Counter(),
       "fone": collections.Counter()}
pii_onde = collections.defaultdict(set)

lote = list(blobs.keys())
proc = subprocess.Popen(["git", "-C", str(REPO), "cat-file", "--batch"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)


def _ler(sha: str):
    """Lê um objeto do `--batch`. Leitura EXATA: `read(n)` em pipe pode devolver
    menos que n, e uma leitura curta desincroniza o batch — o conteúdo do blob
    passa a ser lido como cabeçalho do próximo (aconteceu na 1ª execução)."""
    proc.stdin.write((sha + "\n").encode()); proc.stdin.flush()
    cab = proc.stdout.readline().decode("utf-8", "replace").split()
    if len(cab) < 3:
        return None                               # "<sha> missing" — sem payload
    tam = int(cab[2])

    # ⚠️ CONSUMIR SEMPRE, mesmo quando o objeto não interessa.
    #
    # `rev-list --objects --all` devolve TREES junto com blobs. A versão
    # anterior fazia `return None` para tree ANTES de ler o payload — que
    # continuava na pipe e desalinhava todas as leituras seguintes. O efeito é
    # cruel: nada falha, a leitura seguinte só BLOQUEIA esperando bytes que
    # nunca vêm, e a varredura pendura perto do fim sem dizer por quê.
    #
    # É o MESMO defeito da 1ª execução (leitura curta), num ramo que eu não
    # tinha corrigido — e por isso ele sobreviveu a dois consertos.
    buf = bytearray(); faltam = tam + 1           # +1 = o \n final do git
    while faltam > 0:
        pedaco = proc.stdout.read(faltam)
        if not pedaco:
            break
        buf += pedaco; faltam -= len(pedaco)
    if cab[1] != "blob":
        return None
    return bytes(buf[:-1])


def _escanear(dados: bytes, sha: str, caminhos: set):
    """Todas as regras sobre um blob. Tetos por ISLICE — `list(...)[:N]`
    materializa tudo antes de cortar, e num CSV de 5 MB o teto não protegia
    nada (foi o 2º travamento)."""
    for nome, rx in SEGREDOS.items():
        for m in islice(rx.finditer(dados), TETO_SEG):
            trecho = dados[max(0, m.start() - 60):m.end() + 60]
            if INOCENTE.search(trecho):
                continue
            achados_seg.append({
                "tipo": nome, "sha": sha, "caminhos": sorted(caminhos)[:3],
                "amostra": m.group(0)[:24].decode("utf-8", "replace") + "…",
            })
    for m in islice(CPF.finditer(dados), TETO):
        d = so_digitos(m.group(1))
        if len(d) == 11 and cpf_valido(d):
            pii["cpf"][d.decode()] += 1
            for c in sorted(caminhos)[:2]:
                pii_onde["cpf:" + d.decode()].add(c)
    for m in islice(CNPJ.finditer(dados), TETO):
        d = so_digitos(m.group(1))
        if len(d) == 14 and cnpj_valido(d):
            pii["cnpj"][d.decode()] += 1
            for c in sorted(caminhos)[:2]:
                pii_onde["cnpj:" + d.decode()].add(c)
    for m in islice(CNS.finditer(dados), TETO):
        pii["cns"][m.group(1).decode()] += 1
        for c in sorted(caminhos)[:2]:
            pii_onde["cns:" + m.group(1).decode()].add(c)
    for m in islice(EMAIL.finditer(dados), TETO):
        e = m.group(0).decode().lower()
        if not e.endswith((".png", ".svg", ".jpg")):
            pii["email"][e] += 1
    for m in islice(FONE.finditer(dados), TETO):
        pii["fone"][so_digitos(m.group(0)).decode()] += 1


# WATCHDOG POR BLOB. Uma expressão que retrocede muito trava a varredura sem
# dizer onde — aconteceu duas vezes aqui, e a segunda provou que proteger só as
# regras de SEGREDO não bastava: o travamento estava no bloco de PII.
# O que estourar entra no relatório como NÃO VARRIDO: auditoria que pula em
# silêncio não é auditoria (a família do "gate verde, deploy cego").
def _alarme(signum, frame):
    raise TimeoutError()


signal.signal(signal.SIGALRM, _alarme)

for i, sha in enumerate(lote):
    if i % 500 == 0:
        print(f"[gp3] {i}/{len(lote)}…", file=sys.stderr, flush=True)
    caminhos = blobs[sha]
    if caminhos and all(BIN.search(c.encode()) for c in caminhos):
        pulados.append({"sha": sha, "caminhos": sorted(caminhos)[:2], "razao": "binario_por_extensao"})
        continue
    dados = _ler(sha)
    if dados is None:
        continue                                  # árvore/commit, não blob
    if b"\0" in dados[:1024] or len(dados) > 2_000_000:
        pulados.append({"sha": sha, "tam": len(dados), "caminhos": sorted(caminhos)[:2],
                        "razao": "binario" if b"\0" in dados[:1024] else "grande"})
        continue
    signal.setitimer(signal.ITIMER_REAL, 20.0)
    try:
        _escanear(dados, sha, caminhos)
    except TimeoutError:
        nao_varridos.append({"sha": sha, "tam": len(dados), "caminhos": sorted(caminhos)[:2]})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

proc.stdin.close(); proc.wait()
print("[gp3] varredura concluída", file=sys.stderr, flush=True)

saida = {
    "escopo": {
        "refs": len(git("for-each-ref", "--format=%(refname)").splitlines()),
        "commits": int(git("rev-list", "--all", "--count").strip() or 0),
        "blobs_unicos": len(blobs),
    },
    "segredos": achados_seg,
    "pulados": pulados,
    "nao_varridos_por_tempo": nao_varridos,
    "pii": {k: dict(v.most_common(60)) for k, v in pii.items()},
    "pii_distintos": {k: len(v) for k, v in pii.items()},
    "pii_onde": {k: sorted(v)[:4] for k, v in sorted(pii_onde.items())[:400]},
}
print(json.dumps(saida, ensure_ascii=False, indent=2))
