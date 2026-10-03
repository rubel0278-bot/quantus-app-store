#!/usr/bin/env python3
"""Quantus Node dashboard - live UI for 5tratOS."""

import json
import os
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

NODE_RPC_URL = os.environ.get("NODE_RPC_URL", "http://node:9944")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CONFIG_FILE = DATA_DIR / "quantus-node.env"
SETTINGS_FILE = DATA_DIR / "dashboard-settings.json"


def rpc(method, params=None, rid=1):
    resp = requests.post(
        NODE_RPC_URL,
        json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or []},
        timeout=5,
    )
    return resp.json().get("result", {})


def read_settings():
    defaults = {
        "solo_mining_enabled": True,
        "pool_mining_enabled": False,
        "solo_payout_address": "",
        "pool_stratum_host": "",
        "pool_stratum_port": "3333",
        "pool_payout_address": "",
        "pool_min_difficulty": "1024",
        "pool_max_difficulty": "131072",
        "pool_preset": "MIXED DEFAULT",
    }
    try:
        if SETTINGS_FILE.exists():
            defaults.update(json.loads(SETTINGS_FILE.read_text()))
    except Exception:
        pass
    return defaults


def write_settings(settings):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
    except Exception as exc:
        raise RuntimeError(str(exc))


def node_running_info():
    try:
        health = rpc("system_health")
        block = rpc("chain_getBlock", rid=2)
        header = block.get("block", {}).get("header", {})
        number_hex = header.get("number", "0x0")
        height = int(number_hex, 16) if str(number_hex).startswith("0x") else 0
        peers_raw = health.get("peers", [])
        peers = len(peers_raw) if isinstance(peers_raw, list) else (peers_raw if isinstance(peers_raw, int) else 0)
        is_syncing = bool(health.get("isSyncing", False))
        sync_state = rpc("system_syncState", rid=3)
        best_block = sync_state.get("bestBlock") or sync_state.get("bestBlockNumber") or height
        try:
            finalized_hash = rpc("chain_getFinalizedHead", rid=4)
            finalized_header = rpc("chain_getHeader", params=[finalized_hash], rid=5)
            finalized_hex = finalized_header.get("number", "0x0")
            finalized = int(finalized_hex, 16) if str(finalized_hex).startswith("0x") else 0
        except Exception:
            finalized = 0
        try:
            best = int(str(best_block), 0)
        except Exception:
            best = height
        sync_percentage = None
        if not is_syncing and best > 0 and height > 0 and height >= best - 2:
            sync_percentage = 100
        elif best > 0 and height > 0:
            sync_percentage = min(99, max(0, int(height / best * 100)))
        return {
            "status": "running",
            "state": "Synchronized 100%" if sync_percentage == 100 else ("Syncing" if is_syncing else "Starting"),
            "badge": "Synced" if sync_percentage == 100 else ("Syncing" if is_syncing else "Starting"),
            "sync_percentage": sync_percentage,
            "chain": "mainnet",
            "block_height": height,
            "headers": height,
            "finalized_block": finalized,
            "best_block": height,
            "peers": peers,
            "isSyncing": is_syncing,
            "shouldHavePeers": bool(health.get("shouldHavePeers", False)),
            "chain_lag": "0 / 0",
            "mempool": "-",
            "disk": "-",
            "last_block": f"#{height}" if height > 0 else None,
            "last_block_age": "?",
            "solo_port": "9333",
            "solo_workers": "-",
            "solo_hashrate": "-",
            "readiness_pills": ["Node: " + ("Syncing" if is_syncing else "Synced"), "Pool: Standalone", "Stratum: Unknown"],
            "checklist": [
                {"title": "Quantus node", "ready": True, "detail": "Node RPC is reachable."},
                {"title": "Node RPC", "ready": True, "detail": "JSON-RPC is responding."},
                {"title": "Blockchain sync", "ready": sync_percentage == 100, "detail": "Syncing." if is_syncing else "Synced."},
                {"title": "Mining mode", "ready": bool(read_settings().get("solo_mining_enabled", True)) or bool(read_settings().get("pool_mining_enabled", False)), "detail": "Solo or pool mode configured."},
                {"title": "Miner backend", "ready": False, "detail": "No pool backend currently exposed."},
                {"title": "Required configuration", "ready": CONFIG_FILE.exists(), "detail": "Runtime config persisted under /data."},
            ],
        }
    except Exception as exc:
        return {"status": "error", "state": "Error", "badge": "Error", "sync_percentage": None, "error": str(exc)}


