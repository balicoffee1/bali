import React, { useState, useEffect, useMemo } from 'react';
import { useApp, PageId, MenuTabId, SettingsTabId } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  KnowledgeArticle, KnowledgeCategory,
  getStoredArticles, getStoredCategories,
} from '../data/knowledgeBaseData';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { cn } from '../utils/cn';
import {
  Home, ChevronRight, ChevronDown, Sun, Edit3, Trash2, Plus,
  Coffee, ShoppingBag, Send, Check
} from 'lucide-react';

export interface KnowledgeBasePageProps {
  isStandalone?: boolean;
}

interface SectionTarget {
  name: string;
  page: PageId;
  tab?: MenuTabId | SettingsTabId | string;
}

const SECTION_TARGETS: Record<string, SectionTarget> = {
  'пользователи': { name: 'Пользователи', page: 'users' },
  'пользователи.': { name: 'Пользователи', page: 'users' },
  'корзину': { name: 'Заказы', page: 'orders' },
  'корзина': { name: 'Заказы', page: 'orders' },
  'заказы': { name: 'Заказы (Live Desk)', page: 'orders' },
  'live desk': { name: 'Live Desk', page: 'orders' },
  'меню и товары': { name: 'Меню и товары', page: 'menu', tab: 'products' },
  'меню': { name: 'Меню', page: 'menu', tab: 'products' },
  'товары': { name: 'Товары', page: 'menu', tab: 'products' },
  'категории': { name: 'Категории меню', page: 'menu', tab: 'categories' },
  'добавки': { name: 'Добавки', page: 'menu', tab: 'addons' },
  'смены и бариста': { name: 'Смены и Бариста', page: 'shifts' },
  'смены': { name: 'Смены', page: 'shifts', tab: 'shifts' },
  'сотрудники': { name: 'Сотрудники', page: 'shifts', tab: 'staff' },
  'telegram-бот': { name: 'Telegram-бот', page: 'telegram' },
  'telegram': { name: 'Telegram-бот', page: 'telegram' },
  'push-рассылки': { name: 'Push-рассылки', page: 'notifications' },
  'отзывы клиентов': { name: 'Отзывы клиентов', page: 'reviews' },
  'отзывы': { name: 'Отзывы', page: 'reviews' },
  'кофейни и сеть': { name: 'Кофейни и сеть', page: 'settings', tab: 'shops' },
  'кофейни': { name: 'Кофейни', page: 'settings', tab: 'shops' },
  'эквайринг': { name: 'Эквайринг', page: 'settings', tab: 'acquiring' },
  'журнал аудита': { name: 'Журнал аудита', page: 'logs' },
  'дашборд': { name: 'Дашборд', page: 'dashboard' },
};

