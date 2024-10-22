from dataclasses import dataclass
from enum import Enum

class AttributeOperator(Enum):
    EQUALS = "="
    BEGINS_WITH = "^="
    ENDS_WITH = "$="
    LIKE = "*="

@dataclass
class Attribute:
    key: str
    value: str
    equivalence: AttributeOperator=AttributeOperator.EQUALS

    def __str__(self) -> str:
        return f"[{self.key}{self.equivalence.value}'{self.value}']"

class AttributeSelector:
    def __init__(
            self, 
            element: str | None = None, 
            id_name: str | None = None, 
            classes: list[str] | None = None, 
            attrs: list[Attribute] | None = None
    ):
        self.element = element or ""
        self.id_name = f"#{id_name}" if id_name else ""
        self.classes = "".join(f".{s}" for s in classes) if classes else ""
        self.attrs = "".join(str(a) for a in attrs) if attrs else ""

    def __str__(self) -> str:
        return self.element + self.id_name + self.classes + self.attrs
