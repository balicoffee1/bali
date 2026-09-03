import React, { useState } from 'react';
import { useApp, PageId, MenuTabId, SettingsTabId } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard, ShoppingBag, UtensilsCrossed, Users, Clock,
  Star, FileText, Bell, ShieldCheck, Settings, LogOut,
  ChevronLeft, ChevronRight, ChevronDown, Coffee, Store
} from 'lucide-react';
import { cn } from '../../utils/cn';

interface SubNavItem {
  id: string;
  label: string;
  roles?: ('owner' | 'admin' | 'moderator' | 'support')[];
}

interface NavItem {
  id: PageId;
  label: string;
  icon: React.ReactNode;
  badge?: number;
  roles?: ('owner' | 'admin' | 'moderator' | 'support')[];
  children?: SubNavItem[];
}

export const Sidebar: React.FC = () => {
  const {
    currentPage,
    activeMenuTab,
    activeSettingsTab,
    navigateTo,
    sidebarCollapsed,
    setSidebarCollapsed
  } = useApp();
  const { user, logout, hasRole } = useAuth();

  // Manage open state for collapsible parent groups
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    menu: true,
    settings: true,
  });

  const toggleGroup = (groupId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setOpenGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId],
    }));
  };

  const navItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Дашборд',
      icon: <LayoutDashboard className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator']
    },
    {
      id: 'orders',
      label: 'Заказы (Live Desk)',
      icon: <ShoppingBag className="w-5 h-5" />,
      badge: 2,
      roles: ['owner', 'admin', 'moderator', 'support']
    },
    {
      id: 'menu',
      label: 'Меню и товары',
      icon: <UtensilsCrossed className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator', 'support'],
      children: [
        { id: 'products', label: 'Товары', roles: ['owner', 'admin', 'moderator', 'support'] },
        { id: 'categories', label: 'Категории', roles: ['owner', 'admin', 'moderator', 'support'] },
        { id: 'addons', label: 'Добавки', roles: ['owner', 'admin', 'moderator', 'support'] },
        { id: 'flavors', label: 'Вкусы добавок', roles: ['owner', 'admin', 'moderator', 'support'] },
      ]
    },
    {
      id: 'users',
      label: 'Пользователи',
      icon: <Users className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator', 'support']
    },
    {
      id: 'shifts',
      label: 'Смены и Бариста',
      icon: <Clock className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator']
    },
    {
      id: 'reviews',
      label: 'Отзывы клиентов',
      icon: <Star className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator', 'support']
    },
    {
      id: 'franchise',
      label: 'Франшиза',
      icon: <FileText className="w-5 h-5" />,
      roles: ['owner', 'admin', 'moderator', 'support']
    },
    {
      id: 'notifications',
      label: 'Push-рассылки',
      icon: <Bell className="w-5 h-5" />,
      roles: ['owner', 'admin']
    },
    {
      id: 'logs',
      label: 'Журнал аудита',
      icon: <ShieldCheck className="w-5 h-5" />,
      roles: ['owner', 'admin']
    },
    {
      id: 'settings',
      label: 'Кофейни и сеть',
      icon: <Store className="w-5 h-5" />,
      roles: ['owner', 'admin'],
      children: [
        { id: 'shops', label: 'Кофейни', roles: ['owner', 'admin'] },
        { id: 'cities', label: 'Города', roles: ['owner', 'admin'] },
        { id: 'crm', label: 'CRM и интеграции', roles: ['owner', 'admin'] },
        { id: 'acquiring', label: 'Эквайринг', roles: ['owner', 'admin'] },
      ]
    },
  ];

  const filteredNavItems = navItems.filter(item => {
    if (!item.roles) return true;
    return hasRole(item.roles as any);
  });

  return (
    <aside
      className={cn(
        'h-screen bg-brand-dark text-white flex flex-col justify-between transition-all duration-300 z-30 shrink-0 sticky top-0 font-montserrat select-none',
        sidebarCollapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="h-16 flex items-center justify-between px-5 border-b border-white/10 shrink-0">
          {!sidebarCollapsed ? (
            <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigateTo('dashboard')}>
              <div className="w-9 h-9 rounded-r12 bg-brand-lime flex items-center justify-center text-brand-dark font-extrabold text-lg shadow-sm">
                ☕
              </div>
              <div>
                <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-1.5">
                  Happy Island
                </h1>
                <span className="text-[10px] uppercase tracking-wider font-semibold text-brand-lime block -mt-0.5">
                  Admin Panel
                </span>
              </div>
            </div>
          ) : (
            <div className="w-full flex justify-center cursor-pointer" onClick={() => navigateTo('dashboard')}>
              <div className="w-9 h-9 rounded-r12 bg-brand-lime flex items-center justify-center text-brand-dark font-extrabold text-lg">
                ☕
              </div>
            </div>
          )}

          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="hidden lg:flex w-7 h-7 rounded-lg bg-white/5 hover:bg-white/10 items-center justify-center text-brand-gray-blue hover:text-white transition-colors"
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation items with custom scrollbar */}
        <nav className="p-3 space-y-1 mt-2 flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar">
          {filteredNavItems.map(item => {
            const isPageActive = currentPage === item.id;
            const hasChildren = Boolean(item.children && item.children.length > 0);
            const isGroupOpen = openGroups[item.id] !== false;

            return (
              <div key={item.id} className="space-y-0.5">
                <button
                  onClick={() => {
                    if (hasChildren && !sidebarCollapsed) {
                      // Navigate to default tab or switch group
                      if (!isPageActive) {
                        const defaultTab = item.id === 'menu' ? activeMenuTab : activeSettingsTab;
                        navigateTo(item.id, defaultTab);
                      }
                      toggleGroup(item.id);
                    } else {
                      navigateTo(item.id);
                    }
                  }}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-r12 font-semibold text-xs transition-all duration-150 relative group',
                    isPageActive && !hasChildren
                      ? 'bg-brand-lime text-brand-dark shadow-sm'
                      : isPageActive && hasChildren
                      ? 'bg-white/10 text-white'
                      : 'text-slate-300 hover:bg-white/5 hover:text-white'
                  )}
                  title={sidebarCollapsed ? item.label : undefined}
                >
                  <span className={cn(
                    'shrink-0 transition-transform duration-150 group-hover:scale-110',
                    isPageActive && !hasChildren ? 'text-brand-dark' : isPageActive ? 'text-brand-lime' : 'text-slate-300'
                  )}>
                    {item.icon}
                  </span>
                  {!sidebarCollapsed && (
                    <span className="flex-1 text-left truncate">{item.label}</span>
                  )}
                  {!sidebarCollapsed && item.badge !== undefined && (
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded-full text-[10px] font-extrabold',
                        isPageActive ? 'bg-brand-dark text-white' : 'bg-brand-red text-white'
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                  {!sidebarCollapsed && hasChildren && (
                    <span
                      onClick={(e) => toggleGroup(item.id, e)}
                      className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                    >
                      <ChevronDown
                        className={cn(
                          'w-3.5 h-3.5 transition-transform duration-200',
                          !isGroupOpen && '-rotate-90'
                        )}
                      />
                    </span>
                  )}
                </button>

                {/* Submenu items */}
                {!sidebarCollapsed && hasChildren && isGroupOpen && (
                  <div className="pl-4 pr-1 py-1 space-y-0.5 border-l border-white/10 ml-5 my-0.5 animate-fade-in-up">
                    {item.children!.map(sub => {
                      const isSubActive =
                        isPageActive &&
                        ((item.id === 'menu' && activeMenuTab === sub.id) ||
                         (item.id === 'settings' && activeSettingsTab === sub.id));

                      return (
                        <button
                          key={sub.id}
                          onClick={() => navigateTo(item.id, sub.id)}
                          className={cn(
                            'w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[11px] font-semibold transition-all duration-150',
                            isSubActive
                              ? 'bg-brand-lime text-brand-dark font-bold shadow-sm'
                              : 'text-slate-400 hover:text-white hover:bg-white/5'
                          )}
                        >
                          <span className="truncate">{sub.label}</span>
                          {isSubActive && <span className="w-1.5 h-1.5 rounded-full bg-brand-dark shrink-0"></span>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </div>

      {/* User profile & Logout footer */}
      <div className="p-3 border-t border-white/10 bg-black/10 shrink-0">
        <div className={cn('flex items-center gap-3', sidebarCollapsed ? 'justify-center' : 'p-2')}>
          <div className="w-9 h-9 rounded-full bg-brand-lime/20 border border-brand-lime/40 flex items-center justify-center text-brand-lime font-bold text-xs shrink-0">
            {user?.first_name ? user.first_name[0] : 'A'}
          </div>
          {!sidebarCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-white truncate">{user?.full_name || 'Администратор'}</p>
              <span className="text-[10px] font-semibold text-brand-lime uppercase tracking-wider">
                {user?.role === 'owner' ? 'Владелец' : user?.role === 'admin' ? 'Администратор' : user?.role === 'moderator' ? 'Модератор' : 'Поддержка'}
              </span>
            </div>
          )}
          <button
            onClick={logout}
            className="w-8 h-8 rounded-lg text-slate-400 hover:text-brand-red hover:bg-white/5 flex items-center justify-center transition-colors shrink-0"
            title="Выйти"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
