import { type HTMLAttributes, type ReactElement } from "react";

import { cn } from "@/lib/utils";

import s from "./skeleton.module.css";

export type SkeletonProps = HTMLAttributes<HTMLDivElement>;

/**
 * Rounded block with a subtle 1.5s opacity loop (0.5 → 0.8) — not a hard `animate-pulse` flash.
 */
export function Skeleton({ className, ...rest }: SkeletonProps): ReactElement {
  return <div className={cn("block w-full", s.pulse, className)} aria-hidden {...rest} />;
}
