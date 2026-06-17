from dataclasses import dataclass


@dataclass
class Violation:
    rule_id: str
    severity: str
    line: int
    function_name: str
    message: str
    evidence: str
