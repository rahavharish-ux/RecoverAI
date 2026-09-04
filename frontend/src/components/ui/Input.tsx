import type { InputHTMLAttributes } from 'react'
import { useId } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hideLabel?: boolean
}

/** `label` is required, not optional — an unlabelled input is an
 * accessibility bug waiting to happen, not a style choice. Pass
 * `hideLabel` for a visually-compact input that still has a real
 * <label> for assistive tech, rather than dropping the label. */
export function Input({ label, hideLabel = false, id, className = '', ...rest }: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  return (
    <div>
      <label htmlFor={inputId} className={hideLabel ? 'sr-only' : 'mb-1 block text-xs font-medium text-muted'}>
        {label}
      </label>
      <input
        id={inputId}
        className={`w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint ${className}`}
        {...rest}
      />
    </div>
  )
}
