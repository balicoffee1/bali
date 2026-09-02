import React, { forwardRef } from 'react';
import { cn } from '../../utils/cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  requiredAsterisk?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  leftIcon,
  rightIcon,
  requiredAsterisk,
  className,
  id,
  required,
  ...props
}, ref) => {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full space-y-1.5 font-montserrat">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-semibold text-brand-dark-blue">
          {label}
          {(required || requiredAsterisk) && <span className="text-brand-red ml-1 font-bold">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {leftIcon && (
          <div className="absolute left-3.5 text-brand-gray-blue pointer-events-none flex items-center">
            {leftIcon}
          </div>
        )}
        <input
          id={inputId}
          ref={ref}
          className={cn(
            'w-full h-[50px] bg-brand-light-gray text-brand-dark placeholder-brand-gray-blue text-sm font-medium rounded-r12 px-4 transition-all duration-150 border border-transparent focus:border-brand-lime focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-lime/20',
            leftIcon ? 'pl-11' : 'pl-4',
            rightIcon ? 'pr-11' : 'pr-4',
            error && 'border-brand-red bg-red-50/30 focus:border-brand-red focus:ring-brand-red/20',
            className
          )}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3.5 text-brand-gray-blue flex items-center">
            {rightIcon}
          </div>
        )}
      </div>
      {error && <p className="text-xs text-brand-red font-medium">{error}</p>}
    </div>
  );
});

Input.displayName = 'Input';
