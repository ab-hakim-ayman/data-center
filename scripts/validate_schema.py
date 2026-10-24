#!/usr/bin/env python3
"""
NetDevOps Schema Validator for host_vars using Pydantic.
Validates BGP ASNs, IP addresses, CIDRs, interfaces, and peering models.
"""

import sys
import glob
from pathlib import Path
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
import yaml
from pydantic import BaseModel, Field, field_validator


class LoopbackConfig(BaseModel):
    name: str
    ip: str

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        try:
            IPv4Interface(v)
            return v
        except Exception as exc:
            raise ValueError(f"Invalid loopback IP/CIDR: {v}") from exc


class InterfaceConfig(BaseModel):
    name: str
    description: str
    ip: str

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        try:
            IPv4Interface(v)
            return v
        except Exception as exc:
            raise ValueError(f"Invalid interface IP/CIDR: {v}") from exc


class BGPNeighborConfig(BaseModel):
    peer_ip: str
    remote_as: int = Field(ge=1, le=4294967295)
    description: str | None = None

    @field_validator("peer_ip")
    @classmethod
    def validate_peer_ip(cls, v: str) -> str:
        try:
            IPv4Address(v)
            return v
        except Exception as exc:
            raise ValueError(f"Invalid BGP neighbor IP address: {v}") from exc


class HostVarSchema(BaseModel):
    hostname: str
    router_id: str
    bgp_asn: int = Field(ge=1, le=4294967295)
    loopbacks: list[LoopbackConfig] = []
    interfaces: list[InterfaceConfig] = []
    bgp_neighbors: list[BGPNeighborConfig] = []
    advertised_networks: list[str] = []

    @field_validator("router_id")
    @classmethod
    def validate_router_id(cls, v: str) -> str:
        try:
            IPv4Address(v)
            return v
        except Exception as exc:
            raise ValueError(f"Invalid router_id: {v}") from exc

    @field_validator("advertised_networks")
    @classmethod
    def validate_advertised_networks(cls, v: list[str]) -> list[str]:
        for net in v:
            try:
                IPv4Network(net, strict=False)
            except Exception as exc:
                raise ValueError(f"Invalid advertised network CIDR: {net}") from exc
        return v


def main():
    repo_root = Path(__file__).resolve().parent.parent
    host_vars_dir = repo_root / "inventory" / "host_vars"

    yaml_files = sorted(host_vars_dir.glob("*.yml")) + sorted(host_vars_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"ERROR: No host_vars files found in {host_vars_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Validating {len(yaml_files)} host_vars file(s) with Pydantic...")
    has_errors = False

    for file_path in yaml_files:
        rel_path = file_path.relative_to(repo_root)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                print(f"❌ {rel_path}: Expected YAML dictionary, got {type(data).__name__}")
                has_errors = True
                continue

            HostVarSchema.model_validate(data)
            print(f"✅ {rel_path}: Valid (hostname={data.get('hostname')}, ASN={data.get('bgp_asn')}, router_id={data.get('router_id')})")
        except Exception as e:
            print(f"❌ {rel_path}: Schema validation failed!\n   Error: {e}")
            has_errors = True

    if has_errors:
        print("\n❌ One or more host_vars files failed validation!", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n🎉 All host_vars passed Pydantic schema validation successfully!")


if __name__ == "__main__":
    main()
