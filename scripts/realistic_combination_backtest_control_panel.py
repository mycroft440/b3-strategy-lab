from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import webbrowser
from copy import deepcopy
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = ROOT / "data/universes/fixed_40_2018.json"
CACHE_DIR = ROOT / ".cache/control_panel"
SELECTED_UNIVERSE = CACHE_DIR / "selected_universe_combinations.json"
LOG_PATH = ROOT / "reports/control_panel_combinations.log"
REPORT_PATH = ROOT / "reports/control_panel_strategy_management_combinations.csv.gz"
EXCLUDED_TICKERS = {"BOAC34"}
MIN_START = date(2018, 1, 2)

PROGRESS_RE = re.compile(
    r"^(?P<strategy_done>\d+)/(?P<strategy_total>\d+)\s+estrategias;\s+"
    r"(?P<done>\d+)/(?P<total>\d+)\s+combinacoes;\s+"
    r"(?P<elapsed>[0-9.]+)s$"
)

STATE_LOCK = threading.Lock()
STATE: dict[str, object] = {
    "state": "idle",
    "message": "Pronto para testar todas as combinações.",
    "started_at": None,
    "finished_at": None,
    "current_step": None,
    "selected_tickers": [],
    "config": {},
    "returncode": None,
    "stop_requested": False,
    "progress_percent": 0.0,
    "progress_detail": "Aguardando início.",
    "combinations_completed": 0,
    "combinations_total": 0,
    "strategies_completed": 0,
    "strategies_total": 0,
    "elapsed_seconds": 0.0,
    "combinations_per_second": 0.0,
}
CURRENT_PROCESS: subprocess.Popen[str] | None = None


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_available_tickers(path: Path = DEFAULT_UNIVERSE) -> list[str]:
    payload = _read_json(path)
    tickers = {
        str(item).strip().upper()
        for item in payload.get("tickers", [])
        if str(item).strip()
    }
    tickers.difference_update(EXCLUDED_TICKERS)
    return sorted(tickers)


