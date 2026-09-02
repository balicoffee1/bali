export type UserRole = 'owner' | 'admin' | 'moderator' | 'support' | 'employee' | 'user';

export interface User {
  id: number;
  login: string;
  first_name: string;
  last_name?: string;
  full_name: string;
  phone_number: string;
  email?: string;
  role: UserRole;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  photo?: string | null;
  orders_count?: number;
  discount_rate?: number | null;
  cards?: UserCard[];
}

export interface UserCard {
  id: number;
  card_number: string;
  expiration_date: string;
}

export interface City {
  id: number;
  name: string;
  shops_count?: number;
}

export interface CoffeeShop {
  id: number;
  city: number;
  city_name?: string;
  street: string;
  building_number: string;
  email: string;
  telegram_username?: string;
  telegram_id?: string;
  crm_system?: number;
  acquiring?: number;
  time_open: string;
  time_close: string;
  crm_email?: string;
  crm_layer_name?: string;
  lifepay_api_key?: string;
  lifepay_login?: string;
  inn?: string;
  phone_number?: string;
}

export interface Category {
  id: number;
  coffee_shop: number;
  coffee_shop_street?: string;
  name: string;
  which_menu: 'main_menu' | 'season_menu' | 'both';
  products_count?: number;
}

export interface AdditiveFlavor {
  id: number;
  coffee_shop?: number;
  name: string;
}

export interface Addon {
  id: number;
  coffee_shop?: number;
  name: string;
  description?: string;
  price: number;
  flavors?: number[];
  flavors_details?: AdditiveFlavor[];
}

export type ProductType = 'coffee' | 'ice_cream' | 'matcha' | 'tea' | 'cocktail' | 'fresh_juice';
export type TemperatureType = 'Hot' | 'Cold' | 'All';

export interface Product {
  id: number;
  coffee_shop: number;
  coffee_shop_name?: string;
  category: number;
  category_name?: string;
  product: string;
  price?: number | null;
  price_s?: number | null;
  price_m?: number | null;
  price_l?: number | null;
  availability: boolean;
  product_type: ProductType;
  can_be_hot_and_cold: boolean;
  temperature_type: TemperatureType;
  which_menu: 'main_menu' | 'season_menu' | 'both';
  addons?: number[];
  addons_details?: Addon[];
}

export type OrderStatus = 'New' | 'Waiting' | 'In Progress' | 'Completed' | 'Canceled';
export type PaymentStatus = 'New' | 'Pending' | 'Paid' | 'Failed';

export interface CartItem {
  id: number;
  product: number;
  product_name: string;
  size: 'S' | 'M' | 'L';
  amount: number;
  addons_names?: string[];
  flavors_names?: string[];
  item_total: number;
}

export interface Order {
  id: number;
  user: number;
  user_login: string;
  user_full_name: string;
  city_choose: number;
  city_name: string;
  coffee_shop: number;
  coffee_shop_address: string;
  staff?: number | null;
  staff_name?: string | null;
  client_comments?: string;
  staff_comments?: string;
  time_is_finish?: string;
  status_orders: OrderStatus;
  payment_status: PaymentStatus;
  receipt_photo?: string | null;
  full_price: number;
  cancellation_reason?: string;
  client_confirmed: boolean;
  issued: boolean;
  is_testing?: boolean;
  created_at: string;
  updated_at: string;
  items: CartItem[];
  review_details?: {
    evaluation: number;
    comments?: string;
    very_tasty: boolean;
    wide_range: boolean;
    nice_prices: boolean;
  } | null;
}

export interface StaffMember {
  id: number;
  users: number;
  user_name: string;
  user_phone: string;
  place_of_work: number;
  place_of_work_name?: string;
  current_shift_status: 'Open' | 'Closed';
}

export interface Shift {
  id: number;
  staff: number;
  staff_name: string;
  coffee_shop_name: string;
  start_time: string;
  end_time?: string | null;
  number_orders_closed: number;
  amount_closed_orders: number;
  status_shift: 'Open' | 'Closed';
}

export interface Review {
  id: number;
  coffee_shop: number;
  coffee_shop_name: string;
  user: number;
  user_name: string;
  user_phone: string;
  orders: number;
  order_price?: number;
  evaluation: number;
  very_tasty: boolean;
  wide_range: boolean;
  nice_prices: boolean;
  comments: string;
}

export interface FranchiseRequest {
  id: number;
  name: string;
  number_phone: string;
  text: string;
  status?: 'new' | 'in_progress' | 'completed' | 'rejected';
  manager_comment?: string;
  created_at?: string;
}

export interface DiscountCard {
  id: number;
  user: number;
  user_name: string;
  user_phone: string;
  is_active: boolean;
  qr_code: string;
  qr_code_image?: string;
  discount_rate: number;
  coffee_shop: number;
  coffee_shop_name: string;
}

export interface AdminActivityLog {
  id: number;
  user?: number | null;
  user_login: string;
  user_name: string;
  action: 'CREATE' | 'UPDATE' | 'DELETE' | 'STATUS_CHANGE' | 'LOGIN';
  entity_name: string;
  entity_id: string;
  summary: string;
  changes?: Record<string, any>;
  ip_address?: string;
  created_at: string;
}

export interface DashboardKPI {
  today_revenue: number;
  revenue_growth: number;
  today_orders_count: number;
  today_completed_count: number;
  today_canceled_count: number;
  average_check: number;
  total_users: number;
  active_shifts: number;
}

export interface DashboardChartPoint {
  date: string;
  revenue: number;
  orders_count: number;
  completed_count: number;
}

export interface TopProductItem {
  id: number;
  name: string;
  price: number;
  category: string;
  sales_count?: number;
}
