import React, { useState, useEffect, useMemo } from 'react';
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
import { Badge } from '../components/ui/Badge';
import { cn } from '../utils/cn';
import {
  BookOpen, Search, Plus, Edit3, Trash2, ChevronDown,
  ExternalLink, ArrowRight, ShieldCheck, ShoppingBag, UtensilsCrossed,
  Clock, Send, Bell, Star, Users, Store, HelpCircle, CheckCircle2,
  AlertTriangle, RotateCcw, Download, Coffee, Home, Sparkles, FolderPlus,
  Compass, LayoutGrid, Check
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

// Section mapping for interactive inline buttons in text
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

  // Only OWNER or SUPERUSER can edit categories and articles
  const isOwner = Boolean(user?.is_superuser || user?.role === 'owner');

  // Categories & Articles state loaded from server API
  const [categories, setCategories] = useState<KnowledgeCategory[]>(() => getStoredCategories());
  const [articles, setArticles] = useState<KnowledgeArticle[]>(() => getStoredArticles());
  const [isLoadingData, setIsLoadingData] = useState(false);

  // Selected article
  const [selectedArticleId, setSelectedArticleId] = useState<string>(() => {
    const list = getStoredArticles();
    return list[0]?.id || '';
  });

  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({
    start: true,
    orders: true,
    menu: true,
    staff: true,
    telegram: true,
    marketing: true,
    reviews: true,
    users: true,
    settings: true,
    security: true,
    troubleshooting: true,
  });

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
        if (!selectedArticleId || !serverArts.some(a => a.id === selectedArticleId)) {
          setSelectedArticleId(serverArts[0].id);
        }
      }
    } catch {
      // Gracefully uses local storage fallback
    } finally {
      setIsLoadingData(false);
    }
  };

  const currentArticle = useMemo(() => {
    return articles.find(a => a.id === selectedArticleId || a.slug === selectedArticleId) || articles[0];
  }, [articles, selectedArticleId]);

  const currentCategory = useMemo(() => {
    if (!currentArticle) return null;
    return categories.find(c => c.id === currentArticle.categoryId || c.slug === currentArticle.categoryId) || null;
  }, [categories, currentArticle]);

  // Filtered articles list
  const filteredArticles = useMemo(() => {
    return articles.filter(art => {
      if (roleFilter !== 'all' && art.targetRole !== 'all' && art.targetRole !== roleFilter) {
        return false;
      }
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      const inTitle = art.title.toLowerCase().includes(q);
      const inWhy = art.whyNeeded.toLowerCase().includes(q);
      const inWhat = art.whatIsIt.toLowerCase().includes(q);
      const inSteps = art.steps.some(s => s.toLowerCase().includes(q));
      const inTags = art.tags.some(t => t.toLowerCase().includes(q));
      return inTitle || inWhy || inWhat || inSteps || inTags;
    });
  }, [articles, searchQuery, roleFilter]);

  // Group by category
  const articlesByCategory = useMemo(() => {
    const map: Record<string, KnowledgeArticle[]> = {};
    categories.forEach(cat => {
      map[cat.id] = [];
    });
    filteredArticles.forEach(art => {
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
  }, [categories, filteredArticles]);

  const toggleCategory = (catId: string) => {
    setExpandedCategories(prev => ({
      ...prev,
      [catId]: !prev[catId],
    }));
  };

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
    // Regex matches: (Перейдите в раздел|раздел|вкладка|вкладку)\s*«([^»]+)»
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

      // Push text before match
      if (matchStart > lastIndex) {
        parts.push(text.substring(lastIndex, matchStart));
      }

      if (target) {
        parts.push(
          <span key={matchStart} className="inline-flex items-center gap-1.5 mx-1 align-baseline">
            <span>{prefixText}</span>
            <button
              type="button"
              onClick={() => handleNavigateToSection(target.page, target.tab)}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-bold bg-brand-dark text-brand-lime hover:bg-brand-dark/90 shadow-sm border border-brand-lime/30 transition-all hover:scale-105 active:scale-95 cursor-pointer"
              title={`Открыть раздел «${target.name}» в панели`}
            >
              <span>«{target.name}»</span>
              <ExternalLink className="w-3 h-3 text-brand-lime" />
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

    return parts.length > 0 ? parts : text;
  };

  // Open Edit Article
  const handleOpenEditArticle = (article: KnowledgeArticle) => {
    if (!isOwner) return;
    setEditingArticle({ ...article });
    setIsCreatingNew(false);
    setIsEditDrawerOpen(true);
  };

  // Open Create Article
  const handleOpenCreateArticle = (defaultCategoryId?: string) => {
    if (!isOwner) return;
    const catId = defaultCategoryId || categories[0]?.id || 'start';
    setEditingArticle({
      id: `art-${Date.now()}`,
      slug: `new-article-${Date.now()}`,
      categoryId: catId,
      title: '',
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

  // Save Article to Server
  const handleSaveArticle = async () => {
    if (!isOwner || !editingArticle) return;
    if (!editingArticle.title?.trim()) {
      addToast({ type: 'warning', title: 'Укажите заголовок статьи' });
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
        setSelectedArticleId(created.id);
        addToast({ type: 'success', title: 'Статья создана на сервере', message: `«${created.title}» сохранена` });
      } else if (editingArticle.id) {
        const updated = await api.updateKnowledgeArticle(editingArticle.id, editingArticle);
        setArticles(prev => prev.map(a => (a.id === updated.id || a.slug === updated.id ? updated : a)));
        setSelectedArticleId(updated.id);
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
      if (selectedArticleId === articleToDelete.id || selectedArticleId === articleToDelete.slug) {
        setSelectedArticleId(nextList[0]?.id || '');
      }
      addToast({ type: 'info', title: 'Статья удалена с сервера' });
    } catch {
      addToast({ type: 'error', title: 'Не удалось удалить статью' });
    } finally {
      setArticleToDelete(null);
    }
  };

  // Open Create Category / Department
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

  // Save Category / Department to Server
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
        setExpandedCategories(prev => ({ ...prev, [created.id]: true }));
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
      addToast({ type: 'info', title: 'Отдел удален' });
    } catch {
      addToast({ type: 'error', title: 'Не удалось удалить отдел' });
    } finally {
      setCategoryToDelete(null);
    }
  };

  const getRoleBadge = (role: KnowledgeArticle['targetRole']) => {
    switch (role) {
      case 'barista':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">👤 Бариста</span>;
      case 'manager':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-800 border border-blue-300">💼 Управляющий</span>;
      case 'owner':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 border border-purple-300">👑 Только Owner</span>;
      case 'admin':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">⚡ Администратор</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-300">🌐 Для всех ролей</span>;
    }
  };

  // Render Visual Mockup (Light theme styled)
  const renderVisualMockup = (type?: KnowledgeArticle['mockupType']) => {
    if (!type || type === 'none') return null;

    if (type === 'mobile-order') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[340px] rounded-[38px] border-4 border-slate-800 bg-white p-3 shadow-2xl text-slate-900">
            <div className="w-24 h-4 bg-slate-800 rounded-full mx-auto mb-3" />
            <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-3">
              <div className="h-36 rounded-xl bg-gradient-to-br from-amber-100 to-amber-200 flex items-center justify-center relative overflow-hidden border border-amber-300/40">
                <Coffee className="w-16 h-16 text-amber-700/80" />
                <span className="absolute bottom-2 right-2 bg-slate-900/80 px-2 py-0.5 rounded text-[10px] font-bold text-white">
                  350 мл
                </span>
              </div>
              <div>
                <h4 className="font-extrabold text-sm text-slate-900">Раф Цитрусовый</h4>
                <p className="text-[11px] text-slate-500">Эспрессо, сливки 10%, натуральная цедра апельсина</p>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-200">
                <div>
                  <span className="text-lg font-black text-slate-900">320 ₽</span>
                  <span className="text-[10px] text-emerald-600 font-semibold block">+ 15 бонусов</span>
                </div>
                <button
                  type="button"
                  onClick={() => handleNavigateToSection('menu', 'products')}
                  className="px-4 py-2 rounded-xl bg-brand-lime text-brand-dark font-extrabold text-xs shadow-sm hover:brightness-105"
                >
                  В корзину
                </button>
              </div>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-2">Вид позиции в мобильном приложении гостя</p>
          </div>
        </div>
      );
    }

    if (type === 'order-card') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-4 shadow-lg text-slate-900">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-brand-dark animate-pulse" />
                <span className="font-extrabold text-sm text-slate-900">Заказ #1048</span>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                Ожидает / Pending
              </span>
            </div>
            <div className="py-3 space-y-2 text-xs">
              <div className="flex justify-between text-slate-700">
                <span className="font-bold">Капучино Большой (400 мл)</span>
                <span className="font-black text-slate-900">280 ₽</span>
              </div>
              <div className="text-[11px] text-amber-700 pl-2 border-l-2 border-amber-400">
                • Банановое молоко (+60 ₽)<br />
                • Без сахара
              </div>
              <div className="pt-2 text-slate-500 flex items-center justify-between text-[11px]">
                <span>Гость: Александр (+7 917 ***)</span>
                <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">Оплачено онлайн</span>
              </div>
            </div>
            <div className="pt-3 border-t border-slate-100 flex gap-2">
              <button
                type="button"
                onClick={() => handleNavigateToSection('orders')}
                className="flex-1 py-2 rounded-xl bg-brand-dark text-white font-extrabold text-xs shadow-sm hover:bg-slate-800 transition-all flex items-center justify-center gap-1.5"
              >
                <span>В работу</span>
                <ArrowRight className="w-3.5 h-3.5 text-brand-lime" />
              </button>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-2">Карточка на Канбан-доске в Live Desk</p>
          </div>
        </div>
      );
    }

    if (type === 'telegram-bot') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[380px] rounded-2xl border border-sky-200 bg-sky-50/50 p-4 shadow-md text-slate-900 font-sans">
            <div className="flex items-center gap-2.5 pb-2.5 border-b border-sky-100">
              <div className="w-8 h-8 rounded-full bg-sky-500 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                🤖
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900">Happy Island Orders Bot</p>
                <span className="text-[10px] text-sky-600 font-semibold">бот для бариста</span>
              </div>
            </div>
            <div className="mt-3 bg-white p-3.5 rounded-xl border border-sky-200 shadow-sm space-y-2 text-xs">
              <p className="text-emerald-600 font-black">🔔 НОВЫЙ ЗАКАЗ #1048</p>
              <p className="text-slate-600">Точка: Баумана, 14</p>
              <div className="p-2 bg-slate-50 rounded-lg text-[11px] text-slate-800 border border-slate-200">
                1x Капучино Большой<br />
                🥛 Молоко: Банановое<br />
                🍬 Без сахара
              </div>
              <p className="text-right text-[10px] text-slate-400">14:32</p>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-2">Моментальное звуковое оповещение в Telegram</p>
          </div>
        </div>
      );
    }

    if (type === 'push-preview') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[380px] rounded-2xl border border-slate-200 bg-white p-4 shadow-lg text-slate-900">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-2xl bg-brand-lime flex items-center justify-center text-brand-dark font-black text-lg shrink-0 shadow-sm">
                ☕
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Happy Island</span>
                  <span className="text-[10px] text-slate-400">сейчас</span>
                </div>
                <h5 className="text-xs font-black text-slate-900 mt-0.5">Счастливые часы в Happy Island!</h5>
                <p className="text-xs text-slate-600 mt-1">
                  Скидка 20% на весь авторский кофе сегодня до 18:00! Ждем вас в гости ☕
                </p>
              </div>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-3">Вид пуш-уведомления на смартфоне гостя</p>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className={cn(
      'font-montserrat flex flex-col bg-[#F8FAFC] text-slate-900 select-text',
      isStandalone ? 'min-h-screen w-screen' : 'min-h-[calc(100vh-5rem)] rounded-2xl shadow-sm border border-slate-200'
    )}>
      {/* Top Docs Header: Clean Light Theme */}
      <header className="px-6 py-4 border-b border-slate-200 bg-white sticky top-0 z-20 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setSelectedArticleId(articles[0]?.id || '')}>
            <div className="w-9 h-9 rounded-xl bg-brand-lime flex items-center justify-center text-brand-dark font-black text-lg shadow-sm">
              ☕
            </div>
            <div>
              <span className="font-black text-base tracking-tight text-slate-900 flex items-center gap-2">
                HAPPY ISLAND <span className="text-sky-600 text-xs font-bold uppercase px-2 py-0.5 rounded bg-sky-50 border border-sky-200">Docs</span>
              </span>
              <span className="text-[10px] font-semibold text-slate-400 block -mt-0.5">База знаний и регламенты</span>
            </div>
          </div>
        </div>

        {/* Search bar */}
        <div className="flex-1 max-w-md relative min-w-[260px]">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Поиск по базе: сироп, отмена заказа, telegram, смена..."
            className="w-full pl-9 pr-4 py-2 rounded-xl text-xs font-medium border border-slate-200 bg-slate-50 text-slate-900 placeholder-slate-400 focus:bg-white focus:border-sky-500 focus:ring-2 focus:ring-sky-100 outline-none transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-700"
            >
              ✕
            </button>
          )}
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Role selector */}
          <select
            value={roleFilter}
            onChange={e => setRoleFilter(e.target.value as any)}
            className="px-3 py-1.5 rounded-xl text-xs font-bold border border-slate-200 bg-white text-slate-700 outline-none cursor-pointer hover:border-slate-300"
          >
            <option value="all">Все роли</option>
            <option value="barista">Бариста</option>
            <option value="manager">Управляющий</option>
            <option value="owner">Владелец (Owner)</option>
            <option value="admin">Администратор</option>
          </select>

          {/* Standalone helper button to open main admin */}
          {isStandalone && (
            <button
              type="button"
              onClick={() => handleNavigateToSection('dashboard')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition-colors"
              title="Открыть админ-панель кофейни"
            >
              <span>Админ-панель</span>
              <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
            </button>
          )}

          {/* OWNER-ONLY ACTIONS */}
          {isOwner && (
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleOpenCreateCategory}
                className="gap-1.5 text-xs py-1.5 px-3 bg-white border border-slate-300 text-slate-700 font-bold hover:bg-slate-50"
                title="Создать новый раздел/отдел на сервере"
              >
                <FolderPlus className="w-3.5 h-3.5 text-sky-600" />
                + Отдел
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={() => handleOpenCreateArticle(currentArticle?.categoryId)}
                className="gap-1.5 text-xs py-1.5 px-3 bg-brand-lime text-brand-dark font-black hover:brightness-105 shadow-sm"
                title="Создать новую статью на сервере"
              >
                <Plus className="w-3.5 h-3.5" />
                + Статья
              </Button>
            </div>
          )}
        </div>
      </header>

      {/* Main Docs Body: Left Tree + Right Reading Area */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 bg-white">
        {/* Left Navigation Tree */}
        <aside className="w-full md:w-80 shrink-0 border-r border-slate-200 p-4 overflow-y-auto max-h-[calc(100vh-5rem)] custom-scrollbar select-none bg-slate-50/70">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 px-2 mb-3 flex items-center justify-between">
            <span>Отделы и разделы</span>
            <span className="text-[10px] text-slate-500 font-bold bg-white px-2 py-0.5 rounded-full border border-slate-200">
              {filteredArticles.length} статей
            </span>
          </div>

          <div className="space-y-1">
            {categories.map(cat => {
              const catArticles = articlesByCategory[cat.id] || [];
              const isOpen = expandedCategories[cat.id] !== false;
              const hasActiveChild = catArticles.some(a => a.id === selectedArticleId || a.slug === selectedArticleId);

              if (catArticles.length === 0 && searchQuery) {
                return null;
              }

              return (
                <div key={cat.id} className="space-y-0.5">
                  <div
                    className={cn(
                      'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold transition-all group cursor-pointer',
                      hasActiveChild
                        ? 'text-sky-700 bg-sky-50/80 border border-sky-200/60 shadow-xs'
                        : 'text-slate-700 hover:text-slate-900 hover:bg-white'
                    )}
                    onClick={() => toggleCategory(cat.id)}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className={cn('shrink-0', hasActiveChild ? 'text-sky-600' : 'text-slate-400 group-hover:text-slate-600')}>
                        {CATEGORY_ICONS[cat.iconName] || <BookOpen className="w-4 h-4" />}
                      </span>
                      <span className="truncate">{cat.name}</span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {isOwner && (
                        <button
                          type="button"
                          onClick={(e) => handleOpenEditCategory(cat, e)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-slate-200 text-slate-500 transition-opacity"
                          title="Редактировать отдел"
                        >
                          <Edit3 className="w-3 h-3" />
                        </button>
                      )}
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-bold bg-slate-200/80 text-slate-600">
                        {catArticles.length}
                      </span>
                      <ChevronDown
                        className={cn(
                          'w-3.5 h-3.5 text-slate-400 transition-transform duration-200',
                          !isOpen && '-rotate-90'
                        )}
                      />
                    </div>
                  </div>

                  {/* Sub-articles under category */}
                  {isOpen && catArticles.length > 0 && (
                    <div className="pl-6 pr-1 py-0.5 space-y-0.5 border-l border-slate-200 ml-4 my-0.5">
                      {catArticles.map(art => {
                        const isActive = art.id === selectedArticleId || art.slug === selectedArticleId;
                        return (
                          <button
                            key={art.id}
                            onClick={() => setSelectedArticleId(art.id)}
                            className={cn(
                              'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] font-semibold transition-all duration-150 flex items-center justify-between',
                              isActive
                                ? 'bg-sky-100 text-sky-800 font-bold border-l-2 border-sky-600 pl-2 shadow-xs'
                                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                            )}
                          >
                            <span className="truncate">{art.title}</span>
                            {art.targetRole === 'owner' && (
                              <span className="text-[9px] text-purple-600 shrink-0 font-bold">👑</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </aside>

        {/* Right Main Article Viewer */}
        <main className="flex-1 p-6 md:p-10 overflow-y-auto max-h-[calc(100vh-5rem)] custom-scrollbar bg-white">
          {currentArticle ? (
            <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
              {/* Breadcrumbs */}
              <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
                <span
                  className="flex items-center gap-1 hover:text-sky-600 cursor-pointer"
                  onClick={() => setSelectedArticleId(articles[0]?.id || '')}
                >
                  <Home className="w-3.5 h-3.5" />
                  Главная
                </span>
                <span>/</span>
                <span className="hover:text-sky-600 cursor-pointer">
                  {currentCategory?.name || 'Руководство'}
                </span>
                <span>/</span>
                <span className="text-sky-700 font-bold truncate max-w-[280px]">
                  {currentArticle.title}
                </span>
              </div>

              {/* Title & Actions Bar */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-6 border-b border-slate-200">
                <div className="space-y-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {getRoleBadge(currentArticle.targetRole)}
                    {currentArticle.updatedAt && (
                      <span className="text-[11px] text-slate-400 font-medium">
                        Обновлено: {currentArticle.updatedAt}
                      </span>
                    )}
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight leading-tight">
                    {currentArticle.title}
                  </h1>
                </div>

                {/* OWNER-ONLY ACTIONS */}
                {isOwner && (
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleOpenEditArticle(currentArticle)}
                      className="gap-1.5 text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold border border-slate-300"
                    >
                      <Edit3 className="w-3.5 h-3.5 text-sky-600" />
                      Редактировать статью
                    </Button>
                    <button
                      onClick={() => setArticleToDelete(currentArticle)}
                      className="w-8 h-8 rounded-xl flex items-center justify-center bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors"
                      title="Удалить статью с сервера"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              {/* Block 1: "Зачем это нужно?" */}
              {currentArticle.whyNeeded && (
                <div className="p-5 rounded-2xl border-l-4 border-l-sky-500 rounded-r-2xl bg-sky-50/70 border border-sky-100 space-y-1.5 shadow-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-black text-sky-800 uppercase tracking-wider">
                      📌 Зачем это нужно?
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed font-medium text-slate-800">
                    {currentArticle.whyNeeded}
                  </p>
                </div>
              )}

              {/* Block 2: "Что это такое?" */}
              {currentArticle.whatIsIt && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Суть процесса:
                  </h3>
                  <p className="text-sm leading-relaxed text-slate-700">
                    {currentArticle.whatIsIt}
                  </p>
                </div>
              )}

              {/* Block 3: Visual Mockup */}
              {renderVisualMockup(currentArticle.mockupType)}

              {/* Block 4: "Пошаговая инструкция (Как сделать?)" with Interactive Links */}
              {currentArticle.steps && currentArticle.steps.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-base font-black text-slate-900 flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    Пошаговая инструкция:
                  </h3>

                  <div className="space-y-3">
                    {currentArticle.steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl border border-slate-200 bg-white shadow-xs flex items-start gap-3.5 hover:border-slate-300 transition-all"
                      >
                        <span className="w-6 h-6 rounded-full bg-sky-100 text-sky-700 font-black text-xs flex items-center justify-center shrink-0 border border-sky-200">
                          {idx + 1}
                        </span>
                        <div className="text-sm leading-relaxed font-medium text-slate-800 flex-1">
                          {renderInteractiveStepText(step)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Block 5: Troubleshooting / "Частые ошибки" */}
              {currentArticle.troubleshooting && currentArticle.troubleshooting.length > 0 && (
                <div className="p-5 rounded-2xl border border-amber-200 bg-amber-50/70 space-y-3 shadow-xs">
                  <div className="flex items-center gap-2 text-amber-800 font-extrabold text-sm">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <span>Частые ошибки и пути решения:</span>
                  </div>
                  <ul className="space-y-2 text-xs leading-relaxed">
                    {currentArticle.troubleshooting.map((t, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-amber-900 font-medium">
                        <span className="text-amber-600 font-bold shrink-0">•</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Quick Action Button to Admin Section */}
              {currentArticle.quickAction && (
                <div className="pt-6 border-t border-slate-200 flex flex-wrap items-center justify-between gap-4">
                  <div className="text-xs text-slate-500 font-medium">
                    Примените эту инструкцию на практике:
                  </div>
                  <Button
                    variant="primary"
                    onClick={() => {
                      if (currentArticle.quickAction) {
                        handleNavigateToSection(currentArticle.quickAction.page, currentArticle.quickAction.tab);
                      }
                    }}
                    className="gap-2 text-xs font-black bg-brand-lime text-brand-dark hover:brightness-105 shadow-sm py-2.5 px-5"
                  >
                    <span>{currentArticle.quickAction.label}</span>
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-20 text-slate-400 space-y-3">
              <BookOpen className="w-12 h-12 mx-auto text-slate-400" />
              <p className="text-sm font-semibold text-slate-600">Статьи не найдены</p>
              <button
                onClick={() => { setSearchQuery(''); setRoleFilter('all'); }}
                className="text-xs text-sky-600 underline font-semibold"
              >
                Сбросить поиск и фильтры
              </button>
            </div>
          )}
        </main>
      </div>

      {/* OWNER EDIT / CREATE ARTICLE DRAWER */}
      {isOwner && (
        <Drawer
          isOpen={isEditDrawerOpen}
          onClose={() => setIsEditDrawerOpen(false)}
          title={isCreatingNew ? 'Создание статьи на сервере' : 'Редактирование статьи на сервере'}
          subtitle="Доступно исключительно для роли Владелец (Owner)"
          width="xl"
          footer={
            <div className="flex items-center justify-between w-full">
              <Button variant="ghost" onClick={() => setIsEditDrawerOpen(false)}>
                Отмена
              </Button>
              <Button
                variant="primary"
                onClick={handleSaveArticle}
                className="bg-brand-lime text-brand-dark font-black"
              >
                Сохранить в базу данных
              </Button>
            </div>
          }
        >
          {editingArticle && (
            <div className="p-6 space-y-5 font-montserrat">
              <Input
                label="Заголовок статьи"
                value={editingArticle.title || ''}
                onChange={e => setEditingArticle({ ...editingArticle, title: e.target.value })}
                placeholder="Например: Как добавить новый напиток в меню"
                required
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Отдел (Категория)"
                  value={editingArticle.categoryId || 'start'}
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
                    { value: 'owner', label: 'Только Owner (Владелец)' },
                    { value: 'admin', label: 'Администратор' },
                  ]}
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Зачем это нужно? (Краткое обоснование)
                </label>
                <textarea
                  rows={2}
                  value={editingArticle.whyNeeded || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whyNeeded: e.target.value })}
                  placeholder="Объясните сотруднику бизнес-смысл: почему важно делать именно так..."
                  className="w-full p-3 rounded-xl border border-slate-300 text-xs font-medium focus:border-sky-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Что это такое? (Суть сущности или процесса)
                </label>
                <textarea
                  rows={2}
                  value={editingArticle.whatIsIt || ''}
                  onChange={e => setEditingArticle({ ...editingArticle, whatIsIt: e.target.value })}
                  placeholder="Краткое определение функции или раздела админки..."
                  className="w-full p-3 rounded-xl border border-slate-300 text-xs font-medium focus:border-sky-500 outline-none"
                />
              </div>

              {/* Steps builder */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">
                    Пошаговая инструкция (Как сделать?)
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditingArticle({
                      ...editingArticle,
                      steps: [...(editingArticle.steps || []), ''],
                    })}
                    className="text-xs text-sky-600 font-bold hover:underline"
                  >
                    + Добавить шаг
                  </button>
                </div>
                {(editingArticle.steps || []).map((step, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-400 w-5 text-right">{idx + 1}.</span>
                    <input
                      type="text"
                      value={step}
                      onChange={e => {
                        const nextSteps = [...(editingArticle.steps || [])];
                        nextSteps[idx] = e.target.value;
                        setEditingArticle({ ...editingArticle, steps: nextSteps });
                      }}
                      placeholder={`Например: Перейдите в раздел «Пользователи»...`}
                      className="flex-1 p-2 rounded-lg border border-slate-300 text-xs font-medium focus:border-sky-500 outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const nextSteps = (editingArticle.steps || []).filter((_, i) => i !== idx);
                        setEditingArticle({ ...editingArticle, steps: nextSteps });
                      }}
                      className="text-slate-400 hover:text-red-500 px-1 text-sm"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              {/* Troubleshooting */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">
                    Частые ошибки и пути решения (Troubleshooting)
                  </label>
                  <button
                    type="button"
                    onClick={() => setEditingArticle({
                      ...editingArticle,
                      troubleshooting: [...(editingArticle.troubleshooting || []), ''],
                    })}
                    className="text-xs text-sky-600 font-bold hover:underline"
                  >
                    + Добавить ошибку
                  </button>
                </div>
                {(editingArticle.troubleshooting || []).map((t, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="text-xs text-amber-500 font-bold">•</span>
                    <input
                      type="text"
                      value={t}
                      onChange={e => {
                        const nextT = [...(editingArticle.troubleshooting || [])];
                        nextT[idx] = e.target.value;
                        setEditingArticle({ ...editingArticle, troubleshooting: nextT });
                      }}
                      placeholder="Например: Не нажат статус Готов -> пуш не уйдет клиенту"
                      className="flex-1 p-2 rounded-lg border border-slate-300 text-xs font-medium focus:border-sky-500 outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const nextT = (editingArticle.troubleshooting || []).filter((_, i) => i !== idx);
                        setEditingArticle({ ...editingArticle, troubleshooting: nextT });
                      }}
                      className="text-slate-400 hover:text-red-500 px-1 text-sm"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              {/* Visual Mockup & Target section */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Select
                  label="Интерактивный мокап интерфейса"
                  value={editingArticle.mockupType || 'none'}
                  onChange={e => setEditingArticle({ ...editingArticle, mockupType: e.target.value as any })}
                  options={[
                    { value: 'none', label: 'Без мокапа (Только текст)' },
                    { value: 'mobile-order', label: 'Экран мобильного заказа гостя' },
                    { value: 'order-card', label: 'Карточка заказа Live Desk' },
                    { value: 'telegram-bot', label: 'Сообщение в Telegram-боте' },
                    { value: 'push-preview', label: 'Экран Push-уведомления' },
                  ]}
                />

                <Select
                  label="Кнопка быстрого перехода в админку"
                  value={editingArticle.quickAction?.page || ''}
                  onChange={e => {
                    const page = e.target.value as PageId;
                    if (!page) {
                      setEditingArticle({ ...editingArticle, quickAction: undefined });
                    } else {
                      setEditingArticle({
                        ...editingArticle,
                        quickAction: {
                          label: `Перейти в раздел «${page}»`,
                          page,
                        },
                      });
                    }
                  }}
                  options={[
                    { value: '', label: 'Без кнопки перехода' },
                    { value: 'dashboard', label: 'Дашборд' },
                    { value: 'orders', label: 'Заказы (Live Desk)' },
                    { value: 'menu', label: 'Меню и товары' },
                    { value: 'shifts', label: 'Смены и бариста' },
                    { value: 'telegram', label: 'Telegram-бот' },
                    { value: 'notifications', label: 'Push-рассылки' },
                    { value: 'reviews', label: 'Отзывы клиентов' },
                    { value: 'users', label: 'Пользователи' },
                    { value: 'settings', label: 'Настройки сети' },
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
                  <Button variant="primary" onClick={handleSaveCategory} className="bg-brand-lime text-brand-dark font-bold">
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
          title="Удаление статьи"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Вы действительно хотите удалить статью:</p>
            <p className="font-extrabold text-slate-900">«{articleToDelete?.title}»?</p>
            <p className="text-xs text-slate-500">Статья будет удалена из базы данных на сервере для всех пользователей.</p>
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="ghost" onClick={() => setArticleToDelete(null)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleConfirmDeleteArticle}>
                Удалить статью
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
            <p className="text-xs text-red-600 font-semibold">Все статьи, входящие в этот отдел, также будут удалены из базы!</p>
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
