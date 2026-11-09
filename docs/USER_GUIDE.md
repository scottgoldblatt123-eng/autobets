# AutoBets: user guide

AutoBets runs in **Practice mode**: real (delayed) Betfair prices, simulated money. Nothing is ever sent to Betfair.

## Screens
- **Home**: today, week and month profit, automation state, open positions, pending recommendations, recent alerts.
- **Recommendations**: ideas where the model and the market disagree. Apply or Dismiss. They are guidance, not tips; confidence is never High.
- **Plan**: which scripts are armed on which markets, with status and bets taken.
- **Scripts**: your trading rules. Create from a template, paste JSON, or describe it to Claude (the Copilot panel beside Scripts, Plan and Home, in Build a script mode). Enable, clone, view history, Add to Plan.
- **Manual**: the ladders, Bet Angel style. Open a market from the left list (tennis, football). Click blue to back, pink to lay. Stops, auto-greens, Dutching and Green up are on each market.
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
Every market list (Home, Plan, Manual and the Add to Plan picker) has a day strip: Next up, Today, Tomorrow, the following days, and a calendar box for any later date. Pick a day to list all match-odds markets scheduled on that UK calendar day, then tick and add them to the Plan as usual.

### Recommendations are trade setups
Betfair's prices for who wins are better than any model we can build, so AutoBets does not suggest winners. It looks for games where the model and the market see the *shape* of the game differently and offers a plan to trade it, with a ready-made script:
- **Tennis, back or lay on the swing:** the model rates a player higher (or lower) than the market. The script waits for an early break in set 1 and the price reaction, backs (or lays) the player, and greens up when the set is level, on 8 ticks profit, at the end of set 1, or closes at 10 ticks against.
- **Football, back Over 2.5 after 15 minutes:** the model is more confident of goals than the market. The script waits until minute 15 with 0 or 1 goals and a price at least as good as before kick-off, and holds to the end.
- **Football, scalp Under 2.5:** the model and market both expect a low-scoring game with Under near evens. The script scalps 2 ticks at a time, up to 10 runs, closes a run that goes 6 ticks against and tries again, and stops at 2 goals.
Add to Plan saves the script (switched on) and puts the market on your Plan. Nothing is bet until it is in play and the rules are met. Use Discuss with Claude to challenge a setup or change its rules first.

### Betting grid
Every open market in Manual has a Ladders / Grid switch. The grid is the standard Betfair view: a row per runner with three back and three lay prices, last traded price and your position. Click a price to bet at it with the toolbar stake (same confirm and safety rules as the ladder). Open it with the grid button beside any market in a list, or the Grid link on Home and Plan.

### Bet slip (your own price)
One click on a grid price bets at that price with the toolbar stake. To choose the price yourself, right-click a price (or press Bet... on the runner). The bet slip lets you pick Back or Lay, a price (typed or by tick), the stake (a lay can be sized by stake or liability) and what happens to any unmatched part: cancel when the market turns in play, keep in play, or take the Starting Price at the off. "Cancel after (s)" is fill-or-kill: whatever is unmatched after that many seconds is cancelled. A price better than the market waits in the queue until the market comes to it; a price already on offer matches immediately at the best price available.

### New script proposals and the sport filter
Recommendations has Football / Tennis / All sports chips. **Propose new scripts** asks Claude for up to three scripts that differ from your library, each with a hypothesis about how the market over- or under-reacts, the risk, and the rules. The server also asks about once a day. Proposals appear on Recommendations (New scripts) and in a Recommended scripts strip at the top of Scripts. Discuss opens the idea in the Copilot panel; Save to Scripts / Approve adds it to your library switched off. Proposals are not backtested; test them in practice mode.

### Editing a script
Edit on the Scripts screen opens three tabs. **Settings** is a form: name, sport, description and each rule's conditions and actions (stake, price, persistence, repeat) as fields. **Ask Claude to change it** takes a plain-English change, shows you the revised script, and loads it into Settings only if you press Use this version. **Advanced** is the raw data for experts. Save as new version keeps the old version in History; Save as a copy leaves the original untouched.

### Starter library
Scripts has a **Starter library** button. It holds ready-made tennis and football scripts based on well-known community automation ideas (such as laying a player who breaks early, backing the server each game, laying the draw at half time), rebuilt in our own wording. Each shows what it does, which runner to attach it to, its caveats and its rules. **Add to my library** puts a switched-off copy in Scripts; **Add all** adds the ones you have not got yet. They are starting points, not proven: read them, change the numbers, test in practice mode. A "Not available yet" list explains which popular bots cannot be built here (for example correct-score dutching, and anything that needs the history of earlier points).

### Recommended trades reuse scripts
Accepting a trade setup does not create a script per match. There is one reusable script for each kind of setup (for example "Setup: Back the player on the swing"). The first time you accept that kind it is added to your library; after that, accepting adds only a Plan row for the new market using the same script. Match-specific numbers (the stake, and the price the market had when you accepted) live on the Plan row, not in the script. AI script proposals are different: those are genuinely new ideas, so approving one adds it to the library once.

### Quick apply on Home
In AI recommended trades on Home, **Apply** on a row accepts that idea straight away (a setup is added to the Plan with its reusable script switched on; a script proposal is added to the library switched off). **Apply all** at the top accepts every idea shown, after one Yes/No check. Review still opens the Recommendations screen. Ideas that fail (for example the market has gone) are skipped and reported.

### Analyse date range and comparison
The Date range control on Analyse has presets (Today, Yesterday, Last 7/30/90 days, This week, Last week, This month, Last month, This year) and two calendar boxes for any dates you like. Tick **Compare** to set a second period: Previous period (the same length straight before, or the previous calendar month if you picked a whole month), Same period last year, or your own dates. With Compare on, the tiles show both periods, the Cumulative P&L chart overlays the comparison as a dashed line, and By strategy adds Compare markets, Compare P&L and Change columns. Your choice is remembered in this browser.

### Why hasn't it fired?
On the Plan, open a row's rules (Show rules) and press **Why hasn't it fired?**. It lists every rule's conditions with a tick or cross for how they stand right now, and the readings they look at (market status, in-play, minute, goals, spread, whether the live score feed is connected). A rule with every condition ticked should act on the next pass. It also says if automation or the script itself is switched off.

If a script's entry bet is not matched within 45 seconds it is now cancelled and the same run tries again, so a scalp cannot get stuck waiting on a bet the price has left behind. An alert says when this happens.

### Why so few trade setups?
Recommendations shows a line under the tiles: "Last scan 14:32: N setups found". **Why so few?** breaks the last scan down per sport: matches listed, starting within 8 hours, priced, with live data, with a model view, and setups found, with a plain reason when it is zero. **Scan now** runs it immediately. Setups no longer need a rating or goals model: with no model the tennis swing trade (lay the outsider who breaks early) and the Under 2.5 scalp are still offered from the market's own prices, and their reason says so. Over 2.5 setups still need the goals model, because they depend on a view that differs from the market.

### Select and apply several recommendations
Each trade setup and script proposal on Recommendations has a tick box. A bar above the list has **Select all**, **Apply selected (N)**, **Dismiss selected** and **Apply all (N)**; "all" means everything in the current sport and kind filter. Applying asks Yes/No first. Setups go on the Plan with their reusable script switched on; script proposals go to Scripts switched off. Ideas that fail are skipped and reported. Older single-bet ideas (which would place a bet immediately) are not included and are still applied one at a time.
