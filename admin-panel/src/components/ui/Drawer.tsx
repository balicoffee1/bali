import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useDialogBehavior } from '../../utils/dialog';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: 'md' | 'lg' | 'xl';
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 'lg',
}) => {
  useDialogBehavior(isOpen, onClose);

  if (!isOpen) return null;

  const widths = {
    md: 'sm:max-w-md',
    lg: 'sm:max-w-xl',
    xl: 'sm:max-w-2xl',
  };

  // Рендерим в body: у страниц есть анимация с transform, а такой предок
  // становится containing block для position: fixed и «схлопывает» диалог
  // внутрь контента страницы.
  return createPortal(
    <div className="fixed inset-0 z-[90] flex justify-end font-montserrat">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-brand-dark/40 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'relative z-10 flex h-full w-full flex-col bg-white shadow-drawer animate-slide-in-right',
          widths[width]
        )}
      >
        {/* Header */}
        <div className="shrink-0 flex items-start justify-between gap-3 border-b border-slate-100 bg-slate-50/50 px-4 py-4 sm:px-6 sm:py-5">
          <div className="min-w-0">
            {title && (
              <h2 className="text-lg sm:text-xl font-extrabold text-brand-dark break-words">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-1 text-xs font-medium text-brand-gray-blue break-words">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="shrink-0 w-9 h-9 rounded-r12 flex items-center justify-center text-brand-gray-blue hover:text-brand-dark hover:bg-slate-200/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain px-4 py-5 sm:p-6 space-y-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="shrink-0 border-t border-slate-100 bg-slate-50 px-4 py-3 sm:px-6 sm:py-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] flex flex-wrap items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
