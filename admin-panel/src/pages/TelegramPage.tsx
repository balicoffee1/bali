import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { CoffeeShop, TelegramRecipient } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { cn } from '../utils/cn';
import {
  Send, Store, Users, Clock, Plus, Copy, Check, CheckCircle2,
  ExternalLink, Trash2, ChevronRight, Sparkles, AlertCircle, RefreshCw
} from 'lucide-react';

export const TelegramPage: React.FC = () => {
  const { coffeeShops, addToast } = useApp();

  const [shops, setShops] = useState<CoffeeShop[]>(coffeeShops);
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);

  // Link generation & binding state
  const [tgBindLink, setTgBindLink] = useState<string | null>(null);
  const [tgBindToken, setTgBindToken] = useState<string | null>(null);
  const [isGeneratingLink, setIsGeneratingLink] = useState(false);
  const [hasCopied, setHasCopied] = useState(false);

  // Recipients state
  const [recipients, setRecipients] = useState<TelegramRecipient[]>([]);
  const [isLoadingRecipients, setIsLoadingRecipients] = useState(false);
  const [testingRecipientId, setTestingRecipientId] = useState<string | null>(null);
  const [deletingRecipientId, setDeletingRecipientId] = useState<number | null>(null);

  // Manual fallback state
  const [manualChatId, setManualChatId] = useState('');
  const [manualUsername, setManualUsername] = useState('');
  const [isSavingManual, setIsSavingManual] = useState(false);

  // Synchronize local shops with AppContext
  useEffect(() => {
    if (coffeeShops.length > 0) {
      setShops(coffeeShops);
      if (!selectedShopId) {
        setSelectedShopId(coffeeShops[0].id);
      }
    }
  }, [coffeeShops, selectedShopId]);

  // Selected shop
  const currentShop = shops.find(s => s.id === (selectedShopId || shops[0]?.id));

  // Sync manual inputs when current shop changes
  useEffect(() => {
    if (currentShop) {
      setManualChatId(currentShop.telegram_id || '');
      setManualUsername(currentShop.telegram_username || '');
      setTgBindLink(null);
      setTgBindToken(null);
      setHasCopied(false);
      loadRecipients(currentShop.id);
    }
  }, [currentShop?.id]);

  const loadRecipients = async (shopId: number) => {
    setIsLoadingRecipients(true);
    try {
      const res = await api.getTelegramRecipients(shopId);
      setRecipients(res.recipients || []);
    } catch {
      setRecipients([]);
    } finally {
      setIsLoadingRecipients(false);
    }
  };

  // Live polling for bot start event
  useEffect(() => {
    if (!tgBindToken || !currentShop) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.getTelegramBindStatus(currentShop.id, tgBindToken);
        if (res.bind_event && res.bind_event.status === 'linked') {
          const userTitle = res.bind_event.telegram_username || res.bind_event.first_name || res.bind_event.telegram_id;
          addToast({
            title: 'Сотрудник подключен!',
            message: `Пользователь ${userTitle} успешно привязался к кофейне «${currentShop.street}»`,
            type: 'success',
          });
          setTgBindToken(null);
          setTgBindLink(null);
          loadRecipients(currentShop.id);

          setShops(prev => prev.map(s => s.id === currentShop.id ? {
            ...s,
            telegram_recipients_count: (s.telegram_recipients_count || 0) + 1,
            telegram_id: res.bind_event.telegram_id || s.telegram_id,
            telegram_username: res.bind_event.telegram_username || s.telegram_username,
          } : s));
        }
      } catch {
        // silent polling error
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [tgBindToken, currentShop?.id]);

  // Copy helper
  const copyLink = async (textToCopy?: string) => {
    const text = textToCopy || tgBindLink;
    if (!text) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        textArea.remove();
      }
      setHasCopied(true);
      setTimeout(() => setHasCopied(false), 3000);
      addToast({
        title: 'Ссылка скопирована в буфер!',
        message: 'Отправьте её сотруднику. Ссылка одноразовая и активна 30 минут.',
        type: 'success',
      });
    } catch {
      addToast({
        title: 'Не удалось скопировать',
        message: 'Пожалуйста, выделите ссылку в поле и скопируйте вручную.',
        type: 'warning',
      });
    }
  };

  // Generate binding link
  const handleGenerateLink = async () => {
    if (!currentShop) return;
    setIsGeneratingLink(true);
    try {
      const res = await api.getTelegramBindLink(currentShop.id);
      setTgBindLink(res.link);
      setTgBindToken(res.token);
      await copyLink(res.link);
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось сгенерировать ссылку',
        type: 'error',
      });
    } finally {
      setIsGeneratingLink(false);
    }
  };

  // Test recipient
  const handleTestRecipient = async (telegramId?: string) => {
    if (!currentShop) return;
    setTestingRecipientId(telegramId || 'all');
    try {
      const res = await api.testTelegramNotification(currentShop.id, telegramId);
      if (res.success) {
        addToast({
          title: 'Уведомление отправлено!',
          message: res.message || 'Тестовое сообщение успешно доставлено в Telegram',
          type: 'success',
        });
      } else {
        addToast({
          title: 'Ошибка отправки',
          message: res.error || 'Бот не смог доставить сообщение',
          type: 'error',
        });
      }
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Сбой связи с сервером',
        type: 'error',
      });
    } finally {
      setTestingRecipientId(null);
    }
  };

  // Delete recipient
  const handleDeleteRecipient = async (recipientId: number) => {
    if (!currentShop) return;
    setDeletingRecipientId(recipientId);
    try {
      await api.deleteTelegramRecipient(currentShop.id, recipientId);
      setRecipients(prev => prev.filter(r => r.id !== recipientId));
      setShops(prev => prev.map(s => s.id === currentShop.id ? {
        ...s,
        telegram_recipients_count: Math.max(0, (s.telegram_recipients_count || 1) - 1),
      } : s));
      addToast({
        title: 'Сотрудник отключен',
        message: 'Получатель Telegram удален из кофейни',
        type: 'info',
      });
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось удалить сотрудника',
        type: 'error',
      });
    } finally {
      setDeletingRecipientId(null);
    }
  };

  // Manual save
  const handleSaveManual = async () => {
    if (!currentShop) return;
    setIsSavingManual(true);
    try {
      await api.saveCoffeeShop({
        id: currentShop.id,
        telegram_id: manualChatId.trim(),
        telegram_username: manualUsername.trim(),
      });
      setShops(prev => prev.map(s => s.id === currentShop.id ? {
        ...s,
        telegram_id: manualChatId.trim(),
        telegram_username: manualUsername.trim(),
      } : s));
      addToast({
        title: 'Сохранено',
        message: 'Параметры Telegram обновлены вручную',
        type: 'success',
      });
      loadRecipients(currentShop.id);
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось сохранить настройки',
        type: 'error',
      });
    } finally {
      setIsSavingManual(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in font-montserrat max-w-5xl">
      {/* Header Banner */}
      <Card className="bg-gradient-to-r from-sky-500/10 via-sky-500/5 to-transparent border border-sky-200/80 p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-r18 bg-sky-500 text-white flex items-center justify-center shadow-md shadow-sky-500/20 shrink-0">
              <Send className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-extrabold text-brand-dark">Подключение Telegram-бота</h2>
                <Badge variant="success" size="sm">
                  <CheckCircle2 className="w-3 h-3 mr-1 inline" />
                  Бот активен (@happy_island_bot)
                </Badge>
              </div>
              <p className="text-xs text-brand-dark-blue leading-relaxed max-w-2xl">
                Бот отправляет сотрудникам мгновенные уведомления о новых отзывах гостей и поступивших заказах, а также позволяет бариста смотреть отчеты текущей смены.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href="https://t.me/happy_island_bot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 h-10 px-4 rounded-r12 bg-sky-500 hover:bg-sky-600 active:bg-sky-700 text-white font-semibold text-xs transition-colors shadow-sm"
            >
              <Send className="w-4 h-4" />
              <span>Открыть @happy_island_bot ↗</span>
            </a>
          </div>
        </div>

        {/* 3 Simple Steps Guide */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-sky-100">
          <div className="bg-white/85 p-3 rounded-r12 border border-sky-100 flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
              1
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-800">Выберите кофейню</h4>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                Укажите точку, к которой привязывается сотрудник.
              </p>
            </div>
          </div>

          <div className="bg-white/85 p-3 rounded-r12 border border-sky-100 flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
              2
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-800">Создайте ссылку</h4>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                Нажмите кнопку — ссылка скопируется в буфер.
              </p>
            </div>
          </div>

          <div className="bg-white/85 p-3 rounded-r12 border border-sky-100 flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
              3
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-800">Отправьте человеку</h4>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                Сотрудник жмет «Запустить» в боте и подключается.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Main Connection Flow Card */}
      <Card className="p-6 space-y-6">
        {/* Step 1: Select Coffee Shop */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-bold text-brand-dark flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-brand-dark text-white text-xs flex items-center justify-center font-bold">
                  1
                </span>
                Выберите кофейню
              </h3>
              <p className="text-xs text-brand-gray-blue ml-8">
                Выберите точку сети, к которой нужно подключить сотрудника
              </p>
            </div>

            {currentShop && (
              <Badge variant={recipients.length > 0 ? 'success' : 'neutral'} size="md">
                {recipients.length > 0 ? `🟢 ${recipients.length} сотрудников подключено` : '⚪️ Нет подключений'}
              </Badge>
            )}
          </div>

          {/* Quick Selector Pills */}
          <div className="flex flex-wrap gap-2 pt-1 ml-0 sm:ml-8">
            {shops.map(s => {
              const isSelected = (selectedShopId || shops[0]?.id) === s.id;
              const count = s.telegram_recipients_count ?? (s.telegram_id ? 1 : 0);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedShopId(s.id)}
                  className={cn(
                    'px-3.5 py-2 rounded-r12 text-xs font-semibold flex items-center gap-2 transition-all border select-none',
                    isSelected
                      ? 'bg-brand-dark text-white border-brand-dark shadow-sm'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  )}
                >
                  <span>☕ {s.street}, {s.building_number}</span>
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full font-bold',
                      isSelected
                        ? 'bg-brand-lime text-brand-dark'
                        : count > 0
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-100 text-slate-500'
                    )}
                  >
                    {count > 0 ? `${count} чел.` : '0'}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Selected Shop Info Card */}
          {currentShop && (
            <div className="bg-slate-50 p-4 rounded-r12 border border-slate-200/80 ml-0 sm:ml-8 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-r12 bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm shrink-0">
                  <Store className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">
                    {currentShop.street}, {currentShop.building_number}
                  </h4>
                  <p className="text-[11px] text-slate-500">
                    {currentShop.city_name || 'Альметьевск'} • Часы работы: {currentShop.time_open} – {currentShop.time_close}
                  </p>
                </div>
              </div>

              {recipients.length > 1 && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  leftIcon={<Send className="w-3.5 h-3.5 text-sky-500" />}
                  onClick={() => handleTestRecipient()}
                  disabled={testingRecipientId === 'all'}
                >
                  {testingRecipientId === 'all' ? 'Отправка...' : 'Проверить всех получателей'}
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Step 2: Generate Link & Send */}
        {currentShop && (
          <div className="space-y-4 pt-2 border-t border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-brand-dark flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-brand-dark text-white text-xs flex items-center justify-center font-bold">
                  2
                </span>
                Создайте ссылку для подключения бота
              </h3>
              <p className="text-xs text-brand-gray-blue ml-8">
                Сгенерируйте одноразовую ссылку и отправьте её сотруднику, которому нужно подключиться
              </p>
            </div>

            <div className="ml-0 sm:ml-8 space-y-3">
              <button
                type="button"
                onClick={handleGenerateLink}
                disabled={isGeneratingLink}
                className="w-full sm:w-auto h-11 px-6 rounded-r12 bg-sky-500 hover:bg-sky-600 active:bg-sky-700 text-white font-bold text-xs inline-flex items-center justify-center gap-2 transition-all disabled:opacity-50 active:scale-[0.99] shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>{isGeneratingLink ? 'Генерация ссылки...' : 'Создать ссылку для подключения бота'}</span>
              </button>

              {/* Active Link Box */}
              {tgBindLink && (
                <div className="bg-sky-50/80 border-2 border-sky-300 rounded-r18 p-4 space-y-3 text-xs animate-fade-in shadow-xs">
                  {/* Status header & limits */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 font-bold text-slate-900 text-xs">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
                      </span>
                      <span>Ссылка создана! Ожидание запуска сотрудником...</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-white text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200 shadow-2xs">
                        <Clock className="w-3 h-3 text-amber-500" />
                        <span>Срок: 30 мин</span>
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-white text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200 shadow-2xs">
                        <Users className="w-3 h-3 text-sky-500" />
                        <span>Одноразовая (1 чел.)</span>
                      </span>
                    </div>
                  </div>

                  {/* Explicit user instruction */}
                  <div className="bg-white/90 p-3 rounded-r12 border border-sky-200/70 text-slate-700 text-xs leading-relaxed space-y-1">
                    <p className="font-semibold text-slate-900 flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-sky-500 shrink-0" />
                      Отправьте эту ссылку человеку, которому нужно подключиться:
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Сотрудник перейдет по ссылке и нажмет кнопку <b>«Запустить» (Start)</b> в Telegram. После этого бот мгновенно подключится к кофейне «{currentShop.street}», а ссылка автоматически сгорит.
                    </p>
                  </div>

                  {/* Copy Input Bar */}
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={tgBindLink}
                      onClick={() => copyLink()}
                      className="bg-white border border-slate-200 rounded-r12 px-3.5 py-2.5 text-xs text-slate-800 w-full select-all font-mono outline-none focus:border-sky-400 cursor-pointer shadow-2xs font-semibold"
                      title="Нажмите, чтобы скопировать ссылку"
                    />
                    <button
                      type="button"
                      onClick={() => copyLink()}
                      className={cn(
                        'h-10 px-4 rounded-r12 border text-xs font-bold inline-flex items-center gap-1.5 shrink-0 shadow-xs transition-all active:scale-[0.98]',
                        hasCopied
                          ? 'bg-emerald-500 border-emerald-500 text-white'
                          : 'bg-white border-slate-200 hover:bg-slate-50 text-slate-800'
                      )}
                    >
                      {hasCopied ? (
                        <>
                          <Check className="w-4 h-4 text-white" />
                          <span>Скопировано!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4 text-slate-500" />
                          <span>Копировать</span>
                        </>
                      )}
                    </button>
                    <a
                      href={tgBindLink}
                      target="_blank"
                      rel="noreferrer"
                      className="h-10 px-3 rounded-r12 border border-sky-200 bg-sky-100/70 hover:bg-sky-200 text-sky-800 text-xs font-semibold inline-flex items-center gap-1 shrink-0 transition-colors"
                      title="Открыть ссылку в браузере"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Connected Staff List */}
        {currentShop && (
          <div className="space-y-4 pt-2 border-t border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-brand-dark flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-brand-dark text-white text-xs flex items-center justify-center font-bold">
                  3
                </span>
                Подключенные сотрудники ({recipients.length})
              </h3>
              <p className="text-xs text-brand-gray-blue ml-8">
                Список пользователей Telegram, которые получают уведомления по этой кофейне
              </p>
            </div>

            <div className="ml-0 sm:ml-8">
              {isLoadingRecipients ? (
                <div className="text-center py-6 text-xs text-slate-400">
                  Загрузка списка получателей...
                </div>
              ) : recipients.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {recipients.map(r => (
                    <div
                      key={r.id}
                      className="bg-white p-3.5 rounded-r14 border border-slate-200/90 flex items-center justify-between gap-3 shadow-2xs hover:border-slate-300 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-1">
                        <div className="w-10 h-10 rounded-full bg-sky-100 text-sky-600 flex items-center justify-center font-bold text-xs shrink-0 select-none">
                          {r.first_name
                            ? r.first_name[0].toUpperCase()
                            : r.telegram_username
                            ? r.telegram_username.replace('@', '')[0].toUpperCase()
                            : 'TG'}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-slate-900 text-xs flex items-center gap-1.5 truncate">
                            <span className="truncate">
                              {r.telegram_username || r.first_name || `ID: ${r.telegram_id}`}
                            </span>
                            {r.first_name && r.telegram_username && (
                              <span className="text-[11px] text-slate-400 font-normal shrink-0">
                                ({r.first_name})
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                            Chat ID: {r.telegram_id}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleTestRecipient(r.telegram_id)}
                          disabled={testingRecipientId === r.telegram_id}
                          className="h-8 px-2.5 rounded-lg border border-sky-200 bg-sky-50/70 hover:bg-sky-100 text-sky-700 text-xs font-semibold inline-flex items-center gap-1 transition-colors disabled:opacity-50"
                          title="Отправить тестовое сообщение в Telegram"
                        >
                          <Send className="w-3 h-3 text-sky-500 shrink-0" />
                          <span>{testingRecipientId === r.telegram_id ? 'Отправка...' : 'Тест'}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteRecipient(r.id)}
                          disabled={deletingRecipientId === r.id}
                          className="w-8 h-8 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 flex items-center justify-center transition-colors disabled:opacity-50"
                          title="Отключить сотрудника от кофейни"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-slate-50/70 p-6 rounded-r14 border border-dashed border-slate-200 text-center space-y-2">
                  <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                    <Users className="w-5 h-5" />
                  </div>
                  <p className="text-xs font-bold text-slate-700">
                    В этой кофейне пока нет подключенных сотрудников
                  </p>
                  <p className="text-[11px] text-slate-400 max-w-md mx-auto">
                    Нажмите «Создать ссылку для подключения бота» на шаге 2 выше и отправьте её бариста или управляющему.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Collapsible: Manual Setup Fallback */}
        {currentShop && (
          <details className="group text-xs text-slate-500 pt-3 border-t border-slate-100">
            <summary className="cursor-pointer list-none flex items-center justify-between text-xs font-medium text-slate-500 hover:text-slate-800 py-1 transition-colors">
              <span className="flex items-center gap-1.5">
                <ChevronRight className="w-3.5 h-3.5 transition-transform group-open:rotate-90 text-slate-400" />
                Ручная привязка по Telegram ID / Username (дополнительно)
              </span>
            </summary>
            <div className="space-y-3 pt-3 max-w-lg ml-5">
              <Input
                label="Telegram ID (числовой chat_id)"
                placeholder="Например: 6463435986"
                value={manualChatId}
                onChange={e => setManualChatId(e.target.value)}
              />
              <Input
                label="Telegram Username"
                placeholder="@island_point"
                value={manualUsername}
                onChange={e => setManualUsername(e.target.value)}
              />
              <div className="flex items-center justify-between pt-1">
                <p className="text-[11px] text-slate-400">
                  ID можно узнать через{' '}
                  <a
                    href="https://t.me/getmyid_bot"
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-600 underline"
                  >
                    @getmyid_bot
                  </a>
                </p>
                <Button
                  size="sm"
                  variant="dark"
                  onClick={handleSaveManual}
                  isLoading={isSavingManual}
                  disabled={isSavingManual}
                >
                  Сохранить
                </Button>
              </div>
            </div>
          </details>
        )}
      </Card>
    </div>
  );
};
