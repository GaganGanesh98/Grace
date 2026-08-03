"""Receipt generation + Merkle append.

Two responsibilities split across two modules:
  * ``merkle_append.MerkleAppender`` handles the transactional, per-project
    advisory-locked append + inclusion-proof generation.
  * ``service.ReceiptService`` wires a PipelineRunner together with DB session
    lifetime so that routers can call ``process(...)`` and get a full context
    back.
"""

from axiom.services.receipt.merkle_append import MerkleAppender
from axiom.services.receipt.service import ReceiptService

__all__ = ["MerkleAppender", "ReceiptService"]
