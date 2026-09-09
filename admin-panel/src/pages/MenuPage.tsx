import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import {
  Product, Category, Addon, AdditiveFlavor, ProductType, TemperatureType,
  SeasonMenu, Season, SEASON_LABELS, MENU_ICONS,
} from '../types';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Combobox } from '../components/ui/Combobox';
import { Table, Column } from '../components/ui/Table';
import {
  Plus, Search, Edit2, Trash2, CheckCircle2, XCircle,
  Coffee, Flame, Snowflake, Sparkles, Droplets, Tag, AlertTriangle, Eye, EyeOff
} from 'lucide-react';
import { cn } from '../utils/cn';

export const MenuPage: React.FC = () => {
  const { selectedShopId, addToast, activeMenuTab, setActiveMenuTab } = useApp();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [flavors, setFlavors] = useState<AdditiveFlavor[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  // Product modal/drawer state
  const [editingProduct, setEditingProduct] = useState<Partial<Product> | null>(null);
  const [isProductDrawerOpen, setIsProductDrawerOpen] = useState(false);
  const [isSavingProduct, setIsSavingProduct] = useState(false);

  // Category modal state
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryMenu, setNewCategoryMenu] = useState<'main_menu' | 'season_menu' | 'both'>('main_menu');
  // Оформление плитки категории в приложении. Пусто — берётся локальный набор.
  const [newCategoryColor, setNewCategoryColor] = useState('');
  const [newCategoryIcon, setNewCategoryIcon] = useState('');

  // Addon modal state
  const [isAddonModalOpen, setIsAddonModalOpen] = useState(false);
  const [editingAddon, setEditingAddon] = useState<Partial<Addon> | null>(null);

  // Flavor modal state
  const [isFlavorModalOpen, setIsFlavorModalOpen] = useState(false);
  const [editingFlavor, setEditingFlavor] = useState<Partial<AdditiveFlavor> | null>(null);

  // Season menu state
  const [seasonMenus, setSeasonMenus] = useState<SeasonMenu[]>([]);
  const [isSeasonModalOpen, setIsSeasonModalOpen] = useState(false);
  const [editingSeason, setEditingSeason] = useState<Partial<SeasonMenu> | null>(null);
  const [seasonError, setSeasonError] = useState('');

  const [isLoading, setIsLoading] = useState(true);

  // Ошибки форм показываются после попытки сохранения и гаснут по мере правки.
  const [productErrors, setProductErrors] = useState<Record<string, string>>({});
  const [categoryError, setCategoryError] = useState('');
  const [addonErrors, setAddonErrors] = useState<Record<string, string>>({});
  const [flavorError, setFlavorError] = useState('');

  // Всё в этом разделе принадлежит конкретной точке. Пока она не выбрана,
  // создавать нечего: раньше в тело запроса подставлялось coffee_shop: 1,
  // кофейни с таким id в базе нет, и сервер отвечал
  // «Недопустимый первичный ключ "1" — объект не существует».
  const canManage = selectedShopId !== null;

  useEffect(() => {
    loadData();
  }, [selectedShopId]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [prods, cats, adds, flavs, seasons] = await Promise.all([
        api.getProducts(selectedShopId || undefined),
        api.getCategories(selectedShopId || undefined),
        api.getAddons(selectedShopId || undefined),
        api.getFlavors(selectedShopId || undefined),
        api.getSeasonMenus(selectedShopId || undefined),
      ]);
      setProducts(prods);
      setCategories(cats);
      setAddons(adds);
      setFlavors(flavs);
      setSeasonMenus(seasons);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Пустое поле цены — это «цены нет», а не ноль.
   *
   * Раньше здесь стоял Number(e.target.value), а Number('') === 0: стёртая
   * цена уезжала на сервер нулём, размер оставался доступным и становился
   * бесплатным. Возвращаем null, чтобы размер честно пропал из приложения.
   */
  const parsePriceInput = (raw: string): number | null => {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : null;
  };

  const isDuplicateName = (
    name: string,
    existing: { id: number; name: string }[],
    currentId?: number,
  ) => {
    const normalized = name.trim().toLowerCase();
    return existing.some(
      item => item.id !== currentId && item.name.trim().toLowerCase() === normalized
    );
  };

  const productNames = products.map(p => ({ id: p.id, name: p.product }));

  const validateProduct = (draft: Partial<Product>): Record<string, string> => {
    const errors: Record<string, string> = {};
    const name = (draft.product || '').trim();

    if (!name) {
      errors.product = 'Укажите название товара';
    } else if (name.length > 100) {
      errors.product = 'Не длиннее 100 символов';
    } else if (isDuplicateName(name, productNames, draft.id)) {
      errors.product = 'Товар с таким названием в этой кофейне уже есть';
    }

    if (!draft.category || !categories.some(c => c.id === draft.category)) {
      errors.category = 'Выберите категорию';
    }

    const prices = [draft.price_s, draft.price_m, draft.price_l];
    if (prices.some(price => typeof price === 'number' && price < 0)) {
      errors.prices = 'Цена не может быть отрицательной';
    } else if (!prices.some(price => typeof price === 'number' && price > 0)) {
      errors.prices = 'Заполните цену хотя бы одного размера: размер без цены в приложении недоступен';
    }

    return errors;
  };

  const handleToggleAvailability = async (productId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await api.toggleProductAvailability(productId);
      setProducts(prev => prev.map(p => (p.id === productId ? { ...p, availability: res.availability } : p)));
      addToast({
        type: res.availability ? 'success' : 'warning',
        title: res.availability ? 'Товар в наличии' : 'Товар в стоп-листе',
        message: `Статус доступности товара изменен`,
      });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось обновить статус товара' });
    }
  };

  // --- Product Save ---
  const handleSaveProduct = async () => {
    if (!editingProduct) return;

    if (!selectedShopId && !editingProduct.coffee_shop) {
      addToast({
        type: 'error',
        title: 'Не выбрана кофейня',
        message: 'Выберите точку в шапке: товар заводится для конкретной кофейни',
      });
      return;
    }

    const errors = validateProduct(editingProduct);
    if (Object.keys(errors).length > 0) {
      setProductErrors(errors);
      return;
    }
    setProductErrors({});

    setIsSavingProduct(true);
    try {
      const payload: Partial<Product> = {
        ...editingProduct,
        product: editingProduct.product?.trim(),
        // При правке остаёмся в кофейне товара, при создании берём выбранную.
        coffee_shop: editingProduct.coffee_shop ?? (selectedShopId as number),
        // can_be_hot_and_cold дублирует temperature_type === 'All'. Держим их
        // согласованными, пока поле не убрали из модели.
        can_be_hot_and_cold: editingProduct.temperature_type === 'All',
      };

      const saved = await api.saveProduct(payload);
      setProducts(prev => {
        const exists = prev.some(p => p.id === saved.id);
        if (exists) return prev.map(p => (p.id === saved.id ? saved : p));
        return [saved, ...prev];
      });
      setIsProductDrawerOpen(false);
      setEditingProduct(null);
      addToast({
        type: 'success',
        title: 'Успешно',
        message: editingProduct.id ? 'Изменения сохранены' : 'Товар успешно создан',
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ошибка сохранения',
        message: err?.message || 'Не удалось сохранить товар',
      });
    } finally {
      setIsSavingProduct(false);
    }
  };

  const closeProductDrawer = () => {
    setIsProductDrawerOpen(false);
    setEditingProduct(null);
    setProductErrors({});
  };

  const handleDeleteProduct = async (id: number) => {
    if (!confirm('Вы уверены, что хотите удалить данный товар?')) return;
    try {
      await api.deleteProduct(id);
      setProducts(prev => prev.filter(p => p.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Товар успешно удален' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить товар' });
    }
  };

  // --- Category Save ---
  const handleCreateCategory = async () => {
    if (!selectedShopId) {
      addToast({
        type: 'error',
        title: 'Не выбрана кофейня',
        message: 'Категория создаётся для конкретной точки — выберите её в шапке',
      });
      return;
    }

    const name = newCategoryName.trim();
    if (!name) {
      setCategoryError('Укажите название категории');
      return;
    }
    if (name.length > 255) {
      setCategoryError('Не длиннее 255 символов');
      return;
    }
    if (isDuplicateName(name, categories)) {
      setCategoryError('Категория с таким названием в этой кофейне уже есть');
      return;
    }
    setCategoryError('');

    try {
      const cat = await api.createCategory({
        name,
        which_menu: newCategoryMenu,
        color: newCategoryColor,
        icon: newCategoryIcon,
        coffee_shop: selectedShopId,
      });
      setCategories(prev => [...prev, cat]);
      closeCategoryModal();
      addToast({ type: 'success', title: 'Категория создана', message: cat.name });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: err?.message || 'Не удалось создать категорию',
      });
    }
  };

  /** Сброс формы категории: раньше which_menu протекал в следующую категорию. */
  const closeCategoryModal = () => {
    setIsCategoryModalOpen(false);
    setNewCategoryName('');
    setNewCategoryMenu('main_menu');
    setNewCategoryColor('');
    setNewCategoryIcon('');
    setCategoryError('');
  };

  // --- Addon Save ---
  const handleSaveAddon = async () => {
    if (!editingAddon) return;

    if (!selectedShopId && !editingAddon.coffee_shop) {
      addToast({
        type: 'error',
        title: 'Не выбрана кофейня',
        message: 'Добавка заводится для конкретной точки — выберите её в шапке',
      });
      return;
    }

    const errors: Record<string, string> = {};
    const name = (editingAddon.name || '').trim();

    if (!name) errors.name = 'Укажите название добавки';
    else if (name.length > 255) errors.name = 'Не длиннее 255 символов';
    else if (isDuplicateName(name, addons, editingAddon.id))
      errors.name = 'Добавка с таким названием в этой кофейне уже есть';

    if (typeof editingAddon.price !== 'number') errors.price = 'Укажите стоимость';
    else if (editingAddon.price < 0) errors.price = 'Стоимость не может быть отрицательной';

    if (Object.keys(errors).length > 0) {
      setAddonErrors(errors);
      return;
    }
    setAddonErrors({});

    try {
      const saved = await api.saveAddon({
        ...editingAddon,
        name,
        coffee_shop: editingAddon.coffee_shop ?? (selectedShopId as number),
      });
      setAddons(prev => {
        const exists = prev.some(a => a.id === saved.id);
        if (exists) return prev.map(a => (a.id === saved.id ? saved : a));
        return [...prev, saved];
      });
      closeAddonModal();
      addToast({ type: 'success', title: 'Добавка сохранена', message: saved.name });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: err?.message || 'Не удалось сохранить добавку',
      });
    }
  };

  const closeAddonModal = () => {
    setIsAddonModalOpen(false);
    setEditingAddon(null);
    setAddonErrors({});
  };

  const handleDeleteAddon = async (id: number) => {
    if (!confirm('Удалить добавку?')) return;
    try {
      await api.deleteAddon(id);
      setAddons(prev => prev.filter(a => a.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Добавка удалена' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить добавку' });
    }
  };

  // --- Flavor Save ---
  const handleSaveFlavor = async () => {
    if (!editingFlavor) return;

    if (!selectedShopId && !editingFlavor.coffee_shop) {
      addToast({
        type: 'error',
        title: 'Не выбрана кофейня',
        message: 'Вкус заводится для конкретной точки — выберите её в шапке',
      });
      return;
    }

    const name = (editingFlavor.name || '').trim();
    if (!name) {
      setFlavorError('Укажите название вкуса');
      return;
    }
    if (name.length > 255) {
      setFlavorError('Не длиннее 255 символов');
      return;
    }
    if (isDuplicateName(name, flavors, editingFlavor.id)) {
      setFlavorError('Вкус с таким названием в этой кофейне уже есть');
      return;
    }
    setFlavorError('');

    try {
      const saved = await api.saveFlavor({
        ...editingFlavor,
        name,
        coffee_shop: editingFlavor.coffee_shop ?? (selectedShopId as number),
      });
      setFlavors(prev => {
        const exists = prev.some(f => f.id === saved.id);
        if (exists) return prev.map(f => (f.id === saved.id ? saved : f));
        return [...prev, saved];
      });
      closeFlavorModal();
      addToast({ type: 'success', title: 'Вкус сохранен', message: saved.name });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: err?.message || 'Не удалось сохранить вкус',
      });
    }
  };

  const closeFlavorModal = () => {
    setIsFlavorModalOpen(false);
    setEditingFlavor(null);
    setFlavorError('');
  };

  const handleDeleteFlavor = async (id: number) => {
    if (!confirm('Удалить вкус?')) return;
    try {
      await api.deleteFlavor(id);
      setFlavors(prev => prev.filter(f => f.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Вкус удален' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить вкус' });
    }
  };

  // --- Season menu ---
  const seasonProducts = products.filter(
    p => p.which_menu === 'season_menu' || p.which_menu === 'both'
  );

  const handleSaveSeason = async () => {
    if (!editingSeason) return;

    if (!selectedShopId && !editingSeason.coffee_shop) {
      addToast({
        type: 'error',
        title: 'Не выбрана кофейня',
        message: 'Сезонный раздел заводится для конкретной точки — выберите её в шапке',
      });
      return;
    }

    const section = (editingSeason.seasonal_section || '').trim();
    if (!section) {
      setSeasonError('Укажите название раздела');
      return;
    }

    // Уникальность на сервере — по паре «сезон + раздел» внутри кофейни.
    const clash = seasonMenus.some(
      m =>
        m.id !== editingSeason.id &&
        m.season === editingSeason.season &&
        m.seasonal_section.trim().toLowerCase() === section.toLowerCase()
    );
    if (clash) {
      setSeasonError('Такой раздел в этом сезоне уже есть');
      return;
    }
    setSeasonError('');

    try {
      const saved = await api.saveSeasonMenu({
        ...editingSeason,
        seasonal_section: section,
        coffee_shop: editingSeason.coffee_shop ?? (selectedShopId as number),
      });
      setSeasonMenus(prev => {
        const exists = prev.some(m => m.id === saved.id);
        if (exists) return prev.map(m => (m.id === saved.id ? saved : m));
        return [...prev, saved];
      });
      closeSeasonModal();
      addToast({
        type: 'success',
        title: 'Сезонный раздел сохранён',
        message: saved.seasonal_section,
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: err?.message || 'Не удалось сохранить раздел',
      });
    }
  };

  const handleToggleSeasonActive = async (menu: SeasonMenu) => {
    try {
      const saved = await api.saveSeasonMenu({ id: menu.id, is_active: !menu.is_active });
      setSeasonMenus(prev => prev.map(m => (m.id === saved.id ? { ...m, ...saved } : m)));
      addToast({
        type: saved.is_active ? 'success' : 'warning',
        title: saved.is_active ? 'Раздел показывается' : 'Раздел скрыт',
        message: menu.seasonal_section,
      });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось переключить раздел' });
    }
  };

  const handleDeleteSeason = async (id: number) => {
    if (!confirm('Удалить сезонный раздел? Товары останутся в меню.')) return;
    try {
      await api.deleteSeasonMenu(id);
      setSeasonMenus(prev => prev.filter(m => m.id !== id));
      addToast({ type: 'success', title: 'Удалено', message: 'Сезонный раздел удалён' });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось удалить раздел' });
    }
  };

  const closeSeasonModal = () => {
    setIsSeasonModalOpen(false);
    setEditingSeason(null);
    setSeasonError('');
  };

  const filteredProducts = products.filter(p => {
    if (selectedCategory !== 'All' && String(p.category) !== selectedCategory) return false;
    if (search && !p.product.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const productColumns: Column<Product>[] = [
    {
      header: 'Товар',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-r12 bg-brand-light-gray flex items-center justify-center text-lg shrink-0">
            ☕
          </div>
          <div>
            <p className="font-bold text-brand-dark">{row.product}</p>
            <span className="text-[10px] text-brand-gray-blue font-semibold">{row.category_name}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'Цены (S / M / L)',
      accessor: row => (
        <div className="flex items-center gap-2 text-xs font-bold text-brand-dark">
          {row.price_s && <span className="bg-slate-100 px-2 py-0.5 rounded">S: {row.price_s} ₽</span>}
          {row.price_m && <span className="bg-slate-100 px-2 py-0.5 rounded">M: {row.price_m} ₽</span>}
          {row.price_l && <span className="bg-slate-100 px-2 py-0.5 rounded">L: {row.price_l} ₽</span>}
          {!row.price_s && !row.price_m && !row.price_l && <span>{row.price} ₽</span>}
        </div>
      ),
    },
    {
      header: 'Температура',
      accessor: row => (
        <span className="text-xs font-semibold text-brand-dark-blue flex items-center gap-1">
          {row.temperature_type === 'Hot' && <Flame className="w-3.5 h-3.5 text-brand-red" />}
          {row.temperature_type === 'Cold' && <Snowflake className="w-3.5 h-3.5 text-brand-blue" />}
          {row.temperature_type === 'All' && <Sparkles className="w-3.5 h-3.5 text-brand-orange" />}
          {row.temperature_type === 'Hot' ? 'Горячий' : row.temperature_type === 'Cold' ? 'Холодный' : 'Все виды'}
        </span>
      ),
    },
    {
      header: 'Меню',
      accessor: row => (
        <Badge variant={row.which_menu === 'season_menu' ? 'purple' : 'neutral'}>
          {row.which_menu === 'main_menu' ? 'Основное' : row.which_menu === 'season_menu' ? 'Сезонное' : 'Оба'}
        </Badge>
      ),
    },
    {
      header: 'Доступность (Стоп-лист)',
      accessor: row => (
        <button
          onClick={e => handleToggleAvailability(row.id, e)}
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-extrabold transition-all ${
            row.availability
              ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
              : 'bg-red-50 text-brand-red hover:bg-red-100'
          }`}
        >
          {row.availability ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>В наличии</span>
            </>
          ) : (
            <>
              <XCircle className="w-3.5 h-3.5" />
              <span>Стоп-лист</span>
            </>
          )}
        </button>
      ),
    },
    {
      header: 'Действия',
      align: 'right',
      accessor: row => (
        <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => {
              setEditingProduct({
                ...row,
                addons: row.addons || row.addons_details?.map(a => a.id) || [],
              });
              setIsProductDrawerOpen(true);
            }}
            className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
            title="Редактировать"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleDeleteProduct(row.id)}
            className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
            title="Удалить"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {!canManage && (
        <div className="flex items-start gap-3 rounded-r12 border border-brand-orange/30 bg-brand-orange/10 px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-brand-orange shrink-0 mt-0.5" />
          <p className="text-xs font-semibold text-brand-dark">
            Кофейня не выбрана — показано меню всех точек сети, создание и правка отключены.
            <span className="font-medium text-brand-dark-blue"> Выберите точку в шапке, чтобы работать с её меню.</span>
          </p>
        </div>
      )}

      {/* Top Header Tabs & Action button */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <Tabs
          tabs={[
            { id: 'products', label: 'Товары', count: products.length },
            { id: 'categories', label: 'Категории', count: categories.length },
            { id: 'seasons', label: 'Сезонное меню', count: seasonMenus.length },
            { id: 'addons', label: 'Добавки', count: addons.length },
            { id: 'flavors', label: 'Вкусы добавок', count: flavors.length },
          ]}
          activeTab={activeMenuTab}
          onChange={t => setActiveMenuTab(t as any)}
        />

        <div className="flex items-center gap-2">
          {activeMenuTab === 'products' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              disabled={!canManage}
              title={canManage ? undefined : 'Сначала выберите кофейню'}
              onClick={() => {
                // Цены не предзаполняем: пустая цена размера означает, что
                // размер в приложении недоступен, и это должен решать
                // администратор, а не значение по умолчанию.
                setProductErrors({});
                setEditingProduct({
                  product: '',
                  category: undefined,
                  price_s: null,
                  price_m: null,
                  price_l: null,
                  product_type: 'coffee',
                  temperature_type: 'All',
                  can_be_hot_and_cold: true,
                  which_menu: 'main_menu',
                  availability: true,
                  addons: [],
                });
                setIsProductDrawerOpen(true);
              }}
            >
              Добавить товар
            </Button>
          )}

          {activeMenuTab === 'categories' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              disabled={!canManage}
              title={canManage ? undefined : 'Сначала выберите кофейню'}
              onClick={() => setIsCategoryModalOpen(true)}
            >
              Новая категория
            </Button>
          )}

          {activeMenuTab === 'seasons' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              disabled={!canManage}
              title={canManage ? undefined : 'Сначала выберите кофейню'}
              onClick={() => {
                setSeasonError('');
                setEditingSeason({
                  season: 'winter',
                  seasonal_section: '',
                  is_active: true,
                  color: '',
                  icon: '',
                  products: [],
                });
                setIsSeasonModalOpen(true);
              }}
            >
              Новый раздел
            </Button>
          )}

          {activeMenuTab === 'addons' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              disabled={!canManage}
              title={canManage ? undefined : 'Сначала выберите кофейню'}
              onClick={() => {
                setAddonErrors({});
                setEditingAddon({ name: '', price: null, description: '', flavors: [] });
                setIsAddonModalOpen(true);
              }}
            >
              Добавить добавку
            </Button>
          )}

          {activeMenuTab === 'flavors' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              disabled={!canManage}
              title={canManage ? undefined : 'Сначала выберите кофейню'}
              onClick={() => {
                setFlavorError('');
                setEditingFlavor({ name: '' });
                setIsFlavorModalOpen(true);
              }}
            >
              Добавить вкус
            </Button>
          )}
        </div>
      </div>

      {/* TAB 1: PRODUCTS */}
      {activeMenuTab === 'products' && (
        <>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="w-full sm:w-72">
              <Input
                placeholder="Поиск по названию..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                leftIcon={<Search className="w-4 h-4" />}
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              <button
                onClick={() => setSelectedCategory('All')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
                  selectedCategory === 'All'
                    ? 'bg-brand-lime text-brand-dark shadow-sm'
                    : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
                }`}
              >
                Все категории
              </button>
              {categories.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(String(cat.id))}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
                    selectedCategory === String(cat.id)
                      ? 'bg-brand-lime text-brand-dark shadow-sm'
                      : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
                  }`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>

          <Table
            columns={productColumns}
            data={filteredProducts}
            keyExtractor={p => p.id}
            onRowClick={p => {
              setEditingProduct({
                ...p,
                addons: p.addons || p.addons_details?.map(a => a.id) || [],
              });
              setIsProductDrawerOpen(true);
            }}
            isLoading={isLoading}
            emptyMessage="Товары не найдены"
          />
        </>
      )}

      {/* TAB 2: CATEGORIES */}
      {activeMenuTab === 'categories' && (
        <Table
          columns={[
            { header: 'ID', accessor: r => `#${r.id}` },
            { header: 'Название категории', accessor: r => <span className="font-bold text-brand-dark">{r.name}</span> },
            {
              header: 'Тип меню',
              accessor: r => (
                <Badge variant={r.which_menu === 'season_menu' ? 'purple' : 'neutral'}>
                  {r.which_menu === 'main_menu' ? 'Основное' : r.which_menu === 'season_menu' ? 'Сезонное' : 'Оба'}
                </Badge>
              ),
            },
            {
              header: 'Оформление',
              accessor: r => (
                <div className="flex items-center gap-2 text-xs text-brand-dark-blue font-semibold">
                  <span
                    className="w-4 h-4 rounded shrink-0 border border-slate-200"
                    style={{ backgroundColor: r.color || 'transparent' }}
                  />
                  <span>{r.color || 'из набора'}</span>
                </div>
              ),
            },
            { header: 'Количество товаров', accessor: r => `${r.products_count || 0} поз.` },
          ]}
          data={categories}
          keyExtractor={c => c.id}
          isLoading={isLoading}
          emptyMessage="Категории не созданы"
        />
      )}

      {/* TAB 3: SEASON MENU */}
      {activeMenuTab === 'seasons' && (
        <Table
          columns={[
            {
              header: 'Сезон',
              accessor: r => (
                <Badge variant={r.is_active ? 'purple' : 'neutral'}>
                  {r.season_display || SEASON_LABELS[r.season]}
                </Badge>
              ),
            },
            {
              header: 'Раздел',
              accessor: r => (
                <div className="flex items-center gap-2">
                  <span
                    className="w-4 h-4 rounded shrink-0 border border-slate-200"
                    style={{ backgroundColor: r.color || 'transparent' }}
                    title={r.color || 'Цвет из набора приложения'}
                  />
                  <div>
                    <p className="font-bold text-brand-dark">{r.seasonal_section}</p>
                    <span className="text-[10px] text-brand-gray-blue font-semibold">
                      {r.products_count || 0} поз.
                    </span>
                  </div>
                </div>
              ),
            },
            {
              header: 'Показ в приложении',
              accessor: r => (
                <button
                  onClick={() => handleToggleSeasonActive(r)}
                  className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-extrabold transition-all ${
                    r.is_active
                      ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                      : 'bg-slate-100 text-brand-gray-blue hover:bg-slate-200'
                  }`}
                >
                  {r.is_active ? (
                    <>
                      <Eye className="w-3.5 h-3.5" />
                      <span>Показывается</span>
                    </>
                  ) : (
                    <>
                      <EyeOff className="w-3.5 h-3.5" />
                      <span>Скрыт</span>
                    </>
                  )}
                </button>
              ),
            },
            {
              header: 'Действия',
              align: 'right',
              accessor: r => (
                <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => {
                      setSeasonError('');
                      setEditingSeason({ ...r, products: r.products || [] });
                      setIsSeasonModalOpen(true);
                    }}
                    className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
                    title="Редактировать"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteSeason(r.id)}
                    className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
                    title="Удалить"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ),
            },
          ]}
          data={seasonMenus}
          keyExtractor={m => m.id}
          isLoading={isLoading}
          emptyMessage="Сезонные разделы не созданы. Каждая точка держит свои наборы на все четыре времени года."
        />
      )}

      {/* TAB 4: ADDONS */}
      {activeMenuTab === 'addons' && (
        <Table
          columns={[
            { header: 'ID', accessor: r => `#${r.id}` },
            {
              header: 'Название добавки',
              accessor: r => (
                <div>
                  <p className="font-bold text-brand-dark">{r.name}</p>
                  {r.description && <span className="text-[10px] text-brand-gray-blue">{r.description}</span>}
                </div>
              ),
            },
            {
              header: 'Стоимость (₽)',
              accessor: r => <span className="font-extrabold text-brand-green-text">+{r.price} ₽</span>,
            },
            {
              header: 'Вкусы / Сиропы',
              accessor: r => (
                r.flavors_details && r.flavors_details.length > 0 ? (
                  <span className="text-xs text-brand-dark-blue">
                    {r.flavors_details.map(f => f.name).join(', ')}
                  </span>
                ) : (
                  <span className="text-xs text-brand-gray-blue">—</span>
                )
              ),
            },
            {
              header: 'Действия',
              align: 'right',
              accessor: r => (
                <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => {
                      setEditingAddon({
                        ...r,
                        flavors: r.flavors || r.flavors_details?.map(f => f.id) || [],
                      });
                      setIsAddonModalOpen(true);
                    }}
                    className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteAddon(r.id)}
                    className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ),
            },
          ]}
          data={addons}
          keyExtractor={a => a.id}
          isLoading={isLoading}
          emptyMessage="Добавки не созданы"
        />
      )}

      {/* TAB 5: FLAVORS */}
      {activeMenuTab === 'flavors' && (
        <Table
          columns={[
            { header: 'ID', accessor: r => `#${r.id}` },
            {
              header: 'Вкус добавки / Сироп',
              accessor: r => (
                <div className="flex items-center gap-2">
                  <Droplets className="w-4 h-4 text-brand-purple" />
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
                      setEditingFlavor(r);
                      setIsFlavorModalOpen(true);
                    }}
                    className="w-8 h-8 rounded-lg text-brand-dark-blue hover:text-brand-dark hover:bg-slate-100 flex items-center justify-center transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteFlavor(r.id)}
                    className="w-8 h-8 rounded-lg text-brand-gray-blue hover:text-brand-red hover:bg-red-50 flex items-center justify-center transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ),
            },
          ]}
          data={flavors}
          keyExtractor={f => f.id}
          isLoading={isLoading}
          emptyMessage="Вкусы добавок не созданы"
        />
      )}

      {/* PRODUCT DRAWER (Create / Edit) */}
      {isProductDrawerOpen && editingProduct && (
        <Drawer
          isOpen={isProductDrawerOpen}
          onClose={closeProductDrawer}
          title={editingProduct.id ? 'Редактирование товара' : 'Новый товар'}
          subtitle="Заполните информацию о товаре"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={closeProductDrawer}
                disabled={isSavingProduct}
              >
                Отмена
              </Button>
              <Button
                size="sm"
                onClick={handleSaveProduct}
                isLoading={isSavingProduct}
                disabled={isSavingProduct || !editingProduct.product?.trim()}
              >
                {editingProduct.id ? 'Сохранить изменения' : 'Создать товар'}
              </Button>
            </div>
          }
        >
          <div className="space-y-4 font-montserrat">
            <Combobox
              label="Название товара"
              placeholder="Например: Капучино с корицей"
              value={editingProduct.product || ''}
              suggestions={products.map(p => p.product)}
              error={productErrors.product}
              onChange={value => {
                setProductErrors(prev => ({ ...prev, product: '' }));
                setEditingProduct({ ...editingProduct, product: value });
              }}
              requiredAsterisk
            />

            <Select
              label="Категория"
              value={editingProduct.category ?? ''}
              error={productErrors.category}
              requiredAsterisk
              onChange={e => {
                setProductErrors(prev => ({ ...prev, category: '' }));
                setEditingProduct({
                  ...editingProduct,
                  category: e.target.value ? Number(e.target.value) : undefined,
                });
              }}
              options={[
                { value: '', label: categories.length ? '— выберите категорию —' : 'Категорий пока нет' },
                ...categories.map(c => ({ value: c.id, label: c.name })),
              ]}
            />

            <div className="space-y-1.5">
              <div className="grid grid-cols-1 xs:grid-cols-3 gap-3">
                <Input
                  label="Цена S (₽)"
                  type="number"
                  min={0}
                  step="1"
                  placeholder="нет размера"
                  value={editingProduct.price_s ?? ''}
                  onChange={e => {
                    setProductErrors(prev => ({ ...prev, prices: '' }));
                    setEditingProduct({ ...editingProduct, price_s: parsePriceInput(e.target.value) });
                  }}
                />
                <Input
                  label="Цена M (₽)"
                  type="number"
                  min={0}
                  step="1"
                  placeholder="нет размера"
                  value={editingProduct.price_m ?? ''}
                  onChange={e => {
                    setProductErrors(prev => ({ ...prev, prices: '' }));
                    setEditingProduct({ ...editingProduct, price_m: parsePriceInput(e.target.value) });
                  }}
                />
                <Input
                  label="Цена L (₽)"
                  type="number"
                  min={0}
                  step="1"
                  placeholder="нет размера"
                  value={editingProduct.price_l ?? ''}
                  onChange={e => {
                    setProductErrors(prev => ({ ...prev, prices: '' }));
                    setEditingProduct({ ...editingProduct, price_l: parsePriceInput(e.target.value) });
                  }}
                />
              </div>
              {productErrors.prices ? (
                <p className="text-xs text-brand-red font-medium">{productErrors.prices}</p>
              ) : (
                <p className="text-xs text-brand-gray-blue font-medium">
                  Пустая цена — размер недоступен в приложении.
                </p>
              )}
            </div>

            <Select
              label="Тип продукта"
              value={editingProduct.product_type || 'coffee'}
              onChange={e => setEditingProduct({ ...editingProduct, product_type: e.target.value as ProductType })}
              options={[
                { value: 'coffee', label: 'Кофе' },
                { value: 'tea', label: 'Чай' },
                { value: 'matcha', label: 'Матча' },
                { value: 'cocktail', label: 'Коктейль / Смузи' },
                { value: 'ice_cream', label: 'Мороженое' },
                { value: 'fresh_juice', label: 'Свежевыжатый сок' },
              ]}
            />

            <Select
              label="Температурный режим"
              value={editingProduct.temperature_type || 'All'}
              onChange={e => setEditingProduct({ ...editingProduct, temperature_type: e.target.value as TemperatureType })}
              options={[
                { value: 'All', label: 'Все виды (Горячий / Холодный)' },
                { value: 'Hot', label: 'Только горячий' },
                { value: 'Cold', label: 'Только холодный' },
              ]}
            />

            <Select
              label="Размещение в меню"
              value={editingProduct.which_menu || 'main_menu'}
              onChange={e => setEditingProduct({ ...editingProduct, which_menu: e.target.value as any })}
              options={[
                { value: 'main_menu', label: 'Основное меню' },
                { value: 'season_menu', label: 'Сезонное меню' },
                { value: 'both', label: 'Оба меню' },
              ]}
            />

            {/* Link Addons to Product */}
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="block text-xs font-semibold text-brand-dark-blue">
                Доступные добавки для этого товара
              </label>
              {addons.length === 0 ? (
                <p className="text-xs text-brand-gray-blue">Добавки еще не созданы. Вы можете добавить их во вкладке «Добавки».</p>
              ) : (
                <div className="flex flex-wrap gap-2 pt-1">
                  {addons.map(addon => {
                    const isSelected = (editingProduct.addons || []).includes(addon.id);
                    return (
                      <button
                        key={addon.id}
                        type="button"
                        onClick={() => {
                          const current = editingProduct.addons || [];
                          const next = isSelected
                            ? current.filter(id => id !== addon.id)
                            : [...current, addon.id];
                          setEditingProduct({ ...editingProduct, addons: next });
                        }}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border',
                          isSelected
                            ? 'bg-brand-lime text-brand-dark border-brand-lime font-bold shadow-sm'
                            : 'bg-brand-light-gray text-brand-dark-blue border-slate-200/80 hover:bg-slate-200/60'
                        )}
                      >
                        {addon.name} (+{addon.price} ₽)
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </Drawer>
      )}

      {/* CATEGORY MODAL */}
      <Modal
        isOpen={isCategoryModalOpen}
        onClose={closeCategoryModal}
        title="Новая категория меню"
      >
        <div className="space-y-4">
          <Combobox
            label="Название категории"
            placeholder="Например: Сезонные лимонады"
            value={newCategoryName}
            suggestions={categories.map(c => c.name)}
            error={categoryError}
            onChange={value => {
              setCategoryError('');
              setNewCategoryName(value);
            }}
            requiredAsterisk
          />
          <Select
            label="В каком меню отображать"
            value={newCategoryMenu}
            onChange={e => setNewCategoryMenu(e.target.value as any)}
            options={[
              { value: 'main_menu', label: 'Основное меню' },
              { value: 'season_menu', label: 'Сезонное меню' },
              { value: 'both', label: 'Оба меню' },
            ]}
          />
          <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
            <div className="w-full space-y-1.5">
              <label className="block text-xs font-semibold text-brand-dark-blue">
                Цвет плитки
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={newCategoryColor || '#FFB800'}
                  onChange={e => setNewCategoryColor(e.target.value)}
                  className="h-[50px] w-16 rounded-r12 border border-slate-200 bg-white p-1 cursor-pointer"
                />
                <Button variant="ghost" size="sm" onClick={() => setNewCategoryColor('')}>
                  Из набора
                </Button>
              </div>
              <p className="text-xs text-brand-gray-blue font-medium">
                {newCategoryColor
                  ? `Плитка будет ${newCategoryColor}`
                  : 'Приложение возьмёт цвет из своего набора'}
              </p>
            </div>
            <Select
              label="Иконка плитки"
              value={newCategoryIcon}
              onChange={e => setNewCategoryIcon(e.target.value)}
              options={MENU_ICONS}
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={closeCategoryModal}>
              Отмена
            </Button>
            <Button size="sm" onClick={handleCreateCategory}>
              Создать категорию
            </Button>
          </div>
        </div>
      </Modal>

      {/* SEASON MENU MODAL */}
      {isSeasonModalOpen && editingSeason && (
        <Modal
          isOpen={isSeasonModalOpen}
          onClose={closeSeasonModal}
          title={editingSeason.id ? 'Сезонный раздел' : 'Новый сезонный раздел'}
        >
          <div className="space-y-4">
            <Select
              label="Время года"
              value={editingSeason.season || 'winter'}
              onChange={e => setEditingSeason({ ...editingSeason, season: e.target.value as Season })}
              options={(Object.keys(SEASON_LABELS) as Season[]).map(season => ({
                value: season,
                label: SEASON_LABELS[season],
              }))}
            />

            <Combobox
              label="Название раздела"
              placeholder="Например: Зимние согревающие"
              value={editingSeason.seasonal_section || ''}
              suggestions={seasonMenus.map(m => m.seasonal_section)}
              error={seasonError}
              onChange={value => {
                setSeasonError('');
                setEditingSeason({ ...editingSeason, seasonal_section: value });
              }}
              requiredAsterisk
            />

            <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
              <div className="w-full space-y-1.5">
                <label className="block text-xs font-semibold text-brand-dark-blue">
                  Цвет плитки
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={editingSeason.color || '#CFEBFF'}
                    onChange={e => setEditingSeason({ ...editingSeason, color: e.target.value })}
                    className="h-[50px] w-16 rounded-r12 border border-slate-200 bg-white p-1 cursor-pointer"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditingSeason({ ...editingSeason, color: '' })}
                  >
                    Из набора
                  </Button>
                </div>
                <p className="text-xs text-brand-gray-blue font-medium">
                  {editingSeason.color
                    ? `Плитка будет ${editingSeason.color}`
                    : 'Приложение возьмёт цвет из своего набора'}
                </p>
              </div>

              <Select
                label="Иконка плитки"
                value={editingSeason.icon || ''}
                onChange={e => setEditingSeason({ ...editingSeason, icon: e.target.value })}
                options={MENU_ICONS}
              />
            </div>

            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={editingSeason.is_active ?? true}
                onChange={e => setEditingSeason({ ...editingSeason, is_active: e.target.checked })}
                className="w-4 h-4 accent-brand-lime cursor-pointer"
              />
              <span className="text-xs font-semibold text-brand-dark">
                Показывать раздел в приложении
              </span>
            </label>
            <p className="-mt-2 text-xs text-brand-gray-blue font-medium">
              Наборы всех четырёх сезонов хранятся постоянно — переключается только показ.
            </p>

            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="block text-xs font-semibold text-brand-dark-blue">
                Товары раздела
              </label>
              {seasonProducts.length === 0 ? (
                <p className="text-xs text-brand-gray-blue">
                  Нет товаров с размещением «Сезонное меню» или «Оба меню». Поставьте его товару
                  во вкладке «Товары».
                </p>
              ) : (
                <div className="flex flex-wrap gap-2 pt-1 max-h-48 overflow-y-auto">
                  {seasonProducts.map(product => {
                    const isSelected = (editingSeason.products || []).includes(product.id);
                    return (
                      <button
                        key={product.id}
                        type="button"
                        onClick={() => {
                          const current = editingSeason.products || [];
                          const next = isSelected
                            ? current.filter(id => id !== product.id)
                            : [...current, product.id];
                          setEditingSeason({ ...editingSeason, products: next });
                        }}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border',
                          isSelected
                            ? 'bg-brand-lime text-brand-dark border-brand-lime font-bold shadow-sm'
                            : 'bg-brand-light-gray text-brand-dark-blue border-slate-200/80 hover:bg-slate-200/60'
                        )}
                      >
                        {product.product}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={closeSeasonModal}>
                Отмена
              </Button>
              <Button size="sm" onClick={handleSaveSeason}>
                {editingSeason.id ? 'Сохранить изменения' : 'Создать раздел'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* ADDON MODAL */}
      {isAddonModalOpen && (
        <Modal
          isOpen={isAddonModalOpen}
          onClose={closeAddonModal}
          title={editingAddon?.id ? 'Редактировать добавку' : 'Новая добавка'}
        >
          <div className="space-y-4">
            <Combobox
              label="Название добавки"
              placeholder="Например: Сиропы или Растительное молоко"
              value={editingAddon?.name || ''}
              suggestions={addons.map(a => a.name)}
              error={addonErrors.name}
              onChange={value => {
                setAddonErrors(prev => ({ ...prev, name: '' }));
                setEditingAddon({ ...editingAddon, name: value });
              }}
              requiredAsterisk
            />
            <Input
              label="Описание"
              placeholder="Краткое описание добавки"
              value={editingAddon?.description || ''}
              onChange={e => setEditingAddon({ ...editingAddon, description: e.target.value })}
            />
            <Input
              label="Стоимость добавки (₽)"
              type="number"
              min={0}
              step="1"
              value={editingAddon?.price ?? ''}
              error={addonErrors.price}
              onChange={e => {
                setAddonErrors(prev => ({ ...prev, price: '' }));
                setEditingAddon({ ...editingAddon, price: parsePriceInput(e.target.value) });
              }}
              requiredAsterisk
            />

            {/* Link Flavors to Addon */}
            {flavors.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <label className="block text-xs font-semibold text-brand-dark-blue">
                  Привязать вкусы / сиропы к этой добавке
                </label>
                <p className="text-xs text-brand-gray-blue font-medium">
                  Вкус денег не добавляет: клиент платит за саму добавку и один
                  раз. Но добавку с вкусами нельзя заказать, не выбрав вкус —
                  она работает как категория.
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {flavors.map(flavor => {
                    const isSelected = (editingAddon?.flavors || []).includes(flavor.id);
                    return (
                      <button
                        key={flavor.id}
                        type="button"
                        onClick={() => {
                          const current = editingAddon?.flavors || [];
                          const next = isSelected
                            ? current.filter(id => id !== flavor.id)
                            : [...current, flavor.id];
                          setEditingAddon({ ...editingAddon, flavors: next });
                        }}
                        className={cn(
                          'px-2.5 py-1 rounded-md text-xs font-semibold transition-all border',
                          isSelected
                            ? 'bg-brand-purple text-white border-brand-purple'
                            : 'bg-slate-100 text-brand-dark-blue border-slate-200 hover:bg-slate-200'
                        )}
                      >
                        {flavor.name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={closeAddonModal}>
                Отмена
              </Button>
              <Button size="sm" onClick={handleSaveAddon}>
                {editingAddon?.id ? 'Сохранить изменения' : 'Создать добавку'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* FLAVOR MODAL */}
      {isFlavorModalOpen && (
        <Modal
          isOpen={isFlavorModalOpen}
          onClose={closeFlavorModal}
          title={editingFlavor?.id ? 'Редактировать вкус' : 'Новый вкус / сироп'}
        >
          <div className="space-y-4">
            <Combobox
              label="Название вкуса"
              placeholder="Например: Соленая карамель или Лаванда"
              value={editingFlavor?.name || ''}
              suggestions={flavors.map(f => f.name)}
              error={flavorError}
              onChange={value => {
                setFlavorError('');
                setEditingFlavor({ ...editingFlavor, name: value });
              }}
              requiredAsterisk
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={closeFlavorModal}>
                Отмена
              </Button>
              <Button size="sm" onClick={handleSaveFlavor}>
                {editingFlavor?.id ? 'Сохранить изменения' : 'Создать вкус'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
