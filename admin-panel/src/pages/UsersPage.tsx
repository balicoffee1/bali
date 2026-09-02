import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { User, UserRole } from '../types';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { StatusBadge, Badge } from '../components/ui/Badge';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import { Table, Column } from '../components/ui/Table';
import {
  Search, Shield, Ban, CheckCircle2, User as UserIcon,
  Phone, Mail, CreditCard, Percent, ShoppingBag
} from 'lucide-react';

export const UsersPage: React.FC = () => {
  const { addToast } = useApp();
  const { user: currentUser } = useAuth();
  const canBlockUsers = currentUser?.is_superuser || ['owner', 'admin'].includes(currentUser?.role || '');
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('All');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [newRole, setNewRole] = useState<UserRole>('user');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadUsers();
  }, [roleFilter]);

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const data = await api.getUsers(search, roleFilter);
      setUsers(data);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleBlock = async (userId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      const res = await api.toggleBlockUser(userId);
      setUsers(prev => prev.map(u => (u.id === userId ? { ...u, is_active: res.is_active } : u)));
      if (selectedUser && selectedUser.id === userId) {
        setSelectedUser({ ...selectedUser, is_active: res.is_active });
      }
      addToast({
        type: res.is_active ? 'success' : 'warning',
        title: res.is_active ? 'Пользователь разблокирован' : 'Пользователь заблокирован',
        message: 'Статус доступа обновлен',
      });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось изменить статус пользователя' });
    }
  };

  const handleSetRole = async () => {
    if (!selectedUser) return;
    try {
      const updated = await api.setUserRole(selectedUser.id, newRole);
      setUsers(prev => prev.map(u => (u.id === updated.id ? updated : u)));
      setSelectedUser(updated);
      setIsRoleModalOpen(false);
      addToast({ type: 'success', title: 'Роль изменена', message: `Пользователю назначена роль ${newRole}` });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось изменить роль' });
    }
  };

  const filteredUsers = users.filter(u => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      u.full_name.toLowerCase().includes(s) ||
      u.login.includes(s) ||
      u.phone_number.includes(s) ||
      (u.email && u.email.toLowerCase().includes(s))
    );
  });

  const columns: Column<User>[] = [
    {
      header: 'Пользователь',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-brand-lime/20 border border-brand-lime/50 flex items-center justify-center font-bold text-xs text-brand-dark shrink-0">
            {row.first_name ? row.first_name[0] : 'U'}
          </div>
          <div>
            <p className="font-bold text-brand-dark">{row.full_name}</p>
            <span className="text-[10px] text-brand-gray-blue">{row.login}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'Роль',
      accessor: row => <StatusBadge status={row.role} />,
    },
    {
      header: 'Телефон / Email',
      accessor: row => (
        <div>
          <p className="text-xs">{row.phone_number}</p>
          {row.email && <span className="text-[10px] text-brand-gray-blue">{row.email}</span>}
        </div>
      ),
    },
    {
      header: 'Заказы',
      accessor: row => <span className="font-bold">{row.orders_count || 0} зак.</span>,
    },
    {
      header: 'Скидка',
      accessor: row => (
        row.discount_rate ? (
          <span className="font-bold text-brand-green-text">{row.discount_rate}%</span>
        ) : (
          <span className="text-brand-gray-blue">—</span>
        )
      ),
    },
    {
      header: 'Статус',
      accessor: row => (
        <Badge variant={row.is_active ? 'success' : 'danger'}>
          {row.is_active ? 'Активен' : 'Заблокирован'}
        </Badge>
      ),
    },
    {
      header: 'Действия',
      align: 'right',
      accessor: row => (
        <div className="flex items-center justify-end gap-1.5" onClick={e => e.stopPropagation()}>
          {canBlockUsers ? <Button
            size="sm"
            variant={row.is_active ? 'outline' : 'primary'}
            className="h-8 text-xs px-2.5"
            onClick={e => handleToggleBlock(row.id, e)}
          >
            {row.is_active ? 'Заблокировать' : 'Разблокировать'}
          </Button> : <span className="text-brand-gray-blue">—</span>}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="w-full sm:w-80">
          <Input
            placeholder="Поиск по имени, телефону или email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />
        </div>

        {/* Roles Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {['All', 'owner', 'admin', 'moderator', 'support', 'employee', 'user'].map(role => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
                roleFilter === role
                  ? 'bg-brand-lime text-brand-dark shadow-sm'
                  : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
              }`}
            >
              {role === 'All' ? 'Все' : role}
            </button>
          ))}
        </div>
      </div>

      {/* Users Table */}
      <Table
        columns={columns}
        data={filteredUsers}
        keyExtractor={u => u.id}
        onRowClick={u => setSelectedUser(u)}
        isLoading={isLoading}
        emptyMessage="Пользователи не найдены"
      />

      {/* User Profile Drawer */}
      {selectedUser && (
        <Drawer
          isOpen={!!selectedUser}
          onClose={() => setSelectedUser(null)}
          title={selectedUser.full_name}
          subtitle={`Логин: ${selectedUser.login}`}
          footer={
            <div className="flex items-center justify-between w-full">
              {canBlockUsers && <Button
                variant={selectedUser.is_active ? 'danger' : 'primary'}
                size="sm"
                leftIcon={<Ban className="w-4 h-4" />}
                onClick={() => handleToggleBlock(selectedUser.id)}
              >
                {selectedUser.is_active ? 'Заблокировать доступ' : 'Разблокировать'}
              </Button>}

              {currentUser?.is_superuser || currentUser?.role === 'owner' ? (
                <Button
                  size="sm"
                  variant="dark"
                  leftIcon={<Shield className="w-4 h-4" />}
                  onClick={() => {
                    setNewRole(selectedUser.role);
                    setIsRoleModalOpen(true);
                  }}
                >
                  Изменить роль
                </Button>
              ) : null}
            </div>
          }
        >
          <div className="space-y-5">
            {/* Overview Box */}
            <div className="bg-brand-light-gray p-4 rounded-r18 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Роль в системе</p>
                <div className="mt-1">
                  <StatusBadge status={selectedUser.role} />
                </div>
              </div>
              <div>
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Статус аккаунта</p>
                <div className="mt-1">
                  <Badge variant={selectedUser.is_active ? 'success' : 'danger'}>
                    {selectedUser.is_active ? 'Активен' : 'Заблокирован'}
                  </Badge>
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-bold text-brand-gray-blue uppercase">Скидка лояльности</p>
                <p className="text-base font-extrabold text-brand-green-text mt-0.5">
                  {selectedUser.discount_rate ? `${selectedUser.discount_rate}%` : '0%'}
                </p>
              </div>
            </div>

            {/* Contacts & Cards */}
            <div className="bg-white border border-slate-100 rounded-r18 p-4 space-y-3">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">Контакты и карты</h4>
              <div className="flex items-center gap-2.5 text-xs text-brand-dark">
                <Phone className="w-4 h-4 text-brand-dark-blue" />
                <span>{selectedUser.phone_number}</span>
              </div>
              {selectedUser.email && (
                <div className="flex items-center gap-2.5 text-xs text-brand-dark">
                  <Mail className="w-4 h-4 text-brand-dark-blue" />
                  <span>{selectedUser.email}</span>
                </div>
              )}
              {selectedUser.cards && selectedUser.cards.length > 0 && (
                <div className="pt-2 border-t border-slate-100 space-y-2">
                  <p className="text-[11px] font-bold text-brand-gray-blue">Привязанные банковские карты:</p>
                  {selectedUser.cards.map(c => (
                    <div key={c.id} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg text-xs font-semibold">
                      <div className="flex items-center gap-2">
                        <CreditCard className="w-4 h-4 text-brand-dark-blue" />
                        <span>{c.card_number}</span>
                      </div>
                      <span className="text-brand-gray-blue font-medium">{c.expiration_date}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Orders summary */}
            <div className="bg-white border border-slate-100 rounded-r18 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-r12 bg-brand-lime/20 text-brand-dark flex items-center justify-center">
                  <ShoppingBag className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-brand-dark">История заказов</h4>
                  <p className="text-xs text-brand-gray-blue">{selectedUser.orders_count || 0} оформленных заказов</p>
                </div>
              </div>
            </div>
          </div>
        </Drawer>
      )}

      {/* Role Switcher Modal */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => setIsRoleModalOpen(false)}
        title="Смена роли пользователя"
        description={`Выберите уровень доступа для ${selectedUser?.full_name}`}
      >
        <div className="space-y-4">
          <Select
            label="Роль"
            value={newRole}
            onChange={e => setNewRole(e.target.value as UserRole)}
            options={[
              { value: 'owner', label: 'Владелец (Owner / Super Admin)' },
              { value: 'admin', label: 'Администратор (Admin)' },
              { value: 'moderator', label: 'Модератор меню (Moderator)' },
              { value: 'support', label: 'Служба поддержки (Support)' },
              { value: 'employee', label: 'Сотрудник / Бариста (Employee)' },
              { value: 'user', label: 'Клиент (User)' },
            ]}
          />
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setIsRoleModalOpen(false)}>
              Отмена
            </Button>
            <Button size="sm" onClick={handleSetRole}>
              Применить роль
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
