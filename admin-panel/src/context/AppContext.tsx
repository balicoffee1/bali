import React, { createContext, useContext, useState, useEffect } from 'react';
import { City, CoffeeShop } from '../types';
import { api } from '../api/client';
import { useAuth } from './AuthContext';

export type PageId =
  | 'dashboard'
  | 'orders'
  | 'menu'
  | 'users'
  | 'shifts'
  | 'reviews'
  | 'franchise'
  | 'notifications'
  | 'logs'
  | 'settings';

export type MenuTabId = 'products' | 'categories' | 'addons' | 'flavors';
export type SettingsTabId = 'shops' | 'cities' | 'crm' | 'acquiring';

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message?: string;
}

interface AppContextType {
  currentPage: PageId;
  setCurrentPage: (page: PageId) => void;
  activeMenuTab: MenuTabId;
  setActiveMenuTab: (tab: MenuTabId) => void;
  activeSettingsTab: SettingsTabId;
  setActiveSettingsTab: (tab: SettingsTabId) => void;
  navigateTo: (page: PageId, tab?: string) => void;
  selectedCityId: number | null;
  setSelectedCityId: (id: number | null) => void;
  selectedShopId: number | null;
  setSelectedShopId: (id: number | null) => void;
  cities: City[];
  coffeeShops: CoffeeShop[];
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const parseUrlParams = (): { page: PageId; menuTab: MenuTabId; settingsTab: SettingsTabId } => {
  try {
    const params = new URLSearchParams(window.location.search);
    const validPages: PageId[] = [
      'dashboard', 'orders', 'menu', 'users', 'shifts',
      'reviews', 'franchise', 'notifications', 'logs', 'settings'
    ];
    const pageParam = params.get('page') as PageId;
    const tabParam = params.get('tab');

    const page: PageId = validPages.includes(pageParam) ? pageParam : 'dashboard';

    const validMenuTabs: MenuTabId[] = ['products', 'categories', 'addons', 'flavors'];
    const menuTab: MenuTabId = (tabParam && validMenuTabs.includes(tabParam as MenuTabId))
      ? (tabParam as MenuTabId)
      : 'products';

    const validSettingsTabs: SettingsTabId[] = ['shops', 'cities', 'crm', 'acquiring'];
    const settingsTab: SettingsTabId = (tabParam && validSettingsTabs.includes(tabParam as SettingsTabId))
      ? (tabParam as SettingsTabId)
      : 'shops';

    return { page, menuTab, settingsTab };
  } catch {
    return { page: 'dashboard', menuTab: 'products', settingsTab: 'shops' };
  }
};

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const initial = parseUrlParams();

  const [currentPage, setCurrentPageState] = useState<PageId>(initial.page);
  const [activeMenuTab, setActiveMenuTabState] = useState<MenuTabId>(initial.menuTab);
  const [activeSettingsTab, setActiveSettingsTabState] = useState<SettingsTabId>(initial.settingsTab);

  const [selectedCityId, setSelectedCityId] = useState<number | null>(null);
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);
  const [cities, setCities] = useState<City[]>([]);
  const [coffeeShops, setCoffeeShops] = useState<CoffeeShop[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => window.innerWidth < 1280);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const syncUrl = (page: PageId, menuTab: MenuTabId, settingsTab: SettingsTabId, replace = false) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('page', page);
      if (page === 'menu') {
        url.searchParams.set('tab', menuTab);
      } else if (page === 'settings') {
        url.searchParams.set('tab', settingsTab);
      } else {
        url.searchParams.delete('tab');
      }
      if (replace) {
        window.history.replaceState({ page, menuTab, settingsTab }, '', url.toString());
      } else {
        window.history.pushState({ page, menuTab, settingsTab }, '', url.toString());
      }
    } catch {}
  };

  useEffect(() => {
    const handlePopState = () => {
      const { page, menuTab, settingsTab } = parseUrlParams();
      setCurrentPageState(page);
      setActiveMenuTabState(menuTab);
      setActiveSettingsTabState(settingsTab);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const setCurrentPage = (page: PageId) => {
    setCurrentPageState(page);
    syncUrl(page, activeMenuTab, activeSettingsTab);
  };

  const setActiveMenuTab = (tab: MenuTabId) => {
    setActiveMenuTabState(tab);
    if (currentPage !== 'menu') {
      setCurrentPageState('menu');
      syncUrl('menu', tab, activeSettingsTab);
    } else {
      syncUrl('menu', tab, activeSettingsTab);
    }
  };

  const setActiveSettingsTab = (tab: SettingsTabId) => {
    setActiveSettingsTabState(tab);
    if (currentPage !== 'settings') {
      setCurrentPageState('settings');
      syncUrl('settings', activeMenuTab, tab);
    } else {
      syncUrl('settings', activeMenuTab, tab);
    }
  };

  const navigateTo = (page: PageId, tab?: string) => {
    setCurrentPageState(page);
    let nextMenuTab = activeMenuTab;
    let nextSettingsTab = activeSettingsTab;

    if (page === 'menu' && tab) {
      nextMenuTab = tab as MenuTabId;
      setActiveMenuTabState(nextMenuTab);
    } else if (page === 'settings' && tab) {
      nextSettingsTab = tab as SettingsTabId;
      setActiveSettingsTabState(nextSettingsTab);
    }

    syncUrl(page, nextMenuTab, nextSettingsTab);
  };

  useEffect(() => {
    if (!isAuthenticated) {
      setCities([]);
      setCoffeeShops([]);
      return;
    }

    Promise.all([api.getCities(), api.getCoffeeShops()])
      .then(([loadedCities, loadedShops]) => {
        setCities(loadedCities);
        setCoffeeShops(loadedShops);
      })
      .catch(() => {
        setCities([]);
        setCoffeeShops([]);
      });
  }, [isAuthenticated]);

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = String(Date.now());
    setToasts(prev => [...prev, { ...toast, id }]);
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  return (
    <AppContext.Provider
      value={{
        currentPage,
        setCurrentPage,
        activeMenuTab,
        setActiveMenuTab,
        activeSettingsTab,
        setActiveSettingsTab,
        navigateTo,
        selectedCityId,
        setSelectedCityId,
        selectedShopId,
        setSelectedShopId,
        cities,
        coffeeShops,
        sidebarCollapsed,
        setSidebarCollapsed,
        toasts,
        addToast,
        removeToast,
        searchQuery,
        setSearchQuery,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
