"""Extract route declarations for the finite B01-B08 acceptance matrix."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
API = ROOT / "backend" / "app" / "api" / "v1" / "routers"
FILES = [
    "organization.py", "locations.py", "catalog.py", "product_master.py",
    "branch_product_demand.py", "inventory.py", "inventory_lots.py",
    "inventory_labels.py", "inventory_trace.py", "inventory_transfers.py",
    "inventory_adjustments.py", "inventory_kardex.py", "inventory_valuation.py",
    "inventory_putaway_groups.py", "purchase_requests.py", "purchase_consolidations.py",
    "purchase_quotations.py", "purchase_orders.py", "purchases.py", "retaceos.py",
    "sales.py", "documents.py", "document_general.py",
]


def strings(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def permission_calls(node: ast.AST) -> list[str]:
    result: list[str] = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        name = n.func.id if isinstance(n.func, ast.Name) else (
            n.func.attr if isinstance(n.func, ast.Attribute) else ""
        )
        if name in {"require_permission", "require_any_permission"}:
            values = list(strings(n))
            result.extend(v for v in values if ":" in v)
    return sorted(set(result))


def main() -> None:
    print("METHOD\tPATH\tHANDLER\tDECLARED_PERMISSION\tINTERNAL_PERMISSION_LITERALS\tSCOPE_MARKERS")
    for filename in FILES:
        path = API / filename
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = ""
        router_dependencies: list[str] = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                value = node.value
                if isinstance(target, ast.Name) and target.id == "router" and isinstance(value, ast.Call):
                    for kw in value.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            prefix = str(kw.value.value)
                        if kw.arg == "dependencies":
                            router_dependencies = permission_calls(kw.value)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                if not isinstance(dec.func.value, ast.Name) or dec.func.value.id != "router":
                    continue
                method = dec.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                route = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else ""
                declared = sorted(set(router_dependencies + permission_calls(dec)))
                internal: set[str] = set()
                scope: set[str] = set()
                for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                    name = call.func.id if isinstance(call.func, ast.Name) else (
                        call.func.attr if isinstance(call.func, ast.Attribute) else ""
                    )
                    if name in {"_require_dynamic_permission", "require_permission", "require_any_permission"}:
                        internal.update(v for v in strings(call) if ":" in v)
                    if name in {"resolve_branch_scope", "require_company_access", "require_company_wide_scope", "_transfer_branch_scope", "_authorize_origin_warehouse", "_authorize_demand_branch", "_require_headquarters_scope"}:
                        scope.add(name)
                    if name in {"execute"} and isinstance(call.func, ast.Attribute):
                        if any(isinstance(x, ast.Name) and x.id in {"checker", "permission_checker"} for x in ast.walk(call.func.value)):
                            internal.update(v for v in strings(call) if ":" in v)
                full_path = "/api/v1" + prefix + route
                print("\t".join((method, full_path, f"{filename}:{node.name}", ",".join(declared) or "(sin guardia declarada aquí)", ",".join(sorted(internal)) or "(sin literal dinámico detectado)", ",".join(sorted(scope)) or "(alcance no inferido por AST)")))


if __name__ == "__main__":
    main()
