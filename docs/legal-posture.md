# Legal posture

**Last reviewed:** 2026-08-08 · **Owner:** Gagan Ganesh · **Status:** living document

This records what Grace claims, what it deliberately does not claim, and what
would have to be true before stronger claims could be made. It is an engineering
document written to keep marketing copy and code honest with each other. **It is
not legal advice and has not been reviewed by a lawyer.** Items marked
**[COUNSEL]** are open questions that need one.

---

## 1. Claims register

| Grace claims | Grace does **not** claim |
|---|---|
| Receipts are cryptographically signed (Ed25519 + ML-DSA-65) and independently verifiable without an account | That a receipt is admissible as evidence in any court or tribunal |
| The audit chain is tamper-**evident** — undetected retroactive modification is computationally infeasible | That the chain is tamper-**proof** or immutable in an absolute sense |
| Evidence at rest is encrypted with AES-256-GCM under per-row data-encryption keys | That Grace is FIPS 140-3 validated, or that any module has a CMVP certificate |
| `axiom crypto check` reports the system's FIPS/NIST-PQC **posture** | That this report constitutes certification or third-party attestation |
| Policy packs express common control requirements as machine-checkable rules | That deploying a policy pack makes an organisation compliant with the framework it references |
| Grace evidences what an agent did and under which policy | That Grace prevents all misuse, or substitutes for human oversight |

**Rule of thumb for any new copy:** Grace produces *evidence*. Whether that
evidence is sufficient for a given legal or regulatory purpose is a
determination made by someone other than Grace.

---

## 2. Evidentiary standing

Admissibility is decided by the forum under its own procedural rules; no
software can self-certify it. The relevant framing under EU law is
**Regulation (EU) 910/2014 (eIDAS)** as amended:

- A signature produced with a self-managed Ed25519 key is at best an **advanced**
  electronic signature. The legal presumptions attach to **qualified** signatures
  and seals, which require a certificate from a Qualified Trust Service Provider.
- Likewise for timestamps: only a **qualified** electronic timestamp carries the
  Art. 41 presumption as to the accuracy of the date and time. The configured
  `FreeTSAProvider` is a development convenience and is **not** a QTSP.

`apps/backend/HARDENING_REPORT_TIER_3_4.md` already lists the prerequisites.
Restated here as the gate on any stronger claim:

1. Independent cryptographic **and** legal review of the end-to-end receipt,
   timestamp, and key-handling design.
2. Signing keys held in an HSM or FIPS 140-validated KMS. `KMSKeyProvider` is
   currently a stub; production signing uses `StaticKeyProvider` (key files on
   disk), which is not defensible for evidentiary purposes.
3. Qualified timestamps from a QTSP in the relevant jurisdiction.
4. Documented key ceremony, retention schedule, and audit-log shipping to
   tamper-evident storage.

Until all four hold, the correct public wording is "tamper-evident,
independently verifiable evidence" — never "court-admissible".

**[COUNSEL]** Whether a German court would treat a Grace receipt as meaningful
under ZPO rules on electronic documents, and what weight an advanced (non-qualified)
signature carries in practice.

---

## 3. Personal data

### Role

While Grace is operated only by its author against test data, no processing of
third-party personal data occurs. **The moment Grace processes another
organisation's data, that organisation is the controller and Grace's operator is
a processor** under GDPR Art. 28 — which triggers a data processing agreement,
Art. 30 records, Art. 32 technical measures, and quite possibly a DPIA under
Art. 35, given that Grace systematically records automated decision-making.

**Do not onboard an external user before that paperwork exists.** **[COUNSEL]**

### Erasure vs. the audit chain

Grace holds agent inputs and outputs in the evidence vault; these can contain
personal data. The audit chain is designed to resist modification. That is the
classic Art. 17 tension.

The EDPB's **Guidelines 02/2025 on processing of personal data through blockchain**
(final, 7 July 2026) hold that encrypted personal data remains personal data, and
that hashing is pseudonymisation rather than anonymisation. Two structural facts
put Grace in a better position than the public-ledger case those guidelines
principally address:

- **Grace's chain is private.** It lives in the operator's own PostgreSQL, not on
  a public distributed ledger. Deletion is technically possible; there is no
  consensus mechanism preventing it.
- **Per-row DEKs give a crypto-shredding path.** Under ADR-030, each vault row is
  encrypted under its own data-encryption key, wrapped by a derived KEK.
  Destroying the DEK renders that row's plaintext unrecoverable while the chain
  continues to verify, because the chain commits to *hashes* of the evidence
  rather than to the evidence itself.

This is the erasure story and it should be stated in any DPA: an erasure request
is satisfied by destroying the row's DEK, which is irreversible, auditable, and
leaves chain integrity intact.

