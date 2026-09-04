import type { ReactNode, SelectHTMLAttributes } from 'react'
import { useId } from 'react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  hideLabel?: boolean
  children: ReactNode
}

/** Same required-label rule as Input, and the same radius/border
 * vocabulary as every other control. */
export function Select({ label, hideLabel = false, id, className = '', children, ...rest }: SelectProps) {
  const generatedId = useId()
  const selectId = id ?? generatedId
  return (
    <div>
      <label htmlFor={selectId} className={hideLabel ? 'sr-only' : 'mb-1 block text-xs font-medium text-muted'}>
        {label}
      </label>
      <select
        id={selectId}
        className={`w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink ${className}`}
        {...rest}
      >
        {children}
      </select>
    </div>
  )
}
