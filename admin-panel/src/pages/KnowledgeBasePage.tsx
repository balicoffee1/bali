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
  ExternalLink, ArrowRight, ShieldCheck, CheckCircle2, Clock
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
  'корзину': { name: 'Заказы (Live Desk)', page: 'orders' },
  'корзина': { name: 'Заказы (Live Desk)', page: 'orders' },
  'заказы': { name: 'Заказы (Live Desk)', page: 'orders' },
  'live desk': { name: 'Live Desk', page: 'orders' },
  'меню и товары': { name: 'Меню и товары', page: 'menu', tab: 'products' },
  'меню': { name: 'Меню и товары', page: 'menu', tab: 'products' },
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
  'отзывы': { name: 'Отзывы клиентов', page: 'reviews' },
  'кофейни и сеть': { name: 'Кофейни и сеть', page: 'settings', tab: 'shops' },
  'кофейни': { name: 'Кофейни и сеть', page: 'settings', tab: 'shops' },
  'эквайринг': { name: 'Эквайринг', page: 'settings', tab: 'acquiring' },
  'журнал аудита': { name: 'Журнал аудита', page: 'logs' },
  'дашборд': { name: 'Дашборд', page: 'dashboard' },
  'главный дашборд': { name: 'Дашборд', page: 'dashboard' },
};

