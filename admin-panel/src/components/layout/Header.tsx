import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { MapPin, Store, Shield, Check } from 'lucide-react';
import { UserRole } from '../../types';
import { api } from '../../api/client';

export const Header: React.FC = () => {
  const {
    currentPage,
    cities,
    coffeeShops,
    selectedCityId,
    setSelectedCityId,
    selectedShopId,
    setSelectedShopId,
  } = useApp();
  const { user, switchRole } = useAuth();
  const [roleDropdownOpen, setRoleDropdownOpen] = useState(false);

  const pageTitles: Record<string, { title: string; subtitle: string }> = {
    dashboard: { title: 'Дашборд сети', subtitle: 'Операционные показатели и динамика продаж в реальном времени' },
    orders: { title: 'Заказы (Live Desk)', subtitle: 'Мониторинг, прием и смена статусов заказов' },
    menu: { title: 'Меню и товары', subtitle: 'Товары, категории, добавки, сиропы, цены и стоп-листы' },
    users: { title: 'Пользователи и Клиенты', subtitle: 'База клиентов, персонал, управление ролями и блокировка' },
    shifts: { title: 'Смены и Бариста', subtitle: 'Контроль рабочих смен, закрытые чеки и выручка сотрудников' },
    reviews: { title: 'Отзывы и Оценки', subtitle: 'Удовлетворенность гостей (NPS), комментарии и обратная связь' },
    franchise: { title: 'Заявки на франшизу', subtitle: 'Входящие лиды и потенциальные партнеры сети' },
    notifications: { title: 'Push-рассылки', subtitle: 'Массовые и таргетированные уведомления в мобильное приложение' },
    logs: { title: 'Журнал аудита', subtitle: 'История всех действий администраторов с фиксацией изменений' },
    settings: { title: 'Кофейни и сеть', subtitle: 'Управление точками кофеен, городами, интеграциями CRM и эквайрингом' },
  };

  const currentInfo = pageTitles[currentPage] || { title: 'Админ-панель', subtitle: '' };

  const rolesList: { id: UserRole; name: string }[] = [
    { id: 'owner', name: 'Владелец (Super Admin)' },
    { id: 'admin', name: 'Администратор (Admin)' },
    { id: 'moderator', name: 'Модератор меню (Moderator)' },
    { id: 'support', name: 'Служба поддержки (Support)' },
  ];

  const filteredShops = selectedCityId
    ? coffeeShops.filter(s => s.city === selectedCityId)
    : coffeeShops;

  return (
    <header className="h-20 bg-white border-b border-slate-100 px-6 lg:px-8 flex items-center justify-between sticky top-0 z-20 font-montserrat">
      {/* Title */}
      <div className="flex-1 min-w-0 mr-4">
        <h2 className="text-xl font-extrabold text-brand-dark tracking-tight whitespace-nowrap">{currentInfo.title}</h2>
        <p className="text-xs font-medium text-brand-gray-blue mt-0.5 hidden xl:block truncate">{currentInfo.subtitle}</p>
      </div>

      {/* Action Filters: City / Shop / Role switcher */}
      <div className="flex items-center gap-3">
        {/* City Filter */}
        <div className="hidden md:flex items-center gap-2 bg-brand-light-gray rounded-r12 px-3 py-1.5 border border-slate-200/60">
          <MapPin className="w-4 h-4 text-brand-dark-blue shrink-0" />
          <select
            value={selectedCityId || ''}
            onChange={e => {
              const val = e.target.value ? Number(e.target.value) : null;
              setSelectedCityId(val);
              setSelectedShopId(null);
            }}
            className="bg-transparent text-xs font-bold text-brand-dark focus:outline-none cursor-pointer pr-2"
          >
            <option value="">Все города</option>
            {cities.map(city => (
              <option key={city.id} value={city.id}>
                {city.name}
              </option>
            ))}
          </select>
        </div>

        {/* Coffee Shop Filter */}
        <div className="hidden lg:flex items-center gap-2 bg-brand-light-gray rounded-r12 px-3 py-1.5 border border-slate-200/60">
          <Store className="w-4 h-4 text-brand-dark-blue shrink-0" />
          <select
            value={selectedShopId || ''}
            onChange={e => setSelectedShopId(e.target.value ? Number(e.target.value) : null)}
            className="bg-transparent text-xs font-bold text-brand-dark focus:outline-none cursor-pointer pr-2"
          >
            <option value="">Все кофейни</option>
            {filteredShops.map(shop => (
              <option key={shop.id} value={shop.id}>
                {shop.street} ({shop.city_name})
              </option>
            ))}
          </select>
        </div>

        {/* Demo Role Switcher Dropdown */}
        {api.isMockMode() && <div className="relative">
          <button
            onClick={() => setRoleDropdownOpen(!roleDropdownOpen)}
            className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-brand-dark px-3 py-2 rounded-r12 text-xs font-bold transition-colors border border-slate-200"
            title="Переключить роль для тестирования RBAC"
          >
            <Shield className="w-3.5 h-3.5 text-brand-dark-blue" />
            <span className="capitalize">{user?.role || 'Роль'}</span>
          </button>

          {roleDropdownOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-r12 shadow-xl border border-slate-100 p-1 z-50 animate-fade-in-up">
              <div className="px-3 py-2 border-b border-slate-100 text-[10px] font-bold text-brand-gray-blue uppercase">
                Режим симуляции RBAC
              </div>
              {rolesList.map(r => (
                <button
                  key={r.id}
                  onClick={() => {
                    switchRole(r.id);
                    setRoleDropdownOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 text-xs font-semibold rounded-md hover:bg-brand-light-gray flex items-center justify-between text-brand-dark"
                >
                  <span>{r.name}</span>
                  {user?.role === r.id && <Check className="w-4 h-4 text-brand-green-text" />}
                </button>
              ))}
            </div>
          )}
        </div>}
      </div>
    </header>
  );
};
