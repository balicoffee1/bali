import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Shift, StaffMember } from '../types';
import { Card, StatCard } from '../components/ui/Card';
import { StatusBadge, Badge } from '../components/ui/Badge';
import { Table, Column } from '../components/ui/Table';
import { Clock, CheckCircle2, User, DollarSign, Calendar } from 'lucide-react';

export const ShiftsPage: React.FC = () => {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadShiftsData();
  }, []);

  const loadShiftsData = async () => {
    setIsLoading(true);
    try {
      const [shiftsData, staffData] = await Promise.all([
        api.getShifts(),
        api.getStaff(),
      ]);
      setShifts(shiftsData);
      setStaff(staffData);
    } finally {
      setIsLoading(false);
    }
  };

  const openShiftsCount = shifts.filter(s => s.status_shift === 'Open').length;
  const totalRevenueToday = shifts.reduce((acc, s) => acc + Number(s.amount_closed_orders || 0), 0);

  const columns: Column<Shift>[] = [
    {
      header: 'Сотрудник (Бариста)',
      accessor: row => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-light-gray flex items-center justify-center text-xs font-bold text-brand-dark-blue">
            {row.staff_name ? row.staff_name[0] : 'S'}
          </div>
          <div>
            <p className="font-bold text-brand-dark">{row.staff_name}</p>
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
          icon={<User className="w-6 h-6 text-brand-dark-blue" />}
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

      {/* Shifts History Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-extrabold text-brand-dark">Журнал рабочих смен</h3>
          <span className="text-xs text-brand-gray-blue font-semibold">Всего смен: {shifts.length}</span>
        </div>

        <Table
          columns={columns}
          data={shifts}
          keyExtractor={s => s.id}
          isLoading={isLoading}
          emptyMessage="Смены не найдены"
        />
      </div>
    </div>
  );
};
