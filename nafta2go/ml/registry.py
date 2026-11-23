"""Registro versionado de corridas de ML con alias de campeón y retadores (#161).

El registro es `nafta2go/ml/registry.json`, revisado en cada PR. Cada corrida se
identifica por el SHA-256 de su manifiesto de modelo, el mismo valor que el serving
usa como versión. Los artefactos grandes siguen fuera de Git: se registran sus
hashes y si se conservan, nunca se reconstruyen.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

REGISTRY = Path(__file__).with_name("registry.json")
REFERENCES = ("mediana_previa", "ultimo_precio", "bandera_reciente")


class RegistryError(ValueError):
    """Corrida o promoción incompatible; el registro no se modifica."""


def load(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(registry: dict, path: Path = REGISTRY) -> None:
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    root = REGISTRY.parents[2]
    resolved = path.resolve()
    return str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(path)


def run_entry(manifest_path: Path, report_path: Path | None, policy: str | None) -> dict:
    """Arma la entrada desde un manifiesto y su reporte, sin inventar lo que falta."""
    manifest = json.loads(manifest_path.read_bytes())
    report = json.loads(report_path.read_bytes()) if report_path else None
    candidates = None
    if report is not None:
        if report["chosen_method"] != manifest["chosen_method"]:
            raise RegistryError("El reporte no corresponde al manifiesto")
        candidates = {
            method: {
                "kind": "reference" if method in REFERENCES else "model",
                "selection_mae_ars_per_l": report["selection"][method]["mae_ars_per_l"],
                "validation_mae_ars_per_l": report["validation"][method]["mae_ars_per_l"],
            }
            for method in sorted(report["selection"])
        }
    return {
        "manifest": _relative(manifest_path),
        "report": _relative(report_path) if report_path else None,
        "report_sha256": _sha256(report_path) if report_path else None,
        "chosen_method": manifest["chosen_method"],
        "features_version": manifest["features_version"],
        "parameters": manifest["parameters"],
        "lineage": {
            "dataset_sha256": manifest["dataset_sha256"],
            "dataset_manifest_sha256": manifest["dataset_manifest_sha256"],
            "source_sha256": manifest["source_sha256"],
            "git_commit": manifest["code"]["git_commit"],
            "git_dirty": manifest["code"]["git_dirty"],
        },
        "candidates": candidates,
        # model.joblib y las predicciones quedan fuera de Git; solo se conocen sus hashes.
        "artifacts": {
            manifest["artifact_file"]: {
                "model": manifest["artifact_model"],
                "sha256": manifest["artifact_sha256"],
                "conserved_in_repo": False,
            },
            manifest["validation_predictions_file"]: {
                "sha256": manifest["validation_predictions_sha256"],
                "conserved_in_repo": False,
            },
        },
        "policy": policy,
    }


def register(registry: dict, manifest: Path, report: Path | None, policy: str | None) -> str:
    if policy is not None and policy not in registry["policies"]:
        raise RegistryError(f"Política desconocida: {policy}")
    version = _sha256(manifest)
    if version in registry["runs"]:
        raise RegistryError("La corrida ya está registrada")
    registry["runs"][version] = run_entry(manifest, report, policy)
    return version


def selection_winner(run: dict) -> str:
    """Regla de ADR-014: menor MAE en el período de selección; la validación no se mira."""
    if not run["candidates"]:
        raise RegistryError("La corrida no conserva el reporte de selección")
    return min(run["candidates"], key=lambda m: run["candidates"][m]["selection_mae_ars_per_l"])


def promote(registry: dict, version: str) -> None:
    """Cambia el campeón solo si respeta ADR-014 y la política de alertas auditada."""
    run = registry["runs"].get(version)
    if run is None:
        raise RegistryError("Corrida no registrada")
    winner = selection_winner(run)
    if winner != run["chosen_method"]:
        raise RegistryError("El método elegido no es el de menor error de selección")
    policy = registry["policies"].get(run["policy"])
    if policy is None or policy["method"] != winner:
        raise RegistryError("La corrida no es compatible con una política de alertas auditada")
    registry["aliases"] = {
        "champion": {"run": version, "method": winner},
        "challengers": [
            {"run": version, "method": method}
            for method, candidate in sorted(run["candidates"].items())
            if candidate["kind"] == "model"
        ],
    }


def audited_versions(policy: str, method: str, registry: dict | None = None) -> frozenset:
    """Corridas que el serving acepta para la política: auditadas y con el mismo método."""
    registry = load() if registry is None else registry
    if registry["policies"].get(policy, {}).get("method") != method:
        return frozenset()
    return frozenset(
        version
        for version, run in registry["runs"].items()
        if run["policy"] == policy and run["chosen_method"] == method
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show", help="Campeón, retadores y corridas registradas")
    add = commands.add_parser("register", help="Registrar una corrida de entrenamiento")
    add.add_argument("--manifest", type=Path, required=True)
    add.add_argument("--report", type=Path)
    add.add_argument("--policy", help="Política auditada para esta corrida, si la hay")
    up = commands.add_parser("promote", help="Promover una corrida a campeona")
    up.add_argument("--run", required=True, help="SHA-256 del manifiesto de modelo")
    args = parser.parse_args(argv)
    registry = load()
    try:
        if args.command == "register":
            print(register(registry, args.manifest, args.report, args.policy))
            save(registry)
        elif args.command == "promote":
            promote(registry, args.run)
            save(registry)
    except (RegistryError, OSError, KeyError) as exc:
        print(f"Registro sin cambios: {exc}", file=sys.stderr)
        return 1
    summary = {
        "aliases": registry["aliases"],
        "runs": {v: (r["chosen_method"], r["policy"]) for v, r in registry["runs"].items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