export const KnowledgeBasePage: React.FC<KnowledgeBasePageProps> = ({ isStandalone = false }) => {
  const { navigateTo, addToast } = useApp();
  const { user } = useAuth();

  // Only OWNER or SUPERUSER can edit categories and articles
  const isOwner = Boolean(user?.is_superuser || user?.role === 'owner');

  // Categories & Articles state loaded from server API
  const [categories, setCategories] = useState<KnowledgeCategory[]>(() => getStoredCategories());
  const [articles, setArticles] = useState<KnowledgeArticle[]>(() => getStoredArticles());

  // Selected article ID (default to platform overview 'about-1' or first article)
  const [selectedArticleId, setSelectedArticleId] = useState<string>(() => {
    const list = getStoredArticles();
    const aboutArt = list.find(a => a.categoryId === 'about' || a.slug === 'platform-overview');
    return aboutArt?.id || list[0]?.id || 'orders-1';
  });

  // Track expanded categories in the sidebar tree
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    about: true,
    start: true,
    orders: true,
    menu: false,
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
          const aboutArt = serverArts.find(a => a.categoryId === 'about' || a.slug === 'platform-overview');
          setSelectedArticleId(aboutArt?.id || serverArts[0].id);
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
    const regex = /(Перейдите в раздел|перейдите в раздел|в раздел|раздел|Перейдите в|перейдите в|вкладка|вкладку)\s*(«[^»]+»|Корзину|корзину|Главный Дашборд)/gi;
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
              title={`Открыть раздел «${target.name}» в основном окне админ-панели`}
            >
              «{target.name}»
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
    <div className="min-h-screen bg-[#F8FAFC] text-brand-dark flex flex-col font-montserrat">
      {/* 1:1 WIKKEO DOCS TOP HEADER */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-200/80 px-6 sm:px-8 py-3.5 flex items-center justify-between">
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


          <div className="text-slate-400 p-1 cursor-default" title="Светлая тема">
            <Sun className="w-5 h-5 text-slate-400" />
          </div>
        </div>
      </header>

      {/* 1:1 WIKKEO DOCS LAYOUT: SIDEBAR (NO ICONS) + MAIN CONTENT IN APP BG */}
      <div className="flex-1 flex max-w-[1440px] w-full mx-auto">
        {/* ========================================================================= */}
        {/* LEFT SIDEBAR: PURE TEXT TREE HIERARCHY WITHOUT ICONS                      */}
        {/* ========================================================================= */}
        <aside className="w-72 shrink-0 bg-white border-r border-slate-200/80 py-6 px-4 sm:px-6 overflow-y-auto select-none">
          <nav className="space-y-1">
            {categories.map(cat => {
              const catArticles = articlesByCategory[cat.id] || [];
              const isExpanded = Boolean(expandedCategories[cat.id]);
              const hasArticles = catArticles.length > 0;
              const hasActiveChild = catArticles.some(a => a.id === selectedArticleId || a.slug === selectedArticleId);

              // If category is a single article (e.g. "about"), allow direct click to open
              const isSingleAbout = cat.slug === 'about' || cat.id === 'about';

              return (
                <div key={cat.id} className="py-0.5">
                  {/* Category Header Item */}
                  <div
                    onClick={() => {
                      if (isSingleAbout && catArticles[0]) {
                        setSelectedArticleId(catArticles[0].id);
                      } else if (hasArticles) {
                        toggleCategory(cat.id);
                      }
                    }}
                    className={cn(
                      "flex items-center justify-between py-1.5 px-2 rounded cursor-pointer transition-colors text-[14px]",
                      hasActiveChild || (isSingleAbout && currentArticle?.categoryId === cat.id)
                        ? "text-[#1D4ED8] font-semibold"
                        : "text-slate-700 hover:text-slate-900 font-medium"
                    )}
                  >
                    <span className="truncate pr-2">{cat.name}</span>
                    {hasArticles && !isSingleAbout && (
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
                  {isExpanded && hasArticles && !isSingleAbout && (
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
                              "w-full text-left text-[13px] py-1 px-2.5 rounded transition-colors block leading-snug",
                              isCurrent
                                ? "text-[#1D4ED8] font-semibold bg-blue-50/60"
                                : "text-slate-600 hover:text-slate-900 font-normal hover:bg-slate-50"
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
        {/* MAIN CONTENT AREA: CLEAN WHITE READING CARD OVER APP BACKGROUND           */}
        {/* ========================================================================= */}
        <main className="flex-1 min-w-0 bg-[#F8FAFC] py-8 px-4 sm:px-10 overflow-y-auto">
          {currentArticle ? (
            <div className="bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-10 shadow-xs max-w-4xl mx-auto space-y-8 animate-fadeIn">
              {/* Breadcrumbs: 🏠 > Category > [Article Pill] */}
              <div className="flex items-center gap-2 text-xs text-slate-400 flex-wrap pb-4 border-b border-slate-100">
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
              <div className="flex items-start justify-between gap-4">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
                  {currentArticle.title}
                </h1>


              </div>

              {/* 1. Обоснование и бизнес-логика */}
              {currentArticle.whyNeeded && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                    Обоснование и бизнес-логика
                  </h3>
                  <p className="text-[15px] text-slate-800 leading-relaxed font-normal">
                    {renderInteractiveStepText(currentArticle.whyNeeded)}
                  </p>
                </div>
              )}

              {/* 2. Что это такое и как устроено */}
              {currentArticle.whatIsIt && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                    Устройство и принцип работы
                  </h3>
                  <p className="text-[15px] text-slate-800 leading-relaxed font-normal">
                    {renderInteractiveStepText(currentArticle.whatIsIt)}
                  </p>
                </div>
              )}

              {/* 3. Пошаговый регламент действий (Как сделать) */}
              {currentArticle.steps && currentArticle.steps.length > 0 && (
                <div className="space-y-4 pt-2">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                    Пошаговый регламент действий
                  </h3>
                  <div className="space-y-3">
                    {currentArticle.steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3.5 p-3.5 rounded-xl bg-slate-50/70 border border-slate-200/70 text-slate-800 text-[14.5px] leading-relaxed"
                      >
                        <span className="w-5 h-5 rounded-full bg-[#1D4ED8] text-white text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <div className="flex-1">
                          {renderInteractiveStepText(step)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Troubleshooting: Частые вопросы и ошибки */}
              {currentArticle.troubleshooting && currentArticle.troubleshooting.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-amber-600">
                    Важные нюансы и решение проблем
                  </h3>
                  <div className="space-y-2.5">
                    {currentArticle.troubleshooting.map((tr, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-amber-50/40 border border-amber-200/80 text-slate-800 text-[14px] leading-relaxed"
                      >
                        {renderInteractiveStepText(tr)}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Кнопка быстрого перехода в раздел админки */}
              {currentArticle.quickAction && (
                <div className="pt-4 border-t border-slate-100 flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {currentArticle.tags.map(tag => (
                      <span
                        key={tag}
                        className="px-2.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      const targetPage = currentArticle.quickAction?.page || 'dashboard';
                      const targetTab = currentArticle.quickAction?.tab;
                      handleNavigateToSection(targetPage, targetTab);
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#1D4ED8] hover:bg-[#1e40af] text-white font-bold text-xs shadow-xs transition-colors"
                  >
                    <span>{currentArticle.quickAction.label}</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
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
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Обоснование и бизнес-логика (Зачем это нужно)
                </label>
                <textarea
                  rows={2}
                  value={editingArticle.whyNeeded || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whyNeeded: e.target.value })}
                  className="w-full p-2 rounded border border-slate-300 text-xs outline-none focus:border-blue-600"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Устройство и принцип работы (Что это такое)
                </label>
                <textarea
                  rows={2}
                  value={editingArticle.whatIsIt || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whatIsIt: e.target.value })}
                  className="w-full p-2 rounded border border-slate-300 text-xs outline-none focus:border-blue-600"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-slate-700">
                    Шаги регламента
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditingArticle({
                      ...editingArticle,
                      steps: [...(editingArticle.steps || []), ''],
                    })}
                    className="text-xs font-bold text-blue-600 hover:text-blue-800"
                  >
                    + Добавить шаг
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
                        placeholder="Например: Перейдите в раздел «Пользователи»..."
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
