import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { CoffeeShop, City } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
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

  useEffect(() => {
    loadSettingsData();
  }, []);

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
      header: 'Эквайринг',
      accessor: row => <Badge variant="success" size="sm">Русский Стандарт / LifePay</Badge>,
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
                  email: 'info@happy-island.coffee',
                  telegram_username: '@island_point',
                  time_open: '08:00',
                  time_close: '22:00',
                  crm_email: '',
                  crm_layer_name: 'Основной зал',
                  inn: '',
                  phone_number: '+7 (917) ',
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

            {/* Subtotal API */}
            <Card className="space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-r12 bg-blue-500/20 text-blue-700 flex items-center justify-center font-extrabold text-xl">
                    ST
                  </div>
                  <div>
                    <h4 className="text-base font-extrabold text-brand-dark">Subtotal API</h4>
                    <p className="text-xs text-brand-gray-blue">Интеграция скидок и остатков</p>
                  </div>
                </div>
                <Badge variant="success">Подключено</Badge>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Скидочные карты клиентов:</span>
                  <span className="font-bold text-emerald-600">Синхронизируются</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Сервер:</span>
                  <span className="font-mono text-brand-dark">subtotal.ru/api</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                  <span className="font-semibold text-brand-dark-blue">Проверка скидок по номеру:</span>
                  <span className="font-bold text-emerald-600">Включена</span>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between">
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={<RefreshCw className="w-4 h-4" />}
                  onClick={() => addToast({ type: 'success', title: 'Subtotal API', message: 'Скидки успешно синхронизированы' })}
                >
                  Проверить связь
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
            {/* Russian Standard */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">Русский Стандарт</h4>
                <Badge variant="success">Активен</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Основной эквайринг для оплаты заказов в мобильном приложении</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Шлюз:</span> demo.rsb-processing.ru</p>
                <p><span className="font-bold">Сертификаты:</span> SSL X.509 загружены</p>
              </div>
            </Card>

            {/* LifePay */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">LifePay</h4>
                <Badge variant="success">Активен</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Формирование фискальных чеков и онлайн-касса</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Callback URL:</span> /api/lifepay/callback/</p>
                <p><span className="font-bold">Авто-фискализация:</span> Включена</p>
              </div>
            </Card>

            {/* SBP */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">СБП (Быстрые платежи)</h4>
                <Badge variant="success">Активен</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Оплата по динамическому QR-коду и ссылке</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Комиссия:</span> 0.4% – 0.7%</p>
                <p><span className="font-bold">Мгновенный статус:</span> Работает</p>
              </div>
            </Card>

            {/* Tinkoff Bank */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">Тинькофф Банк</h4>
                <Badge variant="neutral">Резерв</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Резервный эквайринг для онлайн-платежей</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Терминал:</span> Т-Банк E-Commerce</p>
              </div>
            </Card>

            {/* Alfa Bank */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-brand-dark">Альфа-Банк</h4>
                <Badge variant="neutral">Резерв</Badge>
              </div>
              <p className="text-xs text-brand-gray-blue">Резервный эквайринг для кофейных точек Казани</p>
              <div className="pt-2 text-xs space-y-1 text-brand-dark-blue">
                <p><span className="font-bold">Интеграция:</span> Готова к включению</p>
              </div>
            </Card>
          </div>
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
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
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
              <div className="grid grid-cols-2 gap-3">
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
              <Input
                label="Телефон точки"
                placeholder="+7 (917) 000-00-00"
                value={editingShop.phone_number || ''}
                onChange={e => setEditingShop({ ...editingShop, phone_number: e.target.value })}
              />
              <Input
                label="Email для отзывов"
                placeholder="point@happy-island.coffee"
                value={editingShop.email || ''}
                onChange={e => setEditingShop({ ...editingShop, email: e.target.value })}
              />
              <Input
                label="Telegram Username для уведомлений"
                placeholder="@island_point"
                value={editingShop.telegram_username || ''}
                onChange={e => setEditingShop({ ...editingShop, telegram_username: e.target.value })}
              />
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
    </div>
  );
};
