import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AdminActivityLog } from '../types';
import { Badge } from '../components/ui/Badge';
import { Table, Column } from '../components/ui/Table';
import { Drawer } from '../components/ui/Drawer';
import { ShieldCheck, Search, Clock, User, Globe, Code } from 'lucide-react';
import { Input } from '../components/ui/Input';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AdminActivityLog[]>([]);
  const [search, setSearch] = useState('');
  const [selectedLog, setSelectedLog] = useState<AdminActivityLog | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const data = await api.getActivityLogs();
      setLogs(data);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredLogs = logs.filter(l => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      l.summary.toLowerCase().includes(s) ||
      l.entity_name.toLowerCase().includes(s) ||
      l.user_name.toLowerCase().includes(s) ||
      l.user_login.includes(s)
    );
  });

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'CREATE':
        return <Badge variant="success">Создание</Badge>;
      case 'UPDATE':
        return <Badge variant="info">Изменение</Badge>;
      case 'DELETE':
        return <Badge variant="danger">Удаление</Badge>;
      case 'STATUS_CHANGE':
        return <Badge variant="warning">Смена статуса</Badge>;
      case 'LOGIN':
        return <Badge variant="purple">Вход в систему</Badge>;
      default:
        return <Badge variant="neutral">{action}</Badge>;
    }
  };

  const columns: Column<AdminActivityLog>[] = [
    {
      header: 'Время действия',
      accessor: row => (
        <span className="text-xs text-brand-dark-blue font-semibold">
          {new Date(row.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      header: 'Администратор',
      accessor: row => (
        <div>
          <p className="font-bold text-brand-dark">{row.user_name}</p>
          <span className="text-[10px] text-brand-gray-blue">{row.user_login}</span>
        </div>
      ),
    },
    {
      header: 'Тип действия',
      accessor: row => getActionBadge(row.action),
    },
    {
      header: 'Сущность',
      accessor: row => (
        <span className="text-xs font-bold text-brand-dark font-mono bg-slate-100 px-2 py-0.5 rounded">
          {row.entity_name} #{row.entity_id}
        </span>
      ),
    },
    {
      header: 'Описание события',
      accessor: row => (
        <p className="text-xs text-brand-dark max-w-md truncate font-medium">
          {row.summary}
        </p>
      ),
    },
    {
      header: 'IP Адрес',
      accessor: row => (
        <span className="text-xs font-mono text-brand-gray-blue">{row.ip_address || '127.0.0.1'}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-extrabold text-brand-dark flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-brand-green-text" />
            Журнал аудита действий администраторов
          </h3>
          <p className="text-xs text-brand-gray-blue mt-0.5">
            Фиксация всех изменений данных с историей старых и новых значений (Diff)
          </p>
        </div>

        <div className="w-full sm:w-72">
          <Input
            placeholder="Поиск по журналу..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredLogs}
        keyExtractor={l => l.id}
        onRowClick={l => setSelectedLog(l)}
        isLoading={isLoading}
        emptyMessage="Записей в журнале аудита пока нет"
      />

      {/* Detail Drawer */}
      {selectedLog && (
        <Drawer
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          title={`Событие #${selectedLog.id}`}
          subtitle={`Зафиксировано: ${new Date(selectedLog.created_at).toLocaleString()}`}
        >
          <div className="space-y-5 font-montserrat">
            <div className="bg-brand-light-gray p-4 rounded-r18 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-brand-gray-blue uppercase">Тип действия</span>
                {getActionBadge(selectedLog.action)}
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-slate-200">
                <span className="text-xs font-semibold text-brand-dark-blue">Администратор:</span>
                <span className="text-xs font-bold text-brand-dark">{selectedLog.user_name} ({selectedLog.user_login})</span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-slate-200">
                <span className="text-xs font-semibold text-brand-dark-blue">Объект:</span>
                <span className="text-xs font-mono font-bold text-brand-dark">{selectedLog.entity_name} #{selectedLog.entity_id}</span>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-slate-200">
                <span className="text-xs font-semibold text-brand-dark-blue">IP Адрес:</span>
                <span className="text-xs font-mono text-brand-dark">{selectedLog.ip_address || '127.0.0.1'}</span>
              </div>
            </div>

            <div className="bg-white border border-slate-100 rounded-r18 p-4 space-y-2">
              <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider">Описание</h4>
              <p className="text-xs text-brand-dark leading-relaxed font-medium">{selectedLog.summary}</p>
            </div>

            {selectedLog.changes && Object.keys(selectedLog.changes).length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-brand-dark uppercase tracking-wider flex items-center gap-1.5">
                  <Code className="w-4 h-4 text-brand-dark-blue" />
                  Детали изменений (JSON Diff)
                </h4>
                <pre className="p-4 bg-brand-dark text-slate-200 rounded-r18 text-xs font-mono overflow-x-auto">
                  {JSON.stringify(selectedLog.changes, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </Drawer>
      )}
    </div>
  );
};