def _selected_payload(
    selected: list[str],
    base_path: Path = DEFAULT_UNIVERSE,
) -> dict[str, object]:
    base = deepcopy(_read_json(base_path))
    allowed = set(_load_available_tickers(base_path))
    normalized = sorted({item.strip().upper() for item in selected if item.strip()})
    unexpected = sorted(set(normalized) - allowed)
    if unexpected:
        raise ValueError(f"Ativos fora da lista permitida: {', '.join(unexpected)}")
    if not normalized:
        raise ValueError("Selecione pelo menos uma ação.")

    chosen = set(normalized)
    base["id"] = "control_panel_combinations_subset"
    base["selection_mode"] = "user_selected_subset_for_combination_matrix"
    base["tickers"] = normalized
    base["original_tickers"] = [
        ticker for ticker in base.get("original_tickers", [])
        if str(ticker).upper() in chosen
    ]
    base["added_tickers"] = [
        ticker for ticker in base.get("added_tickers", [])
        if str(ticker).upper() in chosen
    ]
    for field in ("issuing_company_by_ticker", "issuer_name_by_ticker", "isins_by_ticker"):
        values = base.get(field)
        if isinstance(values, dict):
            base[field] = {
                key: value for key, value in values.items()
                if str(key).upper() in chosen
            }

    base["control_panel"] = {
        "mode": "strategy_management_combinations",
        "selected_tickers": normalized,
        "no_replacements": True,
        "excluded_tickers": sorted(EXCLUDED_TICKERS),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    return base


def _parse_run_request(payload: dict[str, object]) -> dict[str, object]:
    available = set(_load_available_tickers())
    selected = sorted(
        {
            str(item).strip().upper()
            for item in payload.get("tickers", [])
            if str(item).strip()
        }
    )
    if not selected:
        raise ValueError("Selecione pelo menos uma ação.")
    unknown = sorted(set(selected) - available)
    if unknown:
        raise ValueError(f"Ações não permitidas: {', '.join(unknown)}")

    start = str(payload.get("start", MIN_START.isoformat())).strip() or MIN_START.isoformat()
    end = str(payload.get("end", "")).strip()
    start_date = date.fromisoformat(start)
    if start_date < MIN_START:
        raise ValueError(f"A data inicial mínima é {MIN_START.strftime('%d/%m/%Y')}.")
    if start_date > date.today():
        raise ValueError("A data inicial não pode estar no futuro.")
    if end:
        end_date = date.fromisoformat(end)
        if end_date < start_date:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        if end_date > date.today():
            raise ValueError("A data final não pode estar no futuro.")

    initial_cash = float(payload.get("initial_cash", 1000.0))
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("O capital inicial deve ser um valor finito maior que zero.")

    return {
        "tickers": selected,
        "start": start,
        "end": end,
        "initial_cash": initial_cash,
    }


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {message}\n")


def _set_state(**values: object) -> None:
    with STATE_LOCK:
        STATE.update(values)


def _tail(path: Path, max_chars: int = 18000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _parse_combination_progress(line: str) -> dict[str, object] | None:
    match = PROGRESS_RE.match(line.strip())
    if not match:
        return None
    done = int(match.group("done"))
    total = int(match.group("total"))
    strategy_done = int(match.group("strategy_done"))
    strategy_total = int(match.group("strategy_total"))
    elapsed = float(match.group("elapsed"))
    if total <= 0:
        return None
    percent = min(100.0, max(0.0, done / total * 100.0))
    rate = done / elapsed if elapsed > 0 else 0.0
    return {
        "progress_percent": round(percent, 2),
        "combinations_completed": done,
        "combinations_total": total,
        "strategies_completed": strategy_done,
        "strategies_total": strategy_total,
        "elapsed_seconds": elapsed,
        "combinations_per_second": rate,
        "progress_detail": (
            f"{done:,}/{total:,} combinações concluídas "
            f"({percent:.2f}%) — {strategy_done}/{strategy_total} estratégias"
        ).replace(",", "."),
    }


def _read_winner(path: Path = REPORT_PATH) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
            row = next(csv.DictReader(file), None)
        if not row:
            return None
        return {
            "rank": int(row["rank"]),
            "strategy": row["trading_strategy"],
            "management": row["management_strategy"],
            "final_equity": float(row["final_equity"]),
            "total_return": float(row["total_return"]),
            "cagr": float(row["cagr"]),
            "max_drawdown": float(row["max_drawdown"]),
            "trades": int(float(row["trades"])),
        }
    except Exception:
        return None


def _spawn(command: list[str]) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {
        "cwd": ROOT,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)  # type: ignore[arg-type]


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass


def _worker(config: dict[str, object]) -> None:
    global CURRENT_PROCESS
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text("", encoding="utf-8")
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()

        SELECTED_UNIVERSE.write_text(
            json.dumps(
                _selected_payload(list(config["tickers"])),
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        workers = max(1, min(4, os.cpu_count() or 1))
        command = [
            sys.executable,
            "scripts/backtest_strategy_management_combinations.py",
            "--universe-manifest",
            str(SELECTED_UNIVERSE.relative_to(ROOT)),
            "--start",
            str(config["start"]),
            "--initial-cash",
            str(config["initial_cash"]),
            "--signal-mode",
            "adjusted",
            "--config-set",
            "all",
            "--workers",
            str(workers),
            "--top",
            "10",
            "--output",
            str(REPORT_PATH.relative_to(ROOT)),
        ]
        if config["end"]:
            command.extend(["--end", str(config["end"])])

        _set_state(
            current_step="Testando estratégia × gerenciamento",
            message="Backtest de todas as combinações em andamento.",
            progress_detail="Carregando dados, estratégias e gerenciamentos...",
        )
        _log("=== Matriz completa de combinações ===")
        _log("$ " + " ".join(command))
        process = _spawn(command)
        CURRENT_PROCESS = process
        assert process.stdout is not None

        for line in process.stdout:
            clean = line.rstrip()
            _log(clean)
            progress = _parse_combination_progress(clean)
            if progress:
                _set_state(**progress)
            with STATE_LOCK:
                stop_requested = bool(STATE.get("stop_requested"))
            if stop_requested:
                _terminate_process(process)
                break

        code = process.wait()
        CURRENT_PROCESS = None
        with STATE_LOCK:
            stopped = bool(STATE.get("stop_requested"))
        if stopped:
            _set_state(
                state="stopped",
                message="Backtest interrompido.",
                current_step="Interrompido",
                finished_at=datetime.now(timezone.utc).isoformat(),
                returncode=code,
                progress_detail="Execução interrompida pelo usuário.",
            )
            return
        if code != 0:
            raise RuntimeError(f"Backtest das combinações falhou com código {code}.")

        winner = _read_winner()
        _set_state(
            state="success",
            message="Matriz de combinações concluída.",
            current_step="Concluído",
            finished_at=datetime.now(timezone.utc).isoformat(),
            returncode=0,
            progress_percent=100.0,
            progress_detail="Todas as combinações foram testadas.",
            winner=winner,
        )
        _log("Matriz de combinações concluída com sucesso.")
    except Exception as exc:
        CURRENT_PROCESS = None
        with STATE_LOCK:
            stopped = bool(STATE.get("stop_requested"))
        _set_state(
            state="stopped" if stopped else "error",
            message="Execução interrompida." if stopped else str(exc),
            current_step="Interrompido" if stopped else "Falha",
            finished_at=datetime.now(timezone.utc).isoformat(),
            returncode=-1,
            progress_detail="Execução interrompida." if stopped else f"Falha: {exc}",
        )
        _log(f"ERRO: {exc}")


HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel de Combinações B3</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:#172033;background:#f4f6f8}
*{box-sizing:border-box}body{margin:0}.wrap{max-width:1160px;margin:28px auto;padding:0 18px}
.hero h1{margin:0 0 6px;font-size:30px}.hero p{margin:0;color:#667085}
.grid{display:grid;grid-template-columns:1fr 1.4fr;gap:18px;margin-top:18px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:20px;box-shadow:0 8px 24px rgba(15,23,42,.05)}
.field{margin-bottom:15px}.title{display:block;font-weight:700;margin-bottom:7px}
input[type=date],input[type=number]{width:100%;border:1px solid #d0d5dd;border-radius:10px;padding:11px;font-size:15px}
.actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:10px;padding:11px 16px;font-weight:700;cursor:pointer}
.primary{background:#172033;color:white}.danger{background:#fee4e2;color:#b42318}.soft{background:#eef2f6;color:#344054}
.btn:disabled{opacity:.45;cursor:not-allowed}.stocks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;max-height:400px;overflow:auto}
.stock{display:flex;align-items:center;gap:7px;border:1px solid #eaecf0;border-radius:9px;padding:9px;font-weight:650}
.stocks-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}.hint,.count{font-size:12px;color:#667085}
.status{display:flex;align-items:center;gap:9px;margin:18px 0 8px}.dot{width:10px;height:10px;border-radius:50%;background:#98a2b3}
.running .dot{background:#f79009}.success .dot{background:#12b76a}.error .dot,.stopped .dot{background:#f04438}
.progress-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:12px}
.progress-head span{font-size:12px;color:#667085;text-align:right}.track{height:14px;background:#eaecf0;border-radius:999px;overflow:hidden;margin-top:7px}
.bar{height:100%;width:0;background:#172033;transition:width .35s ease;border-radius:999px}.running .bar{background:#f79009}.success .bar{background:#12b76a}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:13px}.metric{background:#f8fafc;border-radius:10px;padding:11px}
.metric small{display:block;color:#667085}.metric b{display:block;font-size:18px;margin-top:3px}
.winner{margin-top:13px;padding:13px;background:#f8fafc;border-radius:11px;display:none}.winner b{display:block;margin:4px 0}
.log{margin-top:12px;background:#101828;color:#d0d5dd;border-radius:12px;padding:14px;height:280px;overflow:auto;white-space:pre-wrap;font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
.notice{margin-top:14px;padding:11px 13px;background:#fff8e6;border-radius:10px;font-size:12px;color:#7a5b00}
@media(max-width:850px){.grid{grid-template-columns:1fr}.stocks{grid-template-columns:repeat(3,1fr)}.metrics{grid-template-columns:1fr}}
@media(max-width:520px){.stocks{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body><div class="wrap">
<div class="hero"><h1>Matriz de combinações B3</h1><p>Testa todas as estratégias × todos os gerenciamentos com as ações e o período escolhidos.</p></div>
<div class="grid">
<div class="card">
<div class="field"><label class="title">Data inicial</label><input id="start" type="date" min="2018-01-02" value="2018-01-02"></div>
<div class="field"><label class="title">Data final</label><input id="end" type="date" min="2018-01-02" value="__TODAY__"></div>
<div class="field"><label class="title">Capital inicial (R$)</label><input id="cash" type="number" min="1" step="100" value="1000"></div>
<div class="actions"><button id="run" class="btn primary" onclick="runBacktest()">Testar todas as combinações</button><button id="stop" class="btn danger" onclick="stopBacktest()">Parar</button></div>
<div id="statusBox" class="status idle"><span class="dot"></span><strong id="statusText">Pronto para executar.</strong></div>
<div id="step" class="hint"></div>
<div class="progress-head"><strong id="progressPercent">0%</strong><span id="progressDetail">Aguardando início.</span></div>
<div class="track"><div id="progressBar" class="bar"></div></div>
<div class="metrics">
<div class="metric"><small>Combinações</small><b id="comboCount">0 / 0</b></div>
<div class="metric"><small>Estratégias concluídas</small><b id="strategyCount">0 / 0</b></div>
<div class="metric"><small>Velocidade</small><b id="speed">—</b></div>
</div>
<div id="winner" class="winner"><small>Melhor combinação final</small><b id="winnerName"></b><span id="winnerReturn"></span></div>
<div class="notice">Esta é a matriz de pesquisa do projeto: sinais ajustados, execução conforme o motor de combinações e sem dividendos/JCP. A validação realista da combinação vencedora continua sendo uma etapa separada.</div>
</div>
<div class="card">
<div class="stocks-head"><div><strong>Ações testadas</strong><div class="count"><span id="selectedCount">0</span> selecionadas</div></div><div class="actions"><button class="btn soft" onclick="selectAll(true)">Todas</button><button class="btn soft" onclick="selectAll(false)">Limpar</button></div></div>
<div class="stocks">__TICKERS__</div>
<div class="hint" style="margin-top:12px">BOAC34 e qualquer ativo fora da lista original permanecem bloqueados. Nenhuma ação substituta é adicionada.</div>
</div>
</div>
<div class="card" style="margin-top:18px"><strong>Log</strong><div id="log" class="log">Nenhuma execução iniciada.</div></div>
</div>
<script>
const boxes=()=>[...document.querySelectorAll('.ticker')];
function refreshCount(){document.getElementById('selectedCount').textContent=boxes().filter(x=>x.checked).length}
function selectAll(v){boxes().forEach(x=>x.checked=v);refreshCount()}
boxes().forEach(x=>x.addEventListener('change',refreshCount));selectAll(true);
async function runBacktest(){
 const payload={tickers:boxes().filter(x=>x.checked).map(x=>x.value),start:document.getElementById('start').value,end:document.getElementById('end').value,initial_cash:Number(document.getElementById('cash').value)};
 const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();if(!r.ok)alert(d.error||'Falha ao iniciar');refresh();
}
async function stopBacktest(){await fetch('/api/stop',{method:'POST'});refresh()}
function money(v){return Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
function pct(v){return (Number(v)*100).toLocaleString('pt-BR',{maximumFractionDigits:2})+'%'}
function number(v){return Number(v||0).toLocaleString('pt-BR')}
async function refresh(){
 try{
  const r=await fetch('/api/status');const d=await r.json();const box=document.getElementById('statusBox');
  box.className='status '+d.state;document.getElementById('statusText').textContent=d.message||d.state;document.getElementById('step').textContent=d.current_step||'';
  const p=Math.min(100,Math.max(0,Number(d.progress_percent||0)));document.getElementById('progressPercent').textContent=p.toLocaleString('pt-BR',{maximumFractionDigits:2})+'%';
  document.getElementById('progressDetail').textContent=d.progress_detail||'';document.getElementById('progressBar').style.width=p+'%';
  document.getElementById('comboCount').textContent=number(d.combinations_completed)+' / '+number(d.combinations_total);
  document.getElementById('strategyCount').textContent=number(d.strategies_completed)+' / '+number(d.strategies_total);
  document.getElementById('speed').textContent=d.combinations_per_second?Number(d.combinations_per_second).toLocaleString('pt-BR',{maximumFractionDigits:1})+' comb/s':'—';
  document.getElementById('log').textContent=d.log||'Nenhum log.';document.getElementById('log').scrollTop=999999;
  document.getElementById('run').disabled=d.state==='running';document.getElementById('stop').disabled=d.state!=='running';
  if(d.winner){const w=document.getElementById('winner');w.style.display='block';document.getElementById('winnerName').textContent=d.winner.strategy+' + '+d.winner.management;document.getElementById('winnerReturn').textContent=money(d.winner.final_equity)+' • retorno '+pct(d.winner.total_return)+' • CAGR '+pct(d.winner.cagr)}
 }catch(e){}
}
setInterval(refresh,1000);refresh();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "B3CombinationPanel/1.0"

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            ticker_html = "".join(
                f'<label class="stock"><input class="ticker" type="checkbox" value="{ticker}" checked>{ticker}</label>'
                for ticker in _load_available_tickers()
            )
            body = (
                HTML.replace("__TICKERS__", ticker_html)
                .replace("__TODAY__", date.today().isoformat())
                .encode("utf-8")
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/status":
            with STATE_LOCK:
                state = dict(STATE)
            state["log"] = _tail(LOG_PATH)
            if state.get("state") == "success" and not state.get("winner"):
                state["winner"] = _read_winner()
            self._json(state)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/run":
            with STATE_LOCK:
                if STATE.get("state") == "running":
                    self._json({"error": "Já existe uma matriz em andamento."}, 409)
                    return
            try:
                config = _parse_run_request(self._read_body())
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
                return
            _set_state(
                state="running",
                message="Preparando matriz de combinações.",
                current_step="Carregando dados",
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=None,
                selected_tickers=config["tickers"],
                config=config,
                returncode=None,
                stop_requested=False,
                progress_percent=0.0,
                progress_detail="Carregando dados, estratégias e gerenciamentos...",
                combinations_completed=0,
                combinations_total=0,
                strategies_completed=0,
                strategies_total=0,
                elapsed_seconds=0.0,
                combinations_per_second=0.0,
                winner=None,
            )
            threading.Thread(target=_worker, args=(config,), daemon=True).start()
            self._json({"ok": True, "selected_count": len(config["tickers"])}, 202)
            return
        if path == "/api/stop":
            with STATE_LOCK:
                running = STATE.get("state") == "running"
                STATE["stop_requested"] = True
            if running and CURRENT_PROCESS is not None:
                _terminate_process(CURRENT_PROCESS)
            self._json({"ok": True, "running": running})
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Painel local para a matriz completa estratégia × gerenciamento."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    if not DEFAULT_UNIVERSE.exists():
        parser.error(f"Universo fixo não encontrado: {DEFAULT_UNIVERSE}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Painel de combinações disponível em {url}")
    print("Pressione Ctrl+C para encerrar o painel.")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if CURRENT_PROCESS is not None:
            _terminate_process(CURRENT_PROCESS)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
