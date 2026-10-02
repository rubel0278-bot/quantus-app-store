#!/usr/bin/env python3
"""Quantus Node Dashboard - API endpoints for Docker deployment."""

import requests
import os

NODE_RPC_URL = os.environ.get("NODE_RPC_URL", "http://node:9944")
MINER_METRICS_URL = os.environ.get("MINER_METRICS_URL", "http://miner:9900")


def get_node_status():
    """Query node RPC for status using verified Substrate methods."""
    try:
        # system_health returns: peers (array), isSyncing (bool), shouldHavePeers (bool)
        resp = requests.post(
            NODE_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "system_health", "params": []},
            timeout=5,
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_sync_state():
    """Query node RPC for sync state."""
    try:
        resp = requests.post(
            NODE_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "system_syncState", "params": []},
            timeout=5,
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_block_height():
    """Query node RPC for current block height."""
    try:
        resp = requests.post(
            NODE_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "chain_getBlock", "params": []},
            timeout=5,
        )
        data = resp.json()
        block_header = data.get("result", {}).get("block", {}).get("header", {})
        block_number_hex = block_header.get("number", "0x0")
        return int(block_number_hex, 16) if block_number_hex.startswith("0x") else 0
    except Exception as e:
        return f"Error: {e}"


def get_miner_metrics():
    """Query miner Prometheus metrics."""
    try:
        resp = requests.get(f"{MINER_METRICS_URL}/metrics", timeout=5)
        return resp.text
    except Exception as e:
        return f"Error: {e}"