export const KnowledgeBasePage: React.FC<KnowledgeBasePageProps> = ({ isStandalone = false }) => {
  const { navigateTo, addToast } = useApp();
  const { user } = useAuth();

  // Only OWNER or SUPERUSER can edit categories and articles
  const isOwner = Boolean(user?.is_superuser || user?.role === 'owner');

  // Categories & Articles state loaded from server API
  const [categories, setCategories] = useState<KnowledgeCategory[]>(() => getStoredCategories());
  const [articles, setArticles] = useState<KnowledgeArticle[]>(() => getStoredArticles());

  // Selected article ID
  const [selectedArticleId, setSelectedArticleId] = useState<string>(() => {
    const list = getStoredArticles();
    return list[0]?.id || 'orders-1';
  });

  // Track expanded categories in the sidebar tree
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    start: true,
    orders: true,
    menu: true,
    staff: false,
    telegram: false,
    marketing: false,
    reviews: false,
    users: false,
    settings: false,
    security: false,
    troubleshooting: false,
  });

  // Owner state: Edit / Create Article Drawer
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState<Partial<KnowledgeArticle> | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [articleToDelete, setArticleToDelete] = useState<KnowledgeArticle | null>(null);

  // Owner state: Category Modal
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Partial<KnowledgeCategory> | null>(null);
  const [categoryToDelete, setCategoryToDelete] = useState<KnowledgeCategory | null>(null);

  // Load from server API on mount
  useEffect(() => {
    loadKnowledgeBaseFromServer();
  }, []);

  const loadKnowledgeBaseFromServer = async () => {
    try {
      const [serverCats, serverArts] = await Promise.all([
        api.getKnowledgeCategories(),
        api.getKnowledgeArticles(),
      ]);
      if (serverCats && serverCats.length > 0) {
        setCategories(serverCats);
      }
      if (serverArts && serverArts.length > 0) {
        setArticles(serverArts);
        if (!selectedArticleId || !serverArts.some(a => a.id === selectedArticleId)) {
          setSelectedArticleId(serverArts[0].id);
        }
      }
    } catch {
      // Gracefully uses local fallback
    }
  };

  // Current active article
  const currentArticle = useMemo(() => {
    return articles.find(a => a.id === selectedArticleId || a.slug === selectedArticleId) || articles[0];
  }, [articles, selectedArticleId]);

  // Current active category
  const currentCategory = useMemo(() => {
    if (!currentArticle) return null;
    return categories.find(c => c.id === currentArticle.categoryId || c.slug === currentArticle.categoryId) || null;
  }, [categories, currentArticle]);

  // Auto-expand category when selected article changes
  useEffect(() => {
    if (currentArticle?.categoryId) {
      setExpandedCategories(prev => ({
        ...prev,
        [currentArticle.categoryId]: true,
      }));
    }
  }, [currentArticle?.categoryId]);

  // Group articles by category
  const articlesByCategory = useMemo(() => {
    const map: Record<string, KnowledgeArticle[]> = {};
    categories.forEach(cat => {
      map[cat.id] = [];
    });
    articles.forEach(art => {
      const catKey = art.categoryId;
      if (map[catKey]) {
        map[catKey].push(art);
      } else {
        const found = categories.find(c => c.slug === catKey || String(c.id) === String(catKey));
        if (found && map[found.id]) {
          map[found.id].push(art);
        } else {
          map[catKey] = [art];
        }
      }
    });
    return map;
  }, [categories, articles]);

  const toggleCategory = (catId: string) => {
    setExpandedCategories(prev => ({
      ...prev,
      [catId]: !prev[catId],
    }));
  };

  // Safe navigation to admin sections (works both in new window and inside panel)
  const handleNavigateToSection = (page: PageId, tab?: string) => {
    const url = `/?page=${page}${tab ? `&tab=${tab}` : ''}`;
    if (isStandalone) {
      if (window.opener && !window.opener.closed) {
        try {
          window.opener.location.href = url;
          window.opener.focus();
          return;
        } catch {}
      }
      window.open(url, 'happy_island_admin_window');
    } else {
      navigateTo(page, tab);
    }
  };

  // Helper to parse step text and make phrases like "Перейдите в Корзину" or "в раздел «Пользователи»" clean clickable links
  const renderInteractiveStepText = (text: string) => {
    const regex = /(Перейдите в раздел|перейдите в раздел|в раздел|раздел|Перейдите в|перейдите в|вкладка|вкладку)\s*(«[^»]+»|Корзину|корзину)/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
      const matchStart = match.index;
      const matchEnd = regex.lastIndex;
      const prefixText = match[1];
      const targetNameRaw = match[2].replace(/[«»]/g, '').trim();
      const targetKey = targetNameRaw.toLowerCase();
      const target = SECTION_TARGETS[targetKey];

      if (matchStart > lastIndex) {
        parts.push(text.substring(lastIndex, matchStart));
      }

      if (target) {
        parts.push(
          <span key={`link-${matchStart}`} className="inline">
            <span>{prefixText} </span>
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                handleNavigateToSection(target.page, target.tab);
              }}
              className="font-bold text-[#1D4ED8] hover:text-[#1e40af] hover:underline underline-offset-2 transition-colors cursor-pointer inline"
            >
              {match[2]}
            </button>
          </span>
        );
      } else {
        parts.push(
          <span key={`bold-${matchStart}`} className="font-bold text-slate-900 inline">
            {match[0]}
          </span>
        );
      }

      lastIndex = matchEnd;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts;
  };

  // Owner handlers
  const handleOpenCreateArticle = () => {
    if (!isOwner) return;
    setEditingArticle({
      title: '',
      categoryId: currentCategory?.id || categories[0]?.id || 'start',
      targetRole: 'all',
      whyNeeded: '',
      whatIsIt: '',
      steps: [''],
      troubleshooting: [''],
      mockupType: 'none',
      tags: [],
    });
    setIsCreatingNew(true);
    setIsEditDrawerOpen(true);
  };

  const handleOpenEditArticle = (art: KnowledgeArticle) => {
    if (!isOwner) return;
    setEditingArticle({
      ...art,
      steps: [...art.steps],
      troubleshooting: art.troubleshooting ? [...art.troubleshooting] : [''],
      tags: [...art.tags],
    });
    setIsCreatingNew(false);
    setIsEditDrawerOpen(true);
  };

  const handleSaveArticle = async () => {
    if (!isOwner || !editingArticle) return;
    if (!editingArticle.title?.trim()) {
      addToast({ type: 'warning', title: 'Укажите название статьи' });
      return;
    }
    if (!editingArticle.categoryId) {
      addToast({ type: 'warning', title: 'Выберите раздел' });
      return;
    }

    try {
      if (isCreatingNew) {
        const created = await api.createKnowledgeArticle(editingArticle);
        setArticles(prev => [created, ...prev]);
        setSelectedArticleId(created.id);
        addToast({ type: 'success', title: 'Статья сохранена на сервере' });
      } else if (editingArticle.id) {
        const updated = await api.updateKnowledgeArticle(editingArticle.id, editingArticle);
        setArticles(prev => prev.map(a => (a.id === updated.id || a.slug === updated.id ? updated : a)));
        setSelectedArticleId(updated.id);
        addToast({ type: 'success', title: 'Статья обновлена на сервере' });
      }
      setIsEditDrawerOpen(false);
      setEditingArticle(null);
    } catch {
      addToast({ type: 'error', title: 'Ошибка сохранения статьи' });
    }
  };

  const handleConfirmDeleteArticle = async () => {
    if (!isOwner || !articleToDelete) return;
    try {
      await api.deleteKnowledgeArticle(articleToDelete.id);
      const nextList = articles.filter(a => a.id !== articleToDelete.id && a.slug !== articleToDelete.id);
      setArticles(nextList);
      if (selectedArticleId === articleToDelete.id || selectedArticleId === articleToDelete.slug) {
        setSelectedArticleId(nextList[0]?.id || '');
      }
      addToast({ type: 'info', title: 'Статья удалена' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка удаления' });
    } finally {
      setArticleToDelete(null);
    }
  };

  const handleOpenCreateCategory = () => {
    if (!isOwner) return;
    setEditingCategory({
      id: '',
      name: '',
      iconName: 'BookOpen',
      order: categories.length + 1,
    });
    setIsCategoryModalOpen(true);
  };

  const handleSaveCategory = async () => {
    if (!isOwner || !editingCategory?.name?.trim()) return;
    try {
      if (editingCategory.id) {
        const updated = await api.updateKnowledgeCategory(editingCategory.id, editingCategory);
        setCategories(prev => prev.map(c => (c.id === updated.id ? updated : c)));
      } else {
        const created = await api.createKnowledgeCategory(editingCategory);
        setCategories(prev => [...prev, created]);
        setExpandedCategories(prev => ({ ...prev, [created.id]: true }));
      }
      setIsCategoryModalOpen(false);
      setEditingCategory(null);
    } catch {
      addToast({ type: 'error', title: 'Ошибка сохранения раздела' });
    }
  };

  const handleConfirmDeleteCategory = async () => {
    if (!isOwner || !categoryToDelete) return;
    try {
      await api.deleteKnowledgeCategory(categoryToDelete.id);
      setCategories(prev => prev.filter(c => c.id !== categoryToDelete.id));
    } catch {
      addToast({ type: 'error', title: 'Ошибка удаления раздела' });
    } finally {
      setCategoryToDelete(null);
    }
  };

  return (
    <div className="min-h-screen bg-white text-slate-900 flex flex-col font-sans">
      {/* 1:1 WIKKEO DOCS TOP HEADER */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-100 px-6 sm:px-8 py-3.5 flex items-center justify-between">
        {/* Left: Brand Logo text matching WIKKEO Docs 1-to-1 */}
        <div className="flex items-center gap-2">
          <span className="text-xl sm:text-2xl font-black tracking-tight text-[#1D4ED8]">
            HAPPY ISLAND
          </span>
          <span className="text-xs sm:text-sm font-semibold text-[#2563EB] ml-1">
            Docs
          </span>
        </div>

        {/* Right: Sun icon and discreet Owner controls */}
        <div className="flex items-center gap-4">
          {isOwner && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleOpenCreateArticle}
                className="px-2.5 py-1 text-xs font-semibold rounded bg-[#1D4ED8] text-white hover:bg-[#1e40af] transition-colors"
              >
                + Статья
              </button>
              <button
                type="button"
                onClick={handleOpenCreateCategory}
                className="px-2.5 py-1 text-xs font-semibold rounded border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                + Раздел
              </button>
            </div>
          )}

          <div className="text-slate-400 p-1 cursor-default" title="Светлая тема">
            <Sun className="w-5 h-5 text-slate-400" />
          </div>
        </div>
      </header>

      {/* 1:1 WIKKEO DOCS LAYOUT: SIDEBAR (NO ICONS) + MAIN CONTENT */}
      <div className="flex-1 flex max-w-[1440px] w-full mx-auto">
        {/* ========================================================================= */}
        {/* LEFT SIDEBAR: PURE TEXT TREE HIERARCHY WITHOUT ICONS                      */}
        {/* ========================================================================= */}
        <aside className="w-72 shrink-0 border-r border-slate-100 py-6 px-4 sm:px-6 overflow-y-auto select-none">
          <nav className="space-y-1">
            {categories.map(cat => {
              const catArticles = articlesByCategory[cat.id] || [];
              const isExpanded = Boolean(expandedCategories[cat.id]);
              const hasArticles = catArticles.length > 0;
              const hasActiveChild = catArticles.some(a => a.id === selectedArticleId || a.slug === selectedArticleId);

              return (
                <div key={cat.id} className="py-0.5">
                  {/* Category Header Item */}
                  <div
                    onClick={() => {
                      if (hasArticles) {
                        toggleCategory(cat.id);
                      }
                    }}
                    className={cn(
                      "flex items-center justify-between py-1.5 px-2 rounded cursor-pointer transition-colors text-[14px]",
                      hasActiveChild || isExpanded
                        ? "text-[#1D4ED8] font-semibold"
                        : "text-slate-700 hover:text-slate-900 font-medium"
                    )}
                  >
                    <span className="truncate pr-2">{cat.name}</span>
                    {hasArticles && (
                      <span className="text-slate-400 shrink-0">
                        {isExpanded ? (
                          <ChevronDown className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5" />
                        )}
                      </span>
                    )}
                  </div>

                  {/* Sub-items (Articles under category) - NO ICONS */}
                  {isExpanded && hasArticles && (
                    <div className="pl-3 mt-0.5 space-y-0.5">
                      {catArticles.map(art => {
                        const isCurrent = art.id === selectedArticleId || art.slug === selectedArticleId;
                        return (
                          <button
                            key={art.id}
                            type="button"
                            onClick={() => {
                              setSelectedArticleId(art.id);
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                            className={cn(
                              "w-full text-left text-[13.5px] py-1 px-2.5 rounded transition-colors block leading-snug",
                              isCurrent
                                ? "text-[#1D4ED8] font-semibold"
                                : "text-slate-600 hover:text-slate-900 font-normal"
                            )}
                          >
                            {art.title}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* ========================================================================= */}
        {/* MAIN CONTENT AREA: 1-TO-1 WIKKEO DOCS ARTICLE VIEW                        */}
        {/* ========================================================================= */}
        <main className="flex-1 min-w-0 py-8 px-6 sm:px-12 max-w-4xl">
          {currentArticle ? (
            <div>
              {/* Breadcrumbs: 🏠 > Category > [Article Pill] */}
              <div className="flex items-center gap-2 text-xs text-slate-400 mb-6 flex-wrap">
                <Home className="w-3.5 h-3.5 text-slate-800 shrink-0" />
                <span className="text-slate-300 font-light">&gt;</span>
                <span className="text-slate-600 font-medium">
                  {currentCategory?.name || 'Документация'}
                </span>
                <span className="text-slate-300 font-light">&gt;</span>
                <span className="bg-[#EFF6FF] text-[#2563EB] px-3 py-1 rounded-full text-xs font-semibold">
                  {currentArticle.title}
                </span>
              </div>

              {/* H1 Title: Large, bold, clean */}
              <div className="flex items-start justify-between gap-4 mb-4">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                  {currentArticle.title}
                </h1>

                {/* Owner controls */}
                {isOwner && (
                  <div className="flex items-center gap-2 shrink-0 pt-1">
                    <button
                      type="button"
                      onClick={() => handleOpenEditArticle(currentArticle)}
                      className="text-xs text-slate-500 hover:text-[#1D4ED8] font-medium px-2 py-1 rounded border border-slate-200 hover:border-blue-300 transition-colors"
                    >
                      Редактировать
                    </button>
                    <button
                      type="button"
                      onClick={() => setArticleToDelete(currentArticle)}
                      className="text-xs text-red-500 hover:text-red-700 font-medium px-2 py-1 rounded border border-slate-200 hover:border-red-300 transition-colors"
                    >
                      Удалить
                    </button>
                  </div>
                )}
              </div>

              {/* Intro Text */}
              <p className="text-[15px] text-slate-800 leading-relaxed mb-6 font-normal">
                {renderInteractiveStepText(
                  currentArticle.steps[0] ||
                  `Перейдите в Корзину и приступайте к оформлению заказа, нажав Купить`
                )}
              </p>

              {/* 1:1 WIKKEO DOCS MOCKUP SCREENS (Side-by-side Mobile Interface Preview) */}
              <div className="my-8 flex flex-col md:flex-row items-center justify-center gap-6 max-w-3xl mx-auto">
                {/* Screen 1: Mobile App Showcase / Catalog */}
                <div className="w-full max-w-[290px] rounded-[30px] border-4 border-slate-800 bg-white p-2.5 shadow-xl text-slate-900">
                  <div className="w-16 h-3 bg-slate-800 rounded-full mx-auto mb-2" />
                  
                  {/* Search bar inside screen */}
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-xl text-[11px] text-slate-400 mb-2 border border-slate-200">
                    <span className="w-4 h-4 rounded-full bg-amber-400 flex items-center justify-center text-[9px] font-black text-white">W</span>
                    <span>Искать в Happy Island...</span>
                  </div>

                  {/* Banner */}
                  <div className="h-24 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 p-3 text-white flex flex-col justify-between relative overflow-hidden mb-2.5">
                    <div>
                      <span className="text-[9px] bg-white/20 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Спецпредложение</span>
                      <p className="text-xs font-bold mt-1">Скидка 20% на весь авторский кофе</p>
                    </div>
                    <span className="text-[9px] text-white/80">Каждый день до 12:00</span>
                  </div>

                  {/* Categories grid */}
                  <div className="grid grid-cols-4 gap-1.5 text-center text-[10px] mb-2">
                    <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100 font-medium">Кофе</div>
                    <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100 font-medium">Чай</div>
                    <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100 font-medium">Выпечка</div>
                    <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100 font-medium">Десерты</div>
                  </div>

                  {/* Bottom nav inside phone */}
                  <div className="flex items-center justify-around pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                    <span className="text-blue-600 font-bold">Главная</span>
                    <span>Каталог</span>
                    <span className="relative">
                      Корзина
                      <span className="absolute -top-1.5 -right-2.5 w-3.5 h-3.5 bg-red-500 text-white rounded-full text-[8px] font-bold flex items-center justify-center">1</span>
                    </span>
                    <span>Профиль</span>
                  </div>
                </div>

                {/* Screen 2: Cart / Checkout Screen (Matching Wikkeo Right Screen 1-to-1) */}
                <div className="w-full max-w-[290px] rounded-[30px] border-4 border-slate-800 bg-white p-2.5 shadow-xl text-slate-900 flex flex-col justify-between min-h-[390px]">
                  <div>
                    <div className="w-16 h-3 bg-slate-800 rounded-full mx-auto mb-2" />
                    
                    {/* Header in phone */}
                    <div className="flex items-center justify-between px-2 pb-2 border-b border-slate-100 text-xs">
                      <span className="text-slate-400">&lt;</span>
                      <span className="font-bold text-slate-800">Корзина</span>
                      <span className="text-[10px] text-slate-400">Удалить</span>
                    </div>

                    {/* Shop and item in cart */}
                    <div className="pt-2 px-1 space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                        <div className="flex items-center gap-1.5">
                          <span className="w-3.5 h-3.5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[8px]"><Check className="w-2.5 h-2.5" /></span>
                          <span>Happy Island Coffee</span>
                        </div>
                        <span className="font-mono text-slate-500">510 ₽</span>
                      </div>

                      {/* Product item 1 */}
                      <div className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                        <div className="flex items-center justify-between font-bold">
                          <span>Раф Цитрусовый (350 мл)</span>
                          <span className="font-mono">320 ₽</span>
                        </div>
                        <p className="text-[10px] text-slate-500">Альтернативное молоко (овсяное)</p>
                        <span className="inline-block text-[9px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-semibold">+ 15 бонусов</span>
                      </div>

                      {/* Product item 2 */}
                      <div className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                        <div className="flex items-center justify-between font-bold">
                          <span>Круассан миндальный x1</span>
                          <span className="font-mono">190 ₽</span>
                        </div>
                        <p className="text-[10px] text-slate-500">Свежая выпечка</p>
                      </div>
                    </div>
                  </div>

                  {/* Checkout bar matching Wikkeo blue button */}
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between px-1">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                      <span className="w-3.5 h-3.5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[8px]"><Check className="w-2.5 h-2.5" /></span>
                      <span>Итого: <strong className="text-slate-900 font-mono">510 ₽</strong></span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleNavigateToSection('orders')}
                      className="px-4 py-1.5 rounded-full bg-[#1D4ED8] hover:bg-[#1e40af] text-white font-bold text-xs shadow-sm transition-colors"
                    >
                      Купить
                    </button>
                  </div>
                </div>
              </div>

              {/* Detailed Steps text below screenshots */}
              <div className="space-y-4 my-6 text-[14.5px] text-slate-800 leading-relaxed font-normal">
                {currentArticle.steps.slice(1).map((step, idx) => (
                  <p key={idx} className="leading-relaxed">
                    {renderInteractiveStepText(step)}
                  </p>
                ))}
              </div>

              {/* Troubleshooting notes (if any) */}
              {currentArticle.troubleshooting && currentArticle.troubleshooting.length > 0 && (
                <div className="mt-8 pt-6 border-t border-slate-100 text-sm text-slate-700">
                  <h4 className="font-bold text-slate-900 text-sm mb-2">Обратите внимание:</h4>
                  <ul className="list-disc list-inside space-y-1.5 leading-relaxed">
                    {currentArticle.troubleshooting.map((tr, idx) => (
                      <li key={idx}>
                        {renderInteractiveStepText(tr)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-16 text-slate-400">
              <p>Выберите статью в меню слева</p>
            </div>
          )}
        </main>
      </div>

      {/* ========================================================================= */}
      {/* OWNER MODALS & DRAWERS (DISCREET, NON-INTRUSIVE)                          */}
      {/* ========================================================================= */}

      {/* CREATE / EDIT ARTICLE DRAWER */}
      {isOwner && (
        <Drawer
          isOpen={isEditDrawerOpen}
          onClose={() => setIsEditDrawerOpen(false)}
          title={isCreatingNew ? 'Создание статьи' : 'Редактирование статьи'}
          width="lg"
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="text-xs text-slate-400">Синхронизация с сервером</span>
              <div className="flex items-center gap-2">
                <Button variant="ghost" onClick={() => setIsEditDrawerOpen(false)}>
                  Отмена
                </Button>
                <Button variant="primary" onClick={handleSaveArticle} className="bg-[#1D4ED8] text-white font-bold hover:bg-[#1e40af]">
                  Сохранить
                </Button>
              </div>
            </div>
          }
        >
          {editingArticle && (
            <div className="space-y-4 text-sm">
              <Input
                label="Заголовок статьи"
                value={editingArticle.title || ''}
                onChange={e => setEditingArticle({ ...editingArticle, title: e.target.value })}
                placeholder="Например: Оформление заказа"
                required
              />

              <div className="grid grid-cols-2 gap-4">
                <Select
                  label="Раздел"
                  value={editingArticle.categoryId || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, categoryId: e.target.value })}
                  options={categories.map(c => ({ value: c.id, label: c.name }))}
                />

                <Select
                  label="Целевая роль"
                  value={editingArticle.targetRole || 'all'}
                  onChange={e => setEditingArticle({ ...editingArticle, targetRole: e.target.value as any })}
                  options={[
                    { value: 'all', label: 'Для всех ролей' },
                    { value: 'barista', label: 'Бариста' },
                    { value: 'manager', label: 'Управляющий' },
                    { value: 'owner', label: 'Только Owner' },
                    { value: 'admin', label: 'Администратор' },
                  ]}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-slate-700">
                    Текст и шаги инструкции
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditingArticle({
                      ...editingArticle,
                      steps: [...(editingArticle.steps || []), ''],
                    })}
                    className="text-xs font-bold text-blue-600 hover:text-blue-800"
                  >
                    + Добавить абзац/шаг
                  </button>
                </div>
                <div className="space-y-2">
                  {(editingArticle.steps || []).map((step, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="w-4 h-4 text-slate-400 text-xs font-bold flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>
                      <input
                        type="text"
                        value={step}
                        onChange={e => {
                          const next = [...(editingArticle.steps || [])];
                          next[idx] = e.target.value;
                          setEditingArticle({ ...editingArticle, steps: next });
                        }}
                        placeholder="Например: Перейдите в Корзину и нажмите Купить..."
                        className="flex-1 p-2 rounded border border-slate-300 text-xs outline-none focus:border-blue-600"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const next = (editingArticle.steps || []).filter((_, i) => i !== idx);
                          setEditingArticle({ ...editingArticle, steps: next.length ? next : [''] });
                        }}
                        className="p-1 text-slate-400 hover:text-red-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Drawer>
      )}

      {/* CREATE / EDIT CATEGORY MODAL */}
      {isOwner && (
        <Modal
          isOpen={isCategoryModalOpen}
          onClose={() => setIsCategoryModalOpen(false)}
          title={editingCategory?.id ? 'Редактирование раздела' : 'Новый раздел'}
        >
          {editingCategory && (
            <div className="space-y-4">
              <Input
                label="Название раздела"
                value={editingCategory.name || ''}
                onChange={e => setEditingCategory({ ...editingCategory, name: e.target.value })}
                placeholder="Например: Работа с заказом"
                required
              />

              <Input
                label="Порядок сортировки"
                type="number"
                value={String(editingCategory.order || 0)}
                onChange={e => setEditingCategory({ ...editingCategory, order: Number(e.target.value) })}
              />

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <Button variant="ghost" onClick={() => setIsCategoryModalOpen(false)}>
                  Отмена
                </Button>
                <Button variant="primary" onClick={handleSaveCategory} className="bg-[#1D4ED8] text-white">
                  Сохранить
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {/* DELETE CONFIRMATION MODALS */}
      {isOwner && (
        <Modal
          isOpen={Boolean(articleToDelete)}
          onClose={() => setArticleToDelete(null)}
          title="Удаление статьи"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Удалить статью «{articleToDelete?.title}»?</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setArticleToDelete(null)}>Отмена</Button>
              <Button variant="danger" onClick={handleConfirmDeleteArticle}>Удалить</Button>
            </div>
          </div>
        </Modal>
      )}

      {isOwner && (
        <Modal
          isOpen={Boolean(categoryToDelete)}
          onClose={() => setCategoryToDelete(null)}
          title="Удаление раздела"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Удалить раздел «{categoryToDelete?.name}»?</p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCategoryToDelete(null)}>Отмена</Button>
              <Button variant="danger" onClick={handleConfirmDeleteCategory}>Удалить</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
