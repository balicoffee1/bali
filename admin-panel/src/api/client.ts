import {
  User, City, CoffeeShop, Category, Product, Addon, AdditiveFlavor,
  Order, StaffMember, Shift, Review, FranchiseRequest, DiscountCard,
  AdminActivityLog, DashboardKPI, DashboardChartPoint, TopProductItem,
  OrderStatus, UserRole
} from '../types';
import {
  mockCities, mockCoffeeShops, mockCategories, mockProducts, mockAddons, mockFlavors,
  mockUsers, mockOrders, mockStaff, mockShifts, mockReviews, mockFranchiseRequests,
  mockDiscountCards, mockActivityLogs, mockDashboardKPI, mockChartPoints, mockTopProducts
} from './mockData';

class MockModeFallback extends Error {}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * DRF на ошибках валидации отвечает картой поле -> список сообщений
 * ({"login": ["Уже существует."]}). Раньше читались только error и detail,
 * поэтому пользователь вместо причины видел «Не удалось выполнить запрос».
 */
const FIELD_LABELS: Record<string, string> = {
  login: 'Логин',
  phone_number: 'Телефон',
  email: 'Email',
  first_name: 'Имя',
  last_name: 'Фамилия',
  role: 'Роль',
  users: 'Сотрудник',
  place_of_work: 'Кофейня',
};

function describeApiError(details: any): string {
  const fallback = 'Не удалось выполнить запрос.';
  if (!details) return fallback;
  if (typeof details === 'string') return details;
  if (details.error) return String(details.error);
  if (details.detail) return String(details.detail);

  const flatten = (value: unknown): string =>
    Array.isArray(value) ? value.map(flatten).join(' ') : String(value);

  const parts = Object.entries(details)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([field, value]) => {
      const text = flatten(value);
      if (field === 'non_field_errors') return text;
      return `${FIELD_LABELS[field] || field}: ${text}`;
    })
    .filter(Boolean);

  return parts.length ? parts.join('; ') : fallback;
}

// LocalStorage helpers to persist modifications in demo/offline mode
function loadFromStorage<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(`hi_admin_${key}`);
    return item ? JSON.parse(item) : defaultValue;
  } catch {
    return defaultValue;
  }
}

function saveToStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`hi_admin_${key}`, JSON.stringify(value));
  } catch {}
}

class ApiClient {
  private baseUrl = '/api/admin';
  private token: string | null = null;
  private refreshToken: string | null = null;
  public readonly useMock = import.meta.env.VITE_USE_MOCK_API === 'true';

  constructor() {
    this.token = localStorage.getItem('hi_admin_token');
    this.refreshToken = localStorage.getItem('hi_admin_refresh_token');
    // Initialize mock database in localStorage if empty
    if (this.useMock) {
      if (!localStorage.getItem('hi_admin_orders')) saveToStorage('orders', mockOrders);
      if (!localStorage.getItem('hi_admin_products')) saveToStorage('products', mockProducts);
      if (!localStorage.getItem('hi_admin_categories')) saveToStorage('categories', mockCategories);
      if (!localStorage.getItem('hi_admin_users')) saveToStorage('users', mockUsers);
      if (!localStorage.getItem('hi_admin_reviews')) saveToStorage('reviews', mockReviews);
      if (!localStorage.getItem('hi_admin_franchise')) saveToStorage('franchise', mockFranchiseRequests);
      if (!localStorage.getItem('hi_admin_logs')) saveToStorage('logs', mockActivityLogs);
    }
  }

  public setToken(token: string | null) {
    this.token = token;
    if (token) localStorage.setItem('hi_admin_token', token);
    else localStorage.removeItem('hi_admin_token');
  }

  public setTokens(access: string, refresh: string) {
    this.setToken(access);
    this.refreshToken = refresh;
    localStorage.setItem('hi_admin_refresh_token', refresh);
  }

  public clearSession() {
    this.setToken(null);
    this.refreshToken = null;
    localStorage.removeItem('hi_admin_refresh_token');
  }

  public hasSession() {
    return Boolean(this.token);
  }

  public isMockMode() {
    return this.useMock;
  }

