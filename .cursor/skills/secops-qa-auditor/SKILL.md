---
name: secops-qa-auditor
description: "Usa questa skill per eseguire audit di sicurezza, controlli QA prima di un rilascio, scansioni di errori runtime nel browser su localhost e apertura automatica di bug ticket su Linear."
---

# SecOps & Headless QA Auditor

## 1. Checklist Statica SecOps (Addy Osmani & AgentShield)
Ispeziona i file toccati nell'ultimo task o nel branch corrente (`git diff`) verificando:
- **Segreti & Env:** Nessuna chiave privata, token o credenziale hardcoded. Verifica che le variabili `NEXT_PUBLIC_*` o `VITE_*` non espongano segreti server-side.
- **Input Validation & Injection:** Tutti gli input esterni (body, query params, headers, webhook) devono essere validati tramite schema rigoroso (es. `zod`). Nessuna concatenazione raw in query SQL o comandi shell.
- **AuthZ & IDOR:** Ogni endpoint o Server Action mutativa deve verificare sia la sessione dell'utente (Autenticazione) sia i permessi sulla singola risorsa richiesta (Autorizzazione / Row-Level Security).
- **XSS & Rendering:** Vietato l'uso di `dangerouslySetInnerHTML` senza sanitizzazione esplicita (es. `DOMPurify`).

## 2. Scansione Dinamica Zero-Waste (Playwright Headless)
Avvia un'ispezione silenziosa su `localhost` che cattura **esclusivamente** `console.error`, `pageerror` (eccezioni JS non gestite) e risposte di rete fallite (`status >= 400`), ignorando i log normali per risparmiare token:

```bash
node -e '
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const anomalies = [];

  page.on("console", msg => {
    if (msg.type() === "error") anomalies.push(`[CONSOLE_ERROR] ${msg.text()}`);
  });
  page.on("pageerror", err => {
    anomalies.push(`[UNCAUGHT_EXCEPTION] ${err.message}\n${err.stack}`);
  });
  page.on("response", res => {
    if (res.status() >= 400) anomalies.push(`[HTTP_${res.status()}] ${res.url()}`);
  });

  const targetUrl = process.env.APP_URL || "http://localhost:3000";
  await page.goto(targetUrl, { waitUntil: "networkidle" });
  await browser.close();

  if (anomalies.length > 0) {
    console.error("QA_AUDIT_FAILED:\n" + anomalies.join("\n---\n"));
    process.exit(1);
  } else {
    console.log("QA_AUDIT_PASSED: Zero runtime or network errors detected.");
  }
})();
'
```

## 3. Triage & Ticketing via Linear MCP
Se l'audit statico o lo script Playwright rilevano vulnerabilità o errori runtime:
1. Non tentare fix ciechi se il bug richiede decisioni architetturali.
2. Invoca il tool MCP di **Linear** (`create_issue`) compilando il ticket con questo formato:
   - **Title:** `[SecOps/QA] <Breve dell'errore descrizione o vulnerabilità>`
   - **Priority:** `1` (Urgent) per falle di sicurezza o crash bloccanti, `2` (High) per errori HTTP/Console.
   - **Description:**
     - **Impatto:** Cosa rischia il sistema o l'utente.
     - **Evidenza / Stacktrace:** Output esatto catturato da Playwright o riga del file incriminato.
     - **File Coinvolti:** Percorso relativo dei file.
     - **Fix Suggerito:** Proposta tecnica di risoluzione.
