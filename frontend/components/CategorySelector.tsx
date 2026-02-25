"use client";

import type { JewelryCategory } from "../lib/types";

const CATEGORIES: { id: JewelryCategory; label: string }[] = [
  { id: "ring", label: "Ring" },
  { id: "necklace", label: "Necklace" },
  { id: "bracelet", label: "Bracelet" },
  { id: "earrings", label: "Earrings" },
];

type Props = {
  value: JewelryCategory | null;
  onChange: (cat: JewelryCategory | null) => void;
};

export default function CategorySelector({ value, onChange }: Props) {
  return (
    <div className="category-selector">
      {CATEGORIES.map((cat) => (
        <button
          key={cat.id}
          className={`category-pill${value === cat.id ? " category-pill--active" : ""}`}
          onClick={() => onChange(value === cat.id ? null : cat.id)}
          type="button"
        >
          {cat.label}
        </button>
      ))}
    </div>
  );
}
