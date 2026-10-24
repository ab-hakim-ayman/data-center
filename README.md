# 🏢 Data Center Network Automation (Spine-Leaf BGP Fabric)

An automated Data Center NetDevOps lab environment on Ubuntu using Docker, Containerlab, FRRouting (FRR), Ansible, and Jinja2.

## 🏗️ Fabric Topology

```
             +-----------------+        +-----------------+
             |     spine1      |        |     spine2      |
             |   (AS 65001)    |        |   (AS 65002)    |
             |  10.255.0.1/32  |        |  10.255.0.2/32  |
             +--------+--------+        +--------+--------+
                 eth1 |  eth2               eth1 |  eth2
                      |    \                 /   |
                      |     \               /    |
                      |      \             /     |
                 eth1 |   eth1\       eth2/      | eth2
             +--------+--------+        +--------+--------+
             |      leaf1      |        |      leaf2      |
             |   (AS 65011)    |        |   (AS 65012)    |
             |  10.255.0.11/32 |        |  10.255.0.12/32 |
             +-----------------+        +-----------------+
```

### IP Scheme & Interconnects

| Link | Interface 1 | IP 1 | Interface 2 | IP 2 | Subnet |
|------|-------------|------|-------------|------|--------|
| spine1 <-> leaf1 | `spine1:eth1` | `10.0.11.1/30` | `leaf1:eth1` | `10.0.11.2/30` | `10.0.11.0/30` |
| spine1 <-> leaf2 | `spine1:eth2` | `10.0.12.1/30` | `leaf2:eth1` | `10.0.12.2/30` | `10.0.12.0/30` |
| spine2 <-> leaf1 | `spine2:eth1` | `10.0.21.1/30` | `leaf1:eth2` | `10.0.21.2/30` | `10.0.21.0/30` |
| spine2 <-> leaf2 | `spine2:eth2` | `10.0.22.1/30` | `leaf2:eth2` | `10.0.22.2/30` | `10.0.22.0/30` |

### Management Network

- **Subnet**: `172.21.20.0/24`
- **spine1**: `172.21.20.11`
- **spine2**: `172.21.20.12`
- **leaf1**: `172.21.20.21`
- **leaf2**: `172.21.20.22`

---

## 📁 Project Structure

```text
netdevops-lab/
├── ansible.cfg                    # Ansible default configs & stdout formatting
├── configs/                       # Bootstrap FRR configs & daemon files
│   ├── daemons                    # Enables zebra and bgpd daemons
│   ├── vtysh.conf                 # Integrated vtysh config
│   ├── spine1.conf                # Initial bootstrap config
│   ├── spine2.conf                # Initial bootstrap config
│   ├── leaf1.conf                 # Initial bootstrap config
│   └── leaf2.conf                 # Initial bootstrap config
├── inventory/
│   ├── hosts.ini                  # Inventory with spines & leaves (Docker connection)
│   └── host_vars/                 # Per-node BGP & interface definitions
│       ├── spine1.yml
│       ├── spine2.yml
│       ├── leaf1.yml
│       └── leaf2.yml
├── playbooks/
│   └── deploy.yml                 # Automation playbook (Jinja2 render + vtysh apply + verification)
├── templates/
│   └── frr_bgp.j2                 # Jinja2 template for FRR interfaces & BGP peering
├── topology.clab.yml              # Containerlab 4-node topology specification
└── README.md
```

---

## 🚀 Quick Commands

### 1. Inspect Fabric
```bash
clab inspect -t topology.clab.yml
```

### 2. Run Ansible Automation Playbook
```bash
ansible-playbook playbooks/deploy.yml
```

### 3. Access FRR CLI (`vtysh`)
```bash
# Access spine1 vtysh
docker exec -it clab-netdevops-lab-spine1 vtysh

# Check BGP summary
docker exec clab-netdevops-lab-leaf1 vtysh -c "show ip bgp summary"

# Check BGP routes
docker exec clab-netdevops-lab-leaf1 vtysh -c "show ip route bgp"
```

### 4. Test Data Plane Connectivity
```bash
# Ping leaf2 loopback from leaf1
docker exec clab-netdevops-lab-leaf1 ping -c 3 -I 10.255.0.11 10.255.0.12
```

### 5. Destroy the Lab
```bash
clab destroy -t topology.clab.yml
```

---

## 📊 Observability & Telemetry (Prometheus & Grafana)

The lab includes real-time telemetry running in the Containerlab fabric:

- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)
  - Scrapes metrics every 5s from all switches: BGP session states (`frr_bgp_peer_state`), prefix counts (`frr_bgp_peer_pfx_rcd`, `frr_bgp_peer_pfx_snt`), interface traffic (`frr_interface_receive_bytes_total`), and uptime.
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)
  - **Credentials**: `admin` / `admin`
  - Automated datasource provisioning configured to Prometheus at `http://172.21.20.30:9090`.

---

## 🛡️ Enterprise NetDevOps Features

1. **Atomic Reload & Auto-Rollback (`frr-reload.py` + Ansible `block/rescue`)**:
   - Replaces disruptive config reloads with atomic deltas via `/usr/lib/frr/frr-reload.py`.
   - Takes pre-change timestamped backups (`/etc/frr/frr.conf.bak`).
   - If BGP session assertion or end-to-end ping fails, the `rescue` section automatically restores the backup config and reloads FRR.
2. **Pre-Change Validation Layer**:
   - **YAML Linting**: `.yamllint` configuration.
   - **Pydantic Schema Validator**: `scripts/validate_schema.py` validates ASN ranges (1-4294967295) and IPv4/CIDR addresses before deployment.
   - **Dry-Run Diff**: `ansible-playbook playbooks/deploy.yml --check --diff` exports planned configuration changes.
3. **Secrets Management (Ansible Vault)**:
   - Sensitive router credentials encrypted with AES-256 in `inventory/group_vars/all/vault.yml`.
   - Vault password stored in `.vault_pass` (git-ignored).
4. **Pre-Deployment Control Plane Verification (Batfish)**:
   - `scripts/verify_batfish.py` runs formal control plane assertions before live push:
     - Bi-directional BGP session peering reciprocity.
     - Redundant ECMP uplinks (Leaf to Spine degree >= 2).
     - Loop-free routing on all Loopback0 interfaces.
5. **Ultra-Fast Concurrent Automation (Nornir & Scrapli)**:
   - `scripts/nornir_fabric_exec.py` leverages multithreaded Python execution (`nornir_config.yaml`).
   - Audits all fabric switches simultaneously in sub-second execution without Ansible agent overhead.
6. **Model-Driven Telemetry (gNMI & YANG)**:
   - `scripts/gnmi_telemetry.py` implements gRPC Network Management Interface (gNMI) using OpenConfig YANG data models:
     - `/interfaces/interface/state/counters` (real-time byte & packet telemetry)
     - `/network-instances/network-instance/protocols/protocol[identifier=BGP]/neighbors` (BGP telemetry streaming).
7. **Automated CI/CD**:
   - Pull Request: runs `yamllint`, Pydantic schema validation, Batfish pre-change verification, and Ansible syntax/diff check.
   - Push to `main`: live fabric deployment, concurrent post-deployment audit via Nornir, and gNMI telemetry verification.


