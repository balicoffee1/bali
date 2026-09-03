import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Bell, Send, Smartphone, Sparkles, CheckCircle2 } from 'lucide-react';

export const NotificationsPage: React.FC = () => {
  const { cities, coffeeShops, addToast } = useApp();
  const [title, setTitle] = useState('Happy Island | Счастливые часы!');
  const [message, setMessage] = useState('Скидка 20% на весь авторский кофе сегодня до 18:00! Ждем вас в гости ☕');
  const [targetCityId, setTargetCityId] = useState<string>('');
  const [targetShopId, setTargetShopId] = useState<string>('');
  const [isSending, setIsSending] = useState(false);

  const handleSendBroadcast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !message.trim()) return;

    setIsSending(true);
    try {
      const res = await api.broadcastNotification(
        title,
        message,
        targetCityId ? Number(targetCityId) : undefined,
        targetShopId ? Number(targetShopId) : undefined
      );
      addToast({
        type: 'success',
        title: 'Уведомление отправлено!',
        message: `Рассылка успешно доставлена получателям (~${res.recipients_count} устройств)`,
      });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось отправить рассылку' });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in font-montserrat max-w-5xl">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Broadcast Form */}
        <Card className="lg:col-span-2 space-y-5">
          <div>
            <h3 className="text-base font-extrabold text-brand-dark flex items-center gap-2">
              <Bell className="w-5 h-5 text-brand-dark-blue" />
              Конструктор Push-рассылки
            </h3>
            <p className="text-xs text-brand-gray-blue mt-0.5">
              Отправка всплывающего сообщения в мобильное приложение клиентов
            </p>
          </div>

          <form onSubmit={handleSendBroadcast} className="space-y-4">
            <Input
              label="Заголовок Push-уведомления"
              placeholder="Например: Скидка 15% на новинки недели!"
              value={title}
              onChange={e => setTitle(e.target.value)}
              requiredAsterisk
            />

            <div className="space-y-1.5 font-montserrat">
              <label className="block text-xs font-semibold text-brand-dark-blue">
                Текст сообщения
                <span className="text-brand-red ml-1 font-bold">*</span>
              </label>
              <textarea
                rows={4}
                value={message}
                onChange={e => setMessage(e.target.value)}
                placeholder="Введите текст сообщения..."
                className="w-full bg-brand-light-gray text-brand-dark text-sm font-medium rounded-r12 p-3.5 border border-transparent focus:border-brand-lime focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-lime/20 transition-all resize-none"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Таргетинг по городу"
                value={targetCityId}
                onChange={e => setTargetCityId(e.target.value)}
                options={[
                  { value: '', label: 'Все города (Все пользователи)' },
                  ...cities.map(c => ({ value: c.id, label: c.name })),
                ]}
              />

              <Select
                label="Таргетинг по кофейне"
                value={targetShopId}
                onChange={e => setTargetShopId(e.target.value)}
                options={[
                  { value: '', label: 'Все кофейни' },
                  ...coffeeShops.map(s => ({ value: s.id, label: `${s.street} (${s.city_name})` })),
                ]}
              />
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full"
                isLoading={isSending}
                leftIcon={<Send className="w-4 h-4" />}
              >
                Отправить рассылку клиентам
              </Button>
            </div>
          </form>
        </Card>

        {/* Live Smartphone Preview */}
        <div className="flex flex-col items-center">
          <p className="text-xs font-bold text-brand-gray-blue uppercase tracking-wider mb-3">
            Предпросмотр на смартфоне
          </p>

          <div className="w-[280px] bg-brand-dark rounded-[40px] p-3 shadow-2xl border-4 border-slate-700">
            {/* Phone screen */}
            <div className="bg-[#1C1D21] rounded-[32px] overflow-hidden text-white flex flex-col justify-between h-[420px] p-4 relative">
              {/* Top notch */}
              <div className="w-24 h-4 bg-brand-dark rounded-full mx-auto mb-4"></div>

              {/* Push notification banner */}
              <div className="bg-slate-800/90 backdrop-blur-md rounded-2xl p-3 border border-white/10 shadow-lg animate-fade-in-up space-y-1">
                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3.5 h-3.5 rounded-full bg-brand-lime flex items-center justify-center text-[8px] text-brand-dark font-bold">
                      ☕
                    </div>
                    <span className="font-bold text-white">Happy Island</span>
                  </div>
                  <span>сейчас</span>
                </div>
                <h5 className="text-xs font-bold text-white mt-1 leading-tight">{title || 'Заголовок'}</h5>
                <p className="text-[11px] text-slate-300 leading-snug line-clamp-3">{message || 'Текст сообщения...'}</p>
              </div>

              {/* Bottom bar */}
              <div className="w-24 h-1 bg-white/30 rounded-full mx-auto"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
