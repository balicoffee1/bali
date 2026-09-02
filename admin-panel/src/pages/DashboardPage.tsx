import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { DashboardKPI, DashboardChartPoint, TopProductItem, Order } from '../types';
import { Card, StatCard } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/Badge';
import {
  DollarSign, ShoppingBag, Users, Clock, ArrowRight,
  AlertTriangle, TrendingUp, Award, Coffee
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts';

export const DashboardPage: React.FC = () => {
  const { setCurrentPage, selectedShopId, selectedCityId } = useApp();
  const [kpi, setKpi] = useState<DashboardKPI | null>(null);
  const [chartData, setChartData] = useState<DashboardChartPoint[]>([]);
  const [topProducts, setTopProducts] = useState<TopProductItem[]>([]);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [lowReviewsCount, setLowReviewsCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, [selectedShopId, selectedCityId]);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const data = await api.getDashboardStats(selectedShopId || undefined, selectedCityId || undefined);
      setKpi(data.kpi);
      setChartData(data.chart_data);
      setTopProducts(data.top_products);
      setLowReviewsCount(data.low_rating_reviews_count);

      const orders = await api.getOrders(selectedShopId || undefined);
      setRecentOrders(orders.slice(0, 5));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Alert banner if low reviews */}
      {lowReviewsCount > 0 && (
        <div className="bg-amber-50 border border-amber-200 p-4 rounded-r18 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-brand-orange/20 text-brand-orange flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-amber-900">Внимание к качеству сервиса</h4>
              <p className="text-xs text-amber-700 mt-0.5">
                Поступило {lowReviewsCount} отзыв(а) с оценкой ≤ 3 звезды, требующих внимания управляющего.
              </p>
            </div>
          </div>
          <Button size="sm" variant="dark" onClick={() => setCurrentPage('reviews')}>
            Проверить отзывы
          </Button>
        </div>
      )}

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Выручка сегодня"
          value={`${(kpi?.today_revenue || 0).toLocaleString()} ₽`}
          growth={kpi?.revenue_growth}
          subtitle="к вчерашнему дню"
          icon={<DollarSign className="w-6 h-6 text-brand-dark" />}
          iconBg="bg-brand-lime text-brand-dark"
        />
        <StatCard
          title="Заказы сегодня"
          value={kpi?.today_orders_count || 0}
          growth={8.5}
          subtitle={`${kpi?.today_completed_count || 0} выполнено, ${kpi?.today_canceled_count || 0} отменено`}
          icon={<ShoppingBag className="w-6 h-6 text-brand-dark-blue" />}
          iconBg="bg-slate-100 text-brand-dark-blue"
        />
        <StatCard
          title="Средний чек"
          value={`${(kpi?.average_check || 0).toLocaleString()} ₽`}
          growth={4.1}
          subtitle="по всем точкам"
          icon={<TrendingUp className="w-6 h-6 text-brand-green-text" />}
          iconBg="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          title="Открытые смены"
          value={kpi?.active_shifts || 0}
          subtitle="бариста на смене"
          icon={<Clock className="w-6 h-6 text-brand-blue" />}
          iconBg="bg-blue-50 text-brand-blue"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sales & Orders Dynamics Chart */}
        <Card className="lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div>
              <h3 className="text-base font-extrabold text-brand-dark">Динамика продаж (7 дней)</h3>
              <p className="text-xs font-medium text-brand-gray-blue mt-0.5">Выручка и количество закрытых заказов</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-bold">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-brand-lime"></span>
                <span>Выручка (₽)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-brand-dark-blue"></span>
                <span>Заказы</span>
              </div>
            </div>
          </div>

          <div className="h-72 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#AEEC2A" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#AEEC2A" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: '#94A3B8', fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: '#94A3B8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#2B2D31',
                    borderRadius: '12px',
                    border: 'none',
                    color: '#fff',
                    fontSize: '12px',
                    fontFamily: 'Montserrat',
                  }}
                  formatter={(val: any, name: string) => [
                    name === 'revenue' ? `${val.toLocaleString()} ₽` : val,
                    name === 'revenue' ? 'Выручка' : 'Заказы',
                  ]}
                />
                <Area type="monotone" dataKey="revenue" stroke="#73A900" strokeWidth={2.5} fillOpacity={1} fill="url(#revenueGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Top 5 Products */}
        <Card className="flex flex-col justify-between">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div>
              <h3 className="text-base font-extrabold text-brand-dark">Топ позиций меню</h3>
              <p className="text-xs font-medium text-brand-gray-blue mt-0.5">Лидеры продаж</p>
            </div>
            <Award className="w-5 h-5 text-brand-yellow" />
          </div>

          <div className="space-y-3.5 my-4 flex-1">
            {topProducts.map((prod, idx) => (
              <div key={prod.id} className="flex items-center justify-between p-2.5 rounded-r12 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-brand-light-gray flex items-center justify-center text-xs font-extrabold text-brand-dark-blue">
                    {idx + 1}
                  </span>
                  <div>
                    <p className="text-xs font-bold text-brand-dark">{prod.name}</p>
                    <span className="text-[10px] font-medium text-brand-gray-blue">{prod.category}</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs font-extrabold text-brand-green-text">{prod.price} ₽</p>
                  {prod.sales_count && (
                    <span className="text-[10px] text-brand-gray-blue font-semibold">{prod.sales_count} шт</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <Button variant="secondary" size="sm" className="w-full" onClick={() => setCurrentPage('menu')}>
            Перейти в меню
          </Button>
        </Card>
      </div>

      {/* Recent Orders Desk */}
      <Card>
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-4">
          <div>
            <h3 className="text-base font-extrabold text-brand-dark">Текущие заказы (Live Desk)</h3>
            <p className="text-xs font-medium text-brand-gray-blue mt-0.5">Последние поступившие заказы</p>
          </div>
          <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />} onClick={() => setCurrentPage('orders')}>
            Все заказы
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-medium text-brand-dark">
            <thead>
              <tr className="bg-slate-50 text-[11px] font-bold text-brand-dark-blue uppercase border-b border-slate-100">
                <th className="py-3 px-4">№ Заказа</th>
                <th className="py-3 px-4">Клиент</th>
                <th className="py-3 px-4">Состав заказа</th>
                <th className="py-3 px-4">Сумма</th>
                <th className="py-3 px-4">Статус</th>
                <th className="py-3 px-4">Оплата</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentOrders.map(order => (
                <tr
                  key={order.id}
                  onClick={() => setCurrentPage('orders')}
                  className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                >
                  <td className="py-3 px-4 font-bold text-brand-dark">#{order.id}</td>
                  <td className="py-3 px-4">
                    <p className="font-bold">{order.user_full_name}</p>
                    <span className="text-[10px] text-brand-gray-blue">{order.user_login}</span>
                  </td>
                  <td className="py-3 px-4 text-brand-dark-blue">
                    {order.items.map(it => `${it.product_name} (${it.size})`).join(', ')}
                  </td>
                  <td className="py-3 px-4 font-extrabold text-brand-dark">{order.full_price} ₽</td>
                  <td className="py-3 px-4">
                    <StatusBadge status={order.status_orders} />
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={order.payment_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
