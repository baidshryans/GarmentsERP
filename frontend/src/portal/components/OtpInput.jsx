import { useRef } from "react";
import { Input } from "@/components/ui/input";

export default function OtpInput({ length = 6, value = "", onChange }) {
  const refs = useRef([]);
  const digits = value.padEnd(length, "").split("").slice(0, length);

  const handleChange = (idx, e) => {
    const val = e.target.value.replace(/\D/g, "");
    if (!val) return;
    const newDigits = [...digits];
    newDigits[idx] = val[val.length - 1];
    const newValue = newDigits.join("");
    onChange(newValue);
    // Auto-focus next
    if (idx < length - 1) refs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx, e) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      const newDigits = [...digits];
      if (digits[idx]) {
        newDigits[idx] = "";
        onChange(newDigits.join(""));
      } else if (idx > 0) {
        newDigits[idx - 1] = "";
        onChange(newDigits.join(""));
        refs.current[idx - 1]?.focus();
      }
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    onChange(pasted);
    const focusIdx = Math.min(pasted.length, length - 1);
    refs.current[focusIdx]?.focus();
  };

  return (
    <div className="flex gap-2 justify-center">
      {digits.map((d, i) => (
        <Input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d === " " ? "" : d}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={i === 0 ? handlePaste : undefined}
          className="w-10 h-12 text-center text-lg font-mono"
        />
      ))}
    </div>
  );
}
