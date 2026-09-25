import React from 'react';
import { useAuth } from './context/AuthContext';
import { useApp } from './context/AppContext';
import { Layout } from './components/layout/Layout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { OrdersPage } from './pages/OrdersPage';
import { MenuPage } from './pages/MenuPage';
import { UsersPage } from './pages/UsersPage';
import { ShiftsPage } from './pages/ShiftsPage';
import { ReviewsPage } from './pages/ReviewsPage';
import { FranchisePage } from './pages/FranchisePage';
import { NotificationsPage } from './pages/NotificationsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { SettingsPage } from './pages/SettingsPage';
import { TelegramPage } from './pages/TelegramPage';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';

export const App: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const { currentPage } = useApp();

  const isStandalone =
    typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('standalone') === 'true';

  if (isStandalone) {
    return <KnowledgeBasePage isStandalone={true} />;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardPage />;
      case 'orders':
        return <OrdersPage />;
      case 'menu':
        return <MenuPage />;
      case 'users':
        return <UsersPage />;
      case 'shifts':
        return <ShiftsPage />;
      case 'reviews':
        return <ReviewsPage />;
      case 'franchise':
        return <FranchisePage />;
      case 'notifications':
        return <NotificationsPage />;
      case 'telegram':
        return <TelegramPage />;
      case 'logs':
        return <AuditLogsPage />;
      case 'settings':
        return <SettingsPage />;
      case 'knowledge-base':
        return <KnowledgeBasePage />;
      default:
        return <DashboardPage />;
    }
  };

  return <Layout>{renderPage()}</Layout>;
};
