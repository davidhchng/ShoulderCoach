"use client";

import type { FieldSchema } from "@/lib/api";

interface InputFieldProps {
  field: FieldSchema;
  value: string | boolean | number;
  onChange: (value: string | boolean | number) => void;
}

export default function InputField({ field, value, onChange }: InputFieldProps) {
  if (field.type === "button_group") {
    const options = field.options ?? [];
    return (
      <div className="mb-5 last:mb-0">
        <p className="text-[10px] uppercase tracking-widest text-gray-600 mb-2">{field.label}</p>
        <div className="flex gap-1.5">
          {options.map((option) => {
            const selected = value === option;
            return (
              <button
                key={option}
                type="button"
                onClick={() => onChange(option)}
                className={`
                  flex-1 px-2 py-3 text-sm font-semibold border
                  min-h-[44px] will-change-transform
                  ${selected
                    ? "bg-orange-500 border-orange-500 text-white"
                    : "bg-transparent border-[#222] text-gray-400 hover:border-[#444] hover:text-gray-200"
                  }
                `}
              >
                {option}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  if (field.type === "toggle") {
    const checked = Boolean(value);
    return (
      <div className="mb-5 last:mb-0 flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-widest text-gray-600">{field.label}</p>
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className="flex items-center gap-2 min-h-[44px]"
        >
          <span className={`text-sm font-semibold transition-colors ${checked ? "text-orange-400" : "text-gray-600"}`}>
            {checked ? "Yes" : "No"}
          </span>
          <div className={`relative w-10 h-5 rounded-full transition-colors ${checked ? "bg-orange-500" : "bg-[#222]"}`}>
            <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
          </div>
        </button>
      </div>
    );
  }

  if (field.type === "slider") {
    const numValue = Number(value);
    return (
      <div className="mb-5 last:mb-0">
        <div className="flex justify-between mb-2">
          <p className="text-[10px] uppercase tracking-widest text-gray-600">{field.label}</p>
          <span className="text-xs font-bold text-white tabular-nums">{numValue}</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={numValue}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-1 bg-[#222] appearance-none cursor-pointer accent-orange-500"
        />
      </div>
    );
  }

  return null;
}