  private ensureMockFallback(error: unknown) {
    if (!(error instanceof MockModeFallback)) throw error;
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.refreshToken || this.useMock) return false;

    try {
      const response = await fetch(`${this.baseUrl}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: this.refreshToken }),
      });
      if (!response.ok) return false;
      const data = await response.json();
      this.setToken(data.access);
      if (data.refresh) {
        this.refreshToken = data.refresh;
        localStorage.setItem('hi_admin_refresh_token', data.refresh);
      }
      return true;
    } catch {
      return false;
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}, retryAfterRefresh = true): Promise<T> {
    if (this.useMock) throw new MockModeFallback();

    const headers = {
      'Content-Type': 'application/json',
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      ...options.headers,
    };

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${endpoint}`, { ...options, headers });
    } catch (error) {
      throw new ApiError('Сервер недоступен. Проверьте подключение и повторите попытку.', 0, error);
    }

    if (response.status === 401 && retryAfterRefresh && !endpoint.startsWith('/auth/')) {
      if (await this.refreshAccessToken()) {
        return this.request<T>(endpoint, options, false);
      }
      this.clearSession();
      window.dispatchEvent(new Event('hi-admin-session-expired'));
    }

    if (!response.ok) {
      let details: any = null;
      try { details = await response.json(); } catch { /* empty error response */ }
      throw new ApiError(describeApiError(details), response.status, details);
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  // --- Auth ---
  async login(login: string, password: string): Promise<{ token: { access: string; refresh: string }; user: User }> {
    try {
      const result = await this.request<{ token: { access: string; refresh: string }; user: User }>('/auth/login/', {
        method: 'POST',
        body: JSON.stringify({ login, password }),
      });
      this.setTokens(result.token.access, result.token.refresh);
      return result;
    } catch (error) {
      this.ensureMockFallback(error);
      // Explicit demo credentials; mock mode is never enabled implicitly.
      const users: User[] = loadFromStorage('users', mockUsers);
      const found = users.find(u => u.login === login || u.phone_number === login || u.email === login);
      if (!found || password !== 'demo') {
        throw new ApiError('Неверный логин или пароль.', 401);
      }
      const token = { access: 'mock_jwt_access_token_123', refresh: 'mock_jwt_refresh_token_456' };
      this.setTokens(token.access, token.refresh);
      this.logActivity('LOGIN', 'CustomUser', String(found.id), `Вход пользователя ${found.full_name}`);
      return { token, user: found };
    }
  }

  async getMe(): Promise<{ user: User; permissions: any }> {
    try {
      return await this.request('/auth/me/');
    } catch (error) {
      this.ensureMockFallback(error);
      const users: User[] = loadFromStorage('users', mockUsers);
      const savedUser = localStorage.getItem('hi_admin_current_user');
      const user = savedUser ? JSON.parse(savedUser) as User : users[0];
      return {
        user,
        permissions: {
          is_super_admin: user.role === 'owner',
          is_admin: ['owner', 'admin'].includes(user.role),
          is_moderator: ['owner', 'admin', 'moderator'].includes(user.role),
          is_support: ['owner', 'admin', 'support'].includes(user.role),
        },
      };
    }
  }

  // --- Dashboard ---
  async getDashboardStats(coffeeShopId?: number, cityId?: number): Promise<{
    kpi: DashboardKPI;
    chart_data: DashboardChartPoint[];
    top_products: TopProductItem[];
    low_rating_reviews_count: number;
  }> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop_id', String(coffeeShopId));
      if (cityId) params.append('city_id', String(cityId));
      return await this.request(`/dashboard/stats/?${params}`);
    } catch (error) {
      this.ensureMockFallback(error);
      const orders: Order[] = loadFromStorage('orders', mockOrders);
      const reviews: Review[] = loadFromStorage('reviews', mockReviews);
      const lowCount = reviews.filter(r => r.evaluation <= 3).length;
      return {
        kpi: mockDashboardKPI,
        chart_data: mockChartPoints,
        top_products: mockTopProducts,
        low_rating_reviews_count: lowCount,
      };
    }
  }

  // --- Orders ---
  async getOrders(coffeeShopId?: number, statusFilter?: string): Promise<Order[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop', String(coffeeShopId));
      if (statusFilter && statusFilter !== 'All') params.append('status_orders', statusFilter);
      const res: any = await this.request(`/orders/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      let orders: Order[] = loadFromStorage('orders', mockOrders);
      if (coffeeShopId) orders = orders.filter(o => o.coffee_shop === coffeeShopId);
      if (statusFilter && statusFilter !== 'All') orders = orders.filter(o => o.status_orders === statusFilter);
      return orders;
    }
  }

  async updateOrderStatus(orderId: number, newStatus: OrderStatus, cancellationReason?: string): Promise<Order> {
    try {
      const res: any = await this.request(`/orders/${orderId}/update_status/`, {
        method: 'PATCH',
        body: JSON.stringify({ status_orders: newStatus, cancellation_reason: cancellationReason }),
      });
      return res.order;
    } catch (error) {
      this.ensureMockFallback(error);
      const orders: Order[] = loadFromStorage('orders', mockOrders);
      const idx = orders.findIndex(o => o.id === orderId);
      if (idx !== -1) {
        orders[idx].status_orders = newStatus;
        if (cancellationReason) orders[idx].cancellation_reason = cancellationReason;
        orders[idx].updated_at = new Date().toISOString();
        saveToStorage('orders', orders);
        this.logActivity('STATUS_CHANGE', 'Orders', String(orderId), `Заказ #${orderId}: статус изменен на ${newStatus}`);
        return orders[idx];
      }
      throw new Error('Order not found');
    }
  }

  // --- Users ---
  async getUsers(search?: string, roleFilter?: string): Promise<User[]> {
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (roleFilter && roleFilter !== 'All') params.append('role', roleFilter);
      const res: any = await this.request(`/users/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      let users: User[] = loadFromStorage('users', mockUsers);
      if (roleFilter && roleFilter !== 'All') users = users.filter(u => u.role === roleFilter);
      if (search) {
        const s = search.toLowerCase();
        users = users.filter(u => u.full_name.toLowerCase().includes(s) || u.login.includes(s) || u.phone_number.includes(s));
      }
      return users;
    }
  }

  /**
   * Создание сотрудника. Пароль не передаётся намеренно: в панель employee всё
   * равно не пустят (там нужен пароль и роль не ниже support), а мобильное
   * приложение авторизует по номеру телефона и SMS-коду. Логином служит тот же
   * номер — по нему приложение и ищет пользователя.
   */
  async createUser(userData: {
    first_name: string;
    last_name?: string;
    phone_number: string;
    email?: string;
    role?: UserRole;
  }): Promise<User> {
    const phone = userData.phone_number.trim();
    const payload = {
      login: phone,
      first_name: userData.first_name.trim(),
      last_name: (userData.last_name || '').trim(),
      phone_number: phone,
      email: (userData.email || '').trim(),
      role: userData.role || ('employee' as UserRole),
      is_active: true,
    };

    try {
      return await this.request<User>('/users/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } catch (error) {
      this.ensureMockFallback(error);
      const users: User[] = loadFromStorage('users', mockUsers);
      if (users.some(u => u.login === phone || u.phone_number === phone)) {
        throw new ApiError('Пользователь с таким номером телефона уже существует.', 400);
      }
      const created: User = {
        id: Date.now(),
        login: payload.login,
        first_name: payload.first_name,
        last_name: payload.last_name,
        full_name: `${payload.first_name} ${payload.last_name}`.trim(),
        phone_number: payload.phone_number,
        email: payload.email,
        role: payload.role,
        is_active: true,
        is_staff: false,
        is_superuser: false,
        photo: null,
        orders_count: 0,
        discount_rate: null,
      };
      users.push(created);
      saveToStorage('users', users);
      this.logActivity('CREATE', 'CustomUser', String(created.id), `Создан сотрудник ${created.full_name}`);
      return created;
    }
  }

  async toggleBlockUser(userId: number): Promise<{ is_active: boolean }> {
    try {
      return await this.request(`/users/${userId}/toggle_block/`, { method: 'POST' });
    } catch (error) {
      this.ensureMockFallback(error);
      const users: User[] = loadFromStorage('users', mockUsers);
      const user = users.find(u => u.id === userId);
      if (user) {
        user.is_active = !user.is_active;
        saveToStorage('users', users);
        this.logActivity('STATUS_CHANGE', 'CustomUser', String(userId), `Пользователь ${user.full_name} ${user.is_active ? 'разблокирован' : 'заблокирован'}`);
        return { is_active: user.is_active };
      }
      throw new Error('User not found');
    }
  }

  async setUserRole(userId: number, role: UserRole): Promise<User> {
    try {
      const res: any = await this.request(`/users/${userId}/set_role/`, {
        method: 'POST',
        body: JSON.stringify({ role }),
      });
      return res;
    } catch (error) {
      this.ensureMockFallback(error);
      const users: User[] = loadFromStorage('users', mockUsers);
      const user = users.find(u => u.id === userId);
      if (user) {
        user.role = role;
        user.is_staff = ['owner', 'admin', 'employee'].includes(role);
        saveToStorage('users', users);
        this.logActivity('UPDATE', 'CustomUser', String(userId), `Назначена роль ${role} пользователю ${user.full_name}`);
        return user;
      }
      throw new Error('User not found');
    }
  }

  // --- Menu / Products / Categories ---
  async getCategories(coffeeShopId?: number): Promise<Category[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop', String(coffeeShopId));
      const res: any = await this.request(`/categories/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      return loadFromStorage('categories', mockCategories);
    }
  }

  async createCategory(data: Partial<Category>): Promise<Category> {
    try {
      return await this.request('/categories/', { method: 'POST', body: JSON.stringify(data) });
    } catch (error) {
      this.ensureMockFallback(error);
      const categories: Category[] = loadFromStorage('categories', mockCategories);
      const newCat: Category = {
        id: Date.now(),
        coffee_shop: data.coffee_shop || 1,
        name: data.name || 'Новая категория',
        which_menu: data.which_menu || 'main_menu',
        products_count: 0,
      };
      categories.push(newCat);
      saveToStorage('categories', categories);
      this.logActivity('CREATE', 'Category', String(newCat.id), `Создана категория ${newCat.name}`);
      return newCat;
    }
  }

  async getProducts(coffeeShopId?: number, categoryId?: number): Promise<Product[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop', String(coffeeShopId));
      if (categoryId) params.append('category', String(categoryId));
      const res: any = await this.request(`/products/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      let products: Product[] = loadFromStorage('products', mockProducts);
      if (categoryId) products = products.filter(p => p.category === categoryId);
      return products;
    }
  }

  async toggleProductAvailability(productId: number): Promise<{ availability: boolean }> {
    try {
      return await this.request(`/products/${productId}/toggle_availability/`, { method: 'POST' });
    } catch (error) {
      this.ensureMockFallback(error);
      const products: Product[] = loadFromStorage('products', mockProducts);
      const prod = products.find(p => p.id === productId);
      if (prod) {
        prod.availability = !prod.availability;
        saveToStorage('products', products);
        this.logActivity('STATUS_CHANGE', 'Product', String(productId), `Товар ${prod.product} ${prod.availability ? 'включен' : 'переведен в стоп-лист'}`);
        return { availability: prod.availability };
      }
      throw new Error('Product not found');
    }
  }

  async saveProduct(productData: Partial<Product>): Promise<Product> {
    try {
      if (productData.id) {
        return await this.request(`/products/${productData.id}/`, { method: 'PATCH', body: JSON.stringify(productData) });
      } else {
        return await this.request('/products/', { method: 'POST', body: JSON.stringify(productData) });
      }
    } catch (error) {
      this.ensureMockFallback(error);
      const products: Product[] = loadFromStorage('products', mockProducts);
      if (productData.id) {
        const idx = products.findIndex(p => p.id === productData.id);
        if (idx !== -1) {
          products[idx] = { ...products[idx], ...productData } as Product;
          saveToStorage('products', products);
          this.logActivity('UPDATE', 'Product', String(productData.id), `Обновлен товар ${products[idx].product}`);
          return products[idx];
        }
      }
      const newProd: Product = {
        id: Date.now(),
        coffee_shop: productData.coffee_shop || 1,
        category: productData.category || 1,
        product: productData.product || 'Новый товар',
        price: productData.price || 200,
        price_s: productData.price_s || 170,
        price_m: productData.price_m || 200,
        price_l: productData.price_l || 240,
        availability: true,
        product_type: productData.product_type || 'coffee',
        can_be_hot_and_cold: productData.can_be_hot_and_cold || false,
        temperature_type: productData.temperature_type || 'Hot',
        which_menu: productData.which_menu || 'main_menu',
      };
      products.push(newProd);
      saveToStorage('products', products);
      this.logActivity('CREATE', 'Product', String(newProd.id), `Создан товар ${newProd.product}`);
      return newProd;
    }
  }

  async deleteProduct(productId: number): Promise<void> {
    try {
      await this.request(`/products/${productId}/`, { method: 'DELETE' });
    } catch (error) {
      this.ensureMockFallback(error);
      let products: Product[] = loadFromStorage('products', mockProducts);
      products = products.filter(p => p.id !== productId);
      saveToStorage('products', products);
      this.logActivity('DELETE', 'Product', String(productId), `Удален товар #${productId}`);
    }
  }

  // --- Addons & Flavors ---
  async getAddons(coffeeShopId?: number): Promise<Addon[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop', String(coffeeShopId));
      const res: any = await this.request(`/addons/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch {
      return loadFromStorage('addons', mockAddons);
    }
  }

  async saveAddon(addonData: Partial<Addon>): Promise<Addon> {
    try {
      if (addonData.id) {
        return await this.request(`/addons/${addonData.id}/`, { method: 'PATCH', body: JSON.stringify(addonData) });
      } else {
        return await this.request('/addons/', { method: 'POST', body: JSON.stringify(addonData) });
      }
    } catch {
      const addons: Addon[] = loadFromStorage('addons', mockAddons);
      if (addonData.id) {
        const idx = addons.findIndex(a => a.id === addonData.id);
        if (idx !== -1) {
          addons[idx] = { ...addons[idx], ...addonData } as Addon;
          saveToStorage('addons', addons);
          this.logActivity('UPDATE', 'Addon', String(addonData.id), `Обновлена добавка ${addons[idx].name}`);
          return addons[idx];
        }
      }
      const newAddon: Addon = {
        id: Date.now(),
        coffee_shop: addonData.coffee_shop || 1,
        name: addonData.name || 'Новая добавка',
        description: addonData.description || '',
        price: addonData.price || 0,
        flavors: addonData.flavors || [],
      };
      addons.push(newAddon);
      saveToStorage('addons', addons);
      this.logActivity('CREATE', 'Addon', String(newAddon.id), `Создана добавка ${newAddon.name}`);
      return newAddon;
    }
  }

  async deleteAddon(addonId: number): Promise<void> {
    try {
      await this.request(`/addons/${addonId}/`, { method: 'DELETE' });
    } catch {
      let addons: Addon[] = loadFromStorage('addons', mockAddons);
      addons = addons.filter(a => a.id !== addonId);
      saveToStorage('addons', addons);
      this.logActivity('DELETE', 'Addon', String(addonId), `Удалена добавка #${addonId}`);
    }
  }

  async getFlavors(coffeeShopId?: number): Promise<AdditiveFlavor[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('coffee_shop', String(coffeeShopId));
      const res: any = await this.request(`/flavors/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch {
      return loadFromStorage('flavors', mockFlavors);
    }
  }

  async saveFlavor(flavorData: Partial<AdditiveFlavor>): Promise<AdditiveFlavor> {
    try {
      if (flavorData.id) {
        return await this.request(`/flavors/${flavorData.id}/`, { method: 'PATCH', body: JSON.stringify(flavorData) });
      } else {
        return await this.request('/flavors/', { method: 'POST', body: JSON.stringify(flavorData) });
      }
    } catch {
      const flavors: AdditiveFlavor[] = loadFromStorage('flavors', mockFlavors);
      if (flavorData.id) {
        const idx = flavors.findIndex(f => f.id === flavorData.id);
        if (idx !== -1) {
          flavors[idx] = { ...flavors[idx], ...flavorData } as AdditiveFlavor;
          saveToStorage('flavors', flavors);
          return flavors[idx];
        }
      }
      const newFlavor: AdditiveFlavor = {
        id: Date.now(),
        coffee_shop: flavorData.coffee_shop || 1,
        name: flavorData.name || 'Новый вкус',
      };
      flavors.push(newFlavor);
      saveToStorage('flavors', flavors);
      this.logActivity('CREATE', 'AdditiveFlavor', String(newFlavor.id), `Создан вкус ${newFlavor.name}`);
      return newFlavor;
    }
  }

  async deleteFlavor(flavorId: number): Promise<void> {
    try {
      await this.request(`/flavors/${flavorId}/`, { method: 'DELETE' });
    } catch {
      let flavors: AdditiveFlavor[] = loadFromStorage('flavors', mockFlavors);
      flavors = flavors.filter(f => f.id !== flavorId);
      saveToStorage('flavors', flavors);
      this.logActivity('DELETE', 'AdditiveFlavor', String(flavorId), `Удален вкус #${flavorId}`);
    }
  }

  // --- Shifts & Staff ---
  async getShifts(): Promise<Shift[]> {
    try {
      const res: any = await this.request('/shifts/');
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      return loadFromStorage('shifts', mockShifts);
    }
  }

  async getStaff(coffeeShopId?: number): Promise<StaffMember[]> {
    try {
      const params = new URLSearchParams();
      if (coffeeShopId) params.append('place_of_work', String(coffeeShopId));
      const res: any = await this.request(`/staff/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      const staff: StaffMember[] = loadFromStorage('staff', mockStaff);
      return coffeeShopId ? staff.filter(s => s.place_of_work === coffeeShopId) : staff;
    }
  }

  /**
   * Привязка бариста к кофейне. Именно строка Staff, а не роль пользователя,
   * открывает доступ к заказам точки (staff-эндпоинты и WS-канал смены
   * проверяют Staff.place_of_work), поэтому назначение и снятие идут через неё.
   */
  async saveStaff(staffData: { id?: number; users: number; place_of_work: number }): Promise<StaffMember> {
    const payload = { users: staffData.users, place_of_work: staffData.place_of_work };
    try {
      if (staffData.id) {
        return await this.request(`/staff/${staffData.id}/`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
      }
      return await this.request('/staff/', { method: 'POST', body: JSON.stringify(payload) });
    } catch (error) {
      this.ensureMockFallback(error);
      const staff: StaffMember[] = loadFromStorage('staff', mockStaff);
      const users: User[] = loadFromStorage('users', mockUsers);
      const shops: CoffeeShop[] = loadFromStorage('coffee_shops', mockCoffeeShops);
      const user = users.find(u => u.id === staffData.users);
      const shop = shops.find(c => c.id === staffData.place_of_work);
      const shopName = shop
        ? [`${shop.street}, ${shop.building_number}`, shop.city_name].filter(Boolean).join(' - ')
        : undefined;
      const describe = (member: StaffMember) =>
        `${member.user_name} - ${member.place_of_work_name || 'кофейня #' + member.place_of_work}`;

      if (staffData.id) {
        const idx = staff.findIndex(m => m.id === staffData.id);
        if (idx !== -1) {
          staff[idx] = {
            ...staff[idx],
            users: staffData.users,
            place_of_work: staffData.place_of_work,
            user_name: user?.full_name || staff[idx].user_name,
            user_phone: user?.phone_number || staff[idx].user_phone,
            place_of_work_name: shopName || staff[idx].place_of_work_name,
          };
          saveToStorage('staff', staff);
          this.logActivity('UPDATE', 'Staff', String(staffData.id), `Переведен бариста ${describe(staff[idx])}`);
          return staff[idx];
        }
      }

      const created: StaffMember = {
        id: Date.now(),
        users: staffData.users,
        user_name: user?.full_name || 'Новый сотрудник',
        user_phone: user?.phone_number || '',
        place_of_work: staffData.place_of_work,
        place_of_work_name: shopName,
        current_shift_status: 'Closed',
      };
      staff.push(created);
      saveToStorage('staff', staff);
      this.logActivity('CREATE', 'Staff', String(created.id), `Назначен бариста ${describe(created)}`);
      return created;
    }
  }

  async deleteStaff(staffId: number): Promise<void> {
    try {
      await this.request(`/staff/${staffId}/`, { method: 'DELETE' });
    } catch (error) {
      this.ensureMockFallback(error);
      let staff: StaffMember[] = loadFromStorage('staff', mockStaff);
      staff = staff.filter(m => m.id !== staffId);
      saveToStorage('staff', staff);
      this.logActivity('DELETE', 'Staff', String(staffId), `Бариста #${staffId} откреплен от кофейни`);
    }
  }

  // --- Reviews ---
  async getReviews(ratingFilter?: number): Promise<Review[]> {
    try {
      const params = new URLSearchParams();
      if (ratingFilter) params.append('evaluation', String(ratingFilter));
      const res: any = await this.request(`/reviews/?${params}`);
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      let reviews: Review[] = loadFromStorage('reviews', mockReviews);
      if (ratingFilter) reviews = reviews.filter(r => r.evaluation === ratingFilter);
      return reviews;
    }
  }

  // --- Franchise ---
  async getFranchiseRequests(): Promise<FranchiseRequest[]> {
    try {
      const res: any = await this.request('/franchise-requests/');
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      return loadFromStorage('franchise', mockFranchiseRequests);
    }
  }

  async updateFranchiseStatus(id: number, status: string): Promise<void> {
    try {
      await this.request(`/franchise-requests/${id}/`, { method: 'PATCH', body: JSON.stringify({ status }) });
    } catch (error) {
      this.ensureMockFallback(error);
      const requests: FranchiseRequest[] = loadFromStorage('franchise', mockFranchiseRequests);
      const req = requests.find(r => r.id === id);
      if (req) {
        req.status = status as any;
        saveToStorage('franchise', requests);
      }
    }
  }

  // --- Push Notifications ---
  async broadcastNotification(title: string, message: string, cityId?: number, coffeeShopId?: number): Promise<{ recipients_count: number }> {
    try {
      return await this.request('/notifications/broadcast/', {
        method: 'POST',
        body: JSON.stringify({ title, message, city_id: cityId, coffee_shop_id: coffeeShopId }),
      });
    } catch (error) {
      this.ensureMockFallback(error);
      this.logActivity('CREATE', 'Notification', '', `Push-рассылка: "${title}". Отправлено всем клиентам.`);
      return { recipients_count: 1420 };
    }
  }

  // --- Audit Logs ---
  async getActivityLogs(): Promise<AdminActivityLog[]> {
    try {
      const res: any = await this.request('/audit-logs/');
      return Array.isArray(res) ? res : res.results || [];
    } catch (error) {
      this.ensureMockFallback(error);
      return loadFromStorage('logs', mockActivityLogs);
    }
  }

  private logActivity(action: AdminActivityLog['action'], entity_name: string, entity_id: string, summary: string) {
    const logs: AdminActivityLog[] = loadFromStorage('logs', mockActivityLogs);
    const newLog: AdminActivityLog = {
      id: Date.now(),
      user_login: 'admin',
      user_name: 'Администратор',
      action,
      entity_name,
      entity_id,
      summary,
      ip_address: '127.0.0.1',
      created_at: new Date().toISOString(),
    };
    logs.unshift(newLog);
    saveToStorage('logs', logs);
  }

  // --- Coffee Shops & Cities ---
  async getCities(): Promise<City[]> {
    try {
      const res: any = await this.request('/cities/');
      return Array.isArray(res) ? res : res.results || [];
    } catch {
      return loadFromStorage('cities', mockCities);
    }
  }

  async saveCity(cityData: Partial<City>): Promise<City> {
    try {
      if (cityData.id) {
        return await this.request(`/cities/${cityData.id}/`, { method: 'PATCH', body: JSON.stringify(cityData) });
      } else {
        return await this.request('/cities/', { method: 'POST', body: JSON.stringify(cityData) });
      }
    } catch {
      const cities: City[] = loadFromStorage('cities', mockCities);
      if (cityData.id) {
        const idx = cities.findIndex(c => c.id === cityData.id);
        if (idx !== -1) {
          cities[idx] = { ...cities[idx], ...cityData } as City;
          saveToStorage('cities', cities);
          this.logActivity('UPDATE', 'City', String(cityData.id), `Обновлен город ${cities[idx].name}`);
          return cities[idx];
        }
      }
      const newCity: City = {
        id: Date.now(),
        name: cityData.name || 'Новый город',
        shops_count: 0,
      };
      cities.push(newCity);
      saveToStorage('cities', cities);
      this.logActivity('CREATE', 'City', String(newCity.id), `Создан город ${newCity.name}`);
      return newCity;
    }
  }

  async deleteCity(cityId: number): Promise<void> {
    try {
      await this.request(`/cities/${cityId}/`, { method: 'DELETE' });
    } catch {
      let cities: City[] = loadFromStorage('cities', mockCities);
      cities = cities.filter(c => c.id !== cityId);
      saveToStorage('cities', cities);
      this.logActivity('DELETE', 'City', String(cityId), `Удален город #${cityId}`);
    }
  }

  async getCoffeeShops(): Promise<CoffeeShop[]> {
    try {
      const res: any = await this.request('/coffee-shops/');
      return Array.isArray(res) ? res : res.results || [];
    } catch {
      return loadFromStorage('coffee_shops', mockCoffeeShops);
    }
  }

  async saveCoffeeShop(shopData: Partial<CoffeeShop>): Promise<CoffeeShop> {
    try {
      if (shopData.id) {
        return await this.request(`/coffee-shops/${shopData.id}/`, { method: 'PATCH', body: JSON.stringify(shopData) });
      } else {
        return await this.request('/coffee-shops/', { method: 'POST', body: JSON.stringify(shopData) });
      }
    } catch {
      const shops: CoffeeShop[] = loadFromStorage('coffee_shops', mockCoffeeShops);
      const cities: City[] = loadFromStorage('cities', mockCities);
      const cityName = cities.find(c => c.id === shopData.city)?.name || 'Альметьевск';

      if (shopData.id) {
        const idx = shops.findIndex(s => s.id === shopData.id);
        if (idx !== -1) {
          shops[idx] = { ...shops[idx], ...shopData, city_name: cityName } as CoffeeShop;
          saveToStorage('coffee_shops', shops);
          this.logActivity('UPDATE', 'CoffeeShop', String(shopData.id), `Обновлена кофейня ${shops[idx].street}`);
          return shops[idx];
        }
      }
      const newShop: CoffeeShop = {
        id: Date.now(),
        city: shopData.city || 1,
        city_name: cityName,
        street: shopData.street || 'Новая улица',
        building_number: shopData.building_number || '1',
        email: shopData.email || 'info@happy-island.coffee',
        telegram_username: shopData.telegram_username || '',
        telegram_id: shopData.telegram_id || '',
        time_open: shopData.time_open || '08:00',
        time_close: shopData.time_close || '22:00',
        crm_email: shopData.crm_email || '',
        crm_layer_name: shopData.crm_layer_name || 'Основной зал',
        inn: shopData.inn || '',
        phone_number: shopData.phone_number || '',
      };
      shops.push(newShop);
      saveToStorage('coffee_shops', shops);
      this.logActivity('CREATE', 'CoffeeShop', String(newShop.id), `Создана кофейня ${newShop.street}`);
      return newShop;
    }
  }

  async deleteCoffeeShop(shopId: number): Promise<void> {
    try {
      await this.request(`/coffee-shops/${shopId}/`, { method: 'DELETE' });
    } catch {
      let shops: CoffeeShop[] = loadFromStorage('coffee_shops', mockCoffeeShops);
      shops = shops.filter(s => s.id !== shopId);
      saveToStorage('coffee_shops', shops);
      this.logActivity('DELETE', 'CoffeeShop', String(shopId), `Удалена кофейня #${shopId}`);
    }
  }
}

export const api = new ApiClient();
