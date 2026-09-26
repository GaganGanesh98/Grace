import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// Phase 8.3 redesign: sans-serif, sentence case, 8px radius and a 1px hover
// lift. The variant/size API is unchanged so existing call sites keep working.
// Colours come from the theme tokens in globals.css, so every variant follows
// Midnight/Daylight without per-theme classes here.
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-[7px] whitespace-nowrap rounded-md border font-[family-name:var(--font-sans)] text-[13px] font-semibold outline-none transition-[transform,background-color,border-color,color] duration-fast ease-out hover:enabled:-translate-y-px focus-visible:ring-[3px] focus-visible:ring-[color:color-mix(in_oklab,var(--ring)_28%,transparent)] focus-visible:border-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-[0.42] motion-reduce:transition-none motion-reduce:hover:enabled:translate-y-0 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary:
          "h-9 border-transparent bg-primary px-3 text-primary-foreground hover:enabled:bg-[var(--primary-hover)]",
        secondary:
          "h-9 border-border bg-secondary px-3 text-secondary-foreground hover:enabled:border-[var(--border-emphasis)]",
        danger:
          "h-9 border-[color:color-mix(in_oklab,var(--danger)_25%,var(--border))] bg-[var(--danger-soft)] px-3 text-[var(--danger-strong)]",
        ghost:
          "h-9 border-transparent bg-transparent px-3 text-muted-foreground hover:enabled:bg-secondary hover:enabled:text-foreground",
      },
      size: {
        default: "",
        sm: "!h-[30px] !px-2.5 !text-xs",
        icon: "!h-9 !w-9 !p-0",
        "icon-sm": "!h-[30px] !w-[30px] !p-0 [&_svg:not([class*='size-'])]:size-3.5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "primary",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Button, buttonVariants }
