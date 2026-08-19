from __future__ import annotations

import argparse
import json
import os
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
SELECTED_UNIVERSE = CACHE_DIR / "selected_universe.json"
LOG_PATH = ROOT / "reports/control_panel_backtest.log"
STATUS_PATH = ROOT / "reports/control_panel_realistic_pipeline_status.json"
AUDIT_PATH = ROOT / "reports/realistic_input_audit.json"
RAW_SUMMARY = ROOT / "reports/realistic_raw_gap_summary.json"
ECONOMIC_SUMMARY = ROOT / "reports/realistic_economic_gap_summary.json"
EXCLUDED_TICKERS = {"BOAC34"}

STATE_LOCK = threading.Lock()
STATE: dict[str, object] = {
    "state": "idle",
    "message": "Pronto para executar.",
    "started_at": None,
    "finished_at": None,
    "current_step": None,
    "selected_tickers": [],
    "config": {},
    "returncode": None,
    "stop_requested": False,
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


def _selected_payload(selected: list[str], base_path: Path = DEFAULT_UNIVERSE) -> dict[str, object]:
    base = deepcopy(_read_json(base_path))
    allowed = set(_load_available_tickers(base_path))
    normalized = sorted({item.strip().upper() for item in selected if item.strip()})
    unexpected = sorted(set(normalized) - allowed)
    if unexpected:
        raise ValueError(f"Ativos fora da lista permitida: {', '.join(unexpected)}")
    if not normalized:
        raise ValueError("Selecione pelo menos uma ação.")

    chosen = set(normalized)
    base["id"] = "control_panel_subset_of_fixed_40_2018"
    base["selection_mode"] = "user_selected_subset_from_existing_fixed_universe"
    base["tickers"] = normalized
    base["original_tickers"] = [
        ticker for ticker in base.get("original_tickers", []) if str(ticker).upper() in chosen
    ]
    base["added_tickers"] = [
        ticker for ticker in base.get("added_tickers", []) if str(ticker).upper() in chosen
    ]
    for field in ("issuing_company_by_ticker", "issuer_name_by_ticker", "isins_by_ticker"):
        values = base.get(field)
        if isinstance(values, dict):
            base[field] = {
                key: value for key, value in values.items() if str(key).upper() in chosen
            }
    base["control_panel"] = {
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

    start = str(payload.get("start", "2018-01-02")).strip() or "2018-01-02"
    end = str(payload.get("end", "")).strip()
    start_date = date.fromisoformat(start)
    if end:
        end_date = date.fromisoformat(end)
        if end_date < start_date:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        if end_date > date.today():
            raise ValueError("A data final não pode estar no futuro.")
    if start_date > date.today():
        raise ValueError("A data inicial não pode estar no futuro.")

    initial_cash = float(payload.get("initial_cash", 1000.0))
    if initial_cash <= 0:
        raise ValueError("O capital inicial deve ser maior que zero.")

    return {
        "tickers": selected,
        "start": start,
        "end": end,
        "initial_cash": initial_cash,
        "download": bool(payload.get("download", True)),
    }


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {message}\n")


def _set_state(**values: object) -> None:
    with STATE_LOCK:
        STATE.update(values)


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


def _run_command(step: str, command: list[str], accepted_codes: set[int] | None = None) -> int:
    global CURRENT_PROCESS
    accepted = accepted_codes or {0}
    _set_state(current_step=step, message=step)
    _log(f"=== {step} ===")
    _log("$ " + " ".join(command))
    process = _spawn(command)
    CURRENT_PROCESS = process
    assert process.stdout is not None
    for line in process.stdout:
        _log(line.rstrip())
        with STATE_LOCK:
            stop_requested = bool(STATE.get("stop_requested"))
        if stop_requested:
            _terminate_process(process)
            break
    code = process.wait()
    CURRENT_PROCESS = None
    if code not in accepted:
        raise RuntimeError(f"{step} falhou com código {code}.")
    return code


def _compose_status(config: dict[str, object]) -> dict[str, object]:
    audit = _read_json(AUDIT_PATH)
    raw = _read_json(RAW_SUMMARY)
    economic = _read_json(ECONOMIC_SUMMARY)
    return {
        "schema_version": 1,
        "source": "control_panel",
        "selected_tickers": config["tickers"],
        "selected_count": len(config["tickers"]),
        "start": config["start"],
        "end_requested": config["end"] or None,
        "initial_cash": config["initial_cash"],
        "no_replacements": True,
        "excluded_tickers": sorted(EXCLUDED_TICKERS),
        "input_audit": audit,
        "raw_gap": raw,
        "economic_gap": economic,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _worker(config: dict[str, object]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text("", encoding="utf-8")
        for stale in (STATUS_PATH, RAW_SUMMARY, ECONOMIC_SUMMARY):
            if stale.exists():
                stale.unlink()

        selected_payload = _selected_payload(list(config["tickers"]))
        SELECTED_UNIVERSE.write_text(
            json.dumps(selected_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        python = sys.executable
        common_end = ["--end", str(config["end"])] if config["end"] else []
        download = bool(config["download"])

        build = [
            python,
            "scripts/build_point_in_time_universe.py",
            "--allowed-universe",
            str(SELECTED_UNIVERSE.relative_to(ROOT)),
            "--start",
            str(config["start"]),
            *common_end,
        ]
        if download:
            build.append("--download")
        _run_command("1/6 Preparando ações e período", build)

        transitions = [python, "scripts/build_ticker_transitions.py"]
        if download:
            transitions.append("--download")
        _run_command("2/6 Verificando mudanças de ticker", transitions)

        sync = [python, "scripts/sync_point_in_time_universe_realistic.py"]
        if download:
            sync.extend(["--download", "--refresh-actions"])
        _run_command("3/6 Sincronizando dados e proventos", sync)

        _run_command(
            "4/6 Auditando dados",
            [python, "scripts/audit_realistic_backtest_inputs.py"],
            accepted_codes={0, 2},
        )
        audit = _read_json(AUDIT_PATH)
        if not audit.get("ready_for_realistic_estimate"):
            raise RuntimeError(
                "A auditoria não liberou o backtest. Bloqueios: "
                + ", ".join(str(item) for item in audit.get("blockers", []))
            )

        common_backtest = [
            "--start",
            str(config["start"]),
            "--initial-cash",
            str(config["initial_cash"]),
            "--selection-status",
            "retrospective_hypothesis_replay",
            *common_end,
        ]
        _run_command(
            "5/6 Executando raw_gap",
            [
                python,
                "scripts/backtest_strategy_management_realistic.py",
                *common_backtest,
                "--output",
                str(RAW_SUMMARY.relative_to(ROOT)),
                "--curve-output",
                "reports/realistic_raw_gap_curve.csv",
                "--trades-output",
                "reports/realistic_raw_gap_trades.csv",
                "--cash-ledger-output",
                "reports/realistic_raw_gap_distributions.csv",
                "--tax-output",
                "reports/realistic_raw_gap_tax.csv",
            ],
        )
        _run_command(
            "6/6 Executando economic_gap",
            [
                python,
                "scripts/backtest_strategy_management_realistic.py",
                *common_backtest,
                "--economic-gap-adjustment",
                "--output",
                str(ECONOMIC_SUMMARY.relative_to(ROOT)),
                "--curve-output",
                "reports/realistic_economic_gap_curve.csv",
                "--trades-output",
                "reports/realistic_economic_gap_trades.csv",
                "--cash-ledger-output",
                "reports/realistic_economic_gap_distributions.csv",
                "--tax-output",
                "reports/realistic_economic_gap_tax.csv",
            ],
        )

        status = _compose_status(config)
        STATUS_PATH.write_text(
            json.dumps(status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _set_state(
            state="success",
            message="Backtest concluído com sucesso.",
            current_step="Concluído",
            finished_at=datetime.now(timezone.utc).isoformat(),
            returncode=0,
        )
        _log("Backtest concluído com sucesso.")
    except Exception as exc:
        with STATE_LOCK:
            stopped = bool(STATE.get("stop_requested"))
        _set_state(
            state="stopped" if stopped else "error",
            message="Execução interrompida." if stopped else str(exc),
            current_step="Interrompido" if stopped else "Falha",
            finished_at=datetime.now(timezone.utc).isoformat(),
            returncode=-1,
        )
        _log(f"ERRO: {exc}")


def _tail(path: Path, max_chars: int = 16000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _result_summary() -> dict[str, object] | None:
    if not STATUS_PATH.exists():
        return None
    try:
        payload = _read_json(STATUS_PATH)
        raw = payload.get("raw_gap", {})
        economic = payload.get("economic_gap", {})
        return {
            "selected_count": payload.get("selected_count"),
            "selected_tickers": payload.get("selected_tickers"),
            "raw_final_equity": raw.get("final_equity") if isinstance(raw, dict) else None,
            "raw_total_return": raw.get("total_return") if isinstance(raw, dict) else None,
            "economic_final_equity": economic.get("final_equity") if isinstance(economic, dict) else None,
            "economic_total_return": economic.get("total_return") if isinstance(economic, dict) else None,
        }
    except Exception:
        return None


HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel de Backtest B3</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:#172033;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1120px;margin:30px auto;padding:0 18px}.hero{margin-bottom:18px}.hero h1{margin:0 0 6px;font-size:30px}.hero p{margin:0;color:#667085}.grid{display:grid;grid-template-columns:1fr 1.45fr;gap:18px}.card{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:20px;box-shadow:0 8px 24px rgba(15,23,42,.05)}label.title{display:block;font-weight:700;margin-bottom:8px}.field{margin-bottom:16px}input[type=date],input[type=number]{width:100%;border:1px solid #d0d5dd;border-radius:10px;padding:11px;font-size:15px}.actions{display:flex;gap:8px;flex-wrap:wrap}.btn{border:0;border-radius:10px;padding:11px 16px;font-weight:700;cursor:pointer}.primary{background:#172033;color:white}.danger{background:#fee4e2;color:#b42318}.soft{background:#eef2f6;color:#344054}.btn:disabled{opacity:.45;cursor:not-allowed}.stocks-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.count{font-size:13px;color:#667085}.stocks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;max-height:390px;overflow:auto}.stock{display:flex;align-items:center;gap:7px;border:1px solid #eaecf0;border-radius:9px;padding:9px;font-weight:650}.status{display:flex;align-items:center;gap:9px;margin:18px 0 8px}.dot{width:10px;height:10px;border-radius:50%;background:#98a2b3}.running .dot{background:#f79009}.success .dot{background:#12b76a}.error .dot,.stopped .dot{background:#f04438}.result{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:12px}.metric{background:#f8fafc;border-radius:10px;padding:12px}.metric b{display:block;font-size:19px;margin-top:4px}.log{margin-top:12px;background:#101828;color:#d0d5dd;border-radius:12px;padding:14px;height:270px;overflow:auto;white-space:pre-wrap;font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}.hint{font-size:12px;color:#667085;margin-top:6px}@media(max-width:850px){.grid{grid-template-columns:1fr}.stocks{grid-template-columns:repeat(3,1fr)}}@media(max-width:520px){.stocks{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body><div class="wrap">
<div class="hero"><h1>Painel de Backtest B3</h1><p>Escolha as ações, o período e o capital. Nenhuma ação fora da lista original será adicionada.</p></div>
<div class="grid">
<div class="card">
<div class="field"><label class="title">Data inicial</label><input id="start" type="date" value="2018-01-02"></div>
<div class="field"><label class="title">Data final</label><input id="end" type="date" value="__TODAY__"></div>
<div class="field"><label class="title">Capital inicial (R$)</label><input id="cash" type="number" min="1" step="100" value="1000"></div>
<div class="field"><label><input id="download" type="checkbox" checked> Atualizar dados da B3 antes de testar</label><div class="hint">Desmarque apenas se os dados já estiverem em cache.</div></div>
<div class="actions"><button id="run" class="btn primary" onclick="runBacktest()">Iniciar backtest</button><button id="stop" class="btn danger" onclick="stopBacktest()">Parar</button></div>
<div id="statusBox" class="status idle"><span class="dot"></span><strong id="statusText">Pronto para executar.</strong></div>
<div id="step" class="hint"></div>
<div id="result" class="result"></div>
</div>
<div class="card">
<div class="stocks-head"><div><strong>Ações testadas</strong><div class="count"><span id="selectedCount">0</span> selecionadas</div></div><div class="actions"><button class="btn soft" onclick="selectAll(true)">Todas</button><button class="btn soft" onclick="selectAll(false)">Limpar</button></div></div>
<div class="stocks">__TICKERS__</div>
<div class="hint" style="margin-top:12px">BOAC34 e qualquer ativo fora da lista fixa permanecem bloqueados. Se uma ação selecionada não tiver dados válidos em determinada semana, o teste usa apenas as disponíveis, sem reposição.</div>
</div>
</div>
<div class="card" style="margin-top:18px"><strong>Log da execução</strong><div id="log" class="log">Nenhuma execução iniciada.</div></div>
</div>
<script>
const boxes=()=>[...document.querySelectorAll('.ticker')];
function refreshCount(){document.getElementById('selectedCount').textContent=boxes().filter(x=>x.checked).length}
function selectAll(value){boxes().forEach(x=>x.checked=value);refreshCount()}
boxes().forEach(x=>x.addEventListener('change',refreshCount));selectAll(true);
async function runBacktest(){
 const payload={tickers:boxes().filter(x=>x.checked).map(x=>x.value),start:document.getElementById('start').value,end:document.getElementById('end').value,initial_cash:Number(document.getElementById('cash').value),download:document.getElementById('download').checked};
 const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)alert(d.error||'Falha ao iniciar');refresh();
}
async function stopBacktest(){await fetch('/api/stop',{method:'POST'});refresh()}
function money(v){if(v===null||v===undefined)return '—';return Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
function pct(v){if(v===null||v===undefined)return '—';const n=Number(v)*100;return n.toLocaleString('pt-BR',{maximumFractionDigits:2})+'%'}
async function refresh(){
 try{const r=await fetch('/api/status');const d=await r.json();const box=document.getElementById('statusBox');box.className='status '+d.state;document.getElementById('statusText').textContent=d.message||d.state;document.getElementById('step').textContent=d.current_step||'';document.getElementById('log').textContent=d.log||'Nenhum log.';document.getElementById('log').scrollTop=999999;document.getElementById('run').disabled=d.state==='running';document.getElementById('stop').disabled=d.state!=='running';
 if(d.result){document.getElementById('result').innerHTML=`<div class="metric">raw_gap final<b>${money(d.result.raw_final_equity)}</b><span>${pct(d.result.raw_total_return)}</span></div><div class="metric">economic_gap final<b>${money(d.result.economic_final_equity)}</b><span>${pct(d.result.economic_total_return)}</span></div>`}
 }catch(e){}
}
setInterval(refresh,1500);refresh();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "B3BacktestPanel/1.0"

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
            state["result"] = _result_summary()
            self._json(state)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/run":
            with STATE_LOCK:
                if STATE.get("state") == "running":
                    self._json({"error": "Já existe um backtest em andamento."}, 409)
                    return
            try:
                config = _parse_run_request(self._read_body())
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
                return
            _set_state(
                state="running",
                message="Backtest iniciado.",
                current_step="Preparando execução",
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=None,
                selected_tickers=config["tickers"],
                config=config,
                returncode=None,
                stop_requested=False,
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
    parser = argparse.ArgumentParser(description="Painel web local para o backtest realista da B3.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    if not DEFAULT_UNIVERSE.exists():
        parser.error(f"Universo fixo não encontrado: {DEFAULT_UNIVERSE}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Painel disponível em {url}")
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
