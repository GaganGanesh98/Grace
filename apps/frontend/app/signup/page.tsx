"use client";

import type { ReactElement } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import type { z } from "zod";

import { AuthTextField } from "@/components/auth/auth-text-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiSignup, startGoogleOAuth } from "@/lib/api";
import { signupBodySchema } from "@/lib/schemas";

type SignupForm = z.infer<typeof signupBodySchema>;

export default function SignupPage(): ReactElement {
  const router = useRouter();
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupForm>({
    resolver: zodResolver(signupBodySchema),
    defaultValues: { email: "", password: "", full_name: "" },
  });

  const onSubmit = async (data: SignupForm): Promise<void> => {
    try {
      await apiSignup(data.email, data.password, data.full_name);
      toast.success("Account created");
      router.push("/dashboard");
      router.refresh();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Sign up failed");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="space-y-4" onSubmit={(e) => void handleSubmit(onSubmit)(e)}>
            <AuthTextField
              autoComplete="name"
              control={control}
              error={errors.full_name}
              id="full_name"
              label="Full name (optional)"
              name="full_name"
            />
            <AuthTextField
              autoComplete="email"
              control={control}
              error={errors.email}
              id="email"
              label="Email"
              name="email"
              type="email"
            />
            <AuthTextField
              autoComplete="new-password"
              control={control}
              error={errors.password}
              id="password"
              label="Password"
              name="password"
              type="password"
            />
            <Button className="w-full" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Creating…" : "Sign up"}
            </Button>
          </form>
          <Button
            className="w-full"
            type="button"
            variant="secondary"
            onClick={() => {
              startGoogleOAuth();
            }}
          >
            Sign up with Google
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link className="underline" href="/login">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
