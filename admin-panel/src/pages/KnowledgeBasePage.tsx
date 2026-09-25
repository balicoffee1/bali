import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useApp, PageId, MenuTabId, SettingsTabId } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  KnowledgeArticle, KnowledgeCategory,
  getStoredArticles, getStoredCategories,
  saveStoredArticles, saveStoredCategories,
  resetStoredKnowledgeBase, INITIAL_ARTICLES, INITIAL_CATEGORIES
} from '../data/knowledgeBaseData';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { cn } from '../utils/cn';
import {
  Search, Plus, Edit3, Trash2,
  ExternalLink, ArrowRight, ArrowLeft, ShieldCheck, ShoppingBag, UtensilsCrossed,
  Clock, Send, Bell, Star, Users, Store, HelpCircle, CheckCircle2,
  AlertTriangle, RotateCcw, Download, Coffee, Sparkles, FolderPlus,
  BookOpen, Layers, Check, ChevronRight
} from 'lucide-react';

export interface KnowledgeBasePageProps {
  isStandalone?: boolean;
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Compass: <Sparkles className="w-4 h-4" />,
  ShoppingBag: <ShoppingBag className="w-4 h-4" />,
  UtensilsCrossed: <UtensilsCrossed className="w-4 h-4" />,
  Clock: <Clock className="w-4 h-4" />,
  Send: <Send className="w-4 h-4" />,
  Bell: <Bell className="w-4 h-4" />,
  Star: <Star className="w-4 h-4" />,
  Users: <Users className="w-4 h-4" />,
  Store: <Store className="w-4 h-4" />,
  ShieldCheck: <ShieldCheck className="w-4 h-4" />,
  HelpCircle: <HelpCircle className="w-4 h-4" />,
  BookOpen: <BookOpen className="w-4 h-4" />,
  Coffee: <Coffee className="w-4 h-4" />,
};

interface SectionTarget {
  name: string;
  page: PageId;
  tab?: MenuTabId | SettingsTabId | string;
}

const SECTION_TARGETS: Record<string, SectionTarget> = {
  'пользователи': { name: 'Пользователи', page: 'users' },
  'пользователи.': { name: 'Пользователи', page: 'users' },
  'заказы': { name: 'Заказы (Live Desk)', page: 'orders' },
  'live desk': { name: 'Live Desk', page: 'orders' },
  'меню и товары': { name: 'Меню и товары', page: 'menu', tab: 'products' },
  'меню': { name: 'Меню', page: 'menu', tab: 'products' },
  'товары': { name: 'Товары', page: 'menu', tab: 'products' },
  'категории': { name: 'Категории меню', page: 'menu', tab: 'categories' },
  'добавки': { name: 'Добавки', page: 'menu', tab: 'addons' },
  'вкусы добавок': { name: 'Вкусы добавок', page: 'menu', tab: 'flavors' },
  'сезонное меню': { name: 'Сезонное меню', page: 'menu', tab: 'seasons' },
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
  'города': { name: 'Города', page: 'settings', tab: 'cities' },
  'эквайринг': { name: 'Эквайринг', page: 'settings', tab: 'acquiring' },
  'crm и интеграции': { name: 'CRM и интеграции', page: 'settings', tab: 'crm' },
  'журнал аудита': { name: 'Журнал аудита', page: 'logs' },
  'дашборд': { name: 'Дашборд', page: 'dashboard' },
};

