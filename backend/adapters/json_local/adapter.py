"""
Adapter JSON Local — PicSaúde G4B
===================================
Adapter de referência: consome eventos do PicSaúde e salva em arquivo JSON.

Ciclo de vida (por execução):
  [1] Buscar eventos   GET /eventos?org_id=X&desde=<cursor>
  [2] Idempotência     verifica eventos_processados.db
  [3] Transformar      payload canônico → JSON local
  [4] Persistir        arquivo JSON por org_id
  [5] Registrar        INSERT INTO eventos_processados
  [6] ACK              POST /eventos/{id}/ack

Regra de ouro: ACK só após persistência confirmada.
Falha externa: não dá ACK — evento permanece disponível para retry.

Configuração via variáveis de ambiente:
  PICSAUDE_API_KEY     — API key institucional (X-Api-Key)
  PICSAUDE_BASE_URL    — ex: http://localhost:8080
  PICSAUDE_ORG_ID      — org_id do prestador
  ADAPTER_OUTPUT_DIR   — diretório de saída JSON (default: ./output)
  ADAPTER_DB_PATH      — SQLite local (default: ./adapter_state.db)
  ADAPTER_LIMITE       — eventos por ciclo (default: 100)

Uso:
  python3 adapter.py              # executa um ciclo
  python3 adapter.py --loop 30    # loop a cada 30 segundos
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("adapter.json_local")


# ─────────────────────────────────────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────────────────────────────────────

class Config:
    def __init__(self):
        self.api_key    = os.environ.get("PICSAUDE_API_KEY", "")
        self.base_url   = os.environ.get("PICSAUDE_BASE_URL", "http://localhost:8080").rstrip("/")
        self.org_id     = os.environ.get("PICSAUDE_ORG_ID", "")
        self.output_dir = Path(os.environ.get("ADAPTER_OUTPUT_DIR", "./output"))
        self.db_path    = os.environ.get("ADAPTER_DB_PATH", "./adapter_state.db")
        self.limite     = int(os.environ.get("ADAPTER_LIMITE", "100"))

    def validar(self):
        erros = []
        if not self.api_key:
            erros.append("PICSAUDE_API_KEY não configurada.")
        if not self.org_id:
            erros.append("PICSAUDE_ORG_ID não configurado.")
        if not self.base_url:
            erros.append("PICSAUDE_BASE_URL não configurada.")
        if erros:
            for e in erros:
                log.error(e)
            sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Estado local (idempotência + cursor)
# ─────────────────────────────────────────────────────────────────────────────

class EstadoLocal:
    """
    SQLite local para idempotência e cursor de polling.
    Completamente isolado do banco do PicSaúde.
    """

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._criar_schema()

    def _criar_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS eventos_processados (
                evento_id      TEXT PRIMARY KEY,
                processado_em  TEXT NOT NULL,
                resultado      TEXT NOT NULL    -- ok | erro | ignorado
            );
            CREATE TABLE IF NOT EXISTS cursor_polling (
                org_id     TEXT PRIMARY KEY,
                ultimo_ts  TEXT
            );
        """)
        self.conn.commit()

    def ja_processado(self, evento_id: str) -> bool:
        r = self.conn.execute(
            "SELECT 1 FROM eventos_processados WHERE evento_id = ?", (evento_id,)
        ).fetchone()
        return r is not None

    def registrar(self, evento_id: str, resultado: str):
        agora = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR IGNORE INTO eventos_processados (evento_id, processado_em, resultado) VALUES (?, ?, ?)",
            (evento_id, agora, resultado),
        )
        self.conn.commit()

    def obter_cursor(self, org_id: str) -> str | None:
        r = self.conn.execute(
            "SELECT ultimo_ts FROM cursor_polling WHERE org_id = ?", (org_id,)
        ).fetchone()
        return r["ultimo_ts"] if r else None

    def atualizar_cursor(self, org_id: str, ts: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO cursor_polling (org_id, ultimo_ts) VALUES (?, ?)",
            (org_id, ts),
        )
        self.conn.commit()

    def fechar(self):
        self.conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Cliente HTTP (sem dependências externas — só stdlib)
# ─────────────────────────────────────────────────────────────────────────────

