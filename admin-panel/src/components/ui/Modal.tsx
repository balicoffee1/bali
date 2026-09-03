import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useDialogBehavior } from '../../utils/dialog';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'md',
}) => {
  useDialogBehavior(isOpen, onClose);

  if (!isOpen) return null;

  const maxWidths = {
    sm: 'sm:max-w-sm',
    md: 'sm:max-w-md',
    lg: 'sm:max-w-lg',
    xl: 'sm:max-w-2xl',
  };

  // Рендерим в body: у страниц есть анимация с transform, а такой предок
  // становится containing block для position: fixed и «схлопывает» диалог
  // внутрь контента страницы.
  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 font-montserrat">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-brand-dark/40 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog box */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'relative z-10 flex w-full max-h-[calc(100dvh-2rem)] flex-col overflow-hidden rounded-r18 bg-white shadow-2xl animate-fade-in-up',
          maxWidths[maxWidth]
        )}
      >
        {/* Header */}
        <div className="shrink-0 flex items-start justify-between gap-3 border-b border-slate-100 px-5 pt-5 pb-3 sm:px-6">
          <div className="min-w-0">
            {title && <h3 className="text-base sm:text-lg font-bold text-brand-dark break-words">{title}</h3>}
            {description && (
              <p className="mt-0.5 text-xs text-brand-gray-blue break-words">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-brand-gray-blue hover:text-brand-dark hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain px-5 py-4 sm:px-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
};
