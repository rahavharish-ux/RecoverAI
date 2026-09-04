import type { ButtonHTMLAttributes, ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary'

// Same radius (rounded-md) and border vocabulary as every other
// primitive — buttons never get their own rounder or squarer corners.
const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'border border-brand bg-brand text-white hover:bg-brand-strong hover:border-brand-strong',
  secondary: 'border border-line-strong bg-surface text-ink hover:bg-surface-hover',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  children: ReactNode
}

export function Button({ variant = 'primary', className = '', children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT_CLASS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
