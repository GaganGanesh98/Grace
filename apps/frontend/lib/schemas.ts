import { z } from "zod";

export const loginBodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const signupBodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
  full_name: z.string().max(255).optional(),
});

export const googleCallbackBodySchema = z.object({
  code: z.string().min(1),
  state: z.string().min(1),
});

export const createProjectBodySchema = z.object({
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional(),
});
