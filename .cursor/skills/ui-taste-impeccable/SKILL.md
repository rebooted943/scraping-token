---
name: ui-taste-impeccable
description: "Usa questa skill quando crei, modifichi o rifinisci componenti UI, pagine front-end, layout Tailwind CSS o animazioni. Applica i parametri di design system, previene l'estetica AI-slop e verifica il rendering multi-viewport via Playwright."
---

# UI Taste & Impeccable Execution

## 1. Allineamento Preliminare
1. **Lettura Design System:** Prima di scrivere qualsiasi classe CSS/Tailwind, leggi `DESIGN.md` nella root del progetto (se presente) per estrarre palette, tipografia, raggi di curvatura e spaziature.
2. **Parametri Estetici di Default** (sovrascrivibili dal prompt utente o da `DESIGN.md`):
   - `DESIGN_VARIANCE`: **7/10** (Layout asimmetrici intenzionali, bento grid dinamiche, gerarchia tipografica netta; evita griglie 3x3 monotone).
   - `MOTION_INTENSITY`: **6/10** (Micro-interazioni fluide con curve `cubic-bezier(0.22, 1, 0.36, 1)`, transizioni di stato < 200ms, zero animazioni bloccanti).
   - `VISUAL_DENSITY`: **5/10** (Spazio negativo generoso, padding respirabile, densità dati bilanciata).

## 2. Vincoli Rigorosi Anti-AI-Slop (Regole Impeccable)
- **NO Gradienti Neon/Viola-Ciano:** Vietato usare `from-purple-500 to-indigo-600` o sfondi mesh/glow generici a meno che non siano esplicitamente richiesti.
- **NO Card Annidate Inutilmente:** Evita container dentro container con bordi multipli (`border` + `shadow-lg` + `bg-white/5`). Usa separatori sottili (`border-neutral-200 dark:border-neutral-800`) o semplice spazio bianco.
- **Tipografia & Contrasto:** Usa scale tipografiche serrate (`tracking-tight` sui titoli grandi), numeri tabulari (`tabular-nums`) per metriche/prezzi, e gerarchie cromatiche basate su opacità o toni neutri precisi (`text-neutral-900` vs `text-neutral-500`).
- **Iconografia Sobria:** Non inserire icone decorative su ogni singolo elemento di una lista o titolo di card. Usa le icone solo dove aggiungono affordance funzionale.
- **Stati Completi:** Ogni componente interattivo DEVE avere stati `:hover`, `:focus-visible` (con ring accessibile), `:active`, `disabled` e stati di *loading/empty* curati.

## 3. Verifica Visiva Multi-Viewport (Playwright CLI)
Dopo aver modificato il layout, verifica l'assenza di overflow orizzontali o collisioni eseguendo uno screenshot rapido a 3 risoluzioni (Mobile 375px, Tablet 768px, Desktop 1440px):

```bash
node -e '
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const url = process.env.APP_URL || "http://localhost:3000";
  const viewports = [
    { name: "mobile", width: 375, height: 812 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "desktop", width: 1440, height: 900 }
  ];
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(url, { waitUntil: "networkidle" });
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    console.log(`[${vp.name}] Horizontal Overflow: ${hasOverflow}`);
    await page.screenshot({ path: `/tmp/ui-check-${vp.name}.png`, fullPage: true });
  }
  await browser.close();
})();
'
```
Se `Horizontal Overflow` restituisce `true`, ispeziona e correggi immediatamente gli elementi che sforano il viewport prima di concludere il task.
