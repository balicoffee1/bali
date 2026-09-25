import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { CoffeeShop, City } from '../types';
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
  Layers, RefreshCw, Key, Server
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { cities: appCities, coffeeShops: appShops, addToast, activeSettingsTab, setActiveSettingsTab } = useApp();
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

  useEffect(() => {
    loadSettingsData();
  }, []);

  // Poll for Telegram link completion when token is active
  useEffect(() => {
    if (!tgBindToken || !editingShop?.id || !isShopDrawerOpen) return;
    const interval = setInterval(async () => {
      try {
        const res = await api.getTelegramBindStatus(editingShop.id!, tgBindToken);
        if (res.is_connected && res.telegram_id) {
          setEditingShop(prev => prev ? {
            ...prev,
            telegram_id: res.telegram_id,
            telegram_username: res.telegram_username || prev.telegram_username,
          } : null);
          setTgBindToken(null);
          setTgBindLink(null);
          addToast({
            title: 'Telegram успешно подключен!',
            message: `Кофейня привязана к аккаунту ${res.telegram_username || res.telegram_id}`,
            type: 'success',
          });
          setShops(prev => prev.map(s => s.id === editingShop.id ? {
            ...s,
            telegram_id: res.telegram_id,
            telegram_username: res.telegram_username || s.telegram_username,
          } : s));
        }
      } catch (e) {
        // ignore polling error
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [tgBindToken, editingShop?.id, isShopDrawerOpen]);

  const handleGenerateTgLink = async () => {
    if (!editingShop?.id) return;
    setIsGeneratingTgLink(true);
    try {
      const res = await api.getTelegramBindLink(editingShop.id);
      setTgBindLink(res.link);
      setTgBindToken(res.token);
      window.open(res.link, '_blank');
      addToast({
        title: 'Бот открыт в Telegram',
        message: 'Нажмите «Запустить» (Start) в боте для завершения привязки.',
        type: 'info',
      });
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

  const handleTestTg = async () => {
    if (!editingShop?.id) return;
    setIsTestingTg(true);
    try {
      const res = await api.testTelegramNotification(editingShop.id);
      if (res.success) {
        addToast({
          title: 'Успешно!',
          message: 'Тестовое уведомление доставлено в Telegram!',
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
      setIsTestingTg(false);
    }
  };

  const handleUnlinkTg = async () => {
    if (!editingShop?.id) return;
    setIsUnlinkingTg(true);
    try {
      await api.unlinkTelegram(editingShop.id);
      setEditingShop(prev => prev ? { ...prev, telegram_id: '', telegram_username: '' } : null);
      setShops(prev => prev.map(s => s.id === editingShop.id ? { ...s, telegram_id: '', telegram_username: '' } : s));
      addToast({
        title: 'Отвязано',
        message: 'Telegram-уведомления для точки отключены',
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
      accessor: row => (
        row.telegram_id ? (
          <Badge variant="success" size="sm">
            <CheckCircle2 className="w-3 h-3 mr-1 inline" />
            {row.telegram_username || 'Подключен'}
          </Badge>
        ) : (
          <Badge variant="neutral" size="sm">Не подключен</Badge>
        )
      ),
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

      {/* TAB 3: CRM SYSTEMS */}
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
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/80 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Send className="w-4 h-4 text-sky-500" />
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                      Уведомления в Telegram
                    </span>
                  </div>
                  {editingShop.telegram_id ? (
                    <Badge variant="success" size="sm">
                      <CheckCircle2 className="w-3 h-3 mr-1 inline" /> Подключено
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      Не подключено
                    </Badge>
                  )}
                </div>

                {editingShop.id ? (
                  <div className="space-y-2">
                    {editingShop.telegram_id ? (
                      <div className="space-y-2">
                        <div className="text-xs text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200 flex justify-between items-center">
                          <div>
                            <div className="font-semibold text-slate-800">
                              {editingShop.telegram_username || 'ID: ' + editingShop.telegram_id}
                            </div>
                            <div className="text-[11px] text-slate-400 font-mono">
                              Chat ID: {editingShop.telegram_id}
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              className="text-xs py-1 h-7"
                              onClick={handleTestTg}
                              disabled={isTestingTg}
                            >
                              <Send className="w-3 h-3 mr-1 text-sky-500" />
                              {isTestingTg ? 'Отправка...' : 'Проверить'}
                            </Button>
                            <Button
                              type="button"
                              variant="danger"
                              size="sm"
                              className="text-xs py-1 h-7"
                              onClick={handleUnlinkTg}
                              disabled={isUnlinkingTg}
                            >
                              Отвязать
                            </Button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs text-slate-500 leading-relaxed">
                          Подключите Telegram, чтобы мгновенно получать отзывы гостей и оперативные алерты в режиме реального времени.
                        </p>
                        <div className="flex flex-col gap-2">
                          <Button
                            type="button"
                            variant="primary"
                            size="sm"
                            className="w-full bg-sky-500 hover:bg-sky-600 text-white"
                            onClick={handleGenerateTgLink}
                            disabled={isGeneratingTgLink}
                          >
                            <Send className="w-3.5 h-3.5 mr-1.5" />
                            {isGeneratingTgLink ? 'Генерация ссылки...' : 'Подключить через Telegram (в 1 клик)'}
                          </Button>
                          {tgBindLink && (
                            <div className="text-[11px] bg-sky-50 border border-sky-100 text-sky-800 p-2 rounded-lg flex items-center justify-between">
                              <span className="truncate pr-2">Ожидание нажатия Start в боте...</span>
                              <a
                                href={tgBindLink}
                                target="_blank"
                                rel="noreferrer"
                                className="underline font-semibold shrink-0"
                              >
                                Открыть бота ↗
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">
                    Сохраните кофейню, чтобы подключить Telegram-бота.
                  </p>
                )}

                {/* Manual fallback fields */}
                <details className="text-xs text-slate-500 pt-1 border-t border-slate-200/60">
                  <summary className="cursor-pointer text-[11px] font-medium text-slate-500 hover:text-slate-700 py-1">
                    Ручная настройка Telegram ID / Username
                  </summary>
                  <div className="space-y-2 pt-2">
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
                    <p className="text-[10px] text-slate-400">
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
