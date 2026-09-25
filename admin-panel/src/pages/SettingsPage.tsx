import React, { useState, useEffect } from 'react';
import { cn } from '../utils/cn';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { CoffeeShop, City, TelegramRecipient } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { PhoneInput } from '../components/ui/PhoneInput';
import { Select } from '../components/ui/Select';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Table, Column } from '../components/ui/Table';
import {
  Store, MapPin, Plus, Edit2, Trash2, CheckCircle2,
  Clock, Phone, Mail, Send, ShieldCheck, CreditCard,
  Layers, RefreshCw, Key, Server, Users, Copy, ChevronRight, ExternalLink, Check
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { cities: appCities, coffeeShops: appShops, addToast, activeSettingsTab, setActiveSettingsTab, navigateTo } = useApp();
  const [shops, setShops] = useState<CoffeeShop[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingShop, setIsSavingShop] = useState(false);
  const [isSavingCity, setIsSavingCity] = useState(false);

  // Coffee Shop Drawer / Modal state
  const [editingShop, setEditingShop] = useState<Partial<CoffeeShop> | null>(null);
  const [isShopDrawerOpen, setIsShopDrawerOpen] = useState(false);

  // City Modal state
  const [editingCity, setEditingCity] = useState<Partial<City> | null>(null);
  const [isCityModalOpen, setIsCityModalOpen] = useState(false);

  // LifePay Modal state
  const [isLifePayModalOpen, setIsLifePayModalOpen] = useState(false);
  const [targetLifePayShopId, setTargetLifePayShopId] = useState<number | 'all'>('all');
  const [lifePayLogin, setLifePayLogin] = useState('');
  const [lifePayApiKey, setLifePayApiKey] = useState('');
  const [isSavingLifePay, setIsSavingLifePay] = useState(false);
  const [isTestingLifePay, setIsTestingLifePay] = useState(false);

  // Telegram Integration state
  const [tgBindLink, setTgBindLink] = useState<string | null>(null);
  const [tgBindToken, setTgBindToken] = useState<string | null>(null);
  const [isGeneratingTgLink, setIsGeneratingTgLink] = useState(false);
  const [isTestingTg, setIsTestingTg] = useState(false);
  const [isUnlinkingTg, setIsUnlinkingTg] = useState(false);
  const [tgRecipients, setTgRecipients] = useState<TelegramRecipient[]>([]);
  const [isLoadingRecipients, setIsLoadingRecipients] = useState(false);
  const [testingRecipientId, setTestingRecipientId] = useState<string | null>(null);
  const [deletingRecipientId, setDeletingRecipientId] = useState<number | null>(null);
  const [hasCopiedLink, setHasCopiedLink] = useState(false);
  const [selectedTgShopId, setSelectedTgShopId] = useState<number | null>(null);
  const [tgManualId, setTgManualId] = useState('');
  const [tgManualUsername, setTgManualUsername] = useState('');
  const [isSavingManualTg, setIsSavingManualTg] = useState(false);

  useEffect(() => {
    loadSettingsData();
  }, []);

  useEffect(() => {
    if (activeSettingsTab === 'telegram') {
      navigateTo('telegram');
    }
  }, [activeSettingsTab]);

  const loadRecipients = async (shopId: number) => {
    setIsLoadingRecipients(true);
    try {
      const res = await api.getTelegramRecipients(shopId);
      setTgRecipients(res.recipients || []);
    } catch {
      // ignore
    } finally {
      setIsLoadingRecipients(false);
    }
  };

  useEffect(() => {
    if (shops.length > 0 && !selectedTgShopId) {
      setSelectedTgShopId(shops[0].id);
    }
  }, [shops, selectedTgShopId]);

  useEffect(() => {
    if (isShopDrawerOpen && editingShop?.id) {
      loadRecipients(editingShop.id);
    } else if (activeSettingsTab === 'telegram') {
      const targetId = selectedTgShopId || shops[0]?.id;
      if (targetId) {
        loadRecipients(targetId);
      }
    } else {
      setTgRecipients([]);
      setTgBindLink(null);
      setTgBindToken(null);
      setHasCopiedLink(false);
    }
  }, [editingShop?.id, isShopDrawerOpen, activeSettingsTab, selectedTgShopId, shops]);

  const currentTgShop = shops.find(s => s.id === (selectedTgShopId || shops[0]?.id));

  useEffect(() => {
    if (currentTgShop) {
      setTgManualId(currentTgShop.telegram_id || '');
      setTgManualUsername(currentTgShop.telegram_username || '');
    }
  }, [currentTgShop?.id]);

  // Poll for Telegram link completion when token is active
  useEffect(() => {
    const shopId = isShopDrawerOpen ? editingShop?.id : selectedTgShopId;
    if (!tgBindToken || !shopId) return;
    const interval = setInterval(async () => {
      try {
        const res = await api.getTelegramBindStatus(shopId, tgBindToken);
        if (res.bind_event && res.bind_event.status === 'linked') {
          const userTitle = res.bind_event.telegram_username || res.bind_event.first_name || res.bind_event.telegram_id;
          addToast({
            title: 'Пользователь добавлен!',
            message: `К кофейне успешно подключен Telegram: ${userTitle}`,
            type: 'success',
          });
          setTgBindToken(null);
          setTgBindLink(null);
          loadRecipients(shopId);
          setEditingShop(prev => (prev && prev.id === shopId) ? {
            ...prev,
            telegram_id: res.bind_event.telegram_id || prev.telegram_id,
            telegram_username: res.bind_event.telegram_username || prev.telegram_username,
            telegram_recipients_count: (prev.telegram_recipients_count || 0) + 1,
          } : prev);
          setShops(prev => prev.map(s => s.id === shopId ? {
            ...s,
            telegram_recipients_count: (s.telegram_recipients_count || 0) + 1,
            telegram_id: res.bind_event.telegram_id || s.telegram_id,
            telegram_username: res.bind_event.telegram_username || s.telegram_username,
          } : s));
        }
      } catch (e) {
        // ignore polling error
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [tgBindToken, editingShop?.id, selectedTgShopId, isShopDrawerOpen]);

  const copyTgLinkToClipboard = async (linkToCopy?: string) => {
    const text = linkToCopy || tgBindLink;
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
      setHasCopiedLink(true);
      setTimeout(() => setHasCopiedLink(false), 3000);
      addToast({
        title: 'Ссылка скопирована в буфер!',
        message: 'Лимит: 1 подключение (одноразовая). Ссылка активна 30 минут.',
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

  const handleGenerateTgLink = async (shopIdOverride?: number) => {
    const shopId = shopIdOverride ?? (isShopDrawerOpen ? editingShop?.id : selectedTgShopId);
    if (!shopId) return;
    setIsGeneratingTgLink(true);
    try {
      const res = await api.getTelegramBindLink(shopId);
      setTgBindLink(res.link);
      setTgBindToken(res.token);
      await copyTgLinkToClipboard(res.link);
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось получить ссылку привязки',
        type: 'error',
      });
    } finally {
      setIsGeneratingTgLink(false);
    }
  };

  const handleTestRecipient = async (telegramId?: string, shopIdOverride?: number) => {
    const shopId = shopIdOverride ?? (isShopDrawerOpen ? editingShop?.id : selectedTgShopId);
    if (!shopId) return;
    setTestingRecipientId(telegramId || 'all');
    try {
      const res = await api.testTelegramNotification(shopId, telegramId);
      if (res.success) {
        addToast({
          title: 'Успешно!',
          message: res.message || 'Тестовое уведомление доставлено в Telegram!',
          type: 'success',
        });
      } else {
        addToast({
          title: 'Ошибка отправки',
          message: res.error || 'Не удалось отправить сообщение',
          type: 'error',
        });
      }
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Сбой при проверке связи',
        type: 'error',
      });
    } finally {
      setTestingRecipientId(null);
    }
  };

  const handleDeleteRecipient = async (recipientId: number, shopIdOverride?: number) => {
    const shopId = shopIdOverride ?? (isShopDrawerOpen ? editingShop?.id : selectedTgShopId);
    if (!shopId) return;
    setDeletingRecipientId(recipientId);
    try {
      await api.deleteTelegramRecipient(shopId, recipientId);
      setTgRecipients(prev => prev.filter(r => r.id !== recipientId));
      setEditingShop(prev => (prev && prev.id === shopId) ? {
        ...prev,
        telegram_recipients_count: Math.max(0, (prev.telegram_recipients_count || 1) - 1),
      } : prev);
      setShops(prev => prev.map(s => s.id === shopId ? {
        ...s,
        telegram_recipients_count: Math.max(0, (s.telegram_recipients_count || 1) - 1),
      } : s));
      addToast({
        title: 'Удалено',
        message: 'Получатель Telegram удален из кофейни',
        type: 'info',
      });
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err?.message || 'Не удалось удалить получателя',
        type: 'error',
      });
    } finally {
      setDeletingRecipientId(null);
    }
  };

  const handleUnlinkTg = async (shopIdOverride?: number) => {
    const shopId = shopIdOverride ?? (isShopDrawerOpen ? editingShop?.id : selectedTgShopId);
    if (!shopId) return;
    if (!window.confirm('Вы уверены, что хотите отвязать всех сотрудников Telegram от этой точки?')) return;
    setIsUnlinkingTg(true);
    try {
      await api.unlinkTelegram(shopId);
      setTgRecipients([]);
      setTgBindLink(null);
      setTgBindToken(null);
      setEditingShop(prev => (prev && prev.id === shopId) ? {
        ...prev,
        telegram_id: '',
        telegram_username: '',
        telegram_recipients_count: 0,
      } : prev);
      setShops(prev => prev.map(s => s.id === shopId ? {
        ...s,
        telegram_id: '',
        telegram_username: '',
        telegram_recipients_count: 0,
      } : s));
      addToast({
        title: 'Отвязано',
        message: 'Все получатели Telegram для точки удалены',
        type: 'info',
      });
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось отвязать Telegram',
        type: 'error',
      });
    } finally {
      setIsUnlinkingTg(false);
    }
  };

  const handleSaveManualTg = async () => {
    const shopId = selectedTgShopId || shops[0]?.id;
    if (!shopId) return;
    setIsSavingManualTg(true);
    try {
      const res = await api.saveCoffeeShop({
        id: shopId,
        telegram_id: tgManualId,
        telegram_username: tgManualUsername,
      });
      setShops(prev => prev.map(s => s.id === shopId ? { ...s, ...res } : s));
      loadRecipients(shopId);
      addToast({
        title: 'Сохранено',
        message: 'Параметры Telegram успешно обновлены',
        type: 'success',
      });
    } catch (err: any) {
      addToast({
        title: 'Ошибка',
        message: err.message || 'Не удалось сохранить параметры',
        type: 'error',
      });
    } finally {
      setIsSavingManualTg(false);
    }
  };


  const loadSettingsData = async () => {
    setIsLoading(true);
    try {
      const [shopsData, citiesData] = await Promise.all([
        api.getCoffeeShops(),
        api.getCities(),
      ]);
      setShops(shopsData);
      setCities(citiesData);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Save Coffee Shop ---
  const handleSaveShop = async () => {
    if (!editingShop || !editingShop.street?.trim()) {
      addToast({ type: 'error', title: 'Ошибка', message: 'Укажите улицу кофейни' });
      return;
    }
    setIsSavingShop(true);
    try {
      const saved = await api.saveCoffeeShop(editingShop);
      setShops(prev => {
        const exists = prev.some(s => s.id === saved.id);
        if (exists) return prev.map(s => (s.id === saved.id ? saved : s));
        return [saved, ...prev];
      });
      setIsShopDrawerOpen(false);
      setEditingShop(null);
      addToast({
        type: 'success',
        title: 'Успешно',
        message: editingShop.id ? 'Данные кофейни обновлены' : 'Новая кофейня успешно добавлена',
      });
    } catch (err: any) {
      addToast({ type: 'error', title: 'Ошибка', message: err?.message || 'Не удалось сохранить кофейню' });
    } finally {
      setIsSavingShop(false);
    }
  };

  const handleDeleteShop = async (id: number) => {
    if (!confirm('Вы уверены, что хотите удалить эту точку кофейни?')) return;
    try {
      await api.deleteCoffeeShop(id);
      setShops(prev => prev.filter(s => s.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Кофейня удалена' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить кофейню' });
    }
  };

  // --- Save City ---
  const handleSaveCity = async () => {
    if (!editingCity || !editingCity.name?.trim()) {
      addToast({ type: 'error', title: 'Ошибка', message: 'Укажите название города' });
      return;
    }
    setIsSavingCity(true);
    try {
      const saved = await api.saveCity(editingCity);
      setCities(prev => {
        const exists = prev.some(c => c.id === saved.id);
        if (exists) return prev.map(c => (c.id === saved.id ? saved : c));
        return [...prev, saved];
      });
      setIsCityModalOpen(false);
      setEditingCity(null);
      addToast({ type: 'success', title: 'Город сохранен', message: saved.name });
    } catch (err: any) {
      addToast({ type: 'error', title: 'Ошибка', message: err?.message || 'Не удалось сохранить город' });
    } finally {
      setIsSavingCity(false);
    }
  };

  const handleDeleteCity = async (id: number) => {
    if (!confirm('Удалить город?')) return;
    try {
      await api.deleteCity(id);
      setCities(prev => prev.filter(c => c.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Город удален' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить город' });
    }
  };

  // --- LifePay Modal Handlers ---
  const openLifePayModal = (shopId: number | 'all') => {
    setTargetLifePayShopId(shopId);
    if (shopId !== 'all') {
      const shop = shops.find(s => s.id === shopId);
      setLifePayLogin(shop?.lifepay_login || '');
      setLifePayApiKey('');
    } else {
      setLifePayLogin('');
      setLifePayApiKey('');
    }
    setIsLifePayModalOpen(true);
  };

  const handleTestLifePay = async () => {
    if (!lifePayLogin.trim() || !lifePayApiKey.trim()) {
      addToast({ type: 'error', title: 'Ошибка', message: 'Введите логин и API ключ для проверки' });
      return;
    }
    setIsTestingLifePay(true);
    try {
      const res = await api.testLifePayConnection(lifePayApiKey, lifePayLogin);
      if (res.valid) {
        addToast({ type: 'success', title: 'LifePay подключен', message: res.message || 'Реквизиты успешно проверены' });
      } else {
        addToast({ type: 'error', title: 'Ошибка LifePay', message: res.error || 'Проверка не пройдена' });
      }
    } catch (err: any) {
      addToast({ type: 'error', title: 'Ошибка', message: err?.message || 'Не удалось проверить реквизиты' });
    } finally {
      setIsTestingLifePay(false);
    }
  };

  const handleSaveLifePay = async () => {
    if (!lifePayLogin.trim() || !lifePayApiKey.trim()) {
      addToast({ type: 'error', title: 'Ошибка', message: 'Укажите логин и API ключ LifePay' });
      return;
    }
    setIsSavingLifePay(true);
    try {
      if (targetLifePayShopId === 'all') {
        const res = await api.bulkSaveLifePay(lifePayApiKey, lifePayLogin);
        addToast({
          type: 'success',
          title: 'Успешно',
          message: `Реквизиты LifePay обновлены для ${res.updated_count} кофеен сети`,
        });
      } else {
        await api.saveCoffeeShop({
          id: targetLifePayShopId,
          lifepay_login: lifePayLogin,
          lifepay_api_key: lifePayApiKey,
        });
        addToast({
          type: 'success',
          title: 'Успешно',
          message: 'Реквизиты LifePay обновлены для выбранной точки',
        });
      }
      await loadSettingsData();
      setIsLifePayModalOpen(false);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Ошибка', message: err?.message || 'Не удалось сохранить реквизиты' });
    } finally {
      setIsSavingLifePay(false);
    }
  };

  const shopColumns: Column<CoffeeShop>[] = [
    {
      header: 'Адрес кофейни',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-r12 bg-brand-light-gray flex items-center justify-center text-lg shrink-0">
            ☕
          </div>
          <div>
            <p className="font-bold text-brand-dark">{row.street}, {row.building_number}</p>
            <span className="text-[10px] text-brand-gray-blue font-semibold">{row.city_name || 'Альметьевск'}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'График работы',
      accessor: row => (
        <span className="text-xs font-semibold text-brand-dark flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-brand-gray-blue" />
          {row.time_open} – {row.time_close}
        </span>
      ),
    },
    {
      header: 'Контакты',
      accessor: row => (
        <div className="space-y-0.5">
          {row.phone_number && <p className="text-xs font-semibold text-brand-dark">{row.phone_number}</p>}
          <span className="text-[10px] text-brand-gray-blue block">{row.email}</span>
        </div>
      ),
    },
    {
      header: 'CRM / Слой',
      accessor: row => (
        <div className="flex items-center gap-1.5">
          <Badge variant="info" size="sm">QuickResto</Badge>
          {row.crm_layer_name && <span className="text-[10px] text-brand-gray-blue">({row.crm_layer_name})</span>}
        </div>
      ),
    },
    {
      header: 'LifePay / СБП',
      accessor: row => (
        row.has_lifepay_api_key ? (
          <Badge variant="success" size="sm">СБП: настроен</Badge>
        ) : (
          <Badge variant="warning" size="sm">СБП: не настроен</Badge>
        )
      ),
    },
    {
      header: 'Telegram-бот',
      accessor: row => {
        const count = row.telegram_recipients_count ?? (row.telegram_id ? 1 : 0);
        if (count > 0) {
          const label = count === 1 && row.telegram_username
            ? row.telegram_username
            : `${count} ${count === 1 ? 'получатель' : count < 5 ? 'получателя' : 'получателей'}`;
          return (
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                navigateTo('telegram');
              }}
              className="hover:opacity-80 transition-opacity text-left cursor-pointer"
              title="Перейти к управлению Telegram-ботом"
            >
              <Badge variant="success" size="sm">
                <CheckCircle2 className="w-3 h-3 mr-1 inline" />
                {label}
              </Badge>
            </button>
          );
        }
        return (
          <button
            type="button"
            onClick={e => {
              e.stopPropagation();
              navigateTo('telegram');
            }}
            className="hover:opacity-80 transition-opacity text-left cursor-pointer"
            title="Подключить Telegram-бота"
          >
            <Badge variant="neutral" size="sm">Подключить +</Badge>
          </button>
        );
      },
    },
    {
      header: 'Действия',
      align: 'right',
      accessor: row => (
        <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => {
              setEditingShop(row);
              setIsShopDrawerOpen(true);
            }}
            className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
            title="Редактировать параметры"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleDeleteShop(row.id)}
            className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
            title="Удалить точку"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Tabs Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <Tabs
          tabs={[
            { id: 'shops', label: 'Кофейни и Точки', count: shops.length },
            { id: 'cities', label: 'Города присутствия', count: cities.length },
            { id: 'crm', label: 'CRM Системы' },
            { id: 'acquiring', label: 'Эквайринг и Оплата' },
          ]}
          activeTab={activeSettingsTab}
          onChange={t => setActiveSettingsTab(t as any)}
        />

        <div className="flex items-center gap-2">
          {activeSettingsTab === 'shops' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => {
                setEditingShop({
                  city: cities[0]?.id || 1,
                  street: '',
                  building_number: '',
                  email: '',
                  telegram_username: '',
                  time_open: '08:00',
                  time_close: '22:00',
                  crm_email: '',
                  crm_layer_name: '',
                  inn: '',
                  phone_number: '',
                  lifepay_login: '',
                  lifepay_api_key: '',
                });
                setIsShopDrawerOpen(true);
              }}
            >
              Добавить кофейню
            </Button>
          )}

          {activeSettingsTab === 'cities' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => {
                setEditingCity({ name: '' });
                setIsCityModalOpen(true);
              }}
            >
              Добавить город
            </Button>
          )}
        </div>
      </div>

      {/* TAB 1: COFFEE SHOPS */}
      {activeSettingsTab === 'shops' && (
        <Table
          columns={shopColumns}
          data={shops}
          keyExtractor={s => s.id}
          onRowClick={s => {
            setEditingShop(s);
            setIsShopDrawerOpen(true);
          }}
          isLoading={isLoading}
          emptyMessage="Кофейни не найдены"
        />
      )}

      {/* TAB 2: CITIES */}
      {activeSettingsTab === 'cities' && (
        <Table
          columns={[
            { header: 'ID', accessor: r => `#${r.id}` },
            {
              header: 'Название города',
              accessor: r => (
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-brand-dark-blue" />
                  <span className="font-bold text-brand-dark">{r.name}</span>
                </div>
              ),
            },
            {
              header: 'Действия',
              align: 'right',
              accessor: r => (
                <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => {
                      setEditingCity(r);
                      setIsCityModalOpen(true);
                    }}
                    className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteCity(r.id)}
                    className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ),
            },
          ]}
          data={cities}
          keyExtractor={c => c.id}
          isLoading={isLoading}
          emptyMessage="Города не созданы"
        />
      )}

      {/* TAB: TELEGRAM BOT REDIRECT (IF DIRECT TAB URL OPENED) */}
      {activeSettingsTab === 'telegram' && (
        <Card className="p-8 text-center space-y-4 max-w-xl mx-auto my-8">
          <div className="w-12 h-12 rounded-full bg-sky-100 text-sky-600 mx-auto flex items-center justify-center">
            <Send className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800">Раздел перенесен</h3>
            <p className="text-xs text-slate-500">
              Подключение Telegram-бота теперь находится в отдельном пункте главного левого меню.
            </p>
          </div>
          <div className="pt-2">
            <Button variant="dark" onClick={() => navigateTo('telegram')}>
              Перейти в раздел «Telegram-бот»
            </Button>
          </div>
        </Card>
      )}

      {/* TAB 4: CRM SYSTEMS */}
      {activeSettingsTab === 'crm' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* QuickResto */}
            <Card className="space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-r12 bg-amber-500/20 text-amber-700 flex items-center justify-center font-extrabold text-xl">
                    QR
                  </div>
                  <div>
                    <h4 className="text-base font-extrabold text-brand-dark">QuickResto API</h4>
                    <p className="text-xs text-brand-gray-blue">Кассовая и учетная система сети</p>
                  </div>
                </div>
                <Badge variant="success">Подключено</Badge>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Статус синхронизации меню:</span>
                  <span className="font-bold text-emerald-600">Активно (Авто)</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Базовый эндпоинт:</span>
                  <span className="font-mono text-brand-dark">api.quickresto.ru/v1</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Слой заведения по умолчанию:</span>
                  <span className="font-bold text-brand-dark">Основной зал</span>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between">
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={<RefreshCw className="w-4 h-4" />}
                  onClick={() => addToast({ type: 'success', title: 'Синхронизация', message: 'Каталог QuickResto актуализирован' })}
                >
                  Синхронизировать меню
                </Button>
                <Button size="sm" variant="dark">
                  Параметры API
                </Button>
              </div>
            </Card>

          </div>
        </div>
      )}

      {/* TAB 4: ACQUIRING & PAYMENTS */}
      {activeSettingsTab === 'acquiring' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">

            {/* LifePay */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">LifePay & СБП</h4>
                <Badge variant={shops.some(s => s.has_lifepay_api_key) ? "success" : "warning"}>
                  {shops.some(s => s.has_lifepay_api_key) ? "Активен" : "Требует настройки"}
                </Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Оплата через СБП (QR-код и ссылка), фискализация и онлайн-касса</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Callback URL:</span> /api/lifepay/callback/</p>
                <p><span className="font-bold">Точек с ключом:</span> {shops.filter(s => s.has_lifepay_api_key).length} из {shops.length}</p>
              </div>
              <div className="pt-2 flex flex-wrap gap-2">
                <Button size="sm" variant="dark" onClick={() => openLifePayModal('all')}>
                  Массовая настройка сети
                </Button>
              </div>
            </Card>

            {/* SBP */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">СБП (Быстрые платежи)</h4>
                <Badge variant="success">Включено</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Оплата по динамическому QR-коду и ссылке</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Комиссия:</span> 0.4% – 0.7%</p>
                <p><span className="font-bold">Мгновенный статус:</span> Работает</p>
              </div>
            </Card>

          </div>

          {/* Coffee shops LifePay table */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold text-brand-dark">Реквизиты LifePay по точкам кофейни</h4>
                <p className="text-xs text-brand-gray-blue">Статус интеграции и ключи СБП для каждой отдельной точки</p>
              </div>
              <Button size="sm" variant="dark" onClick={() => openLifePayModal('all')}>
                Применить ключ ко всем точкам
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-brand-gray-blue font-semibold uppercase text-[10px] tracking-wider">
                    <th className="py-2.5 px-3">Кофейня</th>
                    <th className="py-2.5 px-3">Город</th>
                    <th className="py-2.5 px-3">Статус СБП</th>
                    <th className="py-2.5 px-3">LifePay Логин</th>
                    <th className="py-2.5 px-3 text-right">Действие</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {shops.map(s => (
                    <tr key={s.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-3 font-semibold text-brand-dark">
                        {s.street}, {s.building_number}
                      </td>
                      <td className="py-3 px-3 text-brand-gray-blue">{s.city_name || '—'}</td>
                      <td className="py-3 px-3">
                        {s.has_lifepay_api_key ? (
                          <Badge variant="success" size="sm">Ключ настроен</Badge>
                        ) : (
                          <Badge variant="warning" size="sm">Не настроен</Badge>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono text-brand-dark-blue">
                        {s.lifepay_login || <span className="text-slate-400 font-sans">Не указан</span>}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Button size="sm" variant="outline" onClick={() => openLifePayModal(s.id)}>
                          Настроить
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {shops.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-brand-gray-blue">
                        Кофейни не найдены
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* COFFEE SHOP DRAWER */}
      {isShopDrawerOpen && editingShop && (
        <Drawer
          isOpen={isShopDrawerOpen}
          onClose={() => {
            setIsShopDrawerOpen(false);
            setEditingShop(null);
          }}
          title={editingShop.id ? 'Редактирование кофейни' : 'Новая точка кофейни'}
          subtitle="Настройка адреса, времени работы, CRM и эквайринга"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsShopDrawerOpen(false);
                  setEditingShop(null);
                }}
                disabled={isSavingShop}
              >
                Отмена
              </Button>
              <Button
                size="sm"
                onClick={handleSaveShop}
                isLoading={isSavingShop}
                disabled={isSavingShop || !editingShop.street?.trim()}
              >
                {editingShop.id ? 'Сохранить изменения' : 'Создать кофейню'}
              </Button>
            </div>
          }
        >
          <div className="space-y-5 font-montserrat">
            {/* Section 1: Address & Contacts */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">1. Локация и контакты</h4>
              <Select
                label="Город"
                value={editingShop.city || 1}
                onChange={e => setEditingShop({ ...editingShop, city: Number(e.target.value) })}
                options={cities.map(c => ({ value: c.id, label: c.name }))}
              />
              <div className="grid grid-cols-1 xs:grid-cols-3 gap-3">
                <div className="xs:col-span-2">
                  <Input
                    label="Улица"
                    placeholder="ул. Заслонова"
                    value={editingShop.street || ''}
                    onChange={e => setEditingShop({ ...editingShop, street: e.target.value })}
                    requiredAsterisk
                  />
                </div>
                <div>
                  <Input
                    label="Номер дома"
                    placeholder="14А"
                    value={editingShop.building_number || ''}
                    onChange={e => setEditingShop({ ...editingShop, building_number: e.target.value })}
                    requiredAsterisk
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
                <Input
                  label="Время открытия"
                  type="time"
                  value={editingShop.time_open || '08:00'}
                  onChange={e => setEditingShop({ ...editingShop, time_open: e.target.value })}
                />
                <Input
                  label="Время закрытия"
                  type="time"
                  value={editingShop.time_close || '22:00'}
                  onChange={e => setEditingShop({ ...editingShop, time_close: e.target.value })}
                />
              </div>
              <PhoneInput
                label="Телефон точки"
                value={editingShop.phone_number || ''}
                onChange={val => setEditingShop({ ...editingShop, phone_number: val })}
              />
              <Input
                label="Email для отзывов"
                placeholder="point@happy-island.coffee"
                value={editingShop.email || ''}
                onChange={e => setEditingShop({ ...editingShop, email: e.target.value })}
              />
              {/* Telegram Integration Block */}
              <div className="bg-slate-50/70 p-4 rounded-r18 border border-slate-200/80 space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-r12 bg-sky-500/10 text-sky-500 flex items-center justify-center shrink-0">
                      <Send className="w-4 h-4" />
                    </div>
                    <div>
                      <h5 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                        Уведомления в Telegram
                      </h5>
                      <p className="text-[11px] text-slate-500">
                        Оповещения об отзывах гостей и сменах
                      </p>
                    </div>
                  </div>
                  {tgRecipients.length > 0 || editingShop.telegram_id ? (
                    <Badge variant="success" size="sm">
                      <CheckCircle2 className="w-3 h-3 mr-0.5" />
                      {tgRecipients.length > 0 ? `${tgRecipients.length} подкл.` : 'Подключено'}
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      Не подключено
                    </Badge>
                  )}
                </div>

                {editingShop.id ? (
                  <div className="space-y-3">
                    {/* List of active recipients */}
                    {isLoadingRecipients ? (
                      <div className="text-center py-3 text-xs text-slate-400">
                        Загрузка получателей...
                      </div>
                    ) : tgRecipients.length > 0 ? (
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
                          <span>Подключенные сотрудники ({tgRecipients.length})</span>
                          {tgRecipients.length > 1 && (
                            <button
                              type="button"
                              onClick={() => handleTestRecipient()}
                              disabled={testingRecipientId === 'all'}
                              className="text-[11px] text-sky-600 hover:text-sky-700 underline font-medium"
                            >
                              {testingRecipientId === 'all' ? 'Отправка...' : 'Проверить всех'}
                            </button>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          {tgRecipients.map(r => (
                            <div
                              key={r.id}
                              className="bg-white p-2.5 rounded-r12 border border-slate-200/80 flex items-center justify-between gap-2 shadow-xs hover:border-slate-300 transition-colors"
                            >
                              <div className="flex items-center gap-2.5 min-w-0 pr-1">
                                <div className="w-8 h-8 rounded-full bg-sky-100/80 text-sky-600 flex items-center justify-center font-bold text-xs shrink-0 select-none">
                                  {r.first_name ? r.first_name[0].toUpperCase() : r.telegram_username ? r.telegram_username.replace('@', '')[0].toUpperCase() : 'TG'}
                                </div>
                                <div className="min-w-0">
                                  <div className="font-semibold text-slate-800 text-xs flex items-center gap-1.5 truncate">
                                    <span className="truncate">{r.telegram_username || r.first_name || `ID: ${r.telegram_id}`}</span>
                                    {r.first_name && r.telegram_username && (
                                      <span className="text-[11px] text-slate-400 font-normal shrink-0">({r.first_name})</span>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-slate-400 font-mono">
                                    Chat ID: {r.telegram_id}
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-1.5 shrink-0">
                                <button
                                  type="button"
                                  onClick={() => handleTestRecipient(r.telegram_id)}
                                  disabled={testingRecipientId === r.telegram_id}
                                  className="h-7 px-2.5 rounded-lg border border-sky-200 bg-sky-50/70 hover:bg-sky-100 text-sky-700 text-xs font-medium inline-flex items-center gap-1 transition-colors disabled:opacity-50"
                                  title="Отправить тестовое сообщение"
                                >
                                  <Send className="w-3 h-3 text-sky-500 shrink-0" />
                                  <span>{testingRecipientId === r.telegram_id ? 'Отправка...' : 'Тест'}</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteRecipient(r.id)}
                                  disabled={deletingRecipientId === r.id}
                                  className="w-7 h-7 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-50 flex items-center justify-center transition-colors disabled:opacity-50"
                                  title="Удалить получателя"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : editingShop.telegram_id ? (
                      /* Fallback legacy display if recipients table is empty */
                      <div className="bg-white p-2.5 rounded-r12 border border-slate-200 flex items-center justify-between gap-2 shadow-xs">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-8 h-8 rounded-full bg-sky-100/80 text-sky-600 flex items-center justify-center font-bold text-xs shrink-0 select-none">
                            TG
                          </div>
                          <div>
                            <div className="font-semibold text-slate-800 text-xs">
                              {editingShop.telegram_username || 'ID: ' + editingShop.telegram_id}
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono">
                              Chat ID: {editingShop.telegram_id}
                            </div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleTestRecipient()}
                          disabled={testingRecipientId !== null}
                          className="h-7 px-2.5 rounded-lg border border-sky-200 bg-sky-50/70 hover:bg-sky-100 text-sky-700 text-xs font-medium inline-flex items-center gap-1 transition-colors disabled:opacity-50"
                        >
                          <Send className="w-3 h-3 text-sky-500 shrink-0" />
                          <span>{testingRecipientId ? 'Отправка...' : 'Проверить'}</span>
                        </button>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 leading-relaxed">
                        Подключите сотрудников через Telegram, чтобы мгновенно получать отзывы гостей и оперативные алерты в режиме реального времени.
                      </p>
                    )}

                    {/* Invite / Add new recipient button */}
                    <div className="flex flex-col gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => handleGenerateTgLink()}
                        disabled={isGeneratingTgLink}
                        className="w-full h-10 px-4 rounded-r12 border border-sky-200 bg-sky-50/60 hover:bg-sky-100/80 text-sky-700 font-semibold text-xs inline-flex items-center justify-center gap-2 transition-all disabled:opacity-50 active:scale-[0.99] shadow-xs"
                      >
                        <Plus className="w-4 h-4 text-sky-600 shrink-0" />
                        <span>{isGeneratingTgLink ? 'Генерация ссылки...' : 'Добавить сотрудника через Telegram'}</span>
                      </button>

                      {tgBindLink && (
                        <div className="bg-sky-50/70 border border-sky-200/80 rounded-r12 p-3.5 space-y-2.5 text-xs animate-fade-in shadow-xs">
                          {/* Status and Direct Open Link */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 font-semibold text-slate-800 text-xs">
                              <span className="relative flex h-2.5 w-2.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                              </span>
                              <span>Ожидание запуска в боте...</span>
                            </div>
                            <a
                              href={tgBindLink}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-sky-600 hover:text-sky-800 font-semibold underline"
                            >
                              Открыть бота <ExternalLink className="w-3 h-3 inline" />
                            </a>
                          </div>

                          {/* Limit badges */}
                          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-white text-slate-700 px-2 py-0.5 rounded-md border border-slate-200/90 shadow-2xs">
                              <Clock className="w-3 h-3 text-amber-500" />
                              <span>Срок: <b className="font-semibold text-slate-900">30 минут</b></span>
                            </span>
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-white text-slate-700 px-2 py-0.5 rounded-md border border-slate-200/90 shadow-2xs">
                              <Users className="w-3 h-3 text-sky-500" />
                              <span>Лимит: <b className="font-semibold text-slate-900">1 сотрудник</b> (одноразовая ссылка)</span>
                            </span>
                          </div>

                          <p className="text-[11px] text-slate-500 leading-normal">
                            Отправьте эту ссылку сотруднику. После нажатия <b>«Запустить» (Start)</b> в боте аккаунт привяжется к кофейне, а токен ссылки сгорит в целях безопасности.
                          </p>

                          {/* Input with click-to-copy & Copy Button */}
                          <div className="flex items-center gap-1.5">
                            <input
                              type="text"
                              readOnly
                              value={tgBindLink}
                              onClick={() => copyTgLinkToClipboard()}
                              className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 w-full select-all font-mono outline-none focus:border-sky-400 cursor-pointer shadow-xs"
                              title="Нажмите, чтобы скопировать ссылку"
                            />
                            <button
                              type="button"
                              onClick={() => copyTgLinkToClipboard()}
                              className={cn(
                                "h-8 px-3 rounded-lg border text-xs font-semibold inline-flex items-center gap-1.5 shrink-0 shadow-xs transition-all active:scale-[0.98]",
                                hasCopiedLink
                                  ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                                  : "bg-white border-slate-200 hover:bg-slate-50 text-slate-700"
                              )}
                            >
                              {hasCopiedLink ? (
                                <>
                                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                                  <span>Скопировано!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5 text-slate-500" />
                                  <span>Копировать</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      {(tgRecipients.length > 0 || editingShop.telegram_id) && (
                        <div className="flex justify-end pt-1">
                          <button
                            type="button"
                            onClick={() => handleUnlinkTg()}
                            disabled={isUnlinkingTg}
                            className="text-xs text-slate-400 hover:text-rose-500 inline-flex items-center gap-1 transition-colors"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>{isUnlinkingTg ? 'Отвязка...' : 'Отвязать всех получателей'}</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">
                    Сохраните кофейню, чтобы подключить Telegram-бота.
                  </p>
                )}

                {/* Manual fallback fields */}
                <details className="group text-xs text-slate-500 pt-2 border-t border-slate-200/60">
                  <summary className="cursor-pointer list-none flex items-center justify-between text-xs font-medium text-slate-500 hover:text-slate-700 py-1 transition-colors">
                    <span className="flex items-center gap-1.5">
                      <ChevronRight className="w-3.5 h-3.5 transition-transform group-open:rotate-90 text-slate-400" />
                      Ручная настройка Telegram ID / Username
                    </span>
                  </summary>
                  <div className="space-y-2.5 pt-2.5">
                    <Input
                      label="Telegram ID (числовой chat_id)"
                      placeholder="Например: 6463435986"
                      value={editingShop.telegram_id || ''}
                      onChange={e => setEditingShop({ ...editingShop, telegram_id: e.target.value })}
                    />
                    <Input
                      label="Telegram Username"
                      placeholder="@island_point"
                      value={editingShop.telegram_username || ''}
                      onChange={e => setEditingShop({ ...editingShop, telegram_username: e.target.value })}
                    />
                    <p className="text-[11px] text-slate-400">
                      ID можно узнать через бота <a href="https://t.me/getmyid_bot" target="_blank" rel="noreferrer" className="text-sky-600 underline">@getmyid_bot</a>. Получатель должен предварительно нажать Start в <a href="https://t.me/happy_island_bot" target="_blank" rel="noreferrer" className="text-sky-600 underline">@happy_island_bot</a>.
                    </p>
                  </div>
                </details>
              </div>
            </div>

            {/* Section 2: CRM & Acquiring */}
            <div className="space-y-3 pt-3 border-t border-slate-100">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">2. Интеграции CRM и Эквайринг</h4>
              <Input
                label="Название слоя в CRM"
                placeholder="Например: Основной зал или Летняя терраса"
                value={editingShop.crm_layer_name || ''}
                onChange={e => setEditingShop({ ...editingShop, crm_layer_name: e.target.value })}
              />
              <Input
                label="Логин/Email для CRM"
                placeholder="crm_user@island.ru"
                value={editingShop.crm_email || ''}
                onChange={e => setEditingShop({ ...editingShop, crm_email: e.target.value })}
              />
              <Input
                label="ИНН кофейни"
                placeholder="164401234567"
                value={editingShop.inn || ''}
                onChange={e => setEditingShop({ ...editingShop, inn: e.target.value })}
              />

              <div className="pt-3 border-t border-slate-100 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-brand-dark">LifePay (СБП и эквайринг)</span>
                  {editingShop.has_lifepay_api_key ? (
                    <Badge variant="success" size="sm">Ключ настроен</Badge>
                  ) : (
                    <Badge variant="warning" size="sm">Ключ не задан</Badge>
                  )}
                </div>
                <Input
                  label="LifePay Логин (телефон администратора)"
                  placeholder="79991234567"
                  value={editingShop.lifepay_login || ''}
                  onChange={e => setEditingShop({ ...editingShop, lifepay_login: e.target.value })}
                />
                <Input
                  label={editingShop.has_lifepay_api_key ? "Новый LifePay API Ключ (оставьте пустым, чтобы не менять)" : "LifePay API Ключ"}
                  placeholder={editingShop.has_lifepay_api_key ? "••••••••••••••••••••••••" : "Введите API ключ LifePay"}
                  type="password"
                  value={editingShop.lifepay_api_key || ''}
                  onChange={e => setEditingShop({ ...editingShop, lifepay_api_key: e.target.value })}
                />
              </div>
            </div>
          </div>
        </Drawer>
      )}

      {/* CITY MODAL */}
      {isCityModalOpen && (
        <Modal
          isOpen={isCityModalOpen}
          onClose={() => {
            setIsCityModalOpen(false);
            setEditingCity(null);
          }}
          title={editingCity?.id ? 'Редактировать город' : 'Новый город'}
        >
          <div className="space-y-4 font-montserrat">
            <Input
              label="Название города"
              placeholder="Например: Альметьевск или Казань"
              value={editingCity?.name || ''}
              onChange={e => setEditingCity({ ...editingCity, name: e.target.value })}
              requiredAsterisk
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsCityModalOpen(false);
                  setEditingCity(null);
                }}
                disabled={isSavingCity}
              >
                Отмена
              </Button>
              <Button
                size="sm"
                onClick={handleSaveCity}
                isLoading={isSavingCity}
                disabled={isSavingCity || !editingCity?.name?.trim()}
              >
                {editingCity?.id ? 'Сохранить изменения' : 'Создать город'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* LIFEPAY MODAL */}
      {isLifePayModalOpen && (
        <Modal
          isOpen={isLifePayModalOpen}
          onClose={() => setIsLifePayModalOpen(false)}
          title="Настройка эквайринга LifePay (СБП)"
        >
          <div className="space-y-4 font-montserrat">
            <Select
              label="Точка кофейни"
              value={targetLifePayShopId}
              onChange={e => {
                const val = e.target.value === 'all' ? 'all' : Number(e.target.value);
                setTargetLifePayShopId(val);
                if (val !== 'all') {
                  const s = shops.find(shop => shop.id === val);
                  setLifePayLogin(s?.lifepay_login || '');
                  setLifePayApiKey('');
                }
              }}
              options={[
                { value: 'all', label: '⭐ Все кофейни сети (массово)' },
                ...shops.map(s => ({ value: s.id, label: `${s.street}, ${s.building_number} (${s.city_name || 'Казань'})` }))
              ]}
            />

            <Input
              label="LifePay Логин (номер телефона администратора)"
              placeholder="79991234567"
              value={lifePayLogin}
              onChange={e => setLifePayLogin(e.target.value)}
              requiredAsterisk
            />

            <Input
              label="LifePay API Ключ"
              placeholder="Введите секретный ключ API"
              type="password"
              value={lifePayApiKey}
              onChange={e => setLifePayApiKey(e.target.value)}
              requiredAsterisk
            />

            <div className="p-3 bg-slate-50 rounded-r12 border border-slate-200 text-xs space-y-1.5 text-brand-dark-blue">
              <p className="font-bold text-brand-dark">ℹ️ Где взять реквизиты:</p>
              <p>В личном кабинете <a href="https://home.life-pay.ru" target="_blank" rel="noreferrer" className="text-brand-dark underline font-semibold">home.life-pay.ru</a> в разделе <strong>Настройки → Разработчикам / API</strong>.</p>
              <p>Callback URL: <code className="bg-white px-1 py-0.5 rounded border border-slate-200 select-all font-mono text-[11px]">http://79.174.81.151/api/lifepay/callback/</code></p>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestLifePay}
                isLoading={isTestingLifePay}
                disabled={isTestingLifePay || isSavingLifePay || !lifePayLogin.trim() || !lifePayApiKey.trim()}
              >
                Проверить подключение
              </Button>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsLifePayModalOpen(false)}
                  disabled={isSavingLifePay}
                >
                  Отмена
                </Button>
                <Button
                  size="sm"
                  onClick={handleSaveLifePay}
                  isLoading={isSavingLifePay}
                  disabled={isSavingLifePay || !lifePayLogin.trim() || !lifePayApiKey.trim()}
                >
                  {targetLifePayShopId === 'all' ? 'Применить ко всем' : 'Сохранить'}
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
