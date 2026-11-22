"""Read and pin the local pipeline configuration."""

from dataclasses import dataclass
from pathlib import Path
import json

from .util import CareReconError, digest, encode

ROOT = Path(__file__).resolve().parents[2]
PRIOR = "payer_claims_previous"
RULE_IDS = {
    "DQ001", "DQ002", "DQ003", "DQ004", "DQ005", "DQ006",
    "RC001", "RC002", "RX001", "RX002", "CT001", "CT002", "SS001",
}


@dataclass(frozen=True)
class Settings:
    contracts: dict
    rules: dict
    demo: dict

    @classmethod
    def load(cls, directory):
        contracts, rules, demo = (
            json.loads((directory / name).read_text(encoding="utf-8"))
            for name in ("source_contracts.json", "rules.json", "demo.json")
        )
        manifest = {rule["rule_id"]: rule for rule in rules["rules"]}
        if (len(manifest) != len(rules["rules"]) or set(manifest) != RULE_IDS
                or any(type(r["enabled"]) is not bool or type(r["version"]) is not int
                       or r["version"] < 1 or r["severity"] not in {"ERROR", "WARN", "REVIEW"}
                       for r in manifest.values())
                or manifest["SS001"]["severity"] != "REVIEW"):
            raise CareReconError("Invalid rule manifest. SS001 must retain REVIEW severity.")
        return cls(contracts, rules, demo)

    @property
    def fingerprint(self):
        return digest(encode([self.contracts, self.rules]).encode("utf-8"))
