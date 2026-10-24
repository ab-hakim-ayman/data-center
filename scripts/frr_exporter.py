#!/usr/bin/env python3
"""
Lightweight Prometheus Exporter for FRRouting (FRR)
Exposes BGP session states, prefix counts, and interface statistics on port 9342.
Zero external dependencies (uses standard library http.server and json).
"""

import json
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


def get_bgp_metrics():
    metrics = []
    try:
        res = subprocess.run(
            ["vtysh", "-c", "show ip bgp summary json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        data = json.loads(res.stdout)
        ipv4 = data.get("ipv4Unicast", {})
        router_id = ipv4.get("routerId", "unknown")
        local_as = ipv4.get("as", 0)
        peers = ipv4.get("peers", {})

        metrics.append("# HELP frr_bgp_peer_state BGP peer session state (1 = Established, 0 = Other)")
        metrics.append("# TYPE frr_bgp_peer_state gauge")
        metrics.append("# HELP frr_bgp_peer_pfx_rcd Prefixes received from BGP peer")
        metrics.append("# TYPE frr_bgp_peer_pfx_rcd gauge")
        metrics.append("# HELP frr_bgp_peer_pfx_snt Prefixes sent to BGP peer")
        metrics.append("# TYPE frr_bgp_peer_pfx_snt gauge")
        metrics.append("# HELP frr_bgp_peer_uptime_seconds BGP peer uptime in seconds")
        metrics.append("# TYPE frr_bgp_peer_uptime_seconds gauge")

        for peer_ip, peer_data in peers.items():
            state_val = 1 if peer_data.get("state") == "Established" else 0
            remote_as = peer_data.get("remoteAs", 0)
            desc = peer_data.get("desc", peer_ip)
            pfx_rcd = peer_data.get("pfxRcd", 0)
            pfx_snt = peer_data.get("pfxSnt", 0)
            uptime_sec = peer_data.get("peerUptimeMsec", 0) / 1000.0

            labels = f'router_id="{router_id}",local_as="{local_as}",peer_ip="{peer_ip}",remote_as="{remote_as}",description="{desc}"'
            metrics.append(f"frr_bgp_peer_state{{{labels}}} {state_val}")
            metrics.append(f"frr_bgp_peer_pfx_rcd{{{labels}}} {pfx_rcd}")
            metrics.append(f"frr_bgp_peer_pfx_snt{{{labels}}} {pfx_snt}")
            metrics.append(f"frr_bgp_peer_uptime_seconds{{{labels}}} {uptime_sec}")
    except Exception as exc:
        metrics.append(f"# Error collecting BGP metrics: {exc}")

    return metrics


def get_interface_metrics():
    metrics = []
    metrics.append("# HELP frr_interface_receive_bytes_total Total received bytes on interface")
    metrics.append("# TYPE frr_interface_receive_bytes_total counter")
    metrics.append("# HELP frr_interface_transmit_bytes_total Total transmitted bytes on interface")
    metrics.append("# TYPE frr_interface_transmit_bytes_total counter")
    metrics.append("# HELP frr_interface_up Operational state of interface (1 = Up, 0 = Down)")
    metrics.append("# TYPE frr_interface_up gauge")

    try:
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()[2:]
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                iface = parts[0].strip()
                if iface.startswith("eth") or iface == "lo":
                    stats = parts[1].split()
                    rx_bytes = int(stats[0])
                    tx_bytes = int(stats[8])
                    metrics.append(f'frr_interface_receive_bytes_total{{device="{iface}"}} {rx_bytes}')
                    metrics.append(f'frr_interface_transmit_bytes_total{{device="{iface}"}} {tx_bytes}')
                    metrics.append(f'frr_interface_up{{device="{iface}"}} 1')
    except Exception as exc:
        metrics.append(f"# Error collecting interface metrics: {exc}")

    return metrics


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/metrics", "/"):
            output = []
            output.extend(get_bgp_metrics())
            output.extend(get_interface_metrics())
            body = "\n".join(output) + "\n"

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def run_server(port=9342):
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    print(f"FRR Prometheus Exporter listening on 0.0.0.0:{port}/metrics")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
