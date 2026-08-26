# LLM Tax-Loss Harvesting (TLH) Advisor

## Objective
The ML engine already has tax-aware selling logic (J2) built into `optimizer.py`, but this logic is quantitative and silent. 
We want to expose a **Tax-Loss Harvesting (TLH) Copilot** using the local LLM to proactively advise the user on how to minimize their tax burden (especially under the German Abgeltungsteuer rules).

## Placement: Briefing Tab vs. Dashboard
**Recommendation:** The **Briefing Tab** is the absolute best place for this. 
- *Why not the Dashboard?* The Dashboard is for static portfolio viewing. A tax-loss harvesting suggestion is only highly relevant when you are actively preparing to sell a profitable stock (an imminent tax event).
- *Why the Briefing Tab?* The Briefing is your daily "Morning Action Plan." If the ML engine decides to sell a huge winner today, the LLM can instantly step in and say: *"Warning: Selling SAP today will trigger ~€500 in capital gains taxes. Consider pairing this sale with your deeply underwater TL0.DE position to harvest a €450 loss and neutralize the tax bill."*

## Architecture / How It Will Work

1. **Data Gathering (`narrator.py`):**
   - Query the `trades` / `orders` table to see if any highly profitable positions are queued to be sold today.
   - Query the `positions_history` table to find all current holdings with a negative unrealized PnL (the "harvestable losses").
   - Read the active tax rate from the `tax_settings` table (e.g., 26.375% for Germany).

2. **The LLM Prompt:**
   - Feed the LLM the pending gains and available losses.
   - Instruct the LLM to find the optimal pairings. (e.g. "Find unrealized losses that perfectly offset the pending realized gains, minimizing the net tax paid without needlessly liquidating the entire portfolio.")

3. **UI Integration (`briefing.html`):**
   - Add a new "🛡️ TAX ADVISOR" card inside the Briefing tab that only appears when a capital gains event is imminent.
   - It will display the LLM's plain-English explanation of exactly which ticker to sell to offset the tax hit.

## Next Steps
- [ ] Update `engine/briefing/data.py` to calculate *Unrealized Losers* and *Pending Realized Gains*.
- [ ] Create a new prompt `tax_advisor_prompt.md`.
- [ ] Wire it into `narrator.py` as an optional LLM sub-agent.
- [ ] Build the UI panel in `briefing.html`.
