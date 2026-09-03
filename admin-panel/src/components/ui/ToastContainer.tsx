import React from 'react';
import { createPortal } from 'react-dom';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { cn } from '../../utils/cn';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useApp();

  if (toasts.length === 0) return null;

  // Рендерим в body и выше диалогов: с z-50 уведомление уходило ЗА панель
  // Drawer'а (z-90) и Modal (z-100). Из-за этого ошибка сохранения, после
  // которой диалог остаётся открытым, вообще не была видна.
  return createPortal(
    <div className="fixed bottom-5 right-5 z-[200] flex flex-col gap-2.5 max-w-[calc(100vw-2.5rem)] sm:max-w-sm w-full pointer-events-none font-montserrat">
      {toasts.map(toast => {
        const icons = {
          success: <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />,
          error: <AlertCircle className="w-5 h-5 text-brand-red shrink-0" />,
          warning: <AlertCircle className="w-5 h-5 text-brand-orange shrink-0" />,
          info: <Info className="w-5 h-5 text-brand-blue shrink-0" />,
        };

        const borders = {
          success: 'border-emerald-200 bg-white',
          error: 'border-red-200 bg-white',
          warning: 'border-amber-200 bg-white',
          info: 'border-blue-200 bg-white',
        };

        return (
          <div
            key={toast.id}
            className={cn(
              'pointer-events-auto p-4 rounded-r18 shadow-lg border flex items-start gap-3 animate-slide-in-right',
              borders[toast.type]
            )}
          >
            {icons[toast.type]}
            <div className="flex-1">
              <h4 className="text-xs font-bold text-brand-dark">{toast.title}</h4>
              {toast.message && <p className="text-xs text-brand-dark-blue mt-0.5">{toast.message}</p>}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-brand-gray-blue hover:text-brand-dark"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>,
    document.body
  );
};
