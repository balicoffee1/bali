import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Lock, User, ArrowRight, Eye, EyeOff, AlertCircle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [loginInput, setLoginInput] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!loginInput.trim() || !password.trim()) {
      setErrorMessage('Пожалуйста, введите логин и пароль.');
      return;
    }

    try {
      await login(loginInput.trim(), password);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Неверный логин или пароль. Проверьте введенные данные.');
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center items-center p-4 font-montserrat">
      <div className="max-w-md w-full space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-16 h-16 rounded-2xl bg-brand-lime flex items-center justify-center text-3xl font-extrabold mx-auto shadow-md">
            ☕
          </div>
          <h1 className="text-2xl font-extrabold text-brand-dark tracking-tight">Happy Island</h1>
          <p className="text-xs font-semibold text-brand-gray-blue uppercase tracking-wider">
            Панель управления сетью кофеен
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white p-8 rounded-r18 border border-slate-100 shadow-xl space-y-6">
          <div className="border-b border-slate-100 pb-4">
            <h2 className="text-base font-extrabold text-brand-dark">Вход в систему</h2>
            <p className="text-xs text-brand-gray-blue mt-0.5">
              Введите ваши учетные данные администратора
            </p>
          </div>

          {errorMessage && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-r12 flex items-center gap-2.5 text-xs text-brand-red font-medium animate-fade-in">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Логин / Телефон / Email"
              placeholder="admin или +79170000000"
              value={loginInput}
              onChange={e => setLoginInput(e.target.value)}
              leftIcon={<User className="w-4 h-4" />}
              required
              autoFocus
            />

            <Input
              label="Пароль"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              leftIcon={<Lock className="w-4 h-4" />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-brand-gray-blue hover:text-brand-dark focus:outline-none"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2"
              isLoading={isLoading}
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Войти в админ-панель
            </Button>
          </form>

          <div className="text-center text-[11px] text-brand-gray-blue pt-2 border-t border-slate-100">
            <p>© {new Date().getFullYear()} Happy Island Coffee. Все права защищены.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
