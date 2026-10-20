# Linee guida agenti — Architettura Zero-Waste

## Principi generali

- **Codice pulito**: nomi chiari, funzioni piccole, niente duplicazione; allineati alle convenzioni del repository.
- **Zero-waste di token**: contesto mirato (grep, simboli, file necessari); evitare dump di file interi; risposte concise ma complete.
- **Modularità**: responsabilità singola per modulo; dipendenze esplicite; interfacce stabili tra layer.

## Workflow

1. Leggere il codice circostante prima di modificare.
2. Diff minimo: solo ciò che serve al task.
3. Verificare build/test rilevanti prima di considerare il lavoro finito.

## Comunicazione

- Spiegare il *perché* delle scelte non ovvie.
- Segnalare rischi, assunzioni e passi manuali (chiavi API, migrazioni, deploy).
