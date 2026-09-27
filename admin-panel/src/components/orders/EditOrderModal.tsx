import React, { useState, useEffect } from 'react';
import { Order } from '../../types';
import { api } from '../../api/client';
import { useApp } from '../../context/AppContext';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Clock, Send, AlertCircle, Snowflake, Flame } from 'lucide-react';
import { cn } from '../../utils/cn';

interface EditOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: Order;
  onOrderUpdated: (updatedOrder: Order) => void;
}

export const EditOrderModal: React.FC<EditOrderModalProps> = ({
  isOpen,
  onClose,
  order,
  onOrderUpdated,
}) => {
  const { addToast } = useApp();
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Helper to format Date to input "YYYY-MM-DDTHH:mm"
  const formatDateTimeLocal = (d: Date) => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const getInitialDate = (): Date => {
    if (order.time_is_finish) {
      const parsed = new Date(order.time_is_finish.replace(' ', 'T'));
      if (!isNaN(parsed.getTime())) return parsed;
    }
    const d = new Date();
    d.setMinutes(d.getMinutes() + 15);
    return d;
  };

  const [selectedDateTime, setSelectedDateTime] = useState<string>(() => formatDateTimeLocal(getInitialDate()));

  useEffect(() => {
    if (isOpen) {
      setSelectedDateTime(formatDateTimeLocal(getInitialDate()));
      setReason(order.cancellation_reason || '');
      setFormError(null);
    }
  }, [isOpen, order]);

  const addMinutes = (mins: number) => {
    const current = new Date(selectedDateTime);
    const base = isNaN(current.getTime()) ? new Date() : current;
    base.setMinutes(base.getMinutes() + mins);
    setSelectedDateTime(formatDateTimeLocal(base));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setFormError('Укажите причину изменения времени заказа (клиент увидит её в уведомлении).');
      return;
    }

    const selectedDate = new Date(selectedDateTime);
    if (isNaN(selectedDate.getTime())) {
      setFormError('Укажите корректную дату и время.');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    try {
      // Backend PatchOrderSerializer accepts ISO string or '%Y-%m-%d %H:%M:%S'
      const formattedIso = selectedDate.toISOString();
      const updated = await api.editOrderTime(order.id, formattedIso, reason.trim());
      addToast({
        type: 'success',
        title: 'Заказ изменён',
        message: 'Заказ успешно изменён и отправлен клиенту на подтверждение',
      });
      onOrderUpdated(updated);
      onClose();
    } catch (err: any) {
      setFormError(err.message || 'Не удалось обновить заказ.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Изменение времени заказа #${order.id}`}
      description="Укажите новое время готовности и причину. Клиент получит уведомление и диалог подтверждения."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {formError && (
          <div className="bg-red-50 text-brand-red p-3 rounded-r12 text-xs flex items-center gap-2 border border-red-200">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{formError}</span>
          </div>
        )}

        {/* Order Items Summary */}
        <div className="bg-brand-light-gray p-3 rounded-r14 space-y-1.5 border border-slate-200/60">
          <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Состав заказа</p>
          <div className="flex flex-wrap gap-1.5">
            {order.items.map(it => (
              <div
                key={it.id}
                className="bg-white border border-slate-200 px-2 py-1 rounded-lg text-xs font-semibold text-brand-dark flex items-center gap-1.5"
              >
                <span>{it.product_name} ({it.size}) × {it.amount}</span>
                {it.temperature_type === 'Cold' && (
                  <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-blue-700 bg-blue-50 border border-blue-200 px-1 py-0.2 rounded-full">
                    <Snowflake className="w-2.5 h-2.5 text-blue-500" />
                    Холодный
                  </span>
                )}
                {it.temperature_type === 'Hot' && (
                  <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-orange-700 bg-orange-50 border border-orange-200 px-1 py-0.2 rounded-full">
                    <Flame className="w-2.5 h-2.5 text-orange-500" />
                    Горячий
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Time adjustments */}
        <div>
          <label className="block text-xs font-bold text-brand-dark mb-1 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-brand-gray-blue" />
            Новое время готовности
          </label>
          <input
            type="datetime-local"
            value={selectedDateTime}
            onChange={e => setSelectedDateTime(e.target.value)}
            className="w-full bg-white border border-slate-200 rounded-r12 px-3 py-2 text-xs font-semibold text-brand-dark focus:outline-none focus:border-brand-dark-blue focus:ring-1 focus:ring-brand-dark-blue"
            required
          />

          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-[11px] text-brand-gray-blue font-medium mr-1">Быстро добавить:</span>
            {[5, 10, 15, 30].map(mins => (
              <button
                key={mins}
                type="button"
                onClick={() => addMinutes(mins)}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-brand-dark rounded-md text-xs font-bold transition-colors"
              >
                +{mins}м
              </button>
            ))}
          </div>
        </div>

        {/* Reason for change */}
        <div>
          <label className="block text-xs font-bold text-brand-dark mb-1">
            Причина изменения <span className="text-brand-red">*</span>
          </label>
          <textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Например: Большая очередь, задержка поставки молока, перегрев кофемашины..."
            rows={3}
            className="w-full bg-white border border-slate-200 rounded-r12 p-3 text-xs text-brand-dark placeholder:text-slate-400 focus:outline-none focus:border-brand-dark-blue focus:ring-1 focus:ring-brand-dark-blue resize-none"
            required
          />
          <p className="text-[11px] text-brand-gray-blue mt-1">
            Эта причина отобразится в модальном окне у клиента в мобильном приложении.
          </p>
        </div>

        {/* Modal actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
          <Button variant="ghost" size="sm" type="button" onClick={onClose} disabled={isSubmitting}>
            Отмена
          </Button>
          <Button
            variant="primary"
            size="sm"
            type="submit"
            isLoading={isSubmitting}
            leftIcon={<Send className="w-3.5 h-3.5" />}
            disabled={!reason.trim()}
          >
            Отправить на подтверждение
          </Button>
        </div>
      </form>
    </Modal>
  );
};
