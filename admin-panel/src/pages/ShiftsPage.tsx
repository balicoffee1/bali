import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../api/client';
import { Shift, StaffMember, User, CoffeeShop } from '../types';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { Card, StatCard } from '../components/ui/Card';
import { StatusBadge, Badge } from '../components/ui/Badge';
import { Table, Column } from '../components/ui/Table';
import { Tabs } from '../components/ui/Tabs';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Drawer } from '../components/ui/Drawer';
import { Modal } from '../components/ui/Modal';
import {
  Clock, User as UserIcon, DollarSign, Plus, Search, Store,
  Pencil, Trash2, AlertTriangle, Info,
} from 'lucide-react';
import { cn } from '../utils/cn';

type ShiftsTabId = 'shifts' | 'staff';
type StaffSource = 'existing' | 'new';

interface NewEmployeeDraft {
  first_name: string;
  last_name: string;
  phone_number: string;
  email: string;
}

const emptyEmployee: NewEmployeeDraft = {
  first_name: '',
  last_name: '',
  phone_number: '',
  email: '',
};

const shopLabel = (shop: CoffeeShop) =>
  [`${shop.street}, ${shop.building_number}`, shop.city_name].filter(Boolean).join(' — ');

// Номер служит и логином: мобильное приложение ищет сотрудника по
// phone_number, а PhoneNumberField на бэкенде принимает только E.164.
const PHONE_PATTERN = /^\+7\d{10}$/;
const normalizePhone = (raw: string) => {
  const digits = raw.replace(/\D/g, '');
  if (!digits) return '';
  const national = digits.length === 11 && (digits[0] === '8' || digits[0] === '7')
    ? digits.slice(1)
    : digits;
  return `+7${national}`;
};

