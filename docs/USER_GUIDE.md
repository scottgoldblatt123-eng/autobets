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

### Recommendations are trade setups
Betfair's prices for who wins are better than any model we can build, so AutoBets does not suggest winners. It looks for games where the model and the market see the *shape* of the game differently and offers a plan to trade it, with a ready-made script:
- **Tennis, back or lay on the swing:** the model rates a player higher (or lower) than the market. The script waits for an early break in set 1 and the price reaction, backs (or lays) the player, and greens up when the set is level, on 8 ticks profit, at the end of set 1, or closes at 10 ticks against.
- **Football, back Over 2.5 after 15 minutes:** the model is more confident of goals than the market. The script waits until minute 15 with 0 or 1 goals and a price at least as good as before kick-off, and holds to the end.
- **Football, scalp Under 2.5:** the model and market both expect a low-scoring game with Under near evens. The script scalps 2 ticks at a time, up to 10 runs, closes a run that goes 6 ticks against and tries again, and stops at 2 goals.
Add to Plan saves the script (switched on) and puts the market on your Plan. Nothing is bet until it is in play and the rules are met. Use Discuss with Claude to challenge a setup or change its rules first.

### Betting grid
Every open market in Manual Trading has a Ladders / Grid switch. The grid is the standard Betfair view: a row per runner with three back and three lay prices, last traded price and your position. Click a price to bet at it with the toolbar stake (same confirm and safety rules as the ladder). Open it with the grid button beside any market in a list, or the Grid link on Home and Plan.
