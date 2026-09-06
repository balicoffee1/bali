import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  AsYouType,
  CountryCode,
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
} from 'libphonenumber-js';
import { ChevronDown, Search, X, Check } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface PhoneInputProps {
  label?: string;
  error?: string;
  value?: string;
  onChange?: (value: string, isValid: boolean) => void;
  requiredAsterisk?: boolean;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
  className?: string;
  defaultCountry?: CountryCode;
}

interface CountryMeta {
  code: CountryCode;
  name: string;
  dialCode: string;
  flag: string;
}

const PRIORITY_COUNTRIES: CountryCode[] = [
  'RU', // Россия
  'ID', // Индонезия / Бали
  'KZ', // Казахстан
  'BY', // Беларусь
  'UZ', // Узбекистан
  'KG', // Кыргызстан
  'AE', // ОАЭ
  'TR', // Турция
  'US', // США
  'TH', // Таиланд
  'GB', // Великобритания
  'DE', // Германия
];

function getFlagEmoji(countryCode: string): string {
  if (!countryCode || countryCode.length !== 2) return '🌐';
  return countryCode
    .toUpperCase()
    .replace(/./g, char => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

const CUSTOM_NAMES: Record<string, string> = {
  RU: 'Россия',
  ID: 'Индонезия (Бали)',
  KZ: 'Казахстан',
  BY: 'Беларусь',
  UZ: 'Узбекистан',
  KG: 'Кыргызстан',
  AE: 'ОАЭ',
  TR: 'Турция',
  US: 'США',
  TH: 'Таиланд',
  GE: 'Грузия',
  AM: 'Армения',
  AZ: 'Азербайджан',
  GB: 'Великобритания',
  DE: 'Германия',
  FR: 'Франция',
  IT: 'Италия',
  ES: 'Испания',
  CN: 'Китай',
  SG: 'Сингапур',
  VN: 'Вьетнам',
};

export const PhoneInput: React.FC<PhoneInputProps> = ({
  label,
  error,
  value = '',
  onChange,
  requiredAsterisk,
  required,
  disabled = false,
  placeholder,
  id,
  className,
  defaultCountry = 'RU',
}) => {
  const [selectedCountry, setSelectedCountry] = useState<CountryCode>(defaultCountry);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Region display names in Russian
  const regionNames = useMemo(() => {
    try {
      return new Intl.DisplayNames(['ru', 'en'], { type: 'region' });
    } catch {
      return null;
    }
  }, []);

  // Build country metadata list
  const allCountries = useMemo<CountryMeta[]>(() => {
    const list = getCountries();
    return list
      .map(code => {
        let dialCode = '';
        try {
          dialCode = `+${getCountryCallingCode(code)}`;
        } catch {
          dialCode = '';
        }
        const name = CUSTOM_NAMES[code] || regionNames?.of(code) || code;
        return {
          code,
          name,
          dialCode,
          flag: getFlagEmoji(code),
        };
      })
      .filter(c => Boolean(c.dialCode));
  }, [regionNames]);

  // Priority vs other countries
  const priorityList = useMemo(() => {
    return PRIORITY_COUNTRIES.map(code => allCountries.find(c => c.code === code)).filter(
      Boolean
    ) as CountryMeta[];
  }, [allCountries]);

  // Filtered list for search
  const filteredCountries = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return allCountries;
    return allCountries.filter(
      c =>
        c.name.toLowerCase().includes(q) ||
        c.dialCode.includes(q) ||
        c.code.toLowerCase().includes(q)
    );
  }, [allCountries, searchQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isDropdownOpen]);

  // Auto-detect country if value changes from outside with a country code
  useEffect(() => {
    if (!value) return;
    const clean = value.trim();
    if (clean.startsWith('+')) {
      const ayt = new AsYouType();
      ayt.input(clean);
      const detected = ayt.getCountry();
      if (detected && detected !== selectedCountry) {
        setSelectedCountry(detected);
      }
    }
  }, [value]);

  const currentCountryMeta = useMemo(() => {
    return (
      allCountries.find(c => c.code === selectedCountry) || {
        code: selectedCountry,
        name: 'Россия',
        dialCode: '+7',
        flag: getFlagEmoji(selectedCountry),
      }
    );
  }, [allCountries, selectedCountry]);

  // Format and validate handler
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let raw = e.target.value;

    // Disallow characters other than digits, +, spaces, hyphens, parentheses
    raw = raw.replace(/[^\d+\s()\-.]/g, '');

    // Max ITU-T E.164 digits limit is 15
    const digitsOnly = raw.replace(/\D/g, '');
    if (digitsOnly.length > 15) return;

    if (!raw.trim()) {
      onChange?.('', true);
      return;
    }

    // Format with AsYouType
    let formatted = '';
    let detectedCountry: CountryCode | undefined;

    if (raw.startsWith('+')) {
      const ayt = new AsYouType();
      formatted = ayt.input(raw);
      detectedCountry = ayt.getCountry();
    } else {
      // If user typed without +, prefix with selected country dial code
      const dial = currentCountryMeta.dialCode;
      const cleanDigits = raw.replace(/\D/g, '');
      const ayt = new AsYouType(selectedCountry);
      formatted = ayt.input(`${dial}${cleanDigits}`);
      detectedCountry = ayt.getCountry() || selectedCountry;
    }

    if (detectedCountry && detectedCountry !== selectedCountry) {
      setSelectedCountry(detectedCountry);
    }

    // Validate
    let isValid = false;
    try {
      const parsed = parsePhoneNumberFromString(formatted, detectedCountry || selectedCountry);
      isValid = Boolean(parsed && parsed.isValid());
    } catch {
      isValid = false;
    }

    onChange?.(formatted, isValid);
  };

  const handleSelectCountry = (country: CountryMeta) => {
    setSelectedCountry(country.code);
    setIsDropdownOpen(false);
    setSearchQuery('');

    // Update existing number to new country prefix if appropriate
    let newNumber = country.dialCode + ' ';
    if (value) {
      const digits = value.replace(/\D/g, '');
      const oldDial = currentCountryMeta.dialCode.replace(/\D/g, '');
      // If number was starting with old country dial code, swap it
      if (digits.startsWith(oldDial)) {
        const nationalPart = digits.slice(oldDial.length);
        const ayt = new AsYouType(country.code);
        newNumber = ayt.input(`${country.dialCode}${nationalPart}`);
      }
    }

    let isValid = false;
    try {
      const parsed = parsePhoneNumberFromString(newNumber, country.code);
      isValid = Boolean(parsed && parsed.isValid());
    } catch {}

    onChange?.(newNumber, isValid);
    inputRef.current?.focus();
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange?.('', true);
    inputRef.current?.focus();
  };

  const inputId = id || (label ? `phone-input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className="w-full space-y-1.5 font-montserrat">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-semibold text-brand-dark-blue">
          {label}
          {(required || requiredAsterisk) && <span className="text-brand-red ml-1 font-bold">*</span>}
        </label>
      )}

      <div
        className={cn(
          'relative flex items-center h-[50px] bg-brand-light-gray rounded-r12 border border-transparent transition-all duration-150',
          'focus-within:border-brand-lime focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-lime/20',
          error && 'border-brand-red bg-red-50/30 focus-within:border-brand-red focus-within:ring-brand-red/20',
          disabled && 'opacity-60 pointer-events-none',
          className
        )}
      >
        {/* Country Selector Button */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="h-[50px] px-3 flex items-center gap-1.5 border-r border-slate-200 hover:bg-slate-200/50 rounded-l-r12 transition-colors focus:outline-none"
            aria-label={`Выбрана страна: ${currentCountryMeta.name}`}
          >
            <span className="text-lg leading-none" role="img" aria-label={currentCountryMeta.name}>
              {currentCountryMeta.flag}
            </span>
            <span className="text-xs font-bold text-brand-dark font-mono">
              {currentCountryMeta.dialCode}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-brand-gray-blue shrink-0" />
          </button>

          {/* Country Dropdown Popover */}
          {isDropdownOpen && (
            <div className="absolute top-[54px] left-0 z-50 w-72 max-h-80 bg-white rounded-r12 shadow-2xl border border-slate-100 flex flex-col overflow-hidden animate-fade-in-up">
              {/* Search Bar */}
              <div className="p-2 border-b border-slate-100 bg-slate-50/50">
                <div className="relative flex items-center">
                  <Search className="w-3.5 h-3.5 text-brand-gray-blue absolute left-2.5 pointer-events-none" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Поиск страны или кода..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full h-8 pl-8 pr-3 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-brand-lime font-medium"
                  />
                </div>
              </div>

              {/* Country List */}
              <div className="overflow-y-auto divide-y divide-slate-50 flex-1 p-1">
                {!searchQuery && (
                  <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-brand-gray-blue">
                    Популярные страны
                  </div>
                )}

                {(!searchQuery ? priorityList : []).map(country => (
                  <button
                    key={`prio-${country.code}`}
                    type="button"
                    onClick={() => handleSelectCountry(country)}
                    className={cn(
                      'w-full px-2.5 py-1.5 flex items-center justify-between text-xs rounded-lg hover:bg-brand-lime/10 transition-colors text-left',
                      selectedCountry === country.code && 'bg-brand-lime/20 font-bold'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="text-base leading-none">{country.flag}</span>
                      <span className="truncate text-brand-dark">{country.name}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      <span className="font-mono text-brand-gray-blue text-[11px]">
                        {country.dialCode}
                      </span>
                      {selectedCountry === country.code && (
                        <Check className="w-3 h-3 text-brand-dark" />
                      )}
                    </div>
                  </button>
                ))}

                {!searchQuery && (
                  <div className="px-2 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-brand-gray-blue">
                    Все страны
                  </div>
                )}

                {filteredCountries.map(country => (
                  <button
                    key={country.code}
                    type="button"
                    onClick={() => handleSelectCountry(country)}
                    className={cn(
                      'w-full px-2.5 py-1.5 flex items-center justify-between text-xs rounded-lg hover:bg-brand-lime/10 transition-colors text-left',
                      selectedCountry === country.code && 'bg-brand-lime/20 font-bold'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className="text-base leading-none">{country.flag}</span>
                      <span className="truncate text-brand-dark">{country.name}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      <span className="font-mono text-brand-gray-blue text-[11px]">
                        {country.dialCode}
                      </span>
                      {selectedCountry === country.code && (
                        <Check className="w-3 h-3 text-brand-dark" />
                      )}
                    </div>
                  </button>
                ))}

                {filteredCountries.length === 0 && (
                  <div className="py-4 text-center text-xs text-brand-gray-blue">
                    Страны не найдены
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Masked Input */}
        <input
          id={inputId}
          ref={inputRef}
          type="tel"
          disabled={disabled}
          placeholder={placeholder || currentCountryMeta.dialCode + ' (___) ___-__-__'}
          value={value}
          onChange={handleInputChange}
          className="w-full h-full bg-transparent px-3 text-sm font-medium text-brand-dark placeholder-brand-gray-blue focus:outline-none"
        />

        {/* Clear Button */}
        {value && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="p-2 text-brand-gray-blue hover:text-brand-dark transition-colors mr-1"
            title="Очистить"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {error && <p className="text-xs text-brand-red font-medium">{error}</p>}
    </div>
  );
};
