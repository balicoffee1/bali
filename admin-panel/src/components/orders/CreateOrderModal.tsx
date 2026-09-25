import React, { useState, useEffect, useMemo } from 'react';
import {
  CoffeeShop, Product, Addon, AdditiveFlavor, User, Order,
  OrderStatus, PaymentStatus, CreateOrderPayload, CreateOrderItemPayload
} from '../../types';
import { api } from '../../api/client';
import { useApp } from '../../context/AppContext';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { PhoneInput } from '../ui/PhoneInput';
import {
  Plus, Trash2, ShoppingBag, Coffee, Minus, Search, Check,
  AlertCircle, Store, User as UserIcon, Sparkles, Phone
} from 'lucide-react';
import { cn } from '../../utils/cn';

interface OrderBuilderItem {
  id: string;
  product: Product;
  size: 'S' | 'M' | 'L';
  temperature_type?: 'Hot' | 'Cold' | null;
  addons: Addon[];
  flavors: AdditiveFlavor[];
  amount: number;
  unitPrice: number;
  totalPrice: number;
}

interface CreateOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOrderCreated: (order: Order) => void;
  initialShopId?: number | null;
}

export const CreateOrderModal: React.FC<CreateOrderModalProps> = ({
  isOpen,
  onClose,
  onOrderCreated,
  initialShopId,
}) => {
  const { addToast } = useApp();

  // Shops & Catalog data
  const [shops, setShops] = useState<CoffeeShop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<number>(initialShopId || 0);
  const [products, setProducts] = useState<Product[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [flavors, setFlavors] = useState<AdditiveFlavor[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);

  // Customer state
  const [customerMode, setCustomerMode] = useState<'guest' | 'user'>('guest');
  const [guestPhone, setGuestPhone] = useState('');
  const [guestName, setGuestName] = useState('');
  const [userSearch, setUserSearch] = useState('');
  const [usersList, setUsersList] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isSearchingUsers, setIsSearchingUsers] = useState(false);

  // Item builder state
  const [selectedProductId, setSelectedProductId] = useState<number | ''>('');
  const [selectedSize, setSelectedSize] = useState<'S' | 'M' | 'L'>('S');
  const [selectedTemp, setSelectedTemp] = useState<'Hot' | 'Cold'>('Hot');
  const [selectedAddonIds, setSelectedAddonIds] = useState<number[]>([]);
  const [selectedFlavorIds, setSelectedFlavorIds] = useState<number[]>([]);
  const [itemAmount, setItemAmount] = useState<number>(1);

  // Order items list & parameters
  const [orderItems, setOrderItems] = useState<OrderBuilderItem[]>([]);
  const [statusOrders, setStatusOrders] = useState<OrderStatus>('Waiting');
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>('Paid');
  const [clientComments, setClientComments] = useState('');
  const [staffComments, setStaffComments] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // 1. Initial load: shops
  useEffect(() => {
    if (!isOpen) return;
    api.getCoffeeShops().then(loadedShops => {
      setShops(loadedShops);
      if (initialShopId && loadedShops.some(s => s.id === initialShopId)) {
        setSelectedShopId(initialShopId);
      } else if (loadedShops.length > 0 && !selectedShopId) {
        setSelectedShopId(loadedShops[0].id);
      }
    });
  }, [isOpen, initialShopId]);

  // 2. Load shop catalog when shop changes
  useEffect(() => {
    if (!selectedShopId || !isOpen) return;
    setIsLoadingCatalog(true);
    setSelectedProductId('');
    setOrderItems([]);
    Promise.all([
      api.getProducts(selectedShopId),
      api.getAddons(selectedShopId),
      api.getFlavors(selectedShopId),
    ])
      .then(([prods, adds, flavs]) => {
        setProducts(prods.filter(p => p.availability !== false));
        setAddons(adds);
        setFlavors(flavs);
      })
      .finally(() => setIsLoadingCatalog(false));
  }, [selectedShopId, isOpen]);

  // 3. User search debounce
  useEffect(() => {
    if (customerMode !== 'user' || !userSearch.trim()) {
      setUsersList([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingUsers(true);
      try {
        const found = await api.getUsers(userSearch.trim(), undefined, 10);
        setUsersList(found);
      } finally {
        setIsSearchingUsers(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [userSearch, customerMode]);

  // Current active product in builder
  const currentProduct = useMemo(
    () => products.find(p => p.id === Number(selectedProductId)),
    [products, selectedProductId]
  );

  // Reset modifiers when changing product
  useEffect(() => {
    if (currentProduct) {
      // Find available size (default to S or first available)
      if (currentProduct.price_s !== null && currentProduct.price_s !== undefined) {
        setSelectedSize('S');
      } else if (currentProduct.price_m !== null && currentProduct.price_m !== undefined) {
        setSelectedSize('M');
      } else if (currentProduct.price_l !== null && currentProduct.price_l !== undefined) {
        setSelectedSize('L');
      } else {
        setSelectedSize('S');
      }
      setSelectedTemp(currentProduct.temperature_type === 'Cold' ? 'Cold' : 'Hot');
      setSelectedAddonIds([]);
      setSelectedFlavorIds([]);
      setItemAmount(1);
    }
  }, [currentProduct]);

  // Calculate unit price for current builder selection
  const currentUnitPrice = useMemo(() => {
    if (!currentProduct) return 0;
    let sizePrice = 0;
    if (selectedSize === 'S') sizePrice = Number(currentProduct.price_s ?? currentProduct.price ?? 0);
    else if (selectedSize === 'M') sizePrice = Number(currentProduct.price_m ?? currentProduct.price ?? 0);
    else if (selectedSize === 'L') sizePrice = Number(currentProduct.price_l ?? currentProduct.price ?? 0);

    const addonsCost = addons
      .filter(a => selectedAddonIds.includes(a.id))
      .reduce((sum, a) => sum + Number(a.price || 0), 0);

    return sizePrice + addonsCost;
  }, [currentProduct, selectedSize, selectedAddonIds, addons]);

  const handleAddCurrentItem = () => {
    if (!currentProduct) return;
    const chosenAddons = addons.filter(a => selectedAddonIds.includes(a.id));
    const chosenFlavors = flavors.filter(f => selectedFlavorIds.includes(f.id));

    const newItem: OrderBuilderItem = {
      id: `${currentProduct.id}-${selectedSize}-${selectedTemp}-${Date.now()}`,
      product: currentProduct,
      size: selectedSize,
      temperature_type: currentProduct.can_be_hot_and_cold || currentProduct.temperature_type === 'All' ? selectedTemp : null,
      addons: chosenAddons,
      flavors: chosenFlavors,
      amount: itemAmount,
      unitPrice: currentUnitPrice,
      totalPrice: currentUnitPrice * itemAmount,
    };

    setOrderItems(prev => [...prev, newItem]);
    setSelectedProductId('');
    setFormError(null);
  };

  const handleRemoveItem = (id: string) => {
    setOrderItems(prev => prev.filter(it => it.id !== id));
  };

  const handleAmountChange = (id: string, delta: number) => {
    setOrderItems(prev =>
      prev.map(it => {
        if (it.id === id) {
          const newAmount = Math.max(1, it.amount + delta);
          return {
            ...it,
            amount: newAmount,
            totalPrice: it.unitPrice * newAmount,
          };
        }
        return it;
      })
    );
  };

  // Total order price
  const orderSubtotal = useMemo(
    () => orderItems.reduce((sum, it) => sum + it.totalPrice, 0),
    [orderItems]
  );

  const handleSubmit = async () => {
    setFormError(null);

    if (!selectedShopId) {
      setFormError('Выберите кофейню.');
      return;
    }
    if (orderItems.length === 0) {
      setFormError('Добавьте хотя бы один товар в заказ.');
      return;
    }

    if (customerMode === 'user' && !selectedUser) {
      setFormError('Выберите зарегистрированного пользователя или переключитесь на ввод телефона гостя.');
      return;
    }
    if (customerMode === 'guest' && !guestPhone.trim()) {
      setFormError('Укажите номер телефона клиента.');
      return;
    }

    const payload: CreateOrderPayload = {
      coffee_shop: selectedShopId,
      items: orderItems.map(it => ({
        product: it.product.id,
        size: it.size,
        temperature_type: it.temperature_type,
        amount: it.amount,
        addons: it.addons.map(a => a.id),
        flavors: it.flavors.map(f => f.id),
      })),
      status_orders: statusOrders,
      payment_status: paymentStatus,
      client_comments: clientComments.trim() || undefined,
      staff_comments: staffComments.trim() || undefined,
    };

    if (customerMode === 'user' && selectedUser) {
      payload.user = selectedUser.id;
    } else {
      payload.user_phone = guestPhone.trim();
      payload.user_name = guestName.trim() || undefined;
    }

    setIsSubmitting(true);
    try {
      const created = await api.createOrder(payload);
      addToast({
        type: 'success',
        title: 'Заказ создан',
        message: `Заказ #${created.id} на сумму ${created.full_price} ₽ успешно создан`,
      });
      onOrderCreated(created);
      onClose();
    } catch (err: any) {
      const errMsg = err?.message || err?.details?.message || err?.details?.items || 'Не удалось создать заказ';
      setFormError(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Создание нового заказа"
      description="Оформление заказа от гостя или клиента на выбранной точке"
      maxWidth="xl"
    >
      <div className="space-y-6 pt-1 font-montserrat">
        {formError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-r12 flex items-center gap-2.5 text-xs text-brand-red font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{formError}</span>
          </div>
        )}

        {/* 1. Coffee Shop Selection */}
        <div className="bg-brand-light-gray p-4 rounded-r18 space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold text-brand-dark uppercase tracking-wider">
            <Store className="w-4 h-4 text-brand-dark-blue" />
            <span>Кофейня</span>
          </div>
          <Select
            value={selectedShopId}
            onChange={e => setSelectedShopId(Number(e.target.value))}
            options={shops.map(s => ({
              value: s.id,
              label: `${s.street}, ${s.building_number}${s.city_name ? ` (${s.city_name})` : ''}`,
            }))}
          />
        </div>

        {/* 2. Customer Section */}
        <div className="bg-white border border-slate-200 rounded-r18 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-brand-dark uppercase tracking-wider">
              <UserIcon className="w-4 h-4 text-brand-dark-blue" />
              <span>Клиент / Гость</span>
            </div>
            <div className="flex items-center bg-brand-light-gray p-0.5 rounded-lg text-xs font-bold">
              <button
                type="button"
                onClick={() => setCustomerMode('guest')}
                className={cn(
                  'px-3 py-1 rounded-md transition-all',
                  customerMode === 'guest' ? 'bg-white shadow-sm text-brand-dark' : 'text-brand-gray-blue hover:text-brand-dark'
                )}
              >
                Новый гость
              </button>
              <button
                type="button"
                onClick={() => setCustomerMode('user')}
                className={cn(
                  'px-3 py-1 rounded-md transition-all',
                  customerMode === 'user' ? 'bg-white shadow-sm text-brand-dark' : 'text-brand-gray-blue hover:text-brand-dark'
                )}
              >
                Постоянный клиент
              </button>
            </div>
          </div>

          {customerMode === 'guest' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <PhoneInput
                label="Телефон гостя"
                value={guestPhone}
                onChange={val => setGuestPhone(val)}
                requiredAsterisk
                placeholder="+7 (999) 000-00-00"
              />
              <Input
                label="Имя гостя (необязательно)"
                value={guestName}
                onChange={e => setGuestName(e.target.value)}
                placeholder="Например, Александр"
              />
            </div>
          ) : (
            <div className="space-y-2">
              <Input
                placeholder="Поиск по имени, телефону или логину..."
                value={userSearch}
                onChange={e => setUserSearch(e.target.value)}
                leftIcon={<Search className="w-4 h-4 text-brand-gray-blue" />}
              />
              {selectedUser ? (
                <div className="p-3 bg-brand-lime/10 border border-brand-lime/30 rounded-r12 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-brand-dark">{selectedUser.full_name || selectedUser.first_name}</p>
                    <p className="text-[11px] text-brand-gray-blue">{selectedUser.phone_number || selectedUser.login}</p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setSelectedUser(null)}>
                    Сменить
                  </Button>
                </div>
              ) : (
                usersList.length > 0 && (
                  <div className="max-h-40 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-r12 bg-white">
                    {usersList.map(u => (
                      <div
                        key={u.id}
                        onClick={() => {
                          setSelectedUser(u);
                          setUserSearch('');
                        }}
                        className="p-2.5 hover:bg-slate-50 cursor-pointer flex items-center justify-between text-xs"
                      >
                        <span className="font-bold text-brand-dark">{u.full_name || u.first_name}</span>
                        <span className="text-brand-gray-blue">{u.phone_number || u.login}</span>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          )}
        </div>

        {/* 3. Items Builder */}
        <div className="bg-white border border-slate-200 rounded-r18 p-4 space-y-4">
          <div className="flex items-center gap-2 text-xs font-bold text-brand-dark uppercase tracking-wider">
            <Coffee className="w-4 h-4 text-brand-dark-blue" />
            <span>Добавление позиций</span>
          </div>

          <div className="space-y-3">
            <Select
              label="Товар из меню"
              value={selectedProductId}
              onChange={e => setSelectedProductId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">-- Выберите товар из меню --</option>
              {products.map(p => (
                <option key={p.id} value={p.id}>
                  {p.product} (от {p.price_s || p.price || p.price_m || 0} ₽)
                </option>
              ))}
            </Select>

            {currentProduct && (
              <div className="p-3.5 bg-brand-light-gray rounded-r14 space-y-3 animate-fade-in text-xs">
                {/* Size choices */}
                <div>
                  <label className="block text-[11px] font-bold text-brand-gray-blue uppercase mb-1.5">Размер напитка / порция</label>
                  <div className="flex items-center gap-2">
                    {(['S', 'M', 'L'] as const).map(sz => {
                      const p = sz === 'S' ? currentProduct.price_s : sz === 'M' ? currentProduct.price_m : currentProduct.price_l;
                      if (p === null || p === undefined) return null;
                      return (
                        <button
                          key={sz}
                          type="button"
                          onClick={() => setSelectedSize(sz)}
                          className={cn(
                            'px-4 py-2 rounded-r10 font-bold border transition-all text-xs flex items-center gap-1.5',
                            selectedSize === sz
                              ? 'bg-brand-lime border-brand-lime text-brand-dark shadow-sm'
                              : 'bg-white border-slate-200 text-brand-dark hover:border-slate-300'
                          )}
                        >
                          <span>{sz}</span>
                          <span className="text-[10px] text-brand-dark-blue font-semibold">{p} ₽</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Temperature choices if available */}
                {(currentProduct.can_be_hot_and_cold || currentProduct.temperature_type === 'All') && (
                  <div>
                    <label className="block text-[11px] font-bold text-brand-gray-blue uppercase mb-1.5">Температура</label>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedTemp('Hot')}
                        className={cn(
                          'px-3.5 py-1.5 rounded-r10 font-bold border text-xs',
                          selectedTemp === 'Hot'
                            ? 'bg-brand-orange text-white border-brand-orange'
                            : 'bg-white border-slate-200 text-brand-dark'
                        )}
                      >
                        🔥 Горячий
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedTemp('Cold')}
                        className={cn(
                          'px-3.5 py-1.5 rounded-r10 font-bold border text-xs',
                          selectedTemp === 'Cold'
                            ? 'bg-brand-light-blue text-brand-dark border-brand-light-blue'
                            : 'bg-white border-slate-200 text-brand-dark'
                        )}
                      >
                        ❄️ Холодный
                      </button>
                    </div>
                  </div>
                )}

                {/* Addons selector */}
                {addons.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-bold text-brand-gray-blue uppercase mb-1.5">Добавки / Сиропы</label>
                    <div className="flex flex-wrap gap-2">
                      {addons.map(addon => {
                        const isSelected = selectedAddonIds.includes(addon.id);
                        return (
                          <button
                            key={addon.id}
                            type="button"
                            onClick={() => {
                              setSelectedAddonIds(prev =>
                                isSelected ? prev.filter(id => id !== addon.id) : [...prev, addon.id]
                              );
                            }}
                            className={cn(
                              'px-3 py-1.5 rounded-full border text-xs font-semibold flex items-center gap-1.5 transition-all',
                              isSelected
                                ? 'bg-brand-dark text-white border-brand-dark'
                                : 'bg-white border-slate-200 text-brand-dark hover:border-slate-300'
                            )}
                          >
                            <span>{addon.name}</span>
                            <span className="text-[10px] text-brand-lime font-bold">+{addon.price} ₽</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Flavors selector if syrups are chosen */}
                {flavors.length > 0 && selectedAddonIds.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-bold text-brand-gray-blue uppercase mb-1.5">Вкус сиропа</label>
                    <div className="flex flex-wrap gap-1.5">
                      {flavors.map(fl => {
                        const isSelected = selectedFlavorIds.includes(fl.id);
                        return (
                          <button
                            key={fl.id}
                            type="button"
                            onClick={() => {
                              setSelectedFlavorIds(prev =>
                                isSelected ? prev.filter(id => id !== fl.id) : [...prev, fl.id]
                              );
                            }}
                            className={cn(
                              'px-2.5 py-1 rounded-md text-[11px] font-medium border transition-all',
                              isSelected
                                ? 'bg-brand-lime text-brand-dark border-brand-lime font-bold'
                                : 'bg-white border-slate-200 text-brand-dark-blue'
                            )}
                          >
                            {fl.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Quantity and Add button */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-200/60">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-brand-dark">Количество:</span>
                    <div className="flex items-center bg-white border border-slate-200 rounded-lg">
                      <button
                        type="button"
                        onClick={() => setItemAmount(prev => Math.max(1, prev - 1))}
                        className="w-7 h-7 flex items-center justify-center text-brand-dark hover:bg-slate-50"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-8 text-center text-xs font-bold">{itemAmount}</span>
                      <button
                        type="button"
                        onClick={() => setItemAmount(prev => prev + 1)}
                        className="w-7 h-7 flex items-center justify-center text-brand-dark hover:bg-slate-50"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-sm font-extrabold text-brand-dark">
                      {currentUnitPrice * itemAmount} ₽
                    </span>
                    <Button size="sm" variant="dark" leftIcon={<Plus className="w-4 h-4" />} onClick={handleAddCurrentItem}>
                      Добавить в заказ
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Current order items table */}
          {orderItems.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs font-bold text-brand-dark">
                <span>Позиции в заказе ({orderItems.length})</span>
                <span className="text-brand-gray-blue text-[11px]">Итого за позиции: {orderSubtotal} ₽</span>
              </div>
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-r14 overflow-hidden">
                {orderItems.map(it => (
                  <div key={it.id} className="p-3 bg-white flex items-center justify-between text-xs">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-brand-dark">{it.product.product}</span>
                        <span className="px-1.5 py-0.5 bg-slate-100 rounded text-[10px] font-bold text-brand-dark-blue">
                          {it.size}
                        </span>
                        {it.temperature_type && (
                          <span className="text-[10px] text-brand-gray-blue">
                            {it.temperature_type === 'Hot' ? 'Горячий' : 'Холодный'}
                          </span>
                        )}
                      </div>
                      {it.addons.length > 0 && (
                        <p className="text-[11px] text-brand-gray-blue">
                          + {it.addons.map(a => a.name).join(', ')}
                          {it.flavors.length > 0 && ` (${it.flavors.map(f => f.name).join(', ')})`}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-4">
                      {/* Quantity stepper */}
                      <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg">
                        <button
                          type="button"
                          onClick={() => handleAmountChange(it.id, -1)}
                          className="w-6 h-6 flex items-center justify-center text-brand-dark hover:bg-slate-100"
                        >
                          <Minus className="w-3 h-3" />
                        </button>
                        <span className="w-6 text-center text-xs font-bold">{it.amount}</span>
                        <button
                          type="button"
                          onClick={() => handleAmountChange(it.id, 1)}
                          className="w-6 h-6 flex items-center justify-center text-brand-dark hover:bg-slate-100"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>

                      <span className="w-16 text-right font-extrabold text-brand-dark">{it.totalPrice} ₽</span>

                      <button
                        type="button"
                        onClick={() => handleRemoveItem(it.id)}
                        className="text-slate-400 hover:text-brand-red transition-colors p-1"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 4. Order Parameters: Status, Payment, Comments */}
        <div className="bg-white border border-slate-200 rounded-r18 p-4 space-y-3 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Select
              label="Статус заказа"
              value={statusOrders}
              onChange={e => setStatusOrders(e.target.value as OrderStatus)}
              options={[
                { value: 'New', label: 'Новый' },
                { value: 'Waiting', label: 'В ожидании' },
                { value: 'In Progress', label: 'Выполняется' },
                { value: 'Completed', label: 'Выполнен' },
              ]}
            />
            <Select
              label="Статус оплаты"
              value={paymentStatus}
              onChange={e => setPaymentStatus(e.target.value as PaymentStatus)}
              options={[
                { value: 'Paid', label: 'Оплачено' },
                { value: 'Pending', label: 'Ожидание оплаты' },
              ]}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Комментарий клиента"
              value={clientComments}
              onChange={e => setClientComments(e.target.value)}
              placeholder="Например: С собой, меньше льда..."
            />
            <Input
              label="Комментарий сотрудника"
              value={staffComments}
              onChange={e => setStaffComments(e.target.value)}
              placeholder="Внутренняя заметка баристы..."
            />
          </div>
        </div>

        {/* 5. Summary & Submit footer */}
        <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold text-brand-gray-blue uppercase">Итого к оплате</p>
            <p className="text-2xl font-extrabold text-brand-dark">{orderSubtotal} ₽</p>
          </div>

          <div className="flex items-center justify-end gap-2.5">
            <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
              Отмена
            </Button>
            <Button
              variant="primary"
              onClick={handleSubmit}
              isLoading={isSubmitting}
              disabled={isSubmitting || orderItems.length === 0}
              leftIcon={<ShoppingBag className="w-4 h-4" />}
            >
              Создать заказ
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
