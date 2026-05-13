import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const COUNTRIES = [
  { code: "IN",  flag: "🇮🇳", dial: "+91",  pattern: /^[6-9]\d{9}$/,    label: "India",           localLen: "10 digits starting 6�9" },
  { code: "US",  flag: "🇺🇸", dial: "+1",   pattern: /^\d{10}$/,         label: "USA",             localLen: "10 digits" },
  { code: "AE",  flag: "🇦🇪", dial: "+971", pattern: /^5\d{8}$/,         label: "UAE",             localLen: "9 digits starting 5" },
  { code: "GB",  flag: "🇬🇧", dial: "+44",  pattern: /^\d{10}$/,         label: "UK",              localLen: "10 digits" },
  { code: "SG",  flag: "🇸🇬", dial: "+65",  pattern: /^[689]\d{7}$/,     label: "Singapore",       localLen: "8 digits" },
  { code: "AU",  flag: "🇦🇺", dial: "+61",  pattern: /^[2-9]\d{8}$/,     label: "Australia",       localLen: "9 digits" },
  { code: "SA",  flag: "🇸🇦", dial: "+966", pattern: /^5\d{8}$/,         label: "Saudi Arabia",    localLen: "9 digits starting 5" },
  { code: "KW",  flag: "🇰🇼", dial: "+965", pattern: /^[569]\d{7}$/,     label: "Kuwait",          localLen: "8 digits" },
  { code: "QA",  flag: "🇶🇦", dial: "+974", pattern: /^[3-7]\d{7}$/,     label: "Qatar",           localLen: "8 digits" },
  { code: "BH",  flag: "🇧🇭", dial: "+973", pattern: /^[136]\d{7}$/,     label: "Bahrain",         localLen: "8 digits" },
  { code: "OM",  flag: "🇴🇲", dial: "+968", pattern: /^[279]\d{7}$/,     label: "Oman",            localLen: "8 digits" },
  { code: "MY",  flag: "🇲🇾", dial: "+60",  pattern: /^1\d{8,9}$/,       label: "Malaysia",        localLen: "9�10 digits starting 1" },
  { code: "LK",  flag: "🇱🇰", dial: "+94",  pattern: /^7\d{8}$/,         label: "Sri Lanka",       localLen: "9 digits starting 7" },
  { code: "NP",  flag: "🇳🇵", dial: "+977", pattern: /^9[78]\d{8}$/,     label: "Nepal",           localLen: "10 digits" },
  { code: "BD",  flag: "🇧🇩", dial: "+880", pattern: /^1[3-9]\d{8}$/,    label: "Bangladesh",      localLen: "10 digits starting 1" },
  { code: "CN",  flag: "🇨🇳", dial: "+86",  pattern: /^1[3-9]\d{9}$/,    label: "China",           localLen: "11 digits starting 1" },
  { code: "JP",  flag: "🇯🇵", dial: "+81",  pattern: /^[789]0\d{8}$/,    label: "Japan",           localLen: "10 digits" },
  { code: "HK",  flag: "🇭🇰", dial: "+852", pattern: /^[5-9]\d{7}$/,     label: "Hong Kong",       localLen: "8 digits" },
  { code: "DE",  flag: "🇩🇪", dial: "+49",  pattern: /^\d{10,11}$/,      label: "Germany",         localLen: "10�11 digits" },
  { code: "FR",  flag: "🇫🇷", dial: "+33",  pattern: /^[67]\d{8}$/,      label: "France",          localLen: "9 digits starting 6/7" },
  { code: "ZA",  flag: "🇿🇦", dial: "+27",  pattern: /^[678]\d{8}$/,     label: "South Africa",    localLen: "9 digits" },
  { code: "KE",  flag: "🇰🇪", dial: "+254", pattern: /^[17]\d{8}$/,      label: "Kenya",           localLen: "9 digits" },
  { code: "PK",  flag: "🇵🇰", dial: "+92",  pattern: /^3\d{9}$/,         label: "Pakistan",        localLen: "10 digits starting 3" },
  { code: "NZ",  flag: "🇳🇿", dial: "+64",  pattern: /^[278]\d{7,9}$/,   label: "New Zealand",     localLen: "8�10 digits" },
  { code: "CA",  flag: "🇨🇦", dial: "+1",   pattern: /^\d{10}$/,         label: "Canada",          localLen: "10 digits" },
  { code: "IE",  flag: "🇮🇪", dial: "+353", pattern: /^8[3-9]\d{7}$/,    label: "Ireland",         localLen: "9 digits starting 8" },
  { code: "CH",  flag: "🇨🇭", dial: "+41",  pattern: /^[789]\d{8}$/,     label: "Switzerland",     localLen: "9 digits" },
  { code: "NL",  flag: "🇳🇱", dial: "+31",  pattern: /^6\d{8}$/,         label: "Netherlands",     localLen: "9 digits starting 6" },
];

