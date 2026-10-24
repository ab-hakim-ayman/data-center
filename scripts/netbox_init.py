#!/usr/bin/env python3
"""
NetBox Population Script for NetDevOps Lab.
Synchronizes host_vars directly into NetBox:
- Sites, Manufacturers, Device Types, Roles
- Devices, Interfaces, Loopbacks, IP Addresses
- Visual DCIM Cables between Spines and Leaves
- Device Local Context (hostname, loopbacks, interfaces, bgp_neighbors, advertised_networks)
"""

import sys
from pathlib import Path
import yaml
import pynetbox

NETBOX_URL = "http://localhost:8000"
NETBOX_TOKEN = "0123456789abcdef0123456789abcdef01234567"
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
HOST_VARS_DIR = WORKSPACE_DIR / "inventory" / "host_vars"

CABLE_TOPOLOGY = [
    ("spine1", "eth1", "leaf1", "eth1"),
    ("spine1", "eth2", "leaf2", "eth1"),
    ("spine2", "eth1", "leaf1", "eth2"),
    ("spine2", "eth2", "leaf2", "eth2"),
]


def main():
    print(f"Connecting to NetBox at {NETBOX_URL}...")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    # 1. Base Setup (Site, Manufacturer, Device Type, Roles)
    site = nb.dcim.sites.get(slug="lab-dc1") or nb.dcim.sites.create(
        name="Lab-DC1", slug="lab-dc1", status="active"
    )
    mfg = nb.dcim.manufacturers.get(slug="frrouting") or nb.dcim.manufacturers.create(
        name="FRRouting", slug="frrouting"
    )
    dt = nb.dcim.device_types.get(slug="frr-router") or nb.dcim.device_types.create(
        model="FRR-Router", slug="frr-router", manufacturer=mfg.id
    )

    roles = {
        "spine": nb.dcim.device_roles.get(slug="spine")
        or nb.dcim.device_roles.create(name="Spine", slug="spine", color="2196f3"),
        "leaf": nb.dcim.device_roles.get(slug="leaf")
        or nb.dcim.device_roles.create(name="Leaf", slug="leaf", color="4caf50"),
    }

    devices = {}
    interfaces = {}

    # 2. Iterate over all host_vars YAML files
    for host_file in sorted(HOST_VARS_DIR.glob("*.yml")):
        hostname = host_file.stem
        with open(host_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        role_name = "spine" if "spine" in hostname else "leaf"
        role = roles[role_name]

        # Get or create device
        dev = nb.dcim.devices.get(name=hostname)
        if not dev:
            dev = nb.dcim.devices.create(
                name=hostname,
                device_type=dt.id,
                role=role.id,
                site=site.id,
                status="active",
            )
            print(f"Created Device: {dev.name} ({role_name})")

        # Save exact host_vars data into local_context_data
        dev.local_context_data = data
        dev.save()
        devices[hostname] = dev

        # Loopbacks
        for lo in data.get("loopbacks", []):
            lo_name = lo["name"]
            intf = nb.dcim.interfaces.get(device_id=dev.id, name=lo_name)
            if not intf:
                intf = nb.dcim.interfaces.create(
                    device=dev.id,
                    name=lo_name,
                    type="virtual",
                    enabled=True,
                )
            interfaces[(hostname, lo_name)] = intf

            ip_str = lo["ip"]
            ip = nb.ipam.ip_addresses.get(address=ip_str)
            if not ip:
                ip = nb.ipam.ip_addresses.create(
                    address=ip_str,
                    assigned_object_type="dcim.interface",
                    assigned_object_id=intf.id,
                    status="active",
                )
            elif ip.assigned_object_id != intf.id:
                ip.assigned_object_type = "dcim.interface"
                ip.assigned_object_id = intf.id
                ip.save()

        # Physical / routed Interfaces
        for intf_item in data.get("interfaces", []):
            intf_name = intf_item["name"]
            intf = nb.dcim.interfaces.get(device_id=dev.id, name=intf_name)
            if not intf:
                intf = nb.dcim.interfaces.create(
                    device=dev.id,
                    name=intf_name,
                    type="1000base-t",
                    description=intf_item.get("description", ""),
                    enabled=True,
                )
            interfaces[(hostname, intf_name)] = intf

            ip_str = intf_item["ip"]
            ip = nb.ipam.ip_addresses.get(address=ip_str)
            if not ip:
                ip = nb.ipam.ip_addresses.create(
                    address=ip_str,
                    assigned_object_type="dcim.interface",
                    assigned_object_id=intf.id,
                    description=intf_item.get("description", ""),
                    status="active",
                )
            elif ip.assigned_object_id != intf.id:
                ip.assigned_object_type = "dcim.interface"
                ip.assigned_object_id = intf.id
                ip.save()

        print(f"Synchronized {hostname} (ASN: {data.get('bgp_asn')}, Router ID: {data.get('router_id')})")

    # 3. Cables (Visual DCIM)
    for dev_a, intf_a, dev_b, intf_b in CABLE_TOPOLOGY:
        obj_a = interfaces.get((dev_a, intf_a))
        obj_b = interfaces.get((dev_b, intf_b))
        if not obj_a or not obj_b:
            continue

        cables_a = list(nb.dcim.cables.filter(termination_a_id=obj_a.id))
        cables_b = list(nb.dcim.cables.filter(termination_b_id=obj_b.id))
        if not cables_a and not cables_b:
            try:
                cable = nb.dcim.cables.create(
                    a_terminations=[{"object_type": "dcim.interface", "object_id": obj_a.id}],
                    b_terminations=[{"object_type": "dcim.interface", "object_id": obj_b.id}],
                    status="connected",
                )
                print(f"Connected Cable: {dev_a}:{intf_a} <---> {dev_b}:{intf_b} (ID: {cable.id})")
            except Exception as e:
                print(f"Cable notice: {e}")

    print("\nNetBox synchronization completed successfully!")


if __name__ == "__main__":
    main()
