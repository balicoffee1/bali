import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Order, OrderStatus } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { StatusBadge, ORDER_STATUS_LABELS, PAYMENT_STATUS_LABELS } from '../components/ui/Badge';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Table, Column } from '../components/ui/Table';
import {
  ShoppingBag, Search, CheckCircle2, Clock, XCircle,
  LayoutGrid, List, User, Phone, MapPin, Coffee, AlertCircle
} from 'lucide-react';

export const OrdersPage: React.FC = () => {
  const { selectedShopId, addToast } = useApp();
  const { user: currentUser } = useAuth();
  const canManageOrders = Boolean(currentUser?.is_superuser || ['owner', 'admin'].includes(currentUser?.role || ''));
  const [orders, setOrders] = useState<Order[]>([]);
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('table');
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [search, setSearch] = useState('');
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [cancellationReason, setCancellationReason] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadOrders();
  }, [selectedShopId, statusFilter]);

  const loadOrders = async () => {
    setIsLoading(true);
    try {
      const data = await api.getOrders(selectedShopId || undefined, statusFilter);
      setOrders(data);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: OrderStatus, reason?: string) => {
    if (!selectedOrder) return;
    try {
      const updated = await api.updateOrderStatus(selectedOrder.id, newStatus, reason);
      setOrders(prev => prev.map(o => (o.id === updated.id ? updated : o)));
      setSelectedOrder(updated);
      setIsCancelModalOpen(false);
      setCancellationReason('');
      addToast({
        type: 'success',
        title: 'Статус заказа обновлен',
        message: `Заказ #${updated.id} переведен в статус "${ORDER_STATUS_LABELS[newStatus] || newStatus}"`,
      });
    } catch {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: 'Не удалось обновить статус заказа',
      });
    }
  };

  const filteredOrders = orders.filter(o => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      String(o.id).includes(s) ||
      o.user_full_name.toLowerCase().includes(s) ||
      o.user_login.includes(s)
    );
  });

  const columns: Column<Order>[] = [
    { header: '№ Заказа', accessor: row => <span className="font-bold">#{row.id}</span> },
    {
      header: 'Клиент',
      accessor: row => (
        <div>
          <p className="font-bold text-brand-dark">{row.user_full_name}</p>
          <span className="text-[10px] text-brand-gray-blue">{row.user_login}</span>
        </div>
      ),
    },
    {
      header: 'Товары',
      accessor: row => (
        <div className="max-w-xs truncate text-brand-dark-blue">
          {row.items.map(it => `${it.product_name} (${it.size}) × ${it.amount}`).join(', ')}
        </div>
      ),
    },
    {
      header: 'Кофейня',
      accessor: row => <span className="text-xs">{row.coffee_shop_address}</span>,
    },
    {
      header: 'Сумма',
      accessor: row => <span className="font-extrabold text-brand-dark">{row.full_price} ₽</span>,
    },
    {
      header: 'Статус',
      accessor: row => <StatusBadge status={row.status_orders} />,
    },
    {
      header: 'Оплата',
      accessor: row => <StatusBadge status={row.payment_status} />,
    },
    {
      header: 'Время создания',
      accessor: row => (
        <span className="text-xs text-brand-gray-blue">
          {new Date(row.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      ),
    },
  ];

  const statusPills: { id: string; label: string }[] = [
    { id: 'All', label: 'Все заказы' },
    { id: 'New', label: 'Новые' },
    { id: 'Waiting', label: 'В ожидании' },
    { id: 'In Progress', label: 'Выполняется' },
    { id: 'Completed', label: 'Выполнен' },
    { id: 'Canceled', label: 'Отменён' },
  ];

  const kanbanStatuses: OrderStatus[] = ['New', 'Waiting', 'In Progress', 'Completed', 'Canceled'];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Top Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Search */}
        <div className="w-full sm:w-72">
          <Input
            placeholder="Поиск по номеру или клиенту..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />
        </div>

        {/* View mode toggle (Table / Kanban) */}
        <div className="flex items-center gap-2">
          <div className="bg-brand-light-gray p-1 rounded-r12 flex items-center gap-1 border border-slate-200/60">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
                viewMode === 'table' ? 'bg-white shadow-sm text-brand-dark' : 'text-brand-dark-blue'
              }`}
            >
              <List className="w-4 h-4" />
              Таблица
            </button>
            <button
              onClick={() => setViewMode('kanban')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
                viewMode === 'kanban' ? 'bg-white shadow-sm text-brand-dark' : 'text-brand-dark-blue'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
              Kanban
            </button>
          </div>
        </div>
      </div>

      {/* Status Pills in Russian */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {statusPills.map(pill => (
          <button
            key={pill.id}
            onClick={() => setStatusFilter(pill.id)}
            className={`px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
              statusFilter === pill.id
                ? 'bg-brand-lime text-brand-dark shadow-sm'
                : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
            }`}
          >
            {pill.label}
          </button>
        ))}
      </div>

      {/* Content View: Table or Kanban */}
      {viewMode === 'table' ? (
        <Table
          columns={columns}
          data={filteredOrders}
          keyExtractor={o => o.id}
          onRowClick={order => setSelectedOrder(order)}
          isLoading={isLoading}
          emptyMessage="Нет активных заказов по выбранным фильтрам"
        />
      ) : (
        /* Kanban Board with Russian column headers */
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 overflow-x-auto pb-4">
          {kanbanStatuses.map(st => {
            const columnOrders = filteredOrders.filter(o => o.status_orders === st);
            return (
              <div key={st} className="bg-slate-100/70 rounded-r18 p-3 flex flex-col min-h-[450px]">
                <div className="flex items-center justify-between px-2 py-1.5 mb-2">
                  <h4 className="text-xs font-extrabold text-brand-dark">{ORDER_STATUS_LABELS[st] || st}</h4>
                  <span className="w-5 h-5 rounded-full bg-white text-[10px] font-extrabold flex items-center justify-center text-brand-dark-blue shadow-xs">
                    {columnOrders.length}
                  </span>
                </div>

                <div className="space-y-2.5 flex-1 overflow-y-auto">
                  {columnOrders.map(order => (
                    <div
                      key={order.id}
                      onClick={() => setSelectedOrder(order)}
                      className="bg-white p-3.5 rounded-r12 shadow-sm border border-slate-100 hover:shadow-md transition-all cursor-pointer space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-extrabold text-xs text-brand-dark">#{order.id}</span>
                        <StatusBadge status={order.payment_status} />
                      </div>
                      <p className="text-xs font-bold text-brand-dark truncate">{order.user_full_name}</p>
                      <div className="text-[11px] text-brand-gray-blue line-clamp-2">
                        {order.items.map(it => `${it.product_name} (${it.size})`).join(', ')}
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-slate-50 text-xs">
                        <span className="font-extrabold text-brand-dark">{order.full_price} ₽</span>
                        <span className="text-[10px] text-brand-gray-blue font-medium">
                          {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  ))}
                  {columnOrders.length === 0 && (
                    <div className="h-32 flex items-center justify-center text-xs text-brand-gray-blue font-medium border-2 border-dashed border-slate-200 rounded-r12">
                      Пусто
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Order Detail Drawer */}
      {selectedOrder && (
        <Drawer
          isOpen={!!selectedOrder}
          onClose={() => setSelectedOrder(null)}
          title={`Заказ #${selectedOrder.id}`}
          subtitle={`Создан: ${new Date(selectedOrder.created_at).toLocaleString()}`}
          footer={canManageOrders ? (
            <div className="flex items-center justify-between w-full">
              <Button
                variant="danger"
                size="sm"
                leftIcon={<XCircle className="w-4 h-4" />}
                onClick={() => setIsCancelModalOpen(true)}
                disabled={selectedOrder.status_orders === 'Canceled' || selectedOrder.status_orders === 'Completed'}
              >
                Отменить заказ
              </Button>

              <div className="flex items-center gap-2">
                {selectedOrder.status_orders === 'New' && (
                  <Button size="sm" onClick={() => handleStatusChange('Waiting')}>
                    Принять заказ
                  </Button>
                )}
                {selectedOrder.status_orders === 'Waiting' && (
                  <Button size="sm" variant="dark" onClick={() => handleStatusChange('In Progress')}>
                    В работу
                  </Button>
                )}
                {selectedOrder.status_orders === 'In Progress' && (
                  <Button size="sm" variant="primary" leftIcon={<CheckCircle2 className="w-4 h-4" />} onClick={() => handleStatusChange('Completed')}>
                    Завершить заказ
                  </Button>
                )}
              </div>
            </div>
          ) : undefined}
        >
          {/* Order Details Body */}
          <div className="space-y-5">
            {/* Status overview */}
            <div className="bg-brand-light-gray p-4 rounded-r18 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Статус выполнения</p>
                <div className="mt-1">
                  <StatusBadge status={selectedOrder.status_orders} />
                </div>
              </div>
              <div>
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Статус оплаты</p>
                <div className="mt-1">
                  <StatusBadge status={selectedOrder.payment_status} />
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Сумма заказа</p>
                <p className="text-lg font-extrabold text-brand-dark mt-0.5">{selectedOrder.full_price} ₽</p>
              </div>
            </div>

            {/* Customer info */}
            <div className="bg-white border border-slate-100 rounded-r18 p-4 space-y-2">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">Данные гостя</h4>
              <div className="flex items-center gap-2 text-xs font-semibold text-brand-dark">
                <User className="w-4 h-4 text-brand-dark-blue" />
                <span>{selectedOrder.user_full_name}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-brand-dark-blue">
                <Phone className="w-4 h-4 text-brand-dark-blue" />
                <span>{selectedOrder.user_login}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-brand-dark-blue">
                <MapPin className="w-4 h-4 text-brand-dark-blue" />
                <span>{selectedOrder.coffee_shop_address}</span>
              </div>
              {selectedOrder.client_comments && (
                <div className="mt-2 p-2.5 bg-amber-50 rounded-lg text-xs text-amber-900 border border-amber-200">
                  <span className="font-bold">Комментарий: </span>
                  {selectedOrder.client_comments}
                </div>
              )}
            </div>

            {/* Order Items */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">Состав заказа</h4>
              <div className="divide-y divide-slate-100 border border-slate-100 rounded-r18 bg-white overflow-hidden">
                {selectedOrder.items.map(item => (
                  <div key={item.id} className="p-3.5 flex items-start justify-between">
                    <div>
                      <p className="text-xs font-bold text-brand-dark">
                        {item.product_name} <span className="text-brand-gray-blue font-semibold">({item.size})</span>
                      </p>
                      {item.addons_names && item.addons_names.length > 0 && (
                        <p className="text-[11px] text-brand-gray-blue mt-0.5">
                          Добавки: {item.addons_names.join(', ')}
                          {item.flavors_names && item.flavors_names.length > 0 && ` (${item.flavors_names.join(', ')})`}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-xs font-extrabold text-brand-dark">{item.item_total} ₽</p>
                      <span className="text-[10px] text-brand-gray-blue font-semibold">{item.amount} шт</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cancellation reason if canceled */}
            {selectedOrder.cancellation_reason && (
              <div className="bg-red-50 p-3.5 rounded-r18 border border-red-200 text-xs text-brand-red">
                <span className="font-bold">Причина отмены: </span>
                {selectedOrder.cancellation_reason}
              </div>
            )}
          </div>
        </Drawer>
      )}

      {/* Cancellation Modal */}
      <Modal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        title="Отмена заказа"
        description="Укажите причину отмены заказа для уведомления клиента"
      >
        <div className="space-y-4">
          <Input
            label="Причина отмены"
            placeholder="Например: Закончилось молоко, клиент не отвечает..."
            value={cancellationReason}
            onChange={e => setCancellationReason(e.target.value)}
            requiredAsterisk
          />
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setIsCancelModalOpen(false)}>
              Назад
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => handleStatusChange('Canceled', cancellationReason)}
              disabled={!cancellationReason.trim()}
            >
              Подтвердить отмену
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
