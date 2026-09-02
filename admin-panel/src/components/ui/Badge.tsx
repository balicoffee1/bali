import React from 'react';
import { cn } from '../../utils/cn';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'neutral' | 'dark';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className,
  ...props
}) => {
  const variants = {
    success: 'bg-[#EBF7D4] text-[#4D7700] border border-[#AEEC2A]/50 font-semibold',
    warning: 'bg-amber-50 text-amber-700 border border-amber-200 font-semibold',
    danger: 'bg-red-50 text-red-700 border border-red-200 font-semibold',
    info: 'bg-blue-50 text-blue-700 border border-blue-200 font-semibold',
    purple: 'bg-purple-50 text-purple-700 border border-purple-200 font-semibold',
    neutral: 'bg-slate-100 text-slate-700 border border-slate-200 font-medium',
    dark: 'bg-brand-dark text-white font-medium',
  };

  const sizes = {
    sm: 'text-[11px] px-2 py-0.5 rounded-full',
    md: 'text-xs px-2.5 py-1 rounded-full',
  };

  return (
    <span className={cn('inline-flex items-center gap-1.5 select-none font-montserrat', variants[variant], sizes[size], className)} {...props}>
      {children}
    </span>
  );
};

export const ORDER_STATUS_LABELS: Record<string, string> = {
  New: 'Новый',
  Waiting: 'В ожидании',
  'In Progress': 'Выполняется',
  Completed: 'Выполнен',
  Canceled: 'Отменён',
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  New: 'Новый',
  Pending: 'Ожидает оплаты',
  Paid: 'Оплачен',
  Failed: 'Ошибка оплаты',
};

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  switch (status) {
    case 'New':
      return <Badge variant="info">Новый</Badge>;
    case 'Waiting':
      return <Badge variant="warning">В ожидании</Badge>;
    case 'In Progress':
      return <Badge variant="purple">Выполняется</Badge>;
    case 'Completed':
      return <Badge variant="success">Выполнен</Badge>;
    case 'Canceled':
      return <Badge variant="danger">Отменён</Badge>;
    case 'Paid':
      return <Badge variant="success">Оплачен</Badge>;
    case 'Pending':
      return <Badge variant="warning">Ожидает оплаты</Badge>;
    case 'Failed':
      return <Badge variant="danger">Ошибка оплаты</Badge>;
    case 'Open':
      return <Badge variant="success">Смена открыта</Badge>;
    case 'Closed':
      return <Badge variant="neutral">Смена закрыта</Badge>;
    case 'owner':
      return <Badge variant="dark">Владелец</Badge>;
    case 'admin':
      return <Badge variant="purple">Администратор</Badge>;
    case 'moderator':
      return <Badge variant="info">Модератор</Badge>;
    case 'support':
      return <Badge variant="warning">Поддержка</Badge>;
    case 'employee':
      return <Badge variant="success">Сотрудник</Badge>;
    case 'user':
      return <Badge variant="neutral">Клиент</Badge>;
    default:
      return <Badge variant="neutral">{ORDER_STATUS_LABELS[status] || PAYMENT_STATUS_LABELS[status] || status}</Badge>;
  }
};
