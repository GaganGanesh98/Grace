"""Property-based tests for crypto primitives (Hypothesis)."""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from axiom.services.crypto import canonical_json, ed25519, merkle, ml_dsa

_json_atom = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**6), max_value=10**6),
    st.text(max_size=12),
)

json_value = st.recursive(
    _json_atom,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(st.text(min_size=1, max_size=6), children, max_size=8),
    ),
    max_leaves=40,
)


@given(json_value)
def test_canonicalize_is_idempotent(data: object) -> None:
    c = canonical_json.canonicalize(data)  # type: ignore[arg-type]
    assert canonical_json.canonicalize(json.loads(c.decode("utf-8"))) == c


@settings(max_examples=25, deadline=None)
@given(st.binary(min_size=1, max_size=4000))
def test_ed25519_sign_verify_round_trip_hypothesis(message: bytes) -> None:
    kp = ed25519.generate_keypair()
    sig = ed25519.sign(kp.private_key_pem, message)
    assert ed25519.verify(kp.public_key_pem, message, sig) is True


@settings(max_examples=8, deadline=None)
@given(st.binary(min_size=1, max_size=4000))
def test_ml_dsa_sign_verify_round_trip_hypothesis(message: bytes) -> None:
    kp = ml_dsa.generate_keypair()
    sig = ml_dsa.sign(kp.private_key_bytes, message)
    assert ml_dsa.verify(kp.public_key_bytes, message, sig) is True


@given(st.lists(st.binary(min_size=1, max_size=24), min_size=1, max_size=32))
def test_merkle_inclusion_proofs_verify(leaves: list[bytes]) -> None:
    tup = tuple(leaves)
    tree = merkle.build_tree(tup)
    for i, leaf in enumerate(tup):
        proof = merkle.inclusion_proof(tree, i)
        assert merkle.verify_inclusion(tree.root, leaf, proof) is True


@given(st.lists(st.binary(min_size=1, max_size=16), min_size=1, max_size=16))
def test_merkle_consistency_for_prefix_extension(prefix: list[bytes]) -> None:
    extra = (b"\xff", b"\xfe", b"\xfd")
    old = merkle.build_tree(tuple(prefix))
    new = merkle.build_tree(tuple(prefix) + extra)
    proof = merkle.consistency_proof(old, new)
    assert merkle.verify_consistency(old.root, new.root, proof) is True


@given(st.lists(st.binary(min_size=1, max_size=12), min_size=1, max_size=12))
def test_merkle_build_is_deterministic(leaves: list[bytes]) -> None:
    tup = tuple(leaves)
    assert merkle.build_tree(tup).root == merkle.build_tree(tup).root


@given(st.lists(st.binary(min_size=1, max_size=8), min_size=2, max_size=8))
def test_merkle_tampered_path_fails(leaves: list[bytes]) -> None:
    tup = tuple(leaves)
    tree = merkle.build_tree(tup)
    proof = merkle.inclusion_proof(tree, 0)
    if not proof.path:
        return
    first = proof.path[0]
    bad_first = bytes([first[0] ^ 1]) + first[1:]
    bad = merkle.InclusionProof(
        leaf_index=proof.leaf_index,
        tree_size=proof.tree_size,
        path=(bad_first, *proof.path[1:]),
    )
    assert merkle.verify_inclusion(tree.root, tup[0], bad) is False