**[COUNSEL]** Whether DEK destruction is accepted as erasure under Art. 17 in the
relevant supervisory authority's practice, and whether the residual hash is
treated as personal data. Both are genuinely contested.

### Data minimisation

The strongest available mitigation is not storing personal data in the first
place. Where a receipt only needs to prove *that* an action occurred, prefer
committing to a hash of the payload rather than retaining the payload.

---

## 4. EU AI Act

**Grace's own classification.** Grace is audit and governance infrastructure. It
does not make or materially influence decisions about natural persons in any of
the Annex III domains; it records decisions made by other systems. On the current
reading it is therefore **not itself a high-risk AI system**, and is not a GPAI
model provider. **[COUNSEL]** — worth confirming rather than assuming, because
the classification drives everything else.

**Timeline, as at 2026-08-08.** The Digital Omnibus provisional agreement of
7 May 2026 defers Annex III (use-based) high-risk obligations from 2 August 2026
to **2 December 2027**, and Annex I (product-regulated) obligations from
August 2027 to **August 2028**. Formal adoption and OJ publication were expected
around the original August 2026 date. Re-verify before relying on this.

**Where the actual exposure is: marketing.** Grace's value proposition sits
adjacent to AI Act Art. 12 (record-keeping) and Art. 14 (human oversight), and
compliance-framework policy packs are on the roadmap. The rule:

- Defensible: "Grace helps you evidence record-keeping and oversight obligations."
- Not defensible: "Grace makes you AI Act compliant."

Every policy pack that names a framework must carry a visible disclaimer in its
description stating that it is a configurable **template**, that it has not been
reviewed or endorsed by any regulator or standards body, and that the deploying
organisation remains responsible for its own compliance determination.

---

## 5. Licensing and IP

- **Grace (this repository): AGPL-3.0.** Chosen so the source is readable and
  self-hostable while a third party cannot take it closed as a competing hosted
  service. AGPL §13 obliges anyone running a modified version as a network
  service to offer that modified source to its users.
- **`packages/axiom-sdk`: MIT, deliberately.** A client SDK under AGPL would
  place copyleft obligations on every application that imports it, which would
  make the SDK unusable in practice. The permissive/copyleft split between client
  and server is intentional and standard. **This must stay documented**, because
  an undocumented licence split inside one repository reads like an oversight.
- **Copyright holder is Gagan Ganesh, a natural person.** Package metadata must
  not attribute authorship to a legal entity that does not exist. Any residual
  "AXIOM Control Systems Inc." attribution in package metadata is a factual
  error and is being corrected.
- **Contributions.** There is currently no CLA and no external contributor. If
  that changes, decide the inbound licensing position *before* accepting a
  patch — retroactive relicensing requires every contributor's consent.

---

## 6. Cryptography and export control

Grace implements Ed25519 and ML-DSA-65 for signatures (authentication) and
AES-256-GCM for the evidence vault (confidentiality). Under **Regulation (EU)
2021/821** the controls target confidentiality functions; authentication and
digital-signature functionality is broadly decontrolled, and publicly available
/ open-source software benefits from further decontrol notes. Publishing Grace
under AGPL-3.0 in a public repository is expected to fall within the
publicly-available decontrol.

Assessed as **low risk**. Revisit if Grace is ever distributed as a compiled
binary to controlled destinations, or bundled with a confidentiality product
sold commercially. **[COUNSEL]** if either becomes true.

---

## 7. Operator's own position

Grace is currently a personal project developed in Germany by the author, who
holds a student residence permit (§16b AufenthG). That permit allows limited
employment but **self-employed or freelance activity requires separate
permission from the Ausländerbehörde**.

Development, publication, and portfolio use are unaffected. **Accepting payment
for Grace — from any customer, in any amount — is commercial activity and must
not happen before that permission is confirmed**, alongside Gewerbeanmeldung and
VAT registration as applicable. **[COUNSEL]** — Ausländerbehörde or a
Fachanwalt für Migrationsrecht, before the first invoice, not after.

---

## 8. Open items

| # | Item | Blocks |
|---|---|---|
| 1 | Confirm AI Act classification for Grace itself | Any regulatory positioning in marketing |
| 2 | DPA template, Art. 30 records, DPIA assessment | Onboarding any external user |
| 3 | Supervisory-authority view on DEK destruction as Art. 17 erasure | Any erasure guarantee in a DPA |
| 4 | Residence-permit position on commercial activity | Accepting any payment |
| 5 | Independent crypto + legal review; HSM/KMS; qualified timestamps | Any evidentiary or "court-admissible" claim |
| 6 | Disclaimer text on every framework-named policy pack | Shipping compliance packs |

Review this document whenever a claim changes, a framework pack ships, or an
external user is onboarded — whichever comes first.
