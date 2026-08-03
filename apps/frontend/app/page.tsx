import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export default async function Home(): Promise<never> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (token) {
    redirect("/dashboard");
  }
  redirect("/login");
}
