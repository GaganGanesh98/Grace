/** DTOs aligned with backend `axiom.schemas.command_center` (DataEnvelope-wrapped in API). */

export type PostureMetrics = {
  calls_governed: number;
  runs_completed: number;
  violations: number;
};

export type CryptoSigningStatus = "all_signed" | "partial" | "never_signed" | "no_data";
export type MerkleStatus = "healthy" | "no_data";

export type CryptoHealthOut = {
  ed25519_status: CryptoSigningStatus;
  mldsa65_status: CryptoSigningStatus;
  merkle_status: MerkleStatus;
  next_rotation_days: number | null;
};

export type PolicyBreakdownOut = {
  policy_name: string | null;
  evaluated_count: number;
  approved_count: number;
  escalated_count: number;
  denied_count: number;
};

export type TsaStatusOut = {
  last_anchor_age_seconds: number | null;
  tsa_authority_url: string | null;
};
