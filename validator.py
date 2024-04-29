from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Callable, Tuple, Optional

if TYPE_CHECKING:
    from .renderConfiguration import Config
    from .renderfarm import FarmRenderDlg
    from bpy.types import Operator  # pylint: disable = no-name-in-module, import-error


class Validator(ABC):
    def __init__(self, main: FarmRenderDlg) -> None:
        self.mainDialog = main

    @abstractmethod
    def getName(self) -> str:
        pass

    @abstractmethod
    def test(self, results: List[TestResult]) -> None:
        pass

    @abstractmethod
    def prepareSave(self, export_folder: str, assets: List[str], scene_settings: "Config") -> None:
        pass

    @abstractmethod
    def postSave(self) -> None:
        pass

    def furtherAction(self, op: Operator, result: TestResult) -> None:
        pass


class TestResult:
    def __init__(
        self, severity: int, validator: Optional[Validator], message: str, type_: Optional[int], 
        info_1: str= None, info_2: str= None
    ):
        self.severity = severity
        self.validator = validator
        self.message = message
        self.type = type_
        self.info_1 = info_1
        self.info_2 = info_2

    @property
    def flagMoreInfos(self) -> bool:
        return self.type != 0


@dataclass
class ResultHelper:
    """
    Helper to remove duplication when appending TestResults to the results list passed to each validator in prepareSave.

    results = ResultHelper(results_, self)
    results.add(severity, message, type_)    == results_.append(TestResult(severity, self, message, type_))
    results.add(severity, message)           == results_.append(TestResult(severity, self, message, None))
    """

    results: List[TestResult]
    validator: Optional[Validator]

    def info(self, message: str, type_: int = None) -> None:
        self.add(0, message, type_)

    def warn(self, message: str, type_: int = None) -> None:
        self.add(1, message, type_)

    def error(self, message: str, type_: int = None, info_1: str= "", info_2: str= "") -> None:
        self.add(2, message, type_, info_1, info_2)

    def add(self, severity: int, message: str, type_: int = None, info_1: str= "", info_2: str= "") -> None:
        self.results.append(TestResult(severity, self.validator, message, type_, info_1, info_2))
