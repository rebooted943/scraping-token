# Design System: Linear Style (High-Density & Speed)
- **Theme & Surfaces**: Dark-first nativo (`#08090A` canvas bg, `#121316` elevated surface, `#1A1B1E` hover state).
- **Borders & Dividers**: Bordi strutturali hair-line `1px solid #222326` (o `rgba(255,255,255,0.08)`). Mai usare ombre pesanti per separare i blocchi.
- **Typography**: `Inter` o `Geist Sans`. Titoli con `letter-spacing: -0.015em`, `font-weight: 500`. Testo secondario `#8A8F98`. Numeri sempre con `font-variant-numeric: tabular-nums`.
- **Components**: Alta densità informativa. Bottoni compatti (`h-8`, `px-3`, `text-xs`, `rounded-md`). Badge di stato minimali con dot colorato. Mostrare sempre gli shortcut da tastiera (`<kbd>`).
- **Motion & Interaction**: Transizioni ultra-rapide `120ms cubic-bezier(0.16, 1, 0.3, 1)`. Zero animazioni superflue o bounce. Focus ring nitido `1px solid #5E6AD2`.