class ClientePicSaude:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key  = api_key

    def _headers(self) -> dict:
        return {
            "X-Api-Key":    self.api_key,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def buscar_eventos(self, org_id: str, desde: str | None, limite: int) -> dict:
        params = f"org_id={org_id}&limite={limite}"
        if desde:
            params += f"&desde={desde}"
        url = f"{self.base_url}/eventos?{params}"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def ack(self, evento_id: str) -> bool:
        url = f"{self.base_url}/eventos/{evento_id}/ack"
        req = urllib.request.Request(url, data=b"", method="POST", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            log.warning("ACK falhou para %s: HTTP %s", evento_id, e.code)
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Transformador
# ─────────────────────────────────────────────────────────────────────────────

def transformar(evento: dict) -> dict:
    """
    Traduz payload canônico do PicSaúde para formato local.
    Ponto de extensão: adaptar para HIS/LIS/TISS conforme necessidade.
    """
    return {
        "evento_id":   evento["id"],
        "tipo":        evento["tipo_evento"],
        "objeto":      evento.get("objeto", {}),
        "org_id":      evento.get("org_id"),
        "unidade_id":  evento.get("unidade_id"),
        "timestamp":   evento.get("timestamp"),
        "dados":       evento.get("payload", {}),
        "_adaptado_em": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Persistência local (arquivo JSON)
# ─────────────────────────────────────────────────────────────────────────────

def persistir_json(output_dir: Path, org_id: str, evento_transformado: dict) -> bool:
    """
    Salva evento em arquivo JSON por org_id.
    Formato: output/{org_id}/eventos.jsonl (uma linha por evento)
    """
    try:
        org_dir = output_dir / org_id
        org_dir.mkdir(parents=True, exist_ok=True)
        dest = org_dir / "eventos.jsonl"
        with dest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento_transformado, ensure_ascii=False) + "\n")
        return True
    except OSError as exc:
        log.error("Erro ao persistir JSON: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Ciclo principal
# ─────────────────────────────────────────────────────────────────────────────

def executar_ciclo(cfg: Config, estado: EstadoLocal, cliente: ClientePicSaude) -> int:
    """
    Executa um ciclo de polling. Retorna número de eventos processados.
    """
    cursor = estado.obter_cursor(cfg.org_id)
    log.info("Iniciando ciclo — org_id=%s, cursor=%s", cfg.org_id, cursor or "início")

    try:
        resposta = cliente.buscar_eventos(cfg.org_id, cursor, cfg.limite)
    except Exception as exc:
        log.error("Falha ao buscar eventos: %s", exc)
        return 0

    eventos = resposta.get("eventos", [])
    if not eventos:
        log.info("Nenhum evento pendente.")
        return 0

    log.info("%d evento(s) recebido(s).", len(eventos))
    processados = 0

    for evento in eventos:
        evento_id = evento["id"]

        # [2] Idempotência
        if estado.ja_processado(evento_id):
            log.debug("Evento %s já processado — ignorando.", evento_id)
            continue

        # [3] Transformar
        try:
            transformado = transformar(evento)
        except Exception as exc:
            log.warning("Erro ao transformar evento %s: %s — ignorando.", evento_id, exc)
            estado.registrar(evento_id, "ignorado")
            continue

        # [4] Persistir
        ok = persistir_json(cfg.output_dir, cfg.org_id, transformado)
        if not ok:
            log.warning("Falha ao persistir evento %s — sem ACK.", evento_id)
            # Não registra como processado; será retentado no próximo ciclo
            continue

        # [5] Registrar localmente
        estado.registrar(evento_id, "ok")

        # [6] ACK no PicSaúde — apenas após persistência confirmada
        if not cliente.ack(evento_id):
            log.warning("ACK falhou para %s — evento pode ser reprocessado.", evento_id)
            # Idempotência local protege contra reprocessamento
        else:
            log.info("Evento %s processado e ackado.", evento_id)

        processados += 1

    # Atualizar cursor
    proximo = resposta.get("proximo_cursor")
    if proximo:
        estado.atualizar_cursor(cfg.org_id, proximo)
        log.info("Cursor atualizado para %s", proximo)

    return processados


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PicSaúde — Adapter JSON Local")
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SEGUNDOS",
        help="Executar em loop com intervalo (0 = execução única)",
    )
    args = parser.parse_args()

    cfg = Config()
    cfg.validar()

    estado  = EstadoLocal(cfg.db_path)
    cliente = ClientePicSaude(cfg.base_url, cfg.api_key)

    try:
        if args.loop > 0:
            log.info("Modo loop — intervalo: %ds", args.loop)
            while True:
                executar_ciclo(cfg, estado, cliente)
                log.info("Aguardando %ds...", args.loop)
                time.sleep(args.loop)
        else:
            n = executar_ciclo(cfg, estado, cliente)
            log.info("Ciclo concluído — %d evento(s) processado(s).", n)
    finally:
        estado.fechar()


if __name__ == "__main__":
    main()
