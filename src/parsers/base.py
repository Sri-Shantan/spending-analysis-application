from abc import ABC, abstractmethod
from src.models import Transaction


class StatementParser(ABC):
    account_name: str

    @abstractmethod
    def can_parse(self, text: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, text: str, source_file: str | None = None) -> list[Transaction]:
        raise NotImplementedError
