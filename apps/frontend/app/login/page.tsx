"use client";

import type { ReactElement } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import type { z } from "zod";

import { apiLogin, startGoogleOAuth } from "@/lib/api";
import { loginBodySchema } from "@/lib/schemas";

import styles from "./login.module.css";

type LoginForm = z.infer<typeof loginBodySchema>;

function GoogleMark(): ReactElement {
  return (
    <svg aria-hidden viewBox="0 0 24 24">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

export default function LoginPage(): ReactElement {
  const router = useRouter();
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginBodySchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: LoginForm): Promise<void> => {
    try {
      await apiLogin(data.email, data.password);
      toast.success("Signed in");
      router.push("/dashboard");
      router.refresh();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Login failed");
    }
  };

  return (
    <div className={styles.pageRoot}>
      <div aria-hidden className={styles.ambientGrid} />
      <div aria-hidden className={styles.ambientGlow} />

      <div className={styles.cornerMeta}>GRACE :: VERIFICATION LAYER</div>
      <div className={styles.cornerMetaBr}>
        <div>ED25519 + ML-DSA-65</div>
        <div className={styles.cornerMetaBrDim}>NIST PQC LEVEL 3</div>
      </div>

      <div className={styles.cardShell}>
        <div className={styles.card}>
          <div aria-hidden className={styles.cardAccent} />

          <div className={styles.wordmarkRow}>
            <div className={styles.wordmarkLeft}>
              <div className={styles.wordmarkIcon}>
                <div className={styles.diamondOuter}>
                  <div className={styles.diamondInner} />
                </div>
              </div>
              <span className={styles.wordmarkTitle}>GRACE</span>
            </div>
            <span className={styles.wordmarkVer}>V0.2.4</span>
          </div>

          <h1 className={styles.heading}>Resume session.</h1>
          <p className={styles.tagline}>VERIFICATION LAYER · AUTONOMOUS SYSTEMS</p>

          <form noValidate onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
            <div className={styles.fieldGroup}>
              <div className={styles.labelRow}>
                <label className={styles.labelText} htmlFor="email">
                  EMAIL
                </label>
              </div>
              <Controller
                control={control}
                name="email"
                render={({ field }) => (
                  <input
                    {...field}
                    autoComplete="email"
                    className={styles.input}
                    id="email"
                    type="email"
                    aria-invalid={errors.email ? true : undefined}
                    aria-describedby={errors.email?.message ? "email-error" : undefined}
                  />
                )}
              />
              {errors.email?.message ? (
                <p className={styles.errorText} id="email-error" role="alert">
                  {errors.email.message}
                </p>
              ) : null}
            </div>

            <div className={`${styles.fieldGroup} ${styles.fieldGroupBeforeSubmit}`}>
              <div className={styles.labelRow}>
                <label className={styles.labelText} htmlFor="password">
                  PASSWORD
                </label>
                <button
                  className={styles.resetLink}
                  type="button"
                  title="Password reset is not available yet"
                >
                  RESET ↗
                </button>
              </div>
              <Controller
                control={control}
                name="password"
                render={({ field }) => (
                  <input
                    {...field}
                    autoComplete="current-password"
                    className={styles.input}
                    id="password"
                    type="password"
                    aria-invalid={errors.password ? true : undefined}
                    aria-describedby={errors.password?.message ? "password-error" : undefined}
                  />
                )}
              />
              {errors.password?.message ? (
                <p className={styles.errorText} id="password-error" role="alert">
                  {errors.password.message}
                </p>
              ) : null}
            </div>

            <button className={styles.primaryBtn} disabled={isSubmitting} type="submit">
              {isSubmitting ? "..." : "CONTINUE →"}
            </button>

            <div className={styles.divider}>
              <span className={styles.dividerLine} />
              <span className={styles.dividerOr}>OR</span>
              <span className={styles.dividerLine} />
            </div>

            <button
              className={styles.googleBtn}
              type="button"
              onClick={() => {
                startGoogleOAuth();
              }}
            >
              <span className={styles.googleBtnIcon} aria-hidden>
                <GoogleMark />
              </span>
              <span className={styles.googleBtnLabel}>Continue with Google</span>
            </button>

            <div className={styles.liveRow}>
              <span aria-hidden className={styles.liveDot} />
              <span className={styles.liveText}>LIVE · NETWORK VERIFIED</span>
            </div>

            <p className={styles.signupRow}>
              No account?{" "}
              <Link className={styles.signupLink} href="/signup">
                Sign up
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