/** Find the country object for an ISO alpha-2 code, falling back to India. */
function findByCode(code) {
  return COUNTRIES.find(c => c.code === code) ?? COUNTRIES[0];
}

/** Parse a stored value like "+91 9876543210" into { country, local }. */
function parseValue(value, defaultCode = 'IN') {
  if (!value || !value.trim()) {
    return { country: findByCode(defaultCode), local: '' };
  }
  if (value.startsWith('+') && value.includes(' ')) {
    const spaceIdx = value.indexOf(' ');
    const dial = value.slice(0, spaceIdx);
    const local = value.slice(spaceIdx + 1);
    const country = COUNTRIES.find(c => c.dial === dial) ?? findByCode(defaultCode);
    return { country, local };
  }
  // Bare number � keep as local under default country
  return { country: findByCode(defaultCode), local: value };
}

/**
 * Export a react-hook-form validate function that checks the local number
 * against the selected country's pattern.
 */
export function makePhoneValidator() {
  return (value) => {
    if (!value || !value.trim()) return true; // field is optional
    const { country, local } = parseValue(value);
    if (!local) return true;
    if (!country.pattern.test(local)) {
      return `${country.label} mobile: ${country.localLen}`;
    }
    return true;
  };
}

/**
 * PhoneInput � flag + dial-code dropdown paired with a local number input.
 *
 * Props:
 *   value            � controlled string, stored as "+91 9876543210" or ""
 *   onChange         � called with the new string value
 *   error            � validation error message (from react-hook-form)
 *   disabled         � disables both controls
 *   placeholder      � placeholder for the number input
 *   defaultCountryCode � ISO alpha-2 to pre-select when value is empty
 *                        (defaults to sessionStorage.default_country_code ?? "IN")
 */
export default function PhoneInput({
  value,
  onChange,
  error,
  disabled = false,
  placeholder = "Mobile number",
  defaultCountryCode,
}) {
  const resolvedDefault =
    defaultCountryCode ||
    sessionStorage.getItem('default_country_code') ||
    'IN';

  const [country, setCountry] = useState(() => parseValue(value, resolvedDefault).country);
  const [local, setLocal]     = useState(() => parseValue(value, resolvedDefault).local);

  // Sync external value changes (e.g. react-hook-form reset)
  useEffect(() => {
    const parsed = parseValue(value, resolvedDefault);
    setCountry(parsed.country);
    setLocal(parsed.local);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const handleCountryChange = (code) => {
    const c = findByCode(code);
    setCountry(c);
    onChange(local ? `${c.dial} ${local}` : '');
  };

  const handleLocalChange = (e) => {
    // Allow only digits
    const digits = e.target.value.replace(/\D/g, '');
    setLocal(digits);
    onChange(digits ? `${country.dial} ${digits}` : '');
  };

  return (
    <div>
      <div className="flex gap-1.5">
        <Select
          value={country.code}
          onValueChange={handleCountryChange}
          disabled={disabled}
        >
          <SelectTrigger className="w-28 h-10 shrink-0 text-sm">
            <span className="flex items-center gap-1 truncate">
              {country.flag} {country.dial}
            </span>
          </SelectTrigger>
          <SelectContent className="max-h-72 overflow-y-auto">
            {COUNTRIES.map((c) => (
              <SelectItem key={c.code} value={c.code}>
                {c.flag} {c.dial} {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="tel"
          inputMode="numeric"
          value={local}
          onChange={handleLocalChange}
          placeholder={placeholder}
          disabled={disabled}
          className="h-10 flex-1 text-sm"
          maxLength={15}
        />
      </div>
      {error && (
        <p className="text-xs text-destructive mt-1">{error}</p>
      )}
    </div>
  );
}
