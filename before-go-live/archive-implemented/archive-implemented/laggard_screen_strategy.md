# Laggard Stock Screen — Research Strategy Plan (ARCHIVED)

> **STATUS (COMPLETED & WIRED IN):**
> - `engine/screens/laggard_screen.py` implements detection & scoring.
> - Wired into `engine/scheduler.py` as weekly step `step_laggard_screen()`.
> - Dashboard route `/laggards` + `templates/laggards.html` renders results with disqualifier badges & conviction ratings.

## Core Concept

When a sector or industry trends upward and lifts most of its peers, the stocks that **did not move proportionally** represent a high-probability opportunity — assuming no fundamental reason explains the underperformance. This plan formalizes that intuition into a repeatable research workflow.

---

## Mental Model: Why This Works

- Markets are inefficient in the short-to-mid term at the **individual stock level**, even when efficient at the **sector level**
- Institutional rotation often hits the largest/most liquid names first — smaller or less-covered peers lag by days, weeks, or months
- Once the sector narrative strengthens, capital eventually flows into the overlooked names
- The edge is in **identifying the lag before the catch-up**, then validating it's not a value trap

---

## Workflow Summary

```
1. Sector rising (mid-term, broad narrative) → confirmed ✓
2. Break into sub-industries → identify lagging sub-industries
3. Build peer group (similar size, same sub-industry) → rank by relative return
4. Flag bottom quartile performers → laggard candidates
5. Run disqualifier checklist → remove value traps
6. Confirm positive thesis → assign conviction tier
7. Decide position size + set catch-up target + set invalidation rule
```
