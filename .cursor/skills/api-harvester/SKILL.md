---
name: api-harvester
description: "Usa questa skill per fare reverse-engineering di API di siti esterni, catturare chiamate XHR/Fetch nascoste e generare client TypeScript tipizzati senza fare scraping HTML tramite LLM."
---

# API Harvester (Reverse-Engineering XHR/Fetch Zero-Token)

## Principio Operativo
Non scaricare mai il DOM HTML di una pagina per estrarre dati tramite LLM. Quasi tutte le web app moderne caricano dati strutturati tramite API JSON (`fetch` o `XHR`) o stato idratato (`__NEXT_DATA__`). Intercetta direttamente il traffico di rete e costruisci un client tipizzato.

## Step 1: Cattura Automatica degli Endpoint (Playwright Network Interceptor)
Quando l'utente fornisce un URL da cui estrarre dati o integrare servizi, esegui questo script per intercettare tutte le chiamate API JSON e salvare gli schemi in `/tmp/harvested-apis.json` (troncando gli array lunghi al primo elemento per non sprecare token):

```bash
node -e '
const { chromium } = require("playwright");
const fs = require("fs");

function pruneSample(data) {
  if (Array.isArray(data)) return data.length > 0 ? [pruneSample(data[0])] : [];
  if (data && typeof data === "object") {
    return Object.fromEntries(Object.entries(data).slice(0, 25).map(([k, v]) => [k, pruneSample(v)]));
  }
  return typeof data === "string" && data.length > 120 ? data.slice(0, 120) + "..." : data;
}

(async () => {
  const targetUrl = process.env.TARGET_URL;
  if (!targetUrl) throw new Error("Specifica TARGET_URL");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const endpoints = [];

  page.on("response", async (res) => {
    const type = res.request().resourceType();
    const contentType = res.headers()["content-type"] || "";
    if ((type === "xhr" || type === "fetch") && contentType.includes("application/json")) {
      try {
        const json = await res.json();
        endpoints.push({
          method: res.request().method(),
          url: res.url(),
          status: res.status(),
          reqHeaders: res.request().headers(),
          postData: res.request().postData(),
          responseSample: pruneSample(json)
        });
      } catch {}
    }
  });

  await page.goto(targetUrl, { waitUntil: "networkidle", timeout: 30000 });
  await browser.close();
  fs.writeFileSync("/tmp/harvested-apis.json", JSON.stringify(endpoints, null, 2));
  console.log(`Catturati ${endpoints.length} endpoint JSON in /tmp/harvested-apis.json`);
})();
'
```
*(Alternativa CLI dedicata: se installato nel sistema, puoi usare `npx github:goodnight000/api-anything <url>` per l'ispezione automatica).*

## Step 2: Analisi Selettiva
Leggi `/tmp/harvested-apis.json` usando `jq` per elencare solo i metodi e gli URL prima di leggere i dettagli:
```bash
jq '.[] | {method, url, status}' /tmp/harvested-apis.json
```
Individua l'endpoint rilevante per l'obiettivo dell'utente ed estrai solo il suo `responseSample`.

## Step 3: Generazione Client TypeScript
A partire dal campione JSON intercettato, genera un modulo autonomo (es. `src/lib/clients/<service>-client.ts`) che includa:
1. **Interfacce TypeScript / Schemi Zod:** Tipizzazione completa della request e della response basata sul payload reale.
2. **Client Fetch Nativo:** Funzioni asincrone tipizzate con gestione degli errori HTTP, timeout (`AbortSignal.timeout`) e passaggio pulito degli header necessari (escludendo header di tracking o cookie effimeri non richiesti).
