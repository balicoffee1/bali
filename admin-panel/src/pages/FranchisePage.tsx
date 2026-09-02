import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { FranchiseRequest } from '../types';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Table, Column } from '../components/ui/Table';
import { Phone, FileText, CheckCircle2, Clock, X } from 'lucide-react';

export const FranchisePage: React.FC = () => {
  const { addToast } = useApp();
  const { user } = useAuth();
  const canManage = Boolean(user?.is_superuser || ['owner', 'admin'].includes(user?.role || ''));
  const [requests, setRequests] = useState<FranchiseRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadRequests();
  }, []);

  const loadRequests = async () => {
    setIsLoading(true);
    try {
      const data = await api.getFranchiseRequests();
      setRequests(data);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await api.updateFranchiseStatus(id, newStatus);
      setRequests(prev => prev.map(r => (r.id === id ? { ...r, status: newStatus as any } : r)));
      addToast({ type: 'success', title: 'Статус заявки обновлен', message: `Переведено в "${newStatus}"` });
    } catch {
      addToast({ type: 'error', title: 'Ошибка', message: 'Не удалось обновить статус заявки' });
    }
  };

  const columns: Column<FranchiseRequest>[] = [
    {
      header: 'Заявитель',
      accessor: row => (
        <div>
          <p className="font-bold text-brand-dark">{row.name}</p>
          <div className="flex items-center gap-1.5 text-xs text-brand-dark-blue mt-0.5 font-semibold">
            <Phone className="w-3.5 h-3.5 text-brand-gray-blue" />
            <a href={`tel:${row.number_phone}`} className="hover:underline text-brand-blue">
              {row.number_phone}
            </a>
          </div>
        </div>
      ),
    },
    {
      header: 'Пожелания и локация',
      accessor: row => (
        <p className="text-xs text-brand-dark-blue max-w-md line-clamp-3 leading-relaxed">
          {row.text}
        </p>
      ),
    },
    {
      header: 'Статус обработки',
      accessor: row => (
        <select
          value={row.status || 'new'}
          onChange={e => handleStatusChange(row.id, e.target.value)}
          disabled={!canManage}
          className="bg-brand-light-gray text-xs font-bold text-brand-dark rounded-lg px-2.5 py-1.5 focus:outline-none border border-slate-200 cursor-pointer"
        >
          <option value="new">Новая заявка</option>
          <option value="in_progress">В работе / Переговоры</option>
          <option value="completed">Договор заключен</option>
          <option value="rejected">Отклонена</option>
        </select>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-extrabold text-brand-dark">Заявки на открытие франшизы</h3>
          <p className="text-xs text-brand-gray-blue mt-0.5">Входящие обращения от потенциальных партнеров</p>
        </div>
      </div>

      <Table
        columns={columns}
        data={requests}
        keyExtractor={r => r.id}
        isLoading={isLoading}
        emptyMessage="Заявок на франшизу пока нет"
      />
    </div>
  );
};
