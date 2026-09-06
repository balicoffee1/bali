from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from orders.models import Orders


LOYALTY_THRESHOLD = Decimal("5000.00")
LOYALTY_DISCOUNT_PERCENT = Decimal("5.00")
MONEY_STEP = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LoyaltyStatus:
    qualifying_spend: Decimal
    progress: Decimal
    threshold: Decimal
    remaining: Decimal
    discount_percent: Decimal
    is_eligible: bool

    def as_dict(self) -> dict:
        return {
            "qualifying_spend": self.qualifying_spend,
            "progress": self.progress,
            "threshold": self.threshold,
            "remaining": self.remaining,
            "discount_percent": self.discount_percent,
            "is_eligible": self.is_eligible,
        }


@dataclass(frozen=True)
class CartPricing:
    subtotal: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    total: Decimal
    loyalty: LoyaltyStatus

    def as_dict(self) -> dict:
        return {
            "subtotal_cart_price": self.subtotal,
            "discount_percent": self.discount_percent,
            "discount_amount": self.discount_amount,
            "total_cart_price": self.total,
            "has_discount": self.discount_amount > 0,
            "loyalty": self.loyalty.as_dict(),
        }


def get_loyalty_status(user) -> LoyaltyStatus:
    """Return loyalty progress calculated only from trusted server data."""
    qualifying_spend = (
        Orders.objects.filter(
            user=user,
            status_orders=Orders.COMPLETED,
            is_testing=False,
        ).aggregate(total=Sum("full_price"))["total"]
        or Decimal("0.00")
    )
    qualifying_spend = _money(qualifying_spend)
    is_eligible = qualifying_spend >= LOYALTY_THRESHOLD

    return LoyaltyStatus(
        qualifying_spend=qualifying_spend,
        progress=min(qualifying_spend, LOYALTY_THRESHOLD),
        threshold=LOYALTY_THRESHOLD,
        remaining=max(LOYALTY_THRESHOLD - qualifying_spend, Decimal("0.00")),
        discount_percent=LOYALTY_DISCOUNT_PERCENT,
        is_eligible=is_eligible,
    )


def calculate_cart_pricing(user, cart) -> CartPricing:
    subtotal = _money(Decimal(cart.cart_total_price))
    loyalty = get_loyalty_status(user)
    discount_percent = loyalty.discount_percent if loyalty.is_eligible else Decimal("0.00")
    discount_amount = _money(subtotal * discount_percent / Decimal("100"))

    return CartPricing(
        subtotal=subtotal,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        total=_money(subtotal - discount_amount),
        loyalty=loyalty,
    )
