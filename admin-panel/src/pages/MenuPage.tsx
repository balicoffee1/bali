import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { Product, Category, Addon, AdditiveFlavor, ProductType, TemperatureType } from '../types';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Tabs } from '../components/ui/Tabs';
import { Badge } from '../components/ui/Badge';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Table, Column } from '../components/ui/Table';
import {
  Plus, Search, Edit2, Trash2, CheckCircle2, XCircle,
  Coffee, Flame, Snowflake, Sparkles, Droplets, Tag
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

  // Addon modal state
  const [isAddonModalOpen, setIsAddonModalOpen] = useState(false);
  const [editingAddon, setEditingAddon] = useState<Partial<Addon> | null>(null);

  // Flavor modal state
  const [isFlavorModalOpen, setIsFlavorModalOpen] = useState(false);
  const [editingFlavor, setEditingFlavor] = useState<Partial<AdditiveFlavor> | null>(null);

  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [selectedShopId]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [prods, cats, adds, flavs] = await Promise.all([
        api.getProducts(selectedShopId || undefined),
        api.getCategories(selectedShopId || undefined),
        api.getAddons(selectedShopId || undefined),
        api.getFlavors(selectedShopId || undefined),
      ]);
      setProducts(prods);
      setCategories(cats);
      setAddons(adds);
      setFlavors(flavs);
    } finally {
      setIsLoading(false);
    }
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
    if (!editingProduct || !editingProduct.product?.trim()) {
      addToast({ type: 'error', title: 'Заполните поля', message: 'Укажите название товара' });
      return;
    }

    setIsSavingProduct(true);
    try {
      const payload: Partial<Product> = {
        ...editingProduct,
        coffee_shop: selectedShopId || 1,
        category: editingProduct.category || categories[0]?.id || 1,
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
    if (!newCategoryName.trim()) return;
    try {
      const cat = await api.createCategory({
        name: newCategoryName,
        which_menu: newCategoryMenu,
        coffee_shop: selectedShopId || 1,
      });
      setCategories(prev => [...prev, cat]);
      setIsCategoryModalOpen(false);
      setNewCategoryName('');
      addToast({ type: 'success', title: 'Категория создана', message: cat.name });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось создать категорию' });
    }
  };

  // --- Addon Save ---
  const handleSaveAddon = async () => {
    if (!editingAddon || !editingAddon.name) return;
    try {
      const saved = await api.saveAddon({
        ...editingAddon,
        coffee_shop: selectedShopId || 1,
      });
      setAddons(prev => {
        const exists = prev.some(a => a.id === saved.id);
        if (exists) return prev.map(a => (a.id === saved.id ? saved : a));
        return [...prev, saved];
      });
      setIsAddonModalOpen(false);
      setEditingAddon(null);
      addToast({ type: 'success', title: 'Добавка сохранена', message: saved.name });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось сохранить добавку' });
    }
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
    if (!editingFlavor || !editingFlavor.name) return;
    try {
      const saved = await api.saveFlavor({
        ...editingFlavor,
        coffee_shop: selectedShopId || 1,
      });
      setFlavors(prev => {
        const exists = prev.some(f => f.id === saved.id);
        if (exists) return prev.map(f => (f.id === saved.id ? saved : f));
        return [...prev, saved];
      });
      setIsFlavorModalOpen(false);
      setEditingFlavor(null);
      addToast({ type: 'success', title: 'Вкус сохранен', message: saved.name });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось сохранить вкус' });
    }
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
      {/* Top Header Tabs & Action button */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <Tabs
          tabs={[
            { id: 'products', label: 'Товары', count: products.length },
            { id: 'categories', label: 'Категории', count: categories.length },
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
              onClick={() => {
                setEditingProduct({
                  product: '',
                  category: categories[0]?.id || 1,
                  price_s: 160,
                  price_m: 190,
                  price_l: 230,
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
              onClick={() => setIsCategoryModalOpen(true)}
            >
              Новая категория
            </Button>
          )}

          {activeMenuTab === 'addons' && (
            <Button
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => {
                setEditingAddon({ name: '', price: 40, description: '', flavors: [] });
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
              onClick={() => {
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
            { header: 'Количество товаров', accessor: r => `${r.products_count || 0} поз.` },
          ]}
          data={categories}
          keyExtractor={c => c.id}
          isLoading={isLoading}
          emptyMessage="Категории не созданы"
        />
      )}

      {/* TAB 3: ADDONS */}
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

      {/* TAB 4: FLAVORS */}
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
          onClose={() => {
            setIsProductDrawerOpen(false);
            setEditingProduct(null);
          }}
          title={editingProduct.id ? 'Редактирование товара' : 'Новый товар'}
          subtitle="Заполните информацию о товаре"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsProductDrawerOpen(false);
                  setEditingProduct(null);
                }}
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
            <Input
              label="Название товара"
              placeholder="Например: Капучино с корицей"
              value={editingProduct.product || ''}
              onChange={e => setEditingProduct({ ...editingProduct, product: e.target.value })}
              requiredAsterisk
            />

            <Select
              label="Категория"
              value={editingProduct.category || ''}
              onChange={e => setEditingProduct({ ...editingProduct, category: Number(e.target.value) })}
              options={categories.map(c => ({ value: c.id, label: c.name }))}
            />

            <div className="grid grid-cols-3 gap-3">
              <Input
                label="Цена S (₽)"
                type="number"
                value={editingProduct.price_s || ''}
                onChange={e => setEditingProduct({ ...editingProduct, price_s: Number(e.target.value) })}
              />
              <Input
                label="Цена M (₽)"
                type="number"
                value={editingProduct.price_m || ''}
                onChange={e => setEditingProduct({ ...editingProduct, price_m: Number(e.target.value) })}
              />
              <Input
                label="Цена L (₽)"
                type="number"
                value={editingProduct.price_l || ''}
                onChange={e => setEditingProduct({ ...editingProduct, price_l: Number(e.target.value) })}
              />
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
                            ? 'bg-brand-lime text-brand-dark border-brand-lime font-bold shadow-xs'
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
        onClose={() => setIsCategoryModalOpen(false)}
        title="Новая категория меню"
      >
        <div className="space-y-4">
          <Input
            label="Название категории"
            placeholder="Например: Сезонные лимонады"
            value={newCategoryName}
            onChange={e => setNewCategoryName(e.target.value)}
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
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setIsCategoryModalOpen(false)}>
              Отмена
            </Button>
            <Button size="sm" onClick={handleCreateCategory}>
              Создать категорию
            </Button>
          </div>
        </div>
      </Modal>

      {/* ADDON MODAL */}
      {isAddonModalOpen && (
        <Modal
          isOpen={isAddonModalOpen}
          onClose={() => {
            setIsAddonModalOpen(false);
            setEditingAddon(null);
          }}
          title={editingAddon?.id ? 'Редактировать добавку' : 'Новая добавка'}
        >
          <div className="space-y-4">
            <Input
              label="Название добавки"
              placeholder="Например: Сиропы или Растительное молоко"
              value={editingAddon?.name || ''}
              onChange={e => setEditingAddon({ ...editingAddon, name: e.target.value })}
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
              value={editingAddon?.price || ''}
              onChange={e => setEditingAddon({ ...editingAddon, price: Number(e.target.value) })}
              requiredAsterisk
            />

            {/* Link Flavors to Addon */}
            {flavors.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <label className="block text-xs font-semibold text-brand-dark-blue">
                  Привязать вкусы / сиропы к этой добавке
                </label>
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
              <Button variant="ghost" size="sm" onClick={() => setIsAddonModalOpen(false)}>
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
          onClose={() => {
            setIsFlavorModalOpen(false);
            setEditingFlavor(null);
          }}
          title={editingFlavor?.id ? 'Редактировать вкус' : 'Новый вкус / сироп'}
        >
          <div className="space-y-4">
            <Input
              label="Название вкуса"
              placeholder="Например: Соленая карамель или Лаванда"
              value={editingFlavor?.name || ''}
              onChange={e => setEditingFlavor({ ...editingFlavor, name: e.target.value })}
              requiredAsterisk
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setIsFlavorModalOpen(false)}>
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
