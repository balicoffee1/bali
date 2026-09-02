import React from 'react';
import { cn } from '../../utils/cn';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className,
  hoverable = false,
  ...props
}) => {
  return (
    <div
      className={cn(
        'bg-white rounded-r18 border border-slate-100/80 shadow-card p-5 font-montserrat transition-all duration-200',
        hoverable && 'hover:shadow-hover hover:border-slate-200 cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  growth?: number; // e.g. +14.2%
  icon?: React.ReactNode;
  iconBg?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  growth,
  icon,
  iconBg = 'bg-brand-lime/20 text-brand-dark',
}) => {
  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-brand-gray-blue uppercase tracking-wider">{title}</p>
          <h3 className="text-2xl lg:text-3xl font-extrabold text-brand-dark mt-1.5">{value}</h3>
        </div>
        {icon && (
          <div className={cn('w-12 h-12 rounded-r12 flex items-center justify-center shrink-0', iconBg)}>
            {icon}
          </div>
        )}
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs">
        {growth !== undefined && (
          <span
            className={cn(
              'font-bold px-1.5 py-0.5 rounded-md flex items-center',
              growth >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-brand-red'
            )}
          >
            {growth >= 0 ? `+${growth}%` : `${growth}%`}
          </span>
        )}
        {subtitle && <span className="text-brand-gray-blue font-medium">{subtitle}</span>}
      </div>
    </Card>
  );
};
