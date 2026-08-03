import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap font-[family-name:var(--font-mono)] outline-none transition-colors duration-fast ease-default focus-visible:outline focus-visible:outline-2 focus-visible:outline-neutral-100 focus-visible:outline-offset-2 disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary:
          "rounded-sm border border-transparent bg-neutral-100 px-4 py-2 text-body font-semibold uppercase tracking-[1px] [color:var(--text-inverse)] hover:bg-white active:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-40",
        secondary:
          "rounded-sm border border-border bg-transparent px-4 py-2 text-body font-medium uppercase tracking-[1px] [color:var(--text-primary)] hover:border-border-strong hover:bg-surface-elevated active:bg-neutral-800 disabled:opacity-40",
        danger:
          "rounded-sm border border-status-denied-border bg-transparent px-3 py-1.5 text-micro uppercase tracking-[1px] [color:var(--status-denied-fg)] hover:border-status-denied-fg hover:bg-status-denied-bg disabled:opacity-40",
        ghost:
          "rounded-sm border border-transparent bg-transparent px-3 py-1.5 text-body font-medium uppercase tracking-[1px] [color:var(--text-secondary)] hover:bg-surface-elevated hover:[color:var(--text-primary)] disabled:opacity-40",
      },
      size: {
        default: "",
        sm: "!min-h-0 rounded-sm !px-3 !py-1.5 !text-micro",
        icon: "h-8 min-h-8 min-w-8 justify-center p-0 [&_svg:not([class*='size-'])]:size-4",
        "icon-sm": "h-7 min-h-7 min-w-7 justify-center p-0 text-[11px] [&_svg:not([class*='size-'])]:size-3.5",
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
