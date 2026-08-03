"""The six concrete pipeline stages."""

from axiom.services.pipeline.stages.authority import AuthorityStage
from axiom.services.pipeline.stages.dispatch import DispatchStage
from axiom.services.pipeline.stages.evidence import EvidenceStage
from axiom.services.pipeline.stages.intent import IntentStage
from axiom.services.pipeline.stages.receipt import ReceiptStage
from axiom.services.pipeline.stages.strategy import StrategyStage

__all__ = [
    "AuthorityStage",
    "DispatchStage",
    "EvidenceStage",
    "IntentStage",
    "ReceiptStage",
    "StrategyStage",
]
