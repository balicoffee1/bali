import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Review } from '../types';
import { Card, StatCard } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Star, MessageSquare, ThumbsUp, Check, AlertCircle } from 'lucide-react';

export const ReviewsPage: React.FC = () => {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [ratingFilter, setRatingFilter] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadReviews();
  }, [ratingFilter]);

  const loadReviews = async () => {
    setIsLoading(true);
    try {
      const data = await api.getReviews(ratingFilter || undefined);
      setReviews(data);
    } finally {
      setIsLoading(false);
    }
  };

  const avgRating = reviews.length > 0
    ? (reviews.reduce((acc, r) => acc + r.evaluation, 0) / reviews.length).toFixed(1)
    : '5.0';

  const positivePercent = reviews.length > 0
    ? Math.round((reviews.filter(r => r.evaluation >= 4).length / reviews.length) * 100)
    : 100;

  return (
    <div className="space-y-6 animate-fade-in font-montserrat">
      {/* Top Ratings KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          title="Средняя оценка сети"
          value={`★ ${avgRating}`}
          subtitle="на основе отзывов гостей"
          icon={<Star className="w-6 h-6 text-brand-dark" />}
          iconBg="bg-brand-yellow text-brand-dark"
        />
        <StatCard
          title="Удовлетворенность (NPS)"
          value={`${positivePercent}%`}
          subtitle="положительных оценок (4-5★)"
          icon={<ThumbsUp className="w-6 h-6 text-emerald-600" />}
          iconBg="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          title="Всего отзывов"
          value={reviews.length}
          subtitle="в базе сервиса"
          icon={<MessageSquare className="w-6 h-6 text-brand-blue" />}
          iconBg="bg-blue-50 text-brand-blue"
        />
      </div>

      {/* Star Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <button
          onClick={() => setRatingFilter(null)}
          className={`px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
            ratingFilter === null
              ? 'bg-brand-lime text-brand-dark shadow-sm'
              : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
          }`}
        >
          Все отзывы ({reviews.length})
        </button>
        {[5, 4, 3, 2, 1].map(stars => (
          <button
            key={stars}
            onClick={() => setRatingFilter(stars)}
            className={`px-4 py-2 rounded-full text-xs font-bold whitespace-nowrap flex items-center gap-1.5 transition-all ${
              ratingFilter === stars
                ? 'bg-brand-lime text-brand-dark shadow-sm'
                : 'bg-white border border-slate-200 text-brand-dark-blue hover:bg-slate-50'
            }`}
          >
            <span>★ {stars}</span>
          </button>
        ))}
      </div>

      {/* Reviews Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {reviews.map(rev => (
          <Card key={rev.id} className="space-y-3 flex flex-col justify-between">
            <div>
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-xs font-bold text-brand-dark">{rev.user_name}</h4>
                  <span className="text-[10px] text-brand-gray-blue">{rev.coffee_shop_name}</span>
                </div>
                <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 font-extrabold text-xs border border-amber-200">
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" />
                  <span>{rev.evaluation}.0</span>
                </div>
              </div>

              {/* Badges: Delicious, Nice prices, Wide range */}
              <div className="flex flex-wrap gap-1.5 mt-2.5">
                {rev.very_tasty && (
                  <Badge variant="success" size="sm">
                    ✓ Очень вкусно
                  </Badge>
                )}
                {rev.wide_range && (
                  <Badge variant="info" size="sm">
                    ✓ Широкий ассортимент
                  </Badge>
                )}
                {rev.nice_prices && (
                  <Badge variant="purple" size="sm">
                    ✓ Приемлемые цены
                  </Badge>
                )}
              </div>

              {/* Comment text */}
              {rev.comments ? (
                <p className="text-xs text-brand-dark bg-slate-50 p-3 rounded-r12 mt-3 italic">
                  "{rev.comments}"
                </p>
              ) : (
                <p className="text-[11px] text-brand-gray-blue mt-2 italic">Без текстового комментария</p>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-brand-gray-blue font-semibold">
              <span>Заказ #{rev.orders}</span>
              {rev.order_price && <span>Сумма: {rev.order_price} ₽</span>}
            </div>
          </Card>
        ))}

        {reviews.length === 0 && !isLoading && (
          <div className="col-span-2 py-16 text-center text-brand-gray-blue bg-white rounded-r18 border border-slate-100">
            <span className="text-3xl block mb-2">⭐</span>
            <p className="text-sm font-semibold">Отзывов с такой оценкой пока нет</p>
          </div>
        )}
      </div>
    </div>
  );
};
