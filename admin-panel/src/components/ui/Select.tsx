import React, { forwardRef } from 'react';
import { cn } from '../../utils/cn';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options?: { value: string | number; label: string }[];
  requiredAsterisk?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({
  label,
  error,
  options,
  children,
  className,
  id,
  required,
  requiredAsterisk,
  ...props
}, ref) => {
  const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full space-y-1.5 font-montserrat">
      {label && (
        <label htmlFor={selectId} className="block text-xs font-semibold text-brand-dark-blue">
          {label}
          {(required || requiredAsterisk) && <span className="text-brand-red ml-1 font-bold">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          ref={ref}
          className={cn(
            'w-full h-[50px] bg-brand-light-gray text-brand-dark text-sm font-medium rounded-r12 px-4 pr-10 appearance-none transition-all duration-150 border border-transparent focus:border-brand-lime focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-lime/20 cursor-pointer',
            error && 'border-brand-red bg-red-50/30',
            className
          )}
          {...props}
        >
          {options
            ? options.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-brand-gray-blue">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      {error && <p className="text-xs text-brand-red font-medium">{error}</p>}
    </div>
  );
});

Select.displayName = 'Select';
