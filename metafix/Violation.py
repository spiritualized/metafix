from metafix.constants import ViolationType


class Violation:
    def __init__(self, violation_type: ViolationType, message: str) -> None:
        self.violation_type = violation_type
        self.message = message

    def __repr__(self) -> str:
        return self.message
