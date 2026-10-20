---
name: grill-and-refactor
description: "Usa questa skill quando l'utente chiede di progettare una nuova feature complessa, fare un refactoring architetturale, lavorare in TDD o chiede esplicitamente di essere interrogato ('grill me') sul proprio piano."
---

# Grill Me, Refactor Plan & Strict TDD

## Regola d'Oro: STOP ALLA SCRITTURA CODICE
Quando questa skill è attiva, **è severamente vietato modificare file di implementazione** finché la Fase 1 e la Fase 2 non sono state completate e approvate esplicitamente dall'utente.

## Fase 1: Modalità "Grill Me" (Interrogatorio Architetturale)
Analizza il codice esistente rilevante e sottoponi l'utente a un interrogatorio tecnico spietato ma costruttivo. Fai **massimo 3-4 domande mirate alla volta** concentrandoti su:
1. **Casi Limite (Edge Cases):** Cosa succede in caso di race condition, payload malformati, disconnessione di rete, stati nulli o concorrenza?
2. **Impatto sul Dominio:** Quali contratti API, schemi database o componenti consumatori rischiano di rompersi (breaking changes)?
3. **Semplificazione (YAGNI):** Quale parte della richiesta può essere eliminata o risolta con un pattern più semplice già presente nella codebase?

*Attendi le risposte dell'utente. Se emergono ambiguità, incalza con ulteriori domande finché il design non è cristallino.*

## Fase 2: Piano di Refactoring Atomico (`request-refactor-plan`)
Una volta chiariti i dubbi, produci un piano di esecuzione strutturato:
- **Elenco File Impattati:** Specifica esattamente quali file verranno creati, modificati o eliminati.
- **Step Atomici:** Dividi il lavoro in step piccoli e verificabili (ogni step deve lasciare l'applicazione in uno stato compilabile).
- **Richiesta di Conferma:** Termina con: *"Approvi questo piano? Rispondi 'Procedi' per passare al ciclo TDD."*

## Fase 3: Ciclo TDD Rigoroso (Red -> Green -> Refactor)
Solo dopo il via libera dell'utente:
1. **RED:** Scrivi/aggiorna prima il test automatico che verifica il requisito o riproduce il bug. Esegui il test runner e mostra che fallisce per il motivo corretto.
2. **GREEN:** Scrivi la quantità *minima* di codice di produzione necessaria per far passare il test.
3. **REFACTOR:** Pulisci duplicazioni, migliora i tipi TypeScript e l'astrazione mantenendo i test verdi.
