#!/usr/bin/env python3
"""Fallback dynamic inventory: парсит вывод `yc compute instance list --format json`.

Используется, если плагин yandex.cloud.yc не работает в текущем окружении.
Запуск: ansible-inventory -i inventory/yc_fallback.py --graph
"""

from __future__ import annotations

import json
import subprocess
import sys


def fetch_instances() -> list[dict]:
    result = subprocess.run(
        ["yc", "compute", "instance", "list", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def build_inventory(instances: list[dict]) -> dict:
    inv: dict = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}
    for inst in instances:
        if inst.get("status") != "RUNNING":
            continue
        name = inst["name"]
        nics = inst.get("network_interfaces") or []
        nat = (nics[0].get("primary_v4_address", {}).get("one_to_one_nat") or {}) if nics else {}
        ip = nat.get("address")
        if not ip:
            continue

        inv["_meta"]["hostvars"][name] = {"ansible_host": ip, "ansible_user": "ubuntu"}
        for label_key, label_val in (inst.get("labels") or {}).items():
            group = f"{label_key}_{label_val}"
            inv.setdefault(group, {"hosts": []})["hosts"].append(name)
    return inv


def main() -> int:
    if "--host" in sys.argv:
        print(json.dumps({}))
        return 0
    print(json.dumps(build_inventory(fetch_instances()), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
