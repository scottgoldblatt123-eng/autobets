# AutoBets: user guide

AutoBets runs in **Practice mode**: real (delayed) Betfair prices, simulated money. Nothing is ever sent to Betfair.

## Screens
- **Home**: today, week and month profit, automation state, open positions, pending recommendations, recent alerts.
- **Recommendations**: ideas where the model and the market disagree. Apply or Dismiss. They are guidance, not tips; confidence is never High.
- **Plan**: which scripts are armed on which markets, with status and bets taken.
- **Scripts**: your trading rules. Create from a template, paste JSON, or describe it to Claude (the Copilot panel beside Scripts, Plan and Home, in Build a script mode). Enable, clone, view history, Add to Plan.
- **Manual Trading**: the ladders, Bet Angel style. Open a market from the left list (tennis, football). Click blue to back, pink to lay. Stops, auto-greens, Dutching and Green up are on each market.
- **Analyse**: Performance, Strategies (script vs manual), Models, Backtesting, AI learning.
- **Alerts**: what the system flagged. **Settings**: all configuration.

## Staying safe
- **Stop all automation** (top strip) halts scripts and AI immediately. Your manual trading and existing stops keep working. Resume from the same button.
- **Loss limits** (daily, weekly): 0 means not set. Once set, manual losses count toward them but manual bets are never blocked; scripts stop entering. Exits still run.
- **Open liability limit** caps what automation can have at risk.
- Lay stakes default to the amount you type being the stake (changeable).

## Scripts in short
A script has entry rules, exit rules and safety rules. Example: back the favourite at 1.6-2.0 pre-match, exit with a green-up when the price drops 8 ticks, or close if the position loses £5. Add it to the Plan on a market and runner to arm it.

## Backtesting
Replays your recorded Betfair prices for markets whose winner is known. Needs data to build up; the more days the app runs, the more it can test. Results show a held-out final 30%, after 5% commission.

## Settings
Safety and limits; Connections and feeds (health and data counts); Credentials (set / not set only; keys live on the server); Trading defaults; AI and costs; Alerts (browser only for now); Versions and models; Appearance (light/dark).

## Phone and tablet
The same app works on smaller screens. Use landscape for ladders.

## Not yet
Real money orders, email/push alerts, auto-apply for recommendations, Full AI mode, horse racing.

### Picking markets on a future day
Every market list (Home, Plan, Manual Trading and the Add to Plan picker) has a day strip: Next up, Today, Tomorrow, the following days, and a calendar box for any later date. Pick a day to list all match-odds markets scheduled on that UK calendar day, then tick and add them to the Plan as usual.
