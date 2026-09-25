import React, { useState, useEffect, useMemo } from 'react';
import { useApp, PageId, MenuTabId, SettingsTabId } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
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
  BookOpen, Search, Plus, Edit3, Trash2, ChevronRight, ChevronDown,
  ExternalLink, ArrowRight, ShieldCheck, ShoppingBag, UtensilsCrossed,
  Clock, Send, Bell, Star, Users, Store, HelpCircle, CheckCircle2,
  AlertTriangle, RotateCcw, Download, Upload, Eye, Smartphone, Coffee,
  Flame, Check, Moon, Sun, Layers, Home, Sparkles
} from 'lucide-react';

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
};

export const KnowledgeBasePage: React.FC = () => {
  const { navigateTo, addToast } = useApp();
  const { user } = useAuth();

  // Strict check: only OWNER or SUPERUSER can edit the knowledge base
  const isOwner = Boolean(user?.is_superuser || user?.role === 'owner');

  // Articles & Categories state
  const [categories, setCategories] = useState<KnowledgeCategory[]>(() => getStoredCategories());
  const [articles, setArticles] = useState<KnowledgeArticle[]>(() => getStoredArticles());

  // Navigation & selection state
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
  const [themeMode, setThemeMode] = useState<'dark' | 'light'>('dark');

  // Edit / Create Drawer state (Owner only)
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState<Partial<KnowledgeArticle> | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);

  // Delete Confirmation Modal state (Owner only)
  const [articleToDelete, setArticleToDelete] = useState<KnowledgeArticle | null>(null);

  // Category Manage Modal
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');

  // Selected article
  const currentArticle = useMemo(() => {
    return articles.find(a => a.id === selectedArticleId) || articles[0];
  }, [articles, selectedArticleId]);

  const currentCategory = useMemo(() => {
    if (!currentArticle) return null;
    return categories.find(c => c.id === currentArticle.categoryId) || null;
  }, [categories, currentArticle]);

  // Filtered articles list based on search and role
  const filteredArticles = useMemo(() => {
    return articles.filter(art => {
      // Role filter
      if (roleFilter !== 'all' && art.targetRole !== 'all' && art.targetRole !== roleFilter) {
        return false;
      }
      // Search filter
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

  // Group filtered articles by category
  const articlesByCategory = useMemo(() => {
    const map: Record<string, KnowledgeArticle[]> = {};
    categories.forEach(cat => {
      map[cat.id] = [];
    });
    filteredArticles.forEach(art => {
      if (map[art.categoryId]) {
        map[art.categoryId].push(art);
      } else {
        map[art.categoryId] = [art];
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

  // Open Edit form
  const handleOpenEdit = (article: KnowledgeArticle) => {
    if (!isOwner) return;
    setEditingArticle({ ...article });
    setIsCreatingNew(false);
    setIsEditDrawerOpen(true);
  };

  // Open Create form
  const handleOpenCreate = (defaultCategoryId?: string) => {
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

  // Save Article (Create or Update)
  const handleSaveArticle = () => {
    if (!isOwner || !editingArticle) return;
    if (!editingArticle.title?.trim()) {
      addToast({ type: 'warning', title: 'Укажите заголовок статьи' });
      return;
    }
    if (!editingArticle.categoryId) {
      addToast({ type: 'warning', title: 'Выберите категорию' });
      return;
    }

    const cleanedArticle: KnowledgeArticle = {
      id: editingArticle.id || `art-${Date.now()}`,
      slug: editingArticle.slug || `art-${Date.now()}`,
      categoryId: editingArticle.categoryId,
      title: editingArticle.title.trim(),
      targetRole: editingArticle.targetRole || 'all',
      whyNeeded: editingArticle.whyNeeded?.trim() || '',
      whatIsIt: editingArticle.whatIsIt?.trim() || '',
      steps: (editingArticle.steps || []).filter(s => Boolean(s.trim())),
      troubleshooting: (editingArticle.troubleshooting || []).filter(t => Boolean(t.trim())),
      mockupType: editingArticle.mockupType || 'none',
      quickAction: editingArticle.quickAction,
      tags: (editingArticle.tags || []).filter(Boolean),
      updatedAt: new Date().toISOString().split('T')[0],
      author: user?.full_name || 'Владелец сети',
    };

    let updatedList: KnowledgeArticle[];
    if (isCreatingNew) {
      updatedList = [cleanedArticle, ...articles];
    } else {
      updatedList = articles.map(a => (a.id === cleanedArticle.id ? cleanedArticle : a));
    }

    setArticles(updatedList);
    saveStoredArticles(updatedList);
    setSelectedArticleId(cleanedArticle.id);
    setIsEditDrawerOpen(false);
    setEditingArticle(null);

    addToast({
      type: 'success',
      title: isCreatingNew ? 'Статья создана' : 'Статья сохранена',
      message: `«${cleanedArticle.title}» успешно обновлена в базе знаний`,
    });
  };

  // Delete Article
  const handleConfirmDelete = () => {
    if (!isOwner || !articleToDelete) return;
    const updatedList = articles.filter(a => a.id !== articleToDelete.id);
    setArticles(updatedList);
    saveStoredArticles(updatedList);
    if (selectedArticleId === articleToDelete.id) {
      setSelectedArticleId(updatedList[0]?.id || '');
    }
    setArticleToDelete(null);
    addToast({
      type: 'info',
      title: 'Статья удалена',
      message: `Статья была удалена из базы знаний`,
    });
  };

  // Reset to Factory Knowledge Base
  const handleResetKnowledgeBase = () => {
    if (!isOwner) return;
    if (confirm('Сбросить базу знаний к исходному руководству сети? Все пользовательские правки будут удалены.')) {
      const reset = resetStoredKnowledgeBase();
      setArticles(reset.articles);
      setCategories(reset.categories);
      setSelectedArticleId(reset.articles[0]?.id || '');
      addToast({
        type: 'success',
        title: 'База знаний сброшена',
        message: 'Восстановлены заводские статьи руководства',
      });
    }
  };

  // Export as JSON
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ categories, articles }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `happy_island_knowledge_base_${new Date().toISOString().split('T')[0]}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    addToast({ type: 'success', title: 'База экспортирована', message: 'Файл JSON сохранен на ваше устройство' });
  };

  const getRoleBadge = (role: KnowledgeArticle['targetRole']) => {
    switch (role) {
      case 'barista':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">👤 Бариста</span>;
      case 'manager':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">💼 Управляющий</span>;
      case 'owner':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">👑 Только Owner</span>;
      case 'admin':
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">⚡ Администратор</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-500/20 text-slate-300 border border-slate-500/30">🌐 Для всех ролей</span>;
    }
  };

  // Mockup Renderer (styled like mobile screens or cards)
  const renderVisualMockup = (type?: KnowledgeArticle['mockupType']) => {
    if (!type || type === 'none') return null;

    if (type === 'mobile-order') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[340px] rounded-[38px] border-4 border-slate-700 bg-slate-950 p-3 shadow-2xl text-white">
            <div className="w-24 h-4 bg-slate-800 rounded-full mx-auto mb-3" />
            <div className="bg-slate-900 rounded-2xl p-4 border border-slate-800 space-y-3">
              <div className="h-36 rounded-xl bg-gradient-to-br from-amber-700 to-amber-900 flex items-center justify-center relative overflow-hidden">
                <Coffee className="w-16 h-16 text-amber-200/80" />
                <span className="absolute bottom-2 right-2 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-amber-300">
                  350 мл
                </span>
              </div>
              <div>
                <h4 className="font-extrabold text-sm text-white">Раф Цитрусовый</h4>
                <p className="text-[11px] text-slate-400">Эспрессо, сливки 10%, натуральная цедра апельсина</p>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <div>
                  <span className="text-lg font-extrabold text-white">320 ₽</span>
                  <span className="text-[10px] text-slate-400 block">+ 15 бонусов</span>
                </div>
                <button className="px-4 py-2 rounded-xl bg-brand-lime text-brand-dark font-extrabold text-xs shadow-md">
                  В корзину
                </button>
              </div>
            </div>
            <p className="text-center text-[10px] text-slate-500 mt-2">Вид позиции в мобильном приложении гостя</p>
          </div>
        </div>
      );
    }

    if (type === 'order-card') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[420px] rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-xl text-white">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-brand-lime animate-pulse" />
                <span className="font-extrabold text-sm">Заказ #1048</span>
              </div>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Ожидает / Pending
              </span>
            </div>
            <div className="py-3 space-y-2 text-xs">
              <div className="flex justify-between text-slate-300">
                <span>Капучино Большой (400 мл)</span>
                <span className="font-bold text-white">280 ₽</span>
              </div>
              <div className="text-[11px] text-amber-400 pl-2 border-l border-amber-500/40">
                • Банановое молоко (+60 ₽)<br />
                • Без сахара
              </div>
              <div className="pt-2 text-slate-400 flex items-center justify-between text-[11px]">
                <span>Гость: Александр (+7 917 ***)</span>
                <span className="text-emerald-400 font-semibold">Оплачено онлайн</span>
              </div>
            </div>
            <div className="pt-3 border-t border-slate-800 flex gap-2">
              <button className="flex-1 py-2 rounded-xl bg-brand-lime text-brand-dark font-extrabold text-xs shadow-md hover:brightness-105 transition-all">
                В работу
              </button>
              <button className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold">
                Отмена
              </button>
            </div>
            <p className="text-center text-[10px] text-slate-500 mt-2">Карточка на Канбан-доске в Live Desk</p>
          </div>
        </div>
      );
    }

    if (type === 'telegram-bot') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[380px] rounded-2xl border border-sky-900/60 bg-[#0e1621] p-4 shadow-xl text-white font-sans">
            <div className="flex items-center gap-2.5 pb-2.5 border-b border-sky-950/80">
              <div className="w-8 h-8 rounded-full bg-sky-500 flex items-center justify-center text-white font-bold text-xs">
                🤖
              </div>
              <div>
                <p className="text-xs font-bold text-white">Happy Island Orders Bot</p>
                <span className="text-[10px] text-sky-400">бот для бариста</span>
              </div>
            </div>
            <div className="mt-3 bg-[#182533] p-3.5 rounded-xl border border-sky-900/40 space-y-2 text-xs">
              <p className="text-emerald-400 font-bold">🔔 НОВЫЙ ЗАКАЗ #1048</p>
              <p className="text-slate-300">Точка: Баумана, 14</p>
              <div className="p-2 bg-[#202f42] rounded-lg text-[11px] text-slate-200">
                1x Капучино Большой<br />
                🥛 Молоко: Банановое<br />
                🍬 Без сахара
              </div>
              <p className="text-right text-[10px] text-slate-400">14:32</p>
            </div>
            <p className="text-center text-[10px] text-slate-500 mt-2">Моментальное звуковое оповещение в Telegram</p>
          </div>
        </div>
      );
    }

    if (type === 'push-preview') {
      return (
        <div className="my-6 flex justify-center">
          <div className="w-full max-w-[380px] rounded-2xl border border-slate-700 bg-slate-900/90 backdrop-blur p-4 shadow-xl text-white">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-2xl bg-brand-lime flex items-center justify-center text-brand-dark font-extrabold text-lg shrink-0 shadow-md">
                ☕
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Happy Island</span>
                  <span className="text-[10px] text-slate-500">сейчас</span>
                </div>
                <h5 className="text-xs font-bold text-white mt-0.5">Счастливые часы в Happy Island!</h5>
                <p className="text-xs text-slate-300 mt-1">
                  Скидка 20% на весь авторский кофе сегодня до 18:00! Ждем вас в гости ☕
                </p>
              </div>
            </div>
            <p className="text-center text-[10px] text-slate-500 mt-3">Вид пуш-уведомления на экране блокировки</p>
          </div>
        </div>
      );
    }

    return null;
  };

  const isDark = themeMode === 'dark';

  return (
    <div
      className={cn(
        'min-h-[calc(100vh-5rem)] rounded-2xl transition-colors duration-200 font-montserrat flex flex-col',
        isDark ? 'bg-[#0f172a] text-slate-100' : 'bg-slate-50 text-slate-800'
      )}
    >
      {/* Top Docs Header (matches user's screenshot Wikkeo Docs style) */}
      <header
        className={cn(
          'px-6 py-4 border-b flex flex-wrap items-center justify-between gap-4 sticky top-0 z-20 backdrop-blur-md',
          isDark ? 'bg-[#0f172a]/90 border-slate-800' : 'bg-white/90 border-slate-200'
        )}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-brand-lime flex items-center justify-center text-brand-dark font-black text-base shadow-sm">
              ☕
            </div>
            <div>
              <span className="font-extrabold text-base tracking-tight flex items-center gap-1.5">
                HAPPY ISLAND <span className="text-sky-400 text-xs font-semibold uppercase px-1.5 py-0.5 rounded bg-sky-500/10 border border-sky-500/20">Docs</span>
              </span>
            </div>
          </div>
          <span className={cn('text-xs font-semibold px-2 py-0.5 rounded-full border', isDark ? 'bg-slate-800 text-slate-400 border-slate-700' : 'bg-slate-100 text-slate-600 border-slate-300')}>
            База знаний
          </span>
        </div>

        {/* Search bar */}
        <div className="flex-1 max-w-md relative min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Поиск по базе: сироп, отмена заказа, telegram, смена..."
            className={cn(
              'w-full pl-9 pr-4 py-2 rounded-xl text-xs font-medium border transition-all outline-none',
              isDark
                ? 'bg-slate-900 border-slate-700 text-white placeholder-slate-500 focus:border-sky-500'
                : 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-sky-500'
            )}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-white"
            >
              ✕
            </button>
          )}
        </div>

        {/* Right action controls */}
        <div className="flex items-center gap-2.5">
          {/* Role selector filter */}
          <select
            value={roleFilter}
            onChange={e => setRoleFilter(e.target.value as any)}
            className={cn(
              'px-3 py-1.5 rounded-xl text-xs font-semibold border outline-none cursor-pointer',
              isDark ? 'bg-slate-900 border-slate-700 text-slate-300' : 'bg-white border-slate-300 text-slate-700'
            )}
          >
            <option value="all">Все роли</option>
            <option value="barista">Бариста</option>
            <option value="manager">Управляющий</option>
            <option value="owner">Владелец (Owner)</option>
            <option value="admin">Администратор</option>
          </select>

          {/* Theme mode toggle */}
          <button
            onClick={() => setThemeMode(isDark ? 'light' : 'dark')}
            className={cn(
              'w-8 h-8 rounded-xl flex items-center justify-center transition-colors border',
              isDark ? 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white' : 'bg-white border-slate-300 text-slate-600 hover:text-black'
            )}
            title="Переключить тему"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-700" />}
          </button>

          {/* OWNER-ONLY ACTIONS */}
          {isOwner && (
            <div className="flex items-center gap-1.5 pl-2 border-l border-slate-700/50">
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleOpenCreate(currentArticle?.categoryId)}
                className="gap-1.5 text-xs py-1.5 px-3 bg-brand-lime text-brand-dark font-extrabold hover:brightness-105"
                title="Доступно только владельцу сети (Owner)"
              >
                <Plus className="w-3.5 h-3.5" />
                Создать статью
              </Button>

              <button
                onClick={handleExportJSON}
                className={cn(
                  'w-8 h-8 rounded-xl flex items-center justify-center transition-colors border',
                  isDark ? 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white' : 'bg-white border-slate-300 text-slate-600 hover:text-black'
                )}
                title="Экспорт базы знаний в JSON"
              >
                <Download className="w-4 h-4" />
              </button>

              <button
                onClick={handleResetKnowledgeBase}
                className={cn(
                  'w-8 h-8 rounded-xl flex items-center justify-center transition-colors border text-amber-400 hover:text-amber-300',
                  isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-300'
                )}
                title="Сбросить к исходным статьям сети"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main Docs Body: Sidebar + Reading Area */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        {/* Left Navigation Tree (collapsible categories and articles) */}
        <aside
          className={cn(
            'w-full md:w-80 shrink-0 border-r p-4 overflow-y-auto max-h-[calc(100vh-10rem)] custom-scrollbar select-none',
            isDark ? 'border-slate-800 bg-[#0b1120]' : 'border-slate-200 bg-slate-100/60'
          )}
        >
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-3 flex items-center justify-between">
            <span>Разделы руководства</span>
            <span className="text-[10px] text-slate-500 font-semibold">{filteredArticles.length} статей</span>
          </div>

          <div className="space-y-1">
            {categories.map(cat => {
              const catArticles = articlesByCategory[cat.id] || [];
              const isOpen = expandedCategories[cat.id] !== false;
              const hasActiveChild = catArticles.some(a => a.id === selectedArticleId);

              if (catArticles.length === 0 && searchQuery) {
                return null;
              }

              return (
                <div key={cat.id} className="space-y-0.5">
                  <button
                    onClick={() => toggleCategory(cat.id)}
                    className={cn(
                      'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold transition-colors group',
                      hasActiveChild
                        ? isDark ? 'text-sky-400 bg-sky-950/30' : 'text-sky-700 bg-sky-50'
                        : isDark ? 'text-slate-300 hover:text-white hover:bg-slate-800/60' : 'text-slate-700 hover:text-black hover:bg-slate-200/60'
                    )}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className={cn('shrink-0', hasActiveChild ? 'text-sky-400' : 'text-slate-400 group-hover:text-slate-200')}>
                        {CATEGORY_ICONS[cat.iconName] || <BookOpen className="w-4 h-4" />}
                      </span>
                      <span className="truncate">{cat.name}</span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full font-semibold bg-slate-800 text-slate-400">
                        {catArticles.length}
                      </span>
                      <ChevronDown
                        className={cn(
                          'w-3.5 h-3.5 text-slate-400 transition-transform duration-200',
                          !isOpen && '-rotate-90'
                        )}
                      />
                    </div>
                  </button>

                  {/* Sub-articles under category */}
                  {isOpen && catArticles.length > 0 && (
                    <div className="pl-6 pr-1 py-0.5 space-y-0.5 border-l border-slate-700/40 ml-4 my-0.5">
                      {catArticles.map(art => {
                        const isActive = art.id === selectedArticleId;
                        return (
                          <button
                            key={art.id}
                            onClick={() => setSelectedArticleId(art.id)}
                            className={cn(
                              'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] font-semibold transition-all duration-150 flex items-center justify-between',
                              isActive
                                ? 'bg-sky-500/20 text-sky-400 font-bold border-l-2 border-sky-400 pl-2 shadow-sm'
                                : isDark
                                ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/40'
                            )}
                          >
                            <span className="truncate">{art.title}</span>
                            {art.targetRole === 'owner' && (
                              <span className="text-[9px] text-purple-400 shrink-0 font-bold">👑</span>
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
        <main className="flex-1 p-6 md:p-10 overflow-y-auto max-h-[calc(100vh-10rem)] custom-scrollbar">
          {currentArticle ? (
            <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
              {/* Breadcrumbs */}
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="flex items-center gap-1 hover:text-sky-400 cursor-pointer">
                  <Home className="w-3.5 h-3.5" />
                  Главная
                </span>
                <span>/</span>
                <span className="hover:text-sky-400 cursor-pointer">
                  {currentCategory?.name || 'Руководство'}
                </span>
                <span>/</span>
                <span className="text-sky-400 font-semibold truncate max-w-[280px]">
                  {currentArticle.title}
                </span>
              </div>

              {/* Title & Actions Bar */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-6 border-b border-slate-700/60">
                <div className="space-y-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {getRoleBadge(currentArticle.targetRole)}
                    {currentArticle.updatedAt && (
                      <span className="text-[11px] text-slate-400">
                        Обновлено: {currentArticle.updatedAt}
                      </span>
                    )}
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-black tracking-tight leading-tight">
                    {currentArticle.title}
                  </h1>
                </div>

                {/* OWNER-ONLY EDIT & DELETE BUTTONS */}
                {isOwner && (
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleOpenEdit(currentArticle)}
                      className="gap-1.5 text-xs bg-slate-800 text-sky-300 hover:bg-slate-700 border border-slate-700"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Редактировать статью
                    </Button>
                    <button
                      onClick={() => setArticleToDelete(currentArticle)}
                      className="w-8 h-8 rounded-xl flex items-center justify-center bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/30 transition-colors"
                      title="Удалить статью"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              {/* Block 1: "Зачем это нужно?" (Why needed) */}
              {currentArticle.whyNeeded && (
                <div
                  className={cn(
                    'p-5 rounded-2xl border-l-4 border-l-sky-500 rounded-r-2xl space-y-1.5',
                    isDark ? 'bg-sky-950/20 border-slate-800' : 'bg-sky-50 border-sky-200'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-extrabold text-sky-400 uppercase tracking-wider">
                      📌 Зачем это нужно?
                    </span>
                  </div>
                  <p className={cn('text-sm leading-relaxed font-medium', isDark ? 'text-slate-200' : 'text-slate-700')}>
                    {currentArticle.whyNeeded}
                  </p>
                </div>
              )}

              {/* Block 2: "Что это такое?" (What is it) */}
              {currentArticle.whatIsIt && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Суть процесса:
                  </h3>
                  <p className={cn('text-sm leading-relaxed', isDark ? 'text-slate-300' : 'text-slate-600')}>
                    {currentArticle.whatIsIt}
                  </p>
                </div>
              )}

              {/* Block 3: Visual Mockup (like screenshot / smartphone frame from user prompt) */}
              {renderVisualMockup(currentArticle.mockupType)}

              {/* Block 4: "Пошаговый алгоритм (Как сделать?)" */}
              {currentArticle.steps && currentArticle.steps.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-base font-extrabold flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-brand-lime" />
                    Пошаговая инструкция:
                  </h3>

                  <div className="space-y-3">
                    {currentArticle.steps.map((step, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          'p-4 rounded-xl border flex items-start gap-3.5 transition-all',
                          isDark ? 'bg-slate-900/60 border-slate-800' : 'bg-white border-slate-200 shadow-sm'
                        )}
                      >
                        <span className="w-6 h-6 rounded-full bg-sky-500/20 text-sky-400 font-extrabold text-xs flex items-center justify-center shrink-0 border border-sky-500/30">
                          {idx + 1}
                        </span>
                        <p className={cn('text-sm leading-relaxed font-medium', isDark ? 'text-slate-200' : 'text-slate-700')}>
                          {step}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Block 5: Troubleshooting / "Частые ошибки" */}
              {currentArticle.troubleshooting && currentArticle.troubleshooting.length > 0 && (
                <div
                  className={cn(
                    'p-5 rounded-2xl border border-amber-500/30 space-y-3',
                    isDark ? 'bg-amber-950/20' : 'bg-amber-50'
                  )}
                >
                  <div className="flex items-center gap-2 text-amber-400 font-extrabold text-sm">
                    <AlertTriangle className="w-5 h-5" />
                    <span>Частые ошибки и пути решения:</span>
                  </div>
                  <ul className="space-y-2 text-xs leading-relaxed">
                    {currentArticle.troubleshooting.map((t, idx) => (
                      <li key={idx} className={cn('flex items-start gap-2', isDark ? 'text-amber-200/90' : 'text-amber-900')}>
                        <span className="text-amber-400 font-bold shrink-0">•</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Quick Action Button to Admin Section */}
              {currentArticle.quickAction && (
                <div className="pt-6 border-t border-slate-800 flex flex-wrap items-center justify-between gap-4">
                  <div className="text-xs text-slate-400">
                    Готовы применить инструкцию на практике?
                  </div>
                  <Button
                    variant="primary"
                    onClick={() => {
                      if (currentArticle.quickAction) {
                        navigateTo(currentArticle.quickAction.page, currentArticle.quickAction.tab);
                      }
                    }}
                    className="gap-2 text-xs font-extrabold bg-brand-lime text-brand-dark hover:brightness-105 shadow-md py-2.5 px-5"
                  >
                    <span>{currentArticle.quickAction.label}</span>
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </div>
              )}

              {/* Tags footer */}
              {currentArticle.tags && currentArticle.tags.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap pt-4">
                  <span className="text-[11px] text-slate-500">Теги:</span>
                  {currentArticle.tags.map((t, i) => (
                    <span
                      key={i}
                      onClick={() => setSearchQuery(t)}
                      className={cn(
                        'px-2 py-0.5 rounded-md text-[10px] font-semibold cursor-pointer border',
                        isDark ? 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white' : 'bg-slate-200 text-slate-600 border-slate-300 hover:text-black'
                      )}
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-20 text-slate-400 space-y-3">
              <BookOpen className="w-12 h-12 mx-auto text-slate-600" />
              <p className="text-sm font-semibold">Статьи не найдены по вашему запросу</p>
              <button
                onClick={() => { setSearchQuery(''); setRoleFilter('all'); }}
                className="text-xs text-sky-400 underline"
              >
                Сбросить фильтры
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
          title={isCreatingNew ? 'Создание новой статьи' : 'Редактирование статьи'}
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
                className="bg-brand-lime text-brand-dark font-extrabold"
              >
                Сохранить статью
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
                  label="Раздел (Категория)"
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
                  className="w-full p-3 rounded-xl border border-slate-300 text-xs font-medium focus:border-brand-lime outline-none"
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
                  className="w-full p-3 rounded-xl border border-slate-300 text-xs font-medium focus:border-brand-lime outline-none"
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
                    className="text-xs text-brand-dark-blue font-bold hover:underline"
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
                      placeholder={`Шаг ${idx + 1}`}
                      className="flex-1 p-2 rounded-lg border border-slate-300 text-xs font-medium focus:border-brand-lime outline-none"
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

              {/* Troubleshooting builder */}
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
                    className="text-xs text-brand-dark-blue font-bold hover:underline"
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
                      className="flex-1 p-2 rounded-lg border border-slate-300 text-xs font-medium focus:border-brand-lime outline-none"
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

              {/* Visual Mockup type */}
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
                          label: `Перейти в раздел ${page}`,
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
                placeholder="заказ, бариста, live desk, канбан"
              />
            </div>
          )}
        </Drawer>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {isOwner && (
        <Modal
          isOpen={Boolean(articleToDelete)}
          onClose={() => setArticleToDelete(null)}
          title="Удаление статьи из базы знаний"
        >
          <div className="space-y-4 text-sm text-slate-700">
            <p>Вы действительно хотите удалить статью:</p>
            <p className="font-extrabold text-brand-dark">«{articleToDelete?.title}»?</p>
            <p className="text-xs text-slate-500">Это действие удалит статью для всех сотрудников сети кофейни.</p>
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="ghost" onClick={() => setArticleToDelete(null)}>
                Отмена
              </Button>
              <Button
                variant="danger"
                onClick={handleConfirmDelete}
              >
                Да, удалить статью
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