export const ShiftsPage: React.FC = () => {
  const { coffeeShops, addToast } = useApp();
  const { user: currentUser } = useAuth();
  const canManageStaff = Boolean(
    currentUser?.is_superuser || ['owner', 'admin'].includes(currentUser?.role || '')
  );

  const [activeTab, setActiveTab] = useState<ShiftsTabId>('shifts');
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [staffSearch, setStaffSearch] = useState('');
  const [shopFilter, setShopFilter] = useState<number | 'all'>('all');

  const [isStaffDrawerOpen, setIsStaffDrawerOpen] = useState(false);
  const [editingStaff, setEditingStaff] = useState<Partial<StaffMember> | null>(null);
  const [userPickerQuery, setUserPickerQuery] = useState('');
  const [alsoSetEmployeeRole, setAlsoSetEmployeeRole] = useState(true);
  const [isSavingStaff, setIsSavingStaff] = useState(false);
  const [staffSource, setStaffSource] = useState<StaffSource>('existing');
  const [newEmployee, setNewEmployee] = useState<NewEmployeeDraft>(emptyEmployee);
  const [staffFormError, setStaffFormError] = useState<string | null>(null);
  const [staffFormNotice, setStaffFormNotice] = useState<string | null>(null);
  const [userSearchResults, setUserSearchResults] = useState<User[] | null>(null);
  const [isSearchingUsers, setIsSearchingUsers] = useState(false);

  const [staffToRemove, setStaffToRemove] = useState<StaffMember | null>(null);
  const [isRemovingStaff, setIsRemovingStaff] = useState(false);

  useEffect(() => {
    loadShiftsData();
  }, []);

  const loadShiftsData = async () => {
    setIsLoading(true);
    try {
      const [shiftsData, staffData, usersData] = await Promise.all([
        api.getShifts(),
        api.getStaff(),
        api.getUsers(),
      ]);
      setShifts(shiftsData);
      setStaff(staffData);
      setUsers(usersData);
    } finally {
      setIsLoading(false);
    }
  };

  const openShiftsCount = shifts.filter(s => s.status_shift === 'Open').length;
  const totalRevenueToday = shifts.reduce((acc, s) => acc + Number(s.amount_closed_orders || 0), 0);

  const shopById = useMemo(
    () => new Map(coffeeShops.map(shop => [shop.id, shop])),
    [coffeeShops]
  );

  const resolveShopName = (member: StaffMember) => {
    const shop = shopById.get(member.place_of_work);
    return shop ? shopLabel(shop) : member.place_of_work_name || 'Кофейня не указана';
  };

  const filteredStaff = useMemo(() => {
    const query = staffSearch.trim().toLowerCase();
    return staff.filter(member => {
      if (shopFilter !== 'all' && member.place_of_work !== shopFilter) return false;
      if (!query) return true;
      return (
        member.user_name?.toLowerCase().includes(query) ||
        member.user_phone?.toLowerCase().includes(query)
      );
    });
  }, [staff, staffSearch, shopFilter]);

  // Один и тот же человек может работать в нескольких точках, но дважды в
  // одной — нет: вторая запись Staff ничего не даёт и ломает выдачу смен.
  const alreadyAtSelectedShop = useMemo(() => {
    if (!editingStaff?.place_of_work) return new Set<number>();
    return new Set(
      staff
        .filter(m => m.place_of_work === editingStaff.place_of_work && m.id !== editingStaff.id)
        .map(m => m.users)
    );
  }, [staff, editingStaff?.place_of_work, editingStaff?.id]);

  // Пользователи отдаются страницами по 20, а поиск фильтровал только уже
  // загруженную страницу — на реальной базе нужного человека в ней почти
  // никогда нет. Поэтому спрашиваем сервер.
  useEffect(() => {
    const query = userPickerQuery.trim();
    if (!isStaffDrawerOpen || staffSource !== 'existing' || query.length < 2) {
      setUserSearchResults(null);
      setIsSearchingUsers(false);
      return;
    }

    let cancelled = false;
    setIsSearchingUsers(true);
    const timer = setTimeout(async () => {
      try {
        const found = await api.getUsers(query.replace(/^\+/, ''), undefined, 50);
        if (!cancelled) setUserSearchResults(found);
      } catch {
        if (!cancelled) setUserSearchResults([]);
      } finally {
        if (!cancelled) setIsSearchingUsers(false);
      }
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [userPickerQuery, isStaffDrawerOpen, staffSource]);

  const selectableUsers = useMemo(() => {
    const query = userPickerQuery.trim().toLowerCase();
    // Пока идёт запрос — показываем совпадения из уже загруженного списка,
    // чтобы поле не мигало пустотой.
    const pool = userSearchResults ?? users;
    const selected = editingStaff?.users;
    return pool
      .filter(u => u.is_active)
      .filter(u => !alreadyAtSelectedShop.has(u.id) || u.id === selected)
      .filter(u => {
        if (!query || userSearchResults) return true;
        return (
          u.full_name?.toLowerCase().includes(query) ||
          u.phone_number?.toLowerCase().includes(query) ||
          u.login?.toLowerCase().includes(query)
        );
      })
      .slice(0, 40);
  }, [users, userSearchResults, userPickerQuery, alreadyAtSelectedShop, editingStaff?.users]);

  // Выбранный может прийти из результатов серверного поиска, а не из первой
  // загруженной страницы, поэтому ищем в обоих списках.
  const selectedUser = editingStaff?.users
    ? [...(userSearchResults ?? []), ...users].find(u => u.id === editingStaff.users)
    : undefined;

  const openCreateStaff = () => {
    setEditingStaff({
      users: undefined,
      place_of_work: shopFilter !== 'all' ? shopFilter : coffeeShops[0]?.id,
    });
    setUserPickerQuery('');
    setStaffFormError(null);
    setStaffFormNotice(null);
    setUserSearchResults(null);
    setAlsoSetEmployeeRole(true);
    setStaffSource('existing');
    setNewEmployee(emptyEmployee);
    setIsStaffDrawerOpen(true);
  };

  const openEditStaff = (member: StaffMember) => {
    setEditingStaff({ ...member });
    setUserPickerQuery('');
    setStaffFormError(null);
    setStaffFormNotice(null);
    setUserSearchResults(null);
    setAlsoSetEmployeeRole(false);
    setStaffSource('existing');
    setNewEmployee(emptyEmployee);
    setIsStaffDrawerOpen(true);
  };

  const closeStaffDrawer = () => {
    setIsStaffDrawerOpen(false);
    setEditingStaff(null);
    setNewEmployee(emptyEmployee);
    setStaffFormError(null);
    setStaffFormNotice(null);
    setUserSearchResults(null);
  };

  const newEmployeePhone = normalizePhone(newEmployee.phone_number);
  const isNewEmployeeValid =
    newEmployee.first_name.trim().length > 0 && PHONE_PATTERN.test(newEmployeePhone);

  // Выбранный может уже работать на этой точке: список его прячет, но после
  // подхвата по занятому номеру он оказывается выбранным явно. Повторная
  // запись Staff ничего не даёт, поэтому отправку блокируем.
  const selectedAlreadyAtShop = Boolean(
    editingStaff?.users && alreadyAtSelectedShop.has(editingStaff.users)
  );

  const canSubmitStaff = Boolean(
    editingStaff?.place_of_work &&
      !selectedAlreadyAtShop &&
      (staffSource === 'new' ? isNewEmployeeValid : editingStaff?.users)
  );

  const handleSaveStaff = async () => {
    if (!editingStaff?.place_of_work || !canSubmitStaff) return;
    setIsSavingStaff(true);
    setStaffFormError(null);
    setStaffFormNotice(null);
    try {
      let userId = editingStaff.users;

      // Нового сотрудника заводим первым шагом: без пользователя привязывать
      // к кофейне нечего.
      if (staffSource === 'new') {
        try {
          const createdUser = await api.createUser({
            first_name: newEmployee.first_name,
            last_name: newEmployee.last_name,
            phone_number: newEmployeePhone,
            email: newEmployee.email,
            role: 'employee',
          });
          setUsers(prev => [...prev, createdUser]);
          userId = createdUser.id;
        } catch (error: any) {
          // Занятый номер — не тупик: человек уже заведён (обычно как клиент),
          // и его достаточно назначить на кофейню, а не создавать заново.
          const existing = await api.findUserByPhone(newEmployeePhone).catch(() => null);
          if (existing) {
            setStaffSource('existing');
            setUserPickerQuery(newEmployeePhone);
            setEditingStaff({ ...editingStaff, users: existing.id });
            setUsers(prev => (prev.some(u => u.id === existing.id) ? prev : [...prev, existing]));
            setStaffFormError(null);

            const atThisShop = staff.some(
              m => m.users === existing.id && m.place_of_work === editingStaff.place_of_work
            );
            if (atThisShop) {
              setStaffFormNotice(
                `${existing.full_name} уже работает на этой кофейне — назначать повторно не нужно.`
              );
            } else {
              setStaffFormNotice(
                `${existing.full_name} уже есть в системе и выбран. Нажмите «Назначить бариста», чтобы дать доступ к заказам кофейни.`
              );
              addToast({
                type: 'info',
                title: 'Пользователь уже зарегистрирован',
                message: 'Он выбран в списке — осталось назначить его на кофейню.',
              });
            }
            return;
          }

          const message = error?.message || 'Не удалось создать пользователя';
          setStaffFormError(message);
          addToast({ type: 'error', title: 'Сотрудник не создан', message });
          return;
        }
      }

      if (!userId) return;

      let saved: StaffMember;
      try {
        saved = await api.saveStaff({
          id: editingStaff.id,
          users: userId,
          place_of_work: editingStaff.place_of_work,
        });
      } catch (error: any) {
        // Пользователь уже создан, а привязка не прошла. Молчать нельзя:
        // иначе повторная попытка упрётся в занятый номер телефона.
        if (staffSource === 'new') {
          const reason = error?.message || 'не удалось привязать к кофейне';
          const message = `${newEmployee.first_name} уже есть в системе, но не назначен на кофейню (${reason}). Назначьте его через «Существующий».`;
          setStaffFormError(message);
          addToast({ type: 'warning', title: 'Сотрудник создан, но не назначен', message });
          setStaffSource('existing');
          setEditingStaff({ ...editingStaff, users: userId });
          return;
        }
        throw error;
      }

      // Роль не влияет на доступ к заказам точки — его даёт сама запись Staff.
      // Но без роли «Сотрудник» человек выглядит клиентом в остальной панели,
      // поэтому назначаем её явным флажком, а не молча.
      if (staffSource === 'existing' && alsoSetEmployeeRole && selectedUser && selectedUser.role === 'user') {
        try {
          const updatedUser = await api.setUserRole(selectedUser.id, 'employee');
          setUsers(prev => prev.map(u => (u.id === updatedUser.id ? updatedUser : u)));
        } catch {
          addToast({
            type: 'warning',
            title: 'Бариста назначен, роль не изменена',
            message: 'Доступ к заказам точки уже выдан. Роль можно поменять на странице «Пользователи».',
          });
        }
      }

      setStaff(prev => {
        const exists = prev.some(m => m.id === saved.id);
        return exists ? prev.map(m => (m.id === saved.id ? saved : m)) : [...prev, saved];
      });
      addToast({
        type: 'success',
        title: editingStaff.id ? 'Бариста переведен' : 'Бариста назначен',
        message: `${saved.user_name} — ${resolveShopName(saved)}`,
      });
      closeStaffDrawer();
    } catch (error: any) {
      const message = error?.message || 'Не удалось сохранить сотрудника';
      setStaffFormError(message);
      addToast({ type: 'error', title: 'Ошибка', message });
    } finally {
      setIsSavingStaff(false);
    }
  };

  const handleRemoveStaff = async () => {
    if (!staffToRemove) return;
    setIsRemovingStaff(true);
    try {
      await api.deleteStaff(staffToRemove.id);
      setStaff(prev => prev.filter(m => m.id !== staffToRemove.id));
      addToast({
        type: 'success',
        title: 'Бариста откреплен',
        message: `${staffToRemove.user_name} больше не работает на точке`,
      });
      setStaffToRemove(null);
    } catch (error: any) {
      addToast({
        type: 'error',
        title: 'Ошибка',
        message: error?.message || 'Не удалось открепить сотрудника',
      });
    } finally {
      setIsRemovingStaff(false);
    }
  };

  const shiftColumns: Column<Shift>[] = [
    {
      header: 'Сотрудник (Бариста)',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-light-gray flex items-center justify-center text-xs font-bold text-brand-dark-blue shrink-0">
            {row.staff_name ? row.staff_name[0] : 'S'}
          </div>
          <div className="min-w-0">
            <p className="font-bold text-brand-dark truncate">{row.staff_name}</p>
            <span className="text-[10px] text-brand-gray-blue">{row.coffee_shop_name}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'Статус смены',
      accessor: row => <StatusBadge status={row.status_shift} />,
    },
    {
      header: 'Время открытия',
      accessor: row => (
        <div className="flex items-center gap-1.5 text-xs text-brand-dark-blue">
          <Clock className="w-3.5 h-3.5 text-brand-gray-blue" />
          <span>{new Date(row.start_time).toLocaleString()}</span>
        </div>
      ),
    },
    {
      header: 'Время закрытия',
      accessor: row => (
        row.end_time ? (
          <span className="text-xs text-brand-dark-blue">{new Date(row.end_time).toLocaleString()}</span>
        ) : (
          <span className="text-xs font-bold text-emerald-600">Смена открыта</span>
        )
      ),
    },
    {
      header: 'Закрытые чеки',
      accessor: row => (
        <span className="font-bold text-brand-dark">{row.number_orders_closed} чеков</span>
      ),
    },
    {
      header: 'Выручка за смену',
      align: 'right',
      accessor: row => (
        <span className="font-extrabold text-brand-green-text">
          {Number(row.amount_closed_orders).toLocaleString()} ₽
        </span>
      ),
    },
  ];

  const staffColumns: Column<StaffMember>[] = [
    {
      header: 'Бариста',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-light-gray flex items-center justify-center text-xs font-bold text-brand-dark-blue shrink-0">
            {row.user_name ? row.user_name[0] : 'S'}
          </div>
          <div className="min-w-0">
            <p className="font-bold text-brand-dark truncate">{row.user_name}</p>
            <span className="text-[10px] text-brand-gray-blue">{row.user_phone}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'Кофейня',
      accessor: row => (
        <div className="flex items-center gap-1.5 text-xs text-brand-dark-blue">
          <Store className="w-3.5 h-3.5 text-brand-gray-blue shrink-0" />
          <span>{resolveShopName(row)}</span>
        </div>
      ),
    },
    {
      header: 'Смена',
      accessor: row =>
        row.current_shift_status === 'Open' ? (
          <Badge variant="success">На смене</Badge>
        ) : (
          <Badge variant="neutral">Смена закрыта</Badge>
        ),
    },
    {
      header: 'Действия',
      align: 'right',
      accessor: row =>
        canManageStaff ? (
          <div className="flex items-center justify-end gap-1">
            <button
              type="button"
              onClick={() => openEditStaff(row)}
              aria-label={`Перевести ${row.user_name} в другую кофейню`}
              className="w-8 h-8 rounded-r8 flex items-center justify-center text-brand-gray-blue hover:text-brand-dark hover:bg-slate-100 transition-colors"
            >
              <Pencil className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setStaffToRemove(row)}
              aria-label={`Открепить ${row.user_name} от кофейни`}
              className="w-8 h-8 rounded-r8 flex items-center justify-center text-brand-gray-blue hover:text-brand-red hover:bg-red-50 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <span className="text-[10px] text-brand-gray-blue">Только просмотр</span>
        ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Top Stat Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          title="Смен открыто сейчас"
          value={openShiftsCount}
          subtitle="активные бариста на точках"
          icon={<Clock className="w-6 h-6 text-brand-dark" />}
          iconBg="bg-brand-lime text-brand-dark"
        />
        <StatCard
          title="Всего сотрудников"
          value={staff.length}
          subtitle="бариста и управляющие"
          icon={<UserIcon className="w-6 h-6 text-brand-dark-blue" />}
          iconBg="bg-slate-100 text-brand-dark-blue"
        />
        <StatCard
          title="Выручка по сменам"
          value={`${totalRevenueToday.toLocaleString()} ₽`}
          subtitle="зафиксировано в отчетах"
          icon={<DollarSign className="w-6 h-6 text-emerald-600" />}
          iconBg="bg-emerald-50 text-emerald-600"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          tabs={[
            { id: 'shifts', label: 'Журнал смен', count: shifts.length },
            { id: 'staff', label: 'Бариста', count: staff.length },
          ]}
          activeTab={activeTab}
          onChange={tab => setActiveTab(tab as ShiftsTabId)}
        />
        {activeTab === 'staff' && canManageStaff && (
          <Button
            size="sm"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={openCreateStaff}
            disabled={coffeeShops.length === 0}
          >
            Добавить бариста
          </Button>
        )}
      </div>

      {activeTab === 'shifts' ? (
        <Table
          columns={shiftColumns}
          data={shifts}
          keyExtractor={s => s.id}
          isLoading={isLoading}
          emptyMessage="Смены не найдены"
        />
      ) : (
        <div className="space-y-4">
          <Card className="flex flex-col sm:flex-row sm:items-center gap-3">
            <Input
              placeholder="Поиск по имени или телефону..."
              value={staffSearch}
              onChange={e => setStaffSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
              className="sm:max-w-sm"
            />
            <Select
              value={shopFilter}
              onChange={e => setShopFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
              options={[
                { value: 'all', label: 'Все кофейни' },
                ...coffeeShops.map(shop => ({ value: shop.id, label: shopLabel(shop) })),
              ]}
              className="sm:max-w-xs"
            />
          </Card>

          <Table
            columns={staffColumns}
            data={filteredStaff}
            keyExtractor={m => m.id}
            isLoading={isLoading}
            emptyMessage={
              staff.length === 0
                ? 'Бариста еще не назначены ни на одну кофейню'
                : 'По этому фильтру бариста не найдены'
            }
          />
        </div>
      )}

      {/* Назначение / перевод бариста */}
      {isStaffDrawerOpen && editingStaff && (
        <Drawer
          isOpen={isStaffDrawerOpen}
          onClose={closeStaffDrawer}
          title={editingStaff.id ? 'Перевод бариста' : 'Новый бариста'}
          subtitle="Сотрудник получит доступ к заказам выбранной кофейни"
          footer={
            <div className="flex items-center justify-end gap-2 w-full">
              <Button variant="ghost" size="sm" onClick={closeStaffDrawer} disabled={isSavingStaff}>
                Отмена
              </Button>
              <Button
                size="sm"
                onClick={handleSaveStaff}
                isLoading={isSavingStaff}
                disabled={isSavingStaff || !canSubmitStaff}
              >
                {editingStaff.id
                  ? 'Сохранить перевод'
                  : staffSource === 'new'
                  ? 'Создать и назначить'
                  : 'Назначить бариста'}
              </Button>
            </div>
          }
        >
          <div className="space-y-5 font-montserrat">
            {/* Тост может остаться незамеченным, а причина отказа нужна прямо
                здесь: диалог после ошибки не закрывается. */}
            {staffFormError && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-r12 bg-red-50 border border-red-200 p-3 text-xs text-brand-dark-blue"
              >
                <AlertTriangle className="w-4 h-4 text-brand-red shrink-0 mt-0.5" />
                <span>{staffFormError}</span>
              </div>
            )}

            {staffFormNotice && (
              <div
                role="status"
                className="flex items-start gap-2.5 rounded-r12 bg-blue-50 border border-blue-200 p-3 text-xs text-brand-dark-blue"
              >
                <Info className="w-4 h-4 text-brand-blue shrink-0 mt-0.5" />
                <span>{staffFormNotice}</span>
              </div>
            )}

            <Select
              label="Кофейня"
              value={editingStaff.place_of_work ?? ''}
              onChange={e =>
                setEditingStaff({ ...editingStaff, place_of_work: Number(e.target.value) })
              }
              options={coffeeShops.map(shop => ({ value: shop.id, label: shopLabel(shop) }))}
              requiredAsterisk
            />

            {!editingStaff.id && (
              <div className="inline-flex w-full p-1 bg-brand-light-gray rounded-r12 gap-1 select-none">
                {([
                  { id: 'existing', label: 'Существующий' },
                  { id: 'new', label: 'Новый сотрудник' },
                ] as { id: StaffSource; label: string }[]).map(option => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setStaffSource(option.id)}
                    className={cn(
                      'flex-1 px-3 py-2 text-xs font-bold rounded-lg transition-all duration-150',
                      staffSource === option.id
                        ? 'bg-white text-brand-dark shadow-sm'
                        : 'text-brand-dark-blue hover:text-brand-dark hover:bg-slate-200/50'
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}

            {staffSource === 'new' && !editingStaff.id ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
                  <Input
                    label="Имя"
                    placeholder="Например: Динара"
                    value={newEmployee.first_name}
                    onChange={e => setNewEmployee({ ...newEmployee, first_name: e.target.value })}
                    requiredAsterisk
                  />
                  <Input
                    label="Фамилия"
                    placeholder="Например: Сафина"
                    value={newEmployee.last_name}
                    onChange={e => setNewEmployee({ ...newEmployee, last_name: e.target.value })}
                  />
                </div>

                <Input
                  label="Телефон"
                  placeholder="+7 917 000-00-00"
                  value={newEmployee.phone_number}
                  onChange={e => setNewEmployee({ ...newEmployee, phone_number: e.target.value })}
                  error={
                    newEmployee.phone_number && !PHONE_PATTERN.test(newEmployeePhone)
                      ? 'Нужен российский номер: +7 и 10 цифр'
                      : undefined
                  }
                  requiredAsterisk
                />

                <Input
                  label="Email"
                  type="email"
                  placeholder="Необязательно"
                  value={newEmployee.email}
                  onChange={e => setNewEmployee({ ...newEmployee, email: e.target.value })}
                />

                <div className="flex items-start gap-2.5 rounded-r12 bg-brand-light-gray p-3 text-xs text-brand-dark-blue">
                  <Info className="w-4 h-4 text-brand-gray-blue shrink-0 mt-0.5" />
                  <span>
                    Сотрудник получит роль «Сотрудник», а номер телефона станет его логином —
                    в приложение бариста он войдёт по SMS-коду, пароль заводить не нужно.
                    Доступа в эту админ-панель у него не будет.
                  </span>
                </div>
              </div>
            ) : (
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-brand-dark-blue">
                Сотрудник<span className="text-brand-red ml-1 font-bold">*</span>
              </label>
              <Input
                placeholder="Поиск по имени, телефону или логину..."
                value={userPickerQuery}
                onChange={e => setUserPickerQuery(e.target.value)}
                leftIcon={<Search className="w-4 h-4" />}
              />

              <div className="max-h-64 overflow-y-auto overscroll-contain rounded-r12 border border-slate-100 divide-y divide-slate-100">
                {isSearchingUsers && selectableUsers.length === 0 ? (
                  <p className="p-4 text-xs text-brand-gray-blue text-center">Ищем по всей базе…</p>
                ) : selectableUsers.length === 0 ? (
                  <p className="p-4 text-xs text-brand-gray-blue text-center">
                    {userPickerQuery
                      ? 'Никто не найден. Уже назначенные на эту кофейню в списке не показываются.'
                      : 'Начните вводить имя или телефон — поиск идёт по всей базе.'}
                  </p>
                ) : (
                  selectableUsers.map(u => {
                    const isSelected = editingStaff.users === u.id;
                    return (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => setEditingStaff({ ...editingStaff, users: u.id })}
                        className={`w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors ${
                          isSelected ? 'bg-brand-lime/20' : 'hover:bg-slate-50'
                        }`}
                      >
                        <div className="w-8 h-8 rounded-full bg-brand-light-gray flex items-center justify-center text-xs font-bold text-brand-dark-blue shrink-0">
                          {u.full_name ? u.full_name[0] : '?'}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-brand-dark truncate">{u.full_name}</p>
                          <span className="text-[10px] text-brand-gray-blue">{u.phone_number}</span>
                        </div>
                        <Badge variant={u.role === 'user' ? 'neutral' : 'info'}>{u.role}</Badge>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
            )}

            {staffSource === 'existing' && selectedUser && selectedUser.role === 'user' && (
              <label className="flex items-start gap-2.5 rounded-r12 bg-brand-light-gray p-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={alsoSetEmployeeRole}
                  onChange={e => setAlsoSetEmployeeRole(e.target.checked)}
                  className="mt-0.5 w-4 h-4 accent-brand-green shrink-0"
                />
                <span className="text-xs text-brand-dark-blue">
                  Назначить роль «Сотрудник»
                  <span className="block text-[10px] text-brand-gray-blue mt-0.5">
                    Доступ к заказам точки даёт сама привязка к кофейне. Роль нужна, чтобы в
                    остальной панели человек не отображался как клиент.
                  </span>
                </span>
              </label>
            )}
          </div>
        </Drawer>
      )}

      {/* Открепление бариста */}
      <Modal
        isOpen={Boolean(staffToRemove)}
        onClose={() => setStaffToRemove(null)}
        title="Открепить бариста"
        description="Сотрудник потеряет доступ к заказам этой кофейни"
      >
        <div className="space-y-4 font-montserrat">
          <div className="flex items-start gap-2.5 rounded-r12 bg-red-50 p-3 text-xs text-brand-dark-blue">
            <AlertTriangle className="w-4 h-4 text-brand-red shrink-0 mt-0.5" />
            <span>
              <b className="text-brand-dark">{staffToRemove?.user_name}</b> больше не сможет
              принимать и закрывать заказы точки «{staffToRemove ? resolveShopName(staffToRemove) : ''}».
              Закрытые смены и история заказов сохранятся.
            </span>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setStaffToRemove(null)}
              disabled={isRemovingStaff}
            >
              Отмена
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleRemoveStaff}
              isLoading={isRemovingStaff}
              disabled={isRemovingStaff}
            >
              Открепить
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