export const KnowledgeBasePage: React.FC<KnowledgeBasePageProps> = ({ isStandalone = false }) => {
  const { navigateTo, addToast } = useApp();
  const { user } = useAuth();
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Only OWNER or SUPERUSER can edit categories and articles
  const isOwner = Boolean(user?.is_superuser || user?.role === 'owner');

  // Categories & Articles state loaded from server API
  const [categories, setCategories] = useState<KnowledgeCategory[]>(() => getStoredCategories());
  const [articles, setArticles] = useState<KnowledgeArticle[]>(() => getStoredArticles());
  const [isLoadingData, setIsLoadingData] = useState(false);

  // Navigation State: 'all' or categoryId for directory filter; null if in catalog view, string if in detail view
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('all');
  const [activeArticleId, setActiveArticleId] = useState<string | null>(null);

  // Filter & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | 'barista' | 'manager' | 'owner' | 'admin'>('all');

  // Edit / Create Article Drawer
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState<Partial<KnowledgeArticle> | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [articleToDelete, setArticleToDelete] = useState<KnowledgeArticle | null>(null);

  // Category Modal (Create / Edit Department)
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Partial<KnowledgeCategory> | null>(null);
  const [categoryToDelete, setCategoryToDelete] = useState<KnowledgeCategory | null>(null);

  // Focus Search Bar on ⌘K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      if (e.key === 'Escape' && activeArticleId !== null && !isEditDrawerOpen && !isCategoryModalOpen) {
        setActiveArticleId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeArticleId, isEditDrawerOpen, isCategoryModalOpen]);

  // Load from server on mount
  useEffect(() => {
    loadKnowledgeBaseFromServer();
  }, []);

  const loadKnowledgeBaseFromServer = async () => {
    setIsLoadingData(true);
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
      }
    } catch {
      // Gracefully uses local storage fallback
    } finally {
      setIsLoadingData(false);
    }
  };

  // Currently active article (if in detail view)
  const activeArticle = useMemo(() => {
    if (!activeArticleId) return null;
    return articles.find(a => a.id === activeArticleId || a.slug === activeArticleId) || null;
  }, [articles, activeArticleId]);

  const activeCategory = useMemo(() => {
    if (!activeArticle) return null;
    return categories.find(c => c.id === activeArticle.categoryId || c.slug === activeArticle.categoryId) || null;
  }, [categories, activeArticle]);

  // Filtered articles for the directory view
  const filteredArticles = useMemo(() => {
    return articles.filter(art => {
      // Category filter
      if (selectedCategoryId !== 'all') {
        const matchesCategory =
          art.categoryId === selectedCategoryId ||
          categories.find(c => (c.id === selectedCategoryId || c.slug === selectedCategoryId) && (c.id === art.categoryId || c.slug === art.categoryId));
        if (!matchesCategory) return false;
      }

      // Role filter
      if (roleFilter !== 'all' && art.targetRole !== 'all' && art.targetRole !== roleFilter) {
        return false;
      }

      // Search query
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      const inTitle = art.title.toLowerCase().includes(q);
      const inWhy = art.whyNeeded.toLowerCase().includes(q);
      const inWhat = art.whatIsIt.toLowerCase().includes(q);
      const inSteps = art.steps.some(s => s.toLowerCase().includes(q));
      const inTags = art.tags.some(t => t.toLowerCase().includes(q));
      return inTitle || inWhy || inWhat || inSteps || inTags;
    });
  }, [articles, categories, selectedCategoryId, roleFilter, searchQuery]);

  // Next and Previous articles in current category for pagination
  const adjacentArticles = useMemo(() => {
    if (!activeArticle) return { prev: null, next: null };
    const list = articles.filter(a => a.categoryId === activeArticle.categoryId || selectedCategoryId === 'all');
    const idx = list.findIndex(a => a.id === activeArticle.id);
    return {
      prev: idx > 0 ? list[idx - 1] : null,
      next: idx >= 0 && idx < list.length - 1 ? list[idx + 1] : null,
    };
  }, [articles, activeArticle, selectedCategoryId]);

  // Safe navigation to admin sections (works both inside admin and in standalone new tab)
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

  // Helper to parse step text and make phrases like "Перейдите в раздел «Пользователи»" clickable!
  const renderInteractiveStepText = (text: string) => {
    const regex = /(Перейдите в раздел|перейдите в раздел|в раздел|раздел|вкладка|вкладку)\s*«([^»]+)»/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
      const matchStart = match.index;
      const matchEnd = regex.lastIndex;
      const prefixText = match[1];
      const targetNameRaw = match[2];
      const targetKey = targetNameRaw.trim().toLowerCase();
      const target = SECTION_TARGETS[targetKey];

      if (matchStart > lastIndex) {
        parts.push(text.substring(lastIndex, matchStart));
      }

      if (target) {
        parts.push(
          <span key={`interactive-${matchStart}`} className="inline-flex items-center mx-1 my-0.5 align-middle">
            <span className="text-slate-600 font-medium mr-1">{prefixText}</span>
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                handleNavigateToSection(target.page, target.tab);
              }}
              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 hover:text-sky-900 border border-sky-200/80 font-semibold text-xs transition-all shadow-2xs hover:scale-102 active:scale-98"
              title={`Открыть раздел «${target.name}» в основном окне админ-панели`}
            >
              <span>«{target.name}»</span>
              <ExternalLink className="w-3 h-3 text-sky-600" />
            </button>
          </span>
        );
      } else {
        parts.push(text.substring(matchStart, matchEnd));
      }

      lastIndex = matchEnd;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts;
  };

  // Open Create Article Drawer
  const handleOpenCreateArticle = () => {
    if (!isOwner) return;
    setEditingArticle({
      title: '',
      categoryId: selectedCategoryId !== 'all' ? selectedCategoryId : (categories[0]?.id || 'start'),
      targetRole: 'all',
      whyNeeded: '',
      whatIsIt: '',
      steps: [''],
      troubleshooting: [''],
      mockupType: 'none',
      tags: [],
      updatedAt: new Date().toISOString().split('T')[0],
      author: user?.full_name || 'Владелец сети',
    });
    setIsCreatingNew(true);
    setIsEditDrawerOpen(true);
  };

  // Open Edit Article Drawer
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

  // Save Article to Server
  const handleSaveArticle = async () => {
    if (!isOwner || !editingArticle) return;
    if (!editingArticle.title?.trim()) {
      addToast({ type: 'warning', title: 'Укажите вопрос / заголовок статьи' });
      return;
    }
    if (!editingArticle.categoryId) {
      addToast({ type: 'warning', title: 'Выберите категорию' });
      return;
    }

    try {
      if (isCreatingNew) {
        const created = await api.createKnowledgeArticle(editingArticle);
        setArticles(prev => [created, ...prev]);
        setActiveArticleId(created.id);
        addToast({ type: 'success', title: 'Вопрос и ответ сохранены на сервере', message: `«${created.title}» добавлена` });
      } else if (editingArticle.id) {
        const updated = await api.updateKnowledgeArticle(editingArticle.id, editingArticle);
        setArticles(prev => prev.map(a => (a.id === updated.id || a.slug === updated.id ? updated : a)));
        setActiveArticleId(updated.id);
        addToast({ type: 'success', title: 'Статья обновлена на сервере', message: `«${updated.title}» сохранена` });
      }
      setIsEditDrawerOpen(false);
      setEditingArticle(null);
    } catch {
      addToast({ type: 'error', title: 'Ошибка сохранения статьи' });
    }
  };

  // Delete Article from Server
  const handleConfirmDeleteArticle = async () => {
    if (!isOwner || !articleToDelete) return;
    try {
      await api.deleteKnowledgeArticle(articleToDelete.id);
      const nextList = articles.filter(a => a.id !== articleToDelete.id && a.slug !== articleToDelete.id);
      setArticles(nextList);
      if (activeArticleId === articleToDelete.id || activeArticleId === articleToDelete.slug) {
        setActiveArticleId(null);
      }
      addToast({ type: 'info', title: 'Вопрос удален с сервера' });
    } catch {
      addToast({ type: 'error', title: 'Не удалось удалить вопрос' });
    } finally {
      setArticleToDelete(null);
    }
  };

  // Open Create Category
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

  // Open Edit Category
  const handleOpenEditCategory = (cat: KnowledgeCategory, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!isOwner) return;
    setEditingCategory({ ...cat });
    setIsCategoryModalOpen(true);
  };

  // Save Category to Server
  const handleSaveCategory = async () => {
    if (!isOwner || !editingCategory?.name?.trim()) {
      addToast({ type: 'warning', title: 'Укажите название отдела' });
      return;
    }

    try {
      if (editingCategory.id) {
        const updated = await api.updateKnowledgeCategory(editingCategory.id, editingCategory);
        setCategories(prev => prev.map(c => (c.id === updated.id ? updated : c)));
        addToast({ type: 'success', title: 'Отдел обновлен на сервере' });
      } else {
        const created = await api.createKnowledgeCategory(editingCategory);
        setCategories(prev => [...prev, created]);
        setSelectedCategoryId(created.id);
        addToast({ type: 'success', title: 'Отдел создан на сервере' });
      }
      setIsCategoryModalOpen(false);
      setEditingCategory(null);
    } catch {
      addToast({ type: 'error', title: 'Ошибка сохранения отдела' });
    }
  };

  // Delete Category
  const handleConfirmDeleteCategory = async () => {
    if (!isOwner || !categoryToDelete) return;
    try {
      await api.deleteKnowledgeCategory(categoryToDelete.id);
      setCategories(prev => prev.filter(c => c.id !== categoryToDelete.id));
      if (selectedCategoryId === categoryToDelete.id) {
        setSelectedCategoryId('all');
      }
      addToast({ type: 'info', title: 'Отдел удален' });
    } catch {
      addToast({ type: 'error', title: 'Не удалось удалить отдел' });
    } finally {
      setCategoryToDelete(null);
    }
  };

  // Role Badge Component (Linear clean style)
  const getRoleBadge = (role: KnowledgeArticle['targetRole']) => {
    switch (role) {
      case 'barista':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            Бариста
          </span>
        );
      case 'manager':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
            Управляющий
          </span>
        );
      case 'owner':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-purple-50 text-purple-800 border border-purple-200">
            Только Owner
          </span>
        );
      case 'admin':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            Администратор
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            Для всех
          </span>
        );
    }
  };

  // Render Visual Mockup in Hero Section (Linear Image 2 style)
  const renderHeroVisualMockup = (article: KnowledgeArticle) => {
    const type = article.mockupType;

    if (type === 'mobile-order') {
      return (
        <div className="w-full max-w-[320px] rounded-[32px] border-4 border-slate-800 bg-white p-3 shadow-xl text-slate-900 mx-auto">
          <div className="w-20 h-3.5 bg-slate-800 rounded-full mx-auto mb-3" />
          <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-3">
            <div className="h-32 rounded-xl bg-gradient-to-br from-amber-100 to-amber-200 flex items-center justify-center relative overflow-hidden border border-amber-300/40">
              <Coffee className="w-14 h-14 text-amber-700/80" />
              <span className="absolute bottom-2 right-2 bg-slate-900/85 px-2 py-0.5 rounded text-[10px] font-bold text-white">
                350 мл
              </span>
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-900">Раф Цитрусовый</h4>
              <p className="text-[11px] text-slate-500">Эспрессо, сливки 10%, натуральная цедра апельсина</p>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-slate-200">
              <div>
                <span className="text-base font-extrabold text-slate-900">320 ₽</span>
                <span className="text-[10px] text-emerald-600 font-semibold block">+ 15 бонусов</span>
              </div>
              <button
                type="button"
                onClick={() => handleNavigateToSection('menu', 'products')}
                className="px-3.5 py-1.5 rounded-lg bg-slate-900 text-white font-bold text-xs hover:bg-slate-800"
              >
                В корзину
              </button>
            </div>
          </div>
          <p className="text-center text-[10px] text-slate-400 mt-2">Витрина в мобильном приложении гостя</p>
        </div>
      );
    }

    if (type === 'order-card') {
      return (
        <div className="w-full max-w-[380px] rounded-2xl border border-slate-200 bg-white p-5 shadow-lg text-slate-900 mx-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-extrabold text-sm text-slate-900">Заказ #1048</span>
            </div>
            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
              Ожидает бариста
            </span>
          </div>
          <div className="py-3 space-y-2 text-xs">
            <div className="flex justify-between items-center text-slate-700">
              <span className="font-semibold">Капучино на овсяном x1</span>
              <span className="font-mono text-slate-500">280 ₽</span>
            </div>
            <div className="flex justify-between items-center text-slate-700">
              <span className="font-semibold">Круассан миндальный x1</span>
              <span className="font-mono text-slate-500">190 ₽</span>
            </div>
            <p className="text-[11px] text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-200">
              💬 Пожелание гостя: «Пожалуйста, без сахара и в свой термостакан»
            </p>
          </div>
          <div className="flex gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => handleNavigateToSection('orders')}
              className="flex-1 py-2 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-slate-800"
            >
              Взять в работу →
            </button>
            <button
              type="button"
              onClick={() => handleNavigateToSection('orders')}
              className="px-3 py-2 rounded-xl bg-slate-100 text-slate-700 font-bold text-xs hover:bg-slate-200"
            >
              Чек
            </button>
          </div>
          <p className="text-center text-[10px] text-slate-400 mt-2">Карточка в Live Desk бариста</p>
        </div>
      );
    }

    if (type === 'telegram-bot') {
      return (
        <div className="w-full max-w-[360px] rounded-2xl border border-slate-200 bg-white shadow-xl overflow-hidden text-slate-900 mx-auto">
          <div className="bg-[#24A1DE] text-white p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4" />
              <span className="font-bold text-xs">Happy Island Orders Bot</span>
            </div>
            <span className="text-[10px] opacity-80">online</span>
          </div>
          <div className="p-3 bg-slate-50 space-y-2 text-xs">
            <div className="bg-white p-3 rounded-xl rounded-tl-none border border-slate-200 shadow-2xs max-w-[85%]">
              <p className="font-bold text-slate-900">🔔 Новый заказ #1052!</p>
              <p className="text-slate-600 text-[11px] mt-1">Точка: Казань, Баумана</p>
              <p className="text-slate-600 text-[11px]">Флэт Уайт x1 (Альтернативное молоко)</p>
              <span className="text-[9px] text-slate-400 block mt-1 text-right">14:32</span>
            </div>
          </div>
          <div className="p-3 bg-white border-t border-slate-100 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">/ping /status</span>
            <button
              type="button"
              onClick={() => handleNavigateToSection('telegram')}
              className="px-3 py-1 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800"
            >
              Открыть чат
            </button>
          </div>
        </div>
      );
    }

    if (type === 'push-preview') {
      return (
        <div className="w-full max-w-[360px] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl text-slate-900 mx-auto space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-500">
            <Bell className="w-4 h-4 text-amber-500" />
            <span>Экран блокировки смартфона гостя</span>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 space-y-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-4 rounded bg-slate-900 text-[9px] font-bold text-white flex items-center justify-center">HI</span>
                <span className="text-xs font-bold text-slate-800">Happy Island Coffee</span>
              </div>
              <span className="text-[10px] text-slate-400">Сейчас</span>
            </div>
            <h5 className="font-bold text-xs text-slate-900">Счастливые часы в Happy Island! ☕</h5>
            <p className="text-[11px] text-slate-600">Скидка 20% на весь фильтр-кофе до 17:00. Заходите погреться и попробовать новый лот Эфиопии!</p>
          </div>
          <button
            type="button"
            onClick={() => handleNavigateToSection('notifications')}
            className="w-full py-2 bg-slate-900 text-white font-bold text-xs rounded-xl hover:bg-slate-800"
          >
            Создать рассылку →
          </button>
        </div>
      );
    }

    // Default Linear-style visual flowchart / workflow architecture
    return (
      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-6 shadow-sm mx-auto space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-800">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <span className="font-bold text-xs text-slate-900 block">Happy Island Workflow</span>
              <span className="text-[10px] text-slate-400">Синхронизация в реальном времени</span>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            ● Активно
          </span>
        </div>

        <div className="space-y-3 py-1">
          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="w-6 h-6 rounded-full bg-slate-900 text-white font-bold text-[11px] flex items-center justify-center shrink-0">
              1
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-900 truncate">Админ-панель Happy Island</p>
              <p className="text-[11px] text-slate-500 truncate">Ввод параметров и подтверждение действия</p>
            </div>
          </div>

          <div className="flex justify-center text-slate-300">
            <ChevronRight className="w-4 h-4 rotate-90" />
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="w-6 h-6 rounded-full bg-sky-600 text-white font-bold text-[11px] flex items-center justify-center shrink-0">
              2
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-900 truncate">Серверный API & PostgreSQL</p>
              <p className="text-[11px] text-slate-500 truncate">Мгновенная запись и аудит изменений</p>
            </div>
          </div>

          <div className="flex justify-center text-slate-300">
            <ChevronRight className="w-4 h-4 rotate-90" />
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80">
            <div className="w-6 h-6 rounded-full bg-emerald-600 text-white font-bold text-[11px] flex items-center justify-center shrink-0">
              3
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-900 truncate">Мобильное приложение гостя / Бот</p>
              <p className="text-[11px] text-slate-500 truncate">Обновление витрины и статуса без перезагрузки</p>
            </div>
          </div>
        </div>

        <p className="text-center text-[10px] text-slate-400">
          Сквозной процесс регламента в экосистеме сети
        </p>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-white text-slate-900 flex flex-col font-sans selection:bg-sky-100 selection:text-sky-900">
      {/* LINEAR-STYLE TOP NAVBAR */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Left: Brand & Mode */}
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() => {
                setActiveArticleId(null);
                setSelectedCategoryId('all');
                setSearchQuery('');
              }}
              className="flex items-center gap-2.5 hover:opacity-80 transition-opacity text-left group"
            >
              <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center shadow-2xs group-hover:scale-105 transition-transform">
                <Coffee className="w-4 h-4 text-brand-lime" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm tracking-tight text-slate-900">Happy Island</span>
                <span className="text-slate-300 font-light">/</span>
                <span className="font-semibold text-sm text-slate-600">База знаний</span>
              </div>
            </button>
            <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
              Светлая тема
            </span>
          </div>

          {/* Center: Search Bar with ⌘K */}
          <div className="flex-1 max-w-md relative hidden md:block">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={e => {
                setSearchQuery(e.target.value);
                if (activeArticleId !== null && e.target.value.trim()) {
                  setActiveArticleId(null);
                }
              }}
              placeholder="Поиск по вопросам и ответам..."
              className="w-full pl-9 pr-14 py-2 bg-slate-50 hover:bg-slate-100/70 focus:bg-white border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-all"
            />
            <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono font-medium text-slate-400 bg-white border border-slate-200 rounded shadow-2xs">
              ⌘K
            </kbd>
          </div>

          {/* Right: Owner Controls & User Role */}
          <div className="flex items-center gap-2.5 shrink-0">
            {isOwner && (
              <>
                <button
                  type="button"
                  onClick={handleOpenCreateArticle}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 text-xs font-bold transition-all shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Новый вопрос</span>
                </button>
                <button
                  type="button"
                  onClick={handleOpenCreateCategory}
                  className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all border border-slate-200"
                >
                  <FolderPlus className="w-3.5 h-3.5" />
                  <span>Отдел</span>
                </button>
              </>
            )}

            {/* Role indicator */}
            <div className="hidden sm:flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <span className="text-[11px] font-semibold text-slate-500">
                {user?.role === 'owner' ? '👑 Owner' : user?.full_name || 'Сотрудник'}
              </span>
            </div>
          </div>
        </div>

        {/* Mobile Search Bar */}
        <div className="mt-3 md:hidden relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value);
              if (activeArticleId !== null && e.target.value.trim()) {
                setActiveArticleId(null);
              }
            }}
            placeholder="Поиск по вопросам..."
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
          />
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <div className="max-w-7xl mx-auto w-full px-4 sm:px-8 py-8 flex-1 flex flex-col">
        {/* ========================================================================= */}
        {/* VIEW 1: DIRECTORY / CATALOG GRID OF QUESTIONS (Image 1 Style)             */}
        {/* ========================================================================= */}
        {activeArticleId === null ? (
          <div className="flex flex-col lg:flex-row gap-8 flex-1">
            {/* Left Sidebar: Categories Navigation */}
            <aside className="w-full lg:w-64 shrink-0 space-y-6">
              <div>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider px-3 mb-2">
                  Отделы базы знаний
                </h3>
                <nav className="space-y-1">
                  <button
                    type="button"
                    onClick={() => setSelectedCategoryId('all')}
                    className={cn(
                      'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all text-left',
                      selectedCategoryId === 'all'
                        ? 'bg-slate-100 text-slate-900 shadow-2xs font-bold'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    )}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                      <span className="truncate">★ Все вопросы</span>
                    </div>
                    <span className="text-[11px] font-mono font-medium text-slate-400">
                      {articles.length}
                    </span>
                  </button>

                  {categories.map(cat => {
                    const count = articles.filter(a => a.categoryId === cat.id || a.categoryId === cat.slug).length;
                    const isActive = selectedCategoryId === cat.id || selectedCategoryId === cat.slug;
                    return (
                      <div key={cat.id} className="group/item relative flex items-center">
                        <button
                          type="button"
                          onClick={() => setSelectedCategoryId(cat.id)}
                          className={cn(
                            'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-all text-left pr-8',
                            isActive
                              ? 'bg-slate-100 text-slate-900 font-bold shadow-2xs'
                              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 font-medium'
                          )}
                        >
                          <div className="flex items-center gap-2.5 truncate">
                            <span className="text-slate-500 shrink-0">
                              {CATEGORY_ICONS[cat.iconName] || <BookOpen className="w-4 h-4" />}
                            </span>
                            <span className="truncate">{cat.name}</span>
                          </div>
                          <span className="text-[11px] font-mono text-slate-400">
                            {count}
                          </span>
                        </button>

                        {isOwner && (
                          <button
                            type="button"
                            onClick={(e) => handleOpenEditCategory(cat, e)}
                            className="absolute right-1.5 opacity-0 group-hover/item:opacity-100 p-1 text-slate-400 hover:text-slate-800 transition-opacity"
                            title="Редактировать отдел"
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </nav>
              </div>

              {/* Owner add department button */}
              {isOwner && (
                <div className="pt-2 px-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={handleOpenCreateCategory}
                    className="w-full py-2 px-3 rounded-xl border border-dashed border-slate-300 text-slate-600 hover:text-slate-900 hover:border-slate-400 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Добавить отдел</span>
                  </button>
                </div>
              )}

              {/* Role filter */}
              <div className="pt-4 border-t border-slate-100 px-3">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Фильтр по роли
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {(['all', 'barista', 'manager', 'owner', 'admin'] as const).map(role => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setRoleFilter(role)}
                      className={cn(
                        'px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all',
                        roleFilter === role
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      )}
                    >
                      {role === 'all' && 'Все'}
                      {role === 'barista' && 'Бариста'}
                      {role === 'manager' && 'Управляющий'}
                      {role === 'owner' && 'Owner'}
                      {role === 'admin' && 'Админ'}
                    </button>
                  ))}
                </div>
              </div>
            </aside>

            {/* Main Area: Questions Directory Grid */}
            <main className="flex-1 min-w-0">
              {/* Category Header */}
              <div className="mb-6 pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
                    {selectedCategoryId === 'all'
                      ? 'Ответы на вопросы'
                      : categories.find(c => c.id === selectedCategoryId || c.slug === selectedCategoryId)?.name || 'Раздел базы знаний'}
                  </h1>
                  <p className="text-xs sm:text-sm text-slate-500 mt-1">
                    Справочник регламентов, инструкций и ответов на частые вопросы по админ-панели и кофейням Happy Island
                  </p>
                </div>

                <div className="text-xs font-medium text-slate-400">
                  Найдено вопросов: <span className="font-bold text-slate-700">{filteredArticles.length}</span>
                </div>
              </div>

              {/* Question Cards Grid (Linear Integrations Card Grid Style) */}
              {filteredArticles.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {filteredArticles.map(art => {
                    const category = categories.find(c => c.id === art.categoryId || c.slug === art.categoryId);
                    return (
                      <div
                        key={art.id}
                        onClick={() => {
                          setActiveArticleId(art.id);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }}
                        className="group relative bg-white border border-slate-200/90 hover:border-slate-400/90 rounded-2xl p-5 transition-all duration-200 hover:shadow-md cursor-pointer flex flex-col justify-between"
                      >
                        <div>
                          {/* Card Top: Icon & Role Badge */}
                          <div className="flex items-start justify-between gap-3 mb-3">
                            <div className="w-11 h-11 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-800 group-hover:scale-105 transition-transform shrink-0">
                              {CATEGORY_ICONS[category?.iconName || 'BookOpen'] || <BookOpen className="w-5 h-5" />}
                            </div>
                            <div className="shrink-0">
                              {getRoleBadge(art.targetRole)}
                            </div>
                          </div>

                          {/* Card Title (The Question) */}
                          <h3 className="font-bold text-sm sm:text-base text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-2 leading-snug">
                            {art.title}
                          </h3>

                          {/* Subtitle */}
                          <p className="text-[11px] text-slate-400 font-medium mt-1 flex items-center gap-1">
                            <span>Happy Island Docs</span>
                            <span>•</span>
                            <span className="truncate">{category?.name || 'База знаний'}</span>
                          </p>

                          {/* Short excerpt / answer summary */}
                          <p className="text-xs text-slate-600 mt-2.5 line-clamp-3 leading-relaxed">
                            {art.whatIsIt || art.whyNeeded}
                          </p>
                        </div>

                        {/* Card Bottom: Tags & Read Answer link */}
                        <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1 overflow-hidden">
                            {art.tags.slice(0, 2).map(tag => (
                              <span
                                key={tag}
                                className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 truncate"
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>

                          <span className="text-xs font-bold text-slate-800 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all inline-flex items-center gap-1 shrink-0">
                            Ответ <ArrowRight className="w-3.5 h-3.5" />
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-16 px-4 bg-slate-50/60 rounded-2xl border border-slate-200/80">
                  <HelpCircle className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                  <h3 className="text-base font-bold text-slate-800">Вопросов не найдено</h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                    Попробуйте изменить поисковый запрос или выбрать другой отдел в левой панели.
                  </p>
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="mt-4 px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold"
                    >
                      Сбросить поиск
                    </button>
                  )}
                </div>
              )}
            </main>
          </div>
        ) : (
          /* ========================================================================= */
          /* VIEW 2: QUESTION DETAIL VIEW (Image 2 & 3 Style)                          */
          /* ========================================================================= */
          activeArticle && (
            <div className="max-w-5xl mx-auto w-full space-y-8 animate-fadeIn">
              {/* Top Navigation & Breadcrumbs */}
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
                <button
                  type="button"
                  onClick={() => setActiveArticleId(null)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Все вопросы</span>
                </button>

                <div className="flex items-center gap-1.5 text-slate-400 font-medium">
                  <span
                    onClick={() => {
                      setActiveArticleId(null);
                      setSelectedCategoryId('all');
                    }}
                    className="hover:text-slate-900 cursor-pointer"
                  >
                    База знаний
                  </span>
                  <span>/</span>
                  <span
                    onClick={() => {
                      setActiveArticleId(null);
                      if (activeCategory) setSelectedCategoryId(activeCategory.id);
                    }}
                    className="hover:text-slate-900 cursor-pointer"
                  >
                    {activeCategory?.name || 'Отдел'}
                  </span>
                  <span>/</span>
                  <span className="text-slate-800 font-bold truncate max-w-xs">{activeArticle.title}</span>
                </div>
              </div>

              {/* Big Expressive Question Headline (Linear Image 2) */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  {getRoleBadge(activeArticle.targetRole)}
                  <span className="text-xs text-slate-400 font-medium">
                    Обновлено: {activeArticle.updatedAt || '2026-09-25'}
                  </span>
                </div>
                <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 leading-tight">
                  {activeArticle.title}
                </h1>
              </div>

              {/* TWO-COLUMN HERO SECTION (Linear Image 2) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
                {/* Left Column: Visual Mockup / Illustration (65%) */}
                <div className="lg:col-span-8 rounded-2xl border border-slate-200 bg-slate-50/60 p-6 flex flex-col items-center justify-center min-h-[360px] shadow-2xs relative">
                  {renderHeroVisualMockup(activeArticle)}
                </div>

                {/* Right Column: Metadata Panel Card (35%) (Linear "Add to Linear" Card Style) */}
                <div className="lg:col-span-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between space-y-6">
                  <div>
                    {/* Header: Icon & App Title */}
                    <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
                      <div className="w-12 h-12 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-800 shrink-0">
                        {CATEGORY_ICONS[activeCategory?.iconName || 'BookOpen'] || <BookOpen className="w-6 h-6" />}
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-extrabold text-sm text-slate-900 truncate">
                          {activeCategory?.name || 'Happy Island'}
                        </h4>
                        <p className="text-[11px] text-slate-400 font-medium flex items-center gap-1">
                          <span>Happy Island Docs</span>
                          <Check className="w-3 h-3 text-emerald-600" />
                        </p>
                      </div>
                    </div>

                    {/* Metadata Table (Linear Details) */}
                    <dl className="mt-4 space-y-3 text-xs">
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Отдел</dt>
                        <dd className="font-semibold text-slate-800">{activeCategory?.name || 'Общий'}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Кому доступно</dt>
                        <dd>{getRoleBadge(activeArticle.targetRole)}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Раздел в админке</dt>
                        <dd className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                          {activeArticle.quickAction?.page || 'dashboard'}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Синхронизация</dt>
                        <dd className="font-medium text-emerald-700 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          Серверная БД
                        </dd>
                      </div>
                    </dl>
                  </div>

                  {/* Primary Action Button (Linear "Add to Linear" Style) */}
                  <div className="space-y-2 pt-4 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => {
                        const targetPage = activeArticle.quickAction?.page || 'orders';
                        const targetTab = activeArticle.quickAction?.tab;
                        handleNavigateToSection(targetPage, targetTab);
                      }}
                      className="w-full py-3 px-4 rounded-full bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs sm:text-sm transition-all shadow-sm flex items-center justify-center gap-2 group"
                    >
                      <span>{activeArticle.quickAction?.label || 'Перейти к разделу'}</span>
                      <ExternalLink className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                    </button>

                    {/* Owner Management Buttons */}
                    {isOwner && (
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => handleOpenEditArticle(activeArticle)}
                          className="flex-1 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs transition-colors flex items-center justify-center gap-1.5"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Изменить</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setArticleToDelete(activeArticle)}
                          className="px-3 py-2 rounded-xl text-red-600 hover:bg-red-50 font-semibold text-xs transition-colors flex items-center justify-center gap-1"
                          title="Удалить вопрос"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* ===================================================================== */}
              {/* CONTENT BODY (Linear Image 3 Style)                                   */}
              {/* ===================================================================== */}
              <div className="pt-6 space-y-10 max-w-4xl">
                {/* 1. Зачем это нужно? */}
                <section className="space-y-2">
                  <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                    <span>📌 Зачем это нужно?</span>
                  </h2>
                  <p className="text-slate-700 leading-relaxed text-sm sm:text-base">
                    {activeArticle.whyNeeded}
                  </p>
                </section>

                {/* 2. Что это такое? */}
                <section className="space-y-2">
                  <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                    <span>💡 Что это такое?</span>
                  </h2>
                  <p className="text-slate-700 leading-relaxed text-sm sm:text-base">
                    {activeArticle.whatIsIt}
                  </p>
                </section>

                {/* 3. Пошаговая инструкция (Как сделать?) */}
                <section className="space-y-4">
                  <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                    <span>📋 Пошаговый ответ (Как сделать?)</span>
                  </h2>
                  <div className="space-y-3">
                    {activeArticle.steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3.5 p-4 rounded-xl border border-slate-200/90 bg-white hover:border-slate-300 transition-colors shadow-2xs"
                      >
                        <div className="w-6 h-6 rounded-full bg-slate-900 text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                          {idx + 1}
                        </div>
                        <div className="text-slate-800 text-xs sm:text-sm leading-relaxed">
                          {renderInteractiveStepText(step)}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 4. Частые ошибки и вопросы (Troubleshooting) */}
                {activeArticle.troubleshooting && activeArticle.troubleshooting.length > 0 && (
                  <section className="space-y-3">
                    <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                      <span>⚠️ Частые вопросы и ошибки (FAQ)</span>
                    </h2>
                    <div className="space-y-2.5">
                      {activeArticle.troubleshooting.map((tr, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 p-3.5 rounded-xl border border-amber-200/80 bg-amber-50/40 text-slate-800 text-xs sm:text-sm leading-relaxed"
                        >
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                          <div className="text-slate-800">
                            {renderInteractiveStepText(tr)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Tags */}
                {activeArticle.tags && activeArticle.tags.length > 0 && (
                  <div className="pt-4 border-t border-slate-100 flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-slate-400">Теги:</span>
                    {activeArticle.tags.map(tag => (
                      <span
                        key={tag}
                        className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200/60"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Pagination: Prev / Next Question */}
                <div className="pt-8 border-t border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {adjacentArticles.prev ? (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveArticleId(adjacentArticles.prev!.id);
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                      }}
                      className="p-4 rounded-2xl border border-slate-200 hover:border-slate-400 text-left transition-all hover:shadow-2xs group"
                    >
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                        <ArrowLeft className="w-3 h-3 group-hover:-translate-x-1 transition-transform" />
                        Предыдущий вопрос
                      </span>
                      <h4 className="font-bold text-sm text-slate-900 mt-1 line-clamp-1">
                        {adjacentArticles.prev.title}
                      </h4>
                    </button>
                  ) : <div />}

                  {adjacentArticles.next && (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveArticleId(adjacentArticles.next!.id);
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                      }}
                      className="p-4 rounded-2xl border border-slate-200 hover:border-slate-400 text-right transition-all hover:shadow-2xs group sm:ml-auto w-full"
                    >
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center justify-end gap-1">
                        Следующий вопрос
                        <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                      </span>
                      <h4 className="font-bold text-sm text-slate-900 mt-1 line-clamp-1">
                        {adjacentArticles.next.title}
                      </h4>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        )}
      </div>

      {/* ========================================================================= */}
      {/* OWNER MODALS & DRAWERS                                                    */}
      {/* ========================================================================= */}

      {/* CREATE / EDIT ARTICLE DRAWER */}
      {isOwner && (
        <Drawer
          isOpen={isEditDrawerOpen}
          onClose={() => setIsEditDrawerOpen(false)}
          title={isCreatingNew ? 'Добавить вопрос и ответ' : 'Редактировать статью'}
          width="lg"
          footer={
            <div className="flex items-center justify-between w-full">
              <span className="text-xs text-slate-400 font-medium">Сохранение в базу данных PostgreSQL</span>
              <div className="flex items-center gap-2">
                <Button variant="ghost" onClick={() => setIsEditDrawerOpen(false)}>
                  Отмена
                </Button>
                <Button variant="primary" onClick={handleSaveArticle} className="bg-slate-900 text-white font-bold hover:bg-slate-800">
                  Сохранить ответ
                </Button>
              </div>
            </div>
          }
        >
          {editingArticle && (
            <div className="space-y-5 text-sm">
              <Input
                label="Вопрос или тема статьи"
                value={editingArticle.title || ''}
                onChange={e => setEditingArticle({ ...editingArticle, title: e.target.value })}
                placeholder="Например: Как принять и выдать заказ в Live Desk?"
                required
              />

              <div className="grid grid-cols-2 gap-4">
                <Select
                  label="Отдел базы знаний"
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
                  Зачем это нужно? (Обоснование процесса)
                </label>
                <textarea
                  rows={3}
                  value={editingArticle.whyNeeded || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whyNeeded: e.target.value })}
                  placeholder="Объясните сотрудникам бизнес-смысл..."
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-xs text-slate-900 focus:border-slate-800 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Что это такое? (Краткая суть)
                </label>
                <textarea
                  rows={2}
                  value={editingArticle.whatIsIt || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whatIsIt: e.target.value })}
                  placeholder="Опишите инструмент или функцию..."
                  className="w-full p-2.5 rounded-xl border border-slate-300 text-xs text-slate-900 focus:border-slate-800 outline-none"
                />
              </div>

              {/* Steps */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold text-slate-800">
                    Шаги по выполнению (Как сделать?)
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditingArticle({
                      ...editingArticle,
                      steps: [...(editingArticle.steps || []), ''],
                    })}
                    className="text-xs font-bold text-sky-700 hover:text-sky-900 flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> Добавить шаг
                  </button>
                </div>
                <div className="space-y-2">
                  {(editingArticle.steps || []).map((step, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-800 text-[10px] font-bold flex items-center justify-center shrink-0">
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
                        className="flex-1 p-2 rounded-lg border border-slate-300 text-xs font-medium focus:border-slate-800 outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const next = (editingArticle.steps || []).filter((_, i) => i !== idx);
                          setEditingArticle({ ...editingArticle, steps: next.length ? next : [''] });
                        }}
                        className="p-1.5 text-slate-400 hover:text-red-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Visual Mockup type */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Интерактивный мокап интерфейса"
                  value={editingArticle.mockupType || 'none'}
                  onChange={e => setEditingArticle({ ...editingArticle, mockupType: e.target.value as any })}
                  options={[
                    { value: 'none', label: 'Стандартная схема (Workflow)' },
                    { value: 'order-card', label: 'Карточка заказа Live Desk' },
                    { value: 'mobile-order', label: 'Экран мобильного приложения' },
                    { value: 'telegram-bot', label: 'Сообщение Telegram-бота' },
                    { value: 'shift-card', label: 'Журнал смен' },
                    { value: 'push-preview', label: 'Push-уведомление гостю' },
                  ]}
                />

                <Select
                  label="Связанный раздел админки"
                  value={editingArticle.quickAction?.page || 'orders'}
                  onChange={e => {
                    const page = e.target.value as PageId;
                    setEditingArticle({
                      ...editingArticle,
                      quickAction: {
                        label: `Перейти в раздел «${page}»`,
                        page,
                      },
                    });
                  }}
                  options={[
                    { value: 'dashboard', label: 'Дашборд' },
                    { value: 'orders', label: 'Заказы (Live Desk)' },
                    { value: 'menu', label: 'Меню и товары' },
                    { value: 'users', label: 'Пользователи и клиенты' },
                    { value: 'shifts', label: 'Смены и персонал' },
                    { value: 'telegram', label: 'Telegram-бот' },
                    { value: 'notifications', label: 'Push-рассылки' },
                    { value: 'reviews', label: 'Отзывы клиентов' },
                    { value: 'settings', label: 'Настройки кофеен и сети' },
                    { value: 'logs', label: 'Журнал аудита' },
                  ]}
                />
              </div>

              {/* Tags */}
              <Input
                label="Теги (через запятую)"
                value={(editingArticle.tags || []).join(', ')}
                onChange={e => setEditingArticle({
                  ...editingArticle,
                  tags: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                })}
                placeholder="пользователи, бонусы, баланс, поиск"
              />
            </div>
          )}
        </Drawer>
      )}

      {/* CREATE / EDIT CATEGORY MODAL */}
      {isOwner && (
        <Modal
          isOpen={isCategoryModalOpen}
          onClose={() => setIsCategoryModalOpen(false)}
          title={editingCategory?.id ? 'Редактирование отдела' : 'Создание нового отдела (категории)'}
        >
          {editingCategory && (
            <div className="space-y-4">
              <Input
                label="Название отдела/категории"
                value={editingCategory.name || ''}
                onChange={e => setEditingCategory({ ...editingCategory, name: e.target.value })}
                placeholder="Например: Стандарты качества и сервис"
                required
              />

              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Иконка отдела"
                  value={editingCategory.iconName || 'BookOpen'}
                  onChange={e => setEditingCategory({ ...editingCategory, iconName: e.target.value })}
                  options={[
                    { value: 'BookOpen', label: 'Книга (BookOpen)' },
                    { value: 'ShoppingBag', label: 'Сумка/Заказ (ShoppingBag)' },
                    { value: 'UtensilsCrossed', label: 'Меню (UtensilsCrossed)' },
                    { value: 'Clock', label: 'Смены/Часы (Clock)' },
                    { value: 'Send', label: 'Telegram/Самолетик (Send)' },
                    { value: 'Bell', label: 'Колокольчик (Bell)' },
                    { value: 'Star', label: 'Звезда/Отзывы (Star)' },
                    { value: 'Users', label: 'Пользователи (Users)' },
                    { value: 'Store', label: 'Кофейня/Магазин (Store)' },
                    { value: 'ShieldCheck', label: 'Безопасность (ShieldCheck)' },
                    { value: 'HelpCircle', label: 'Вопрос/FAQ (HelpCircle)' },
                    { value: 'Coffee', label: 'Чашка кофе (Coffee)' },
                  ]}
                />

                <Input
                  label="Порядок сортировки"
                  type="number"
                  value={String(editingCategory.order || 0)}
                  onChange={e => setEditingCategory({ ...editingCategory, order: Number(e.target.value) })}
                />
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                {editingCategory.id ? (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      setIsCategoryModalOpen(false);
                      setCategoryToDelete(editingCategory as KnowledgeCategory);
                    }}
                  >
                    Удалить отдел
                  </Button>
                ) : <div />}

                <div className="flex items-center gap-2">
                  <Button variant="ghost" onClick={() => setIsCategoryModalOpen(false)}>
                    Отмена
                  </Button>
                  <Button variant="primary" onClick={handleSaveCategory} className="bg-slate-900 text-white font-bold hover:bg-slate-800">
                    Сохранить на сервере
                  </Button>
                </div>
              </div>
            </div>
          )}
        </Modal>
      )}

      {/* DELETE ARTICLE MODAL */}
      {isOwner && (
        <Modal
          isOpen={Boolean(articleToDelete)}
          onClose={() => setArticleToDelete(null)}
          title="Удаление вопроса / статьи"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Вы действительно хотите удалить вопрос:</p>
            <p className="font-extrabold text-slate-900">«{articleToDelete?.title}»?</p>
            <p className="text-xs text-slate-500">Вопрос будет удален из базы данных на сервере для всех пользователей.</p>
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="ghost" onClick={() => setArticleToDelete(null)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleConfirmDeleteArticle}>
                Удалить
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* DELETE CATEGORY MODAL */}
      {isOwner && (
        <Modal
          isOpen={Boolean(categoryToDelete)}
          onClose={() => setCategoryToDelete(null)}
          title="Удаление отдела базы знаний"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Вы уверены, что хотите удалить отдел:</p>
            <p className="font-extrabold text-slate-900">«{categoryToDelete?.name}»?</p>
            <p className="text-xs text-red-600 font-semibold">Все статьи, входящие в этот отдел, также будут удалены!</p>
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="ghost" onClick={() => setCategoryToDelete(null)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleConfirmDeleteCategory}>
                Да, удалить отдел
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
