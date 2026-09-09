import React, { useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '../../utils/cn';

export interface ComboboxProps {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  /** Уже существующие названия — то, что показывается в раскрывашке. */
  suggestions: string[];
  placeholder?: string;
  error?: string;
  /** Подсказка под полем: например «такое название уже есть». */
  hint?: string;
  requiredAsterisk?: boolean;
  disabled?: boolean;
  id?: string;
}

/**
 * Поле со свободным вводом и списком уже заведённых названий.
 *
 * Нужен там, где раньше стоял обычный Input: администратор не видел, что
 * «Сироп» в этой точке уже есть, и заводил второй — отсюда дубли в списке
 * добавок. Данные для списка уже загружены на страницу, сеть не требуется.
 */
export const Combobox: React.FC<ComboboxProps> = ({
  label,
  value,
  onChange,
  suggestions,
  placeholder,
  error,
  hint,
  requiredAsterisk,
  disabled,
  id,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputId = id || (label ? `combo-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const listId = inputId ? `${inputId}-list` : undefined;

  const matches = useMemo(() => {
    const query = value.trim().toLowerCase();
    const unique = Array.from(new Set(suggestions.filter(Boolean)));
    const filtered = query
      ? unique.filter(name => name.toLowerCase().includes(query))
      : unique;
    return filtered.sort((a, b) => a.localeCompare(b, 'ru')).slice(0, 8);
  }, [suggestions, value]);

  useEffect(() => {
    if (!isOpen) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [isOpen]);

  const pick = (name: string) => {
    onChange(name);
    setIsOpen(false);
    setHighlighted(-1);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setIsOpen(false);
      return;
    }
    if (!matches.length) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIsOpen(true);
      setHighlighted(prev => (prev + 1) % matches.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setIsOpen(true);
      setHighlighted(prev => (prev <= 0 ? matches.length - 1 : prev - 1));
    } else if (event.key === 'Enter' && isOpen && highlighted >= 0) {
      event.preventDefault();
      pick(matches[highlighted]);
    }
  };

  return (
    <div className="w-full space-y-1.5 font-montserrat" ref={wrapperRef}>
      {label && (
        <label htmlFor={inputId} className="block text-xs font-semibold text-brand-dark-blue">
          {label}
          {requiredAsterisk && <span className="text-brand-red ml-1 font-bold">*</span>}
        </label>
      )}

      <div className="relative">
        <input
          id={inputId}
          role="combobox"
          aria-expanded={isOpen}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          disabled={disabled}
          value={value}
          placeholder={placeholder}
          onChange={event => {
            onChange(event.target.value);
            setIsOpen(true);
            setHighlighted(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={onKeyDown}
          className={cn(
            'w-full h-[50px] bg-brand-light-gray text-brand-dark placeholder-brand-gray-blue text-sm font-medium rounded-r12 px-4 pr-10 transition-all duration-150 border border-transparent focus:border-brand-lime focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-lime/20 disabled:opacity-50',
            error && 'border-brand-red bg-red-50/30 focus:border-brand-red focus:ring-brand-red/20'
          )}
        />

        {matches.length > 0 && (
          <button
            type="button"
            tabIndex={-1}
            aria-label={isOpen ? 'Скрыть подсказки' : 'Показать существующие названия'}
            onClick={() => setIsOpen(open => !open)}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-brand-gray-blue hover:text-brand-dark transition-colors"
          >
            <svg className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}

        {isOpen && matches.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            className="absolute z-30 left-0 right-0 top-[54px] max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-r12 shadow-lg py-1"
          >
            {matches.map((name, index) => (
              <li key={name} role="option" aria-selected={index === highlighted}>
                <button
                  type="button"
                  onMouseEnter={() => setHighlighted(index)}
                  onClick={() => pick(name)}
                  className={cn(
                    'w-full text-left px-4 py-2 text-sm font-medium transition-colors',
                    index === highlighted
                      ? 'bg-brand-light-gray text-brand-dark'
                      : 'text-brand-dark-blue hover:bg-slate-50'
                  )}
                >
                  {name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="text-xs text-brand-red font-medium">{error}</p>}
      {!error && hint && <p className="text-xs text-brand-orange font-medium">{hint}</p>}
    </div>
  );
};