@app.route("/")
def index():
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quantus Node</title>
<style>
body{margin:0;background:#050505;color:#f6f6f6;font-family:Inter,system-ui,sans-serif}
.shell{max-width:1100px;margin:0 auto;padding:28px}
.header{display:flex;gap:14px;align-items:center;justify-content:space-between;margin-bottom:24px}
.badge{border:1px solid #f9d268;color:#f9d268;border-radius:999px;padding:3px 10px;font-size:12px}
.tabs{display:flex;gap:18px;border-bottom:1px solid #242424;padding-bottom:8px;margin-bottom:24px;overflow-x:auto}
.tab{padding:8px 12px;border-radius:999px;cursor:pointer;color:#ddd}
.tab.active{background:#151515;color:#f9d268;border:1px solid #f9d268}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.card{background:linear-gradient(180deg,#161616,#111);border:1px solid #2b2b2b;border-radius:18px;padding:18px;box-shadow:0 0 0 1px #000}
.card h3{margin:0 0 14px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#aaa}
.big{font-size:34px;font-weight:800}
.metric{background:#1b1b1b;border:1px solid #272727;border-radius:14px;padding:14px}
.metric label{display:block;color:#888;font-size:11px;text-transform:uppercase}
.metric .val{font-size:22px;font-weight:700;margin-top:6px}
.row{display:flex;gap:10px;flex-wrap:wrap}
.pill{border:1px solid #343434;border-radius:999px;padding:6px 10px;color:#bbb;font-size:12px}
.panel{display:none}
.panel.active{display:block}
.toggle{display:flex;align-items:center;gap:10px;margin:10px 0}
input[type=checkbox]{width:18px;height:18px}
button{background:#f9d268;color:#111;border:0;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}
button.secondary{background:#222;color:#eee;border:1px solid #333}
.small{color:#888;font-size:12px;margin-top:8px}
</style>
</head>
<body>
<div class="shell">
  <div class="header">
    <div>
      <h1>Quantus Node v1.0.2</h1>
      <div>Quantus Network node with optional solo mining</div>
    </div>
    <div id="syncBadge" class="badge">Syncing</div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="showTab('home')">Home</div>
    <div class="tab" onclick="showTab('pool')">Pool</div>
    <div class="tab" onclick="showTab('luck')">Luck</div>
    <div class="tab" onclick="showTab('blocks')">Blocks</div>
    <div class="tab" onclick="showTab('settings')">Settings</div>
    <div class="tab" onclick="showTab('project')">Project</div>
  </div>

  <div id="home" class="panel active">
    <div class="card" style="border-color:#2e8f5b;background:linear-gradient(180deg,#111,#0d0d0d);border-radius:24px;padding:22px;margin-bottom:18px">
      <div class="grid" style="grid-template-columns:2fr 1fr;gap:18px">
        <div>
          <div class="small" style="font-weight:700;text-transform:none;color:#f4f4f4">Blockchain</div>
          <h1 id="syncText" style="font-size:42px;margin:8px 0 4px;line-height:1.1">Loading...</h1>
          <div class="small" id="chainMeta" style="color:#aaa"></div>
          <div class="small" id="lastBlockLine" style="margin-top:8px;color:#b5b5b5"></div>
          <div class="small" style="margin-top:6px;color:#8c8c8c">Changes require an app restart to apply.</div>
        </div>
        <div style="display:flex;align-items:center;justify-content:center">
          <div style="width:150px;height:150px;border-radius:50%;border:10px solid #2c2c2c;border-top-color:#f7a11a;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:800" id="syncCircle">-</div>
        </div>
      </div>
      <div style="height:18px"></div>
      <div style="display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:12px">
        <div class="metric"><label>Blocks</label><div class="val" id="blocks">-</div></div>
        <div class="metric"><label>Headers</label><div class="val" id="headers">-</div></div>
        <div class="metric"><label>Peers</label><div class="val" id="peers">-</div></div>
        <div class="metric"><label>Chain lag</label><div class="val" id="chainLag">-</div></div>
        <div class="metric"><label>Mempool</label><div class="val" id="mempool">-</div></div>
        <div class="metric"><label>Disk</label><div class="val" id="disk">-</div></div>
      </div>
    </div>

    <div class="card" style="border-color:#2e8f5b;background:linear-gradient(180deg,#111,#0d0d0d);border-radius:24px;padding:22px;margin-bottom:18px">
      <h3>Solo Pool</h3>
      <div class="small" style="color:#bbb;margin-bottom:12px">Stratum v1</div>
      <div class="row">
        <div class="metric"><label>Port</label><div class="val" id="soloPort">9333</div></div>
        <div class="metric"><label>Workers</label><div class="val" id="soloWorkers">-</div></div>
        <div class="metric"><label>Hashrate</label><div class="val" id="soloHashrate">-</div></div>
      </div>
      <div style="height:12px"></div>
      <button onclick="showTab('pool')" class="secondary" style="border:1px solid #f9d268;background:#1b1b1b;color:#f9d268">Open Pool</button>
    </div>

    <div class="card" style="border-color:#2e8f5b;background:linear-gradient(180deg,#111,#0d0d0d);border-radius:24px;padding:22px">
      <h3>Readiness</h3>
      <div class="small" style="color:#aaa;margin-bottom:12px">Direct visibility into what is blocking the node and pool.</div>
      <div class="row" id="readinessPills"></div>
      <div style="height:14px"></div>
      <div id="checklist" style="display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:12px"></div>
    </div>
  </div>

  <div id="pool" class="panel">
    <div class="card">
      <h3>Pool mining</h3>
      <div class="row">
        <div class="metric"><label>Stratum host</label><div class="val" id="poolHost">-</div></div>
        <div class="metric"><label>Stratum port</label><div class="val" id="poolPort">-</div></div>
        <div class="metric"><label>Preset</label><div class="val" id="poolPreset">-</div></div>
      </div>
      <div style="height:12px"></div>
      <button onclick="saveSettings()">Save pool settings</button>
    </div>
  </div>

  <div id="luck" class="panel">
    <div class="card"><h3>Luck</h3><div class="small">No found blocks yet. Waiting for first block.</div><div style="height:10px"></div><div class="big">0%</div></div>
  </div>

  <div id="blocks" class="panel">
    <div class="card"><h3>Blocks</h3><div class="small">No blocks found by local solo pool yet.</div><div style="height:10px"></div><div class="big" id="blocksCount">0</div></div>
  </div>

  <div id="settings" class="panel">
    <div class="card">
      <h3>Node settings</h3>
      <div class="toggle"><input type="checkbox" id="settingsSolo"><label for="settingsSolo">Solo mining active</label></div>
      <div class="toggle"><input type="checkbox" id="settingsPool"><label for="settingsPool">Pool mining active</label></div>
      <button onclick="saveSettings()">Save settings</button>
      <div class="small">Saved to the persistent app data directory. Restart the app to apply mining mode changes.</div>
    </div>
  </div>

  <div id="project" class="panel">
    <div class="card"><h3>Project</h3><div class="small">Official Quantus Network chain repository and node binary.</div><div class="small">https://github.com/Quantus-Network/chain</div></div>
  </div>
</div>
<script>
function showTab(id){document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.getElementById(id).classList.add('active');event.currentTarget.classList.add('active')}
async function loadStatus(){try{let r=await fetch('/api/status');let j=await r.json();document.getElementById('syncText').textContent=j.state;document.getElementById('syncCircle').textContent=j.sync_percentage===null?'-':(j.sync_percentage+'%');document.getElementById('syncBadge').textContent=j.badge;document.getElementById('blocks').textContent=j.block_height??'-';document.getElementById('headers').textContent=j.headers??'-';document.getElementById('peers').textContent=j.peers??'-';document.getElementById('chainLag').textContent=j.chain_lag??'-';document.getElementById('mempool').textContent=j.mempool??'-';document.getElementById('disk').textContent=j.disk??'-';document.getElementById('chainMeta').textContent=(j.chain||'main')+' | peers '+j.peers+' | finalized #'+(j.finalized_block??'-');document.getElementById('lastBlockLine').textContent=j.last_block?('Best '+j.last_block+' | Finalized #'+(j.finalized_block??'-')+' | Peers '+j.peers):'';document.getElementById('soloPort').textContent=j.solo_port??'9333';document.getElementById('soloWorkers').textContent=j.solo_workers??'-';document.getElementById('soloHashrate').textContent=j.solo_hashrate??'-';document.getElementById('readinessPills').innerHTML=(j.readiness_pills||[]).map(p=>'<span class="pill">'+p+'</span>').join('');document.getElementById('checklist').innerHTML=(j.checklist||[]).map(c=>'<div class="metric"><label>'+c.title+'</label><div class="val" style="color:'+(c.ready?'#00ff88':'#ffaa00')+'">'+(c.ready?'Ready':'Needs attention')+'</div><div class="small">'+c.detail+'</div></div>').join('');document.getElementById('miningMode').textContent=j.solo_mining?'Solo':'Off';document.getElementById('soloState').textContent=j.solo_mining?'Active':'Inactive';document.getElementById('poolState').textContent=j.pool_mining?'Active':'Inactive';document.getElementById('soloToggle').checked=j.solo_mining;document.getElementById('poolToggle').checked=j.pool_mining;document.getElementById('settingsSolo').checked=j.solo_mining;document.getElementById('settingsPool').checked=j.pool_mining}catch(e){}}
async function loadSettings(){let r=await fetch('/api/settings');let s=await r.json();document.getElementById('poolHost').textContent=s.pool_stratum_host||'-';document.getElementById('poolPort').textContent=s.pool_stratum_port||'-';document.getElementById('poolPreset').textContent=s.pool_preset||'-'}
async function saveSettings(){let s={solo_mining_enabled:document.getElementById('settingsSolo').checked,pool_mining_enabled:document.getElementById('settingsPool').checked};await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});loadSettings();loadStatus();alert('Settings saved. Restart the app to apply mining mode changes.')}
setInterval(loadStatus,3000);loadStatus();loadSettings();
</script>
</body>
</html>
"""


@app.route("/api/status")
def api_status():
    info = node_running_info()
    settings = read_settings()
    info["solo_mining"] = bool(settings.get("solo_mining_enabled"))
    info["pool_mining"] = bool(settings.get("pool_mining_enabled"))
    return jsonify(info)


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    settings = read_settings()
    if request.method == "POST":
        changes = request.get_json(silent=True) or {}
        for key in ["solo_mining_enabled", "pool_mining_enabled", "pool_stratum_host", "pool_stratum_port", "pool_payout_address", "pool_min_difficulty", "pool_max_difficulty", "pool_preset"]:
            if key in changes:
                settings[key] = changes[key]
        write_settings(settings)
    return jsonify(settings)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
