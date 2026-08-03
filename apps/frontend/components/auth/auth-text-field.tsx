"use client";

import type { ReactElement } from "react";
import type { Control, FieldPath, FieldValues } from "react-hook-form";
import { Controller, type FieldError } from "react-hook-form";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Native `<input>` styled like `components/ui/input.tsx`.
 * Base UI `Input` delegates to an internal control layer; ref merge can prevent
 * `register()` from observing values; `Controller` + native input avoids that.
 */
const authInputClassName = cn(
  "h-8 w-full min-w-0 rounded-sm border border-border bg-surface-input px-3 py-2 text-body text-text-primary transition-colors outline-none",
  "placeholder:text-text-tertiary focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2",
  "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
  "aria-invalid:border-destructive aria-invalid:outline-status-denied-fg",
  "md:text-sm",
);

type AuthTextFieldProps<T extends FieldValues> = {
  control: Control<T>;
  name: FieldPath<T>;
  id: string;
  label: string;
  type?: React.HTMLInputTypeAttribute;
  autoComplete?: string;
  error?: FieldError;
};

export function AuthTextField<T extends FieldValues>({
  control,
  name,
  id,
  label,
  type = "text",
  autoComplete,
  error,
}: AuthTextFieldProps<T>): ReactElement {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <input
            {...field}
            id={id}
            type={type}
            autoComplete={autoComplete}
            aria-invalid={error ? true : undefined}
            className={authInputClassName}
          />
        )}
      />
      {error?.message ? <p className="text-sm text-destructive">{error.message}</p> : null}
    </div>
  );
}
