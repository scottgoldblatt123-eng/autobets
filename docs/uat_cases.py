"""UAT cases for AutoBets, feature by feature. Run `python3 docs/uat_cases.py` to regenerate docs/uat_cases.json and docs/UAT.md.
Mode: Demo = fake prices with the demo controls strip (safe, repeatable); Practice = real delayed Betfair prices, simulated orders; Either = same in both."""
import json, os

S = []  # (section, intro, [cases])


def sec(name, intro, cases):
    S.append((name, intro, cases))


def c(title, mode, steps, expected):
    return {"title": title, "mode": mode, "steps": steps, "expected": expected}


sec("Setup and access", "Before anything else. Demo mode is the safe place to run most of this script.", [
    c("Open the app and see the mode badge", "Either", ["Open the AutoBets address in a browser."], "The header badge reads DEMO — FAKE PRICES or PRACTICE MODE. It never reads LIVE."),
    c("Token prompt appears when no token is stored", "Either", ["Open the app in a private window.", "Do not enter a token."], "A token prompt is shown. Nothing else is usable."),
    c("Wrong token is refused", "Practice", ["Enter a wrong token and submit."], "A clear 'try again' message. No market list loads."),
    c("Right token is accepted and remembered", "Practice", ["Enter the right token.", "Reload the page."], "Markets load. The token is not asked for again on reload."),
    c("Backend unreachable shows a message, not a blank page", "Either", ["Stop the service (or disconnect the network) and reload."], "A readable error with a Try again button."),
])

sec("Markets list and opening ladders", "The left-hand market list and what opening a market does.", [
    c("Tennis and Football tabs list markets", "Either", ["Click Tennis, then Football."], "Each tab lists its own matches with competition and start time."),
    c("Opening a market opens ALL its runners together", "Either", ["Click a tennis match."], "Two ladders (A and B) appear in one market block, side by side."),
    c("Football match odds opens three ladders", "Demo", ["Click the football match with a draw."], "Three ladders open: home, away and the draw, in one block."),
    c("Four-ladder cap with a clear message", "Demo", ["Open the football match (3 ladders).", "Open a tennis match (needs 2)."], "A message says it needs 2 ladders but only 1 slot is free. Nothing half-opens."),
    c("Opening the same market twice is refused", "Either", ["Open a market.", "Click the same market again."], "A message says it is already open. No duplicate ladders."),
    c("Closing one market with the X closes all its ladders", "Either", ["Click the X at the top right of a market block."], "All ladders of that market close together. You cannot close just one runner's ladder."),
    c("Closing a market with a position or open orders asks first", "Demo", ["Place a bet and leave an unmatched bet.", "Click the market's X."], "A confirm dialog warns about the position and the unmatched orders. Cancel keeps the market open."),
])

sec("Ladder display", "How a ladder looks and what each column means (Bet Angel is the reference).", [
    c("Column order and colours", "Either", ["Look at any ladder."], "Left to right: P&L column, my back bets, back (blue), price (dark blue), lay (pink), my lay bets, recent volume."),
    c("Back is blue and on the left, lay is pink and on the right", "Either", ["Hover each side and read the tooltips."], "Left cells say 'Back at x', right cells say 'Lay at x'."),
    c("Back prices sit at or below the best back; lay prices at or above the best lay", "Either", ["Compare the blue and pink cells with the price column."], "Blue numbers appear on prices up to the best back price; pink numbers from the best lay price upwards; one tick between them when the spread is a tick."),
    c("Tinted empty zones", "Either", ["Look at the empty cells beyond the best prices."], "Empty cells in the back zone and the lay zone are tinted; cells in between are plain."),
    c("Last traded price is highlighted", "Either", ["Find the orange outlined price."], "The last traded price row is outlined in orange and updates as the market moves."),
    c("Recent volume column", "Either", ["Watch the right-hand bars for a minute."], "Bars show volume matched at each price in the short window (solid) and long window (lighter). Numbers appear for the short window."),
    c("Total matched column (optional)", "Either", ["Ladder settings → show the total matched column."], "An extra column appears with the total matched at each price. Switching it off removes it."),
    c("Weight of money bar", "Either", ["Look at the bar above the ladder."], "Blue and pink shares add to 100%, with an arrow showing which side is heavier, and the number of bets each side."),
    c("Footer shows matched volume and market share", "Practice", ["Look at the line under the price rows."], "It shows £ matched on that runner and its % of the market. If Betfair sends none it says 'volume not available' (expected on a delayed key)."),
    c("Light and dark themes", "Either", ["Click Dark / Light in the header."], "Both themes are readable: colours, price column, chips and panels."),
])

sec("Ladder movement", "Scrolling, recentring and reversing the ladder.", [
    c("Mouse wheel moves the prices", "Either", ["Hover the price rows and use the wheel."], "The ladder moves up and down the price ladder one tick per notch."),
    c("Wheel outside the price rows does not move prices", "Either", ["Hover the chart or the header and use the wheel."], "The prices do not move."),
    c("Ladder stays put when the price moves (auto-centre off)", "Demo", ["Leave auto-centre off.", "Wait for the price to drift."], "The ladder holds its position and shows ▲ or ▼ with the price when the market has moved out of view."),
    c("Recentre with Enter and the ⌖ button", "Either", ["Scroll away, then press Enter.", "Scroll away, then click ⌖ on one ladder."], "Enter recentres every ladder; ⌖ recentres just that one."),
    c("Auto-centre setting", "Either", ["Ladder settings → auto-recentre on.", "Let the price drift."], "The ladder follows the price by itself."),
    c("Reverse ladders (R key and button)", "Either", ["Press R, then press it again."], "Lowest price moves to the top, then back. Back stays on the left and lay on the right; clicking still places the side of the column you clicked."),
])

sec("Stakes", "Every way of choosing how much to bet.", [
    c("Preset stake buttons", "Either", ["Click 2, 5, 10, 20 in the toolbar."], "The chosen preset is highlighted and used for the next bet."),
    c("Free-form stake box", "Either", ["Press S, type 65, press Enter."], "The stake box shows 65 and the next bet is £65. Clearing the box goes back to the preset."),
    c("Pound sign and commas accepted", "Either", ["Type £1,250 in the stake box."], "It is read as £1,250."),
    c("Stakes under £1 are refused", "Either", ["Type 0.50 in the stake box and click a price."], "A message says the minimum is £1. No bet is placed."),
    c("Invalid text is flagged", "Either", ["Type abc in the stake box."], "The box turns red with 'min £1'. Clicking a price places nothing."),
    c("Per-ladder stake", "Either", ["On one ladder click a stake chip or type in its own stake box.", "Place a bet on each ladder."], "Each ladder uses its own stake. A ladder with an empty box uses the toolbar stake."),
    c("Number keys 1–8 act on the hovered ladder", "Either", ["Hover one ladder and press 3."], "That ladder's stake becomes the 3rd preset. The other ladder is unchanged. With no ladder hovered it changes the toolbar stake."),
    c("Lay stake or liability", "Either", ["Ladder settings → lay stakes entered as liability.", "Stake 10, lay at 3.0."], "The bet placed is a lay of £5 (liability £10). Switching back to 'a stake' lays £10."),
    c("Confirm large orders", "Either", ["Set 'confirm orders of £50 or more'.", "Bet £60."], "A confirm card shows side, runner, price and size. Place sends it; Cancel (or Esc) does not."),
    c("Percentage-of-bank stakes", "Either", ["Settings → stakes as % of bank; bank £500.", "Look at the preset chips; click a 4% chip and place a bet."], "Chips show %; a 4% bet is £20."),
    c("Type 2% in a stake box", "Either", ["With bank £500 type 2% in the stake box."], "The next bet is £10, whatever the stake mode."),
    c("Separate lay stake", "Either", ["Settings → separate stake for lay bets.", "Enter a lay stake of 20, back stake 10."], "A Lay £ box appears. Back bets use £10, lay bets use £20. Blank lay box uses the back stake."),
])

sec("Placing and matching bets", "Clicks, sides, prices and what 'matched' means.", [
    c("Click blue = BACK, click pink = LAY", "Either", ["Click a blue cell, then a pink cell, both with stake £2."], "Confirmation says BACK (blue tag) then LAY (pink tag) at the prices you clicked. The Matched bets panel lists them with the same sides."),
    c("A bet at the best price matches immediately", "Either", ["Click the best back price (the highest blue number)."], "Status 'matched'. Your position line appears."),
    c("A bet at a worse price takes the better price", "Demo", ["Click a lay cell above the best lay price."], "The bet matches at the best lay price, not the price you clicked. The Matched bets panel shows both 'Asked' and 'Matched at'."),
    c("A bet at a better price waits (unmatched)", "Demo", ["Lay at a price well below the best back, or back at a price well above the best lay."], "Status 'waiting (unmatched)'. It appears in Unmatched bets and on the ladder."),
    c("Waiting bets are summed at their price", "Demo", ["Place three £10 lays at the same low price."], "That row shows '£30 ×3' in your own-bets column and 'LAY £30 waiting' over the volume bar; BACK shows blue. Hover shows the count and total."),
    c("A waiting bet matches when the price reaches it", "Demo", ["Wait with a lay waiting just below the market until the price drops to it (or place it one tick away)."], "The bet moves from Unmatched bets to Matched bets and your position updates."),
    c("Price steps follow Betfair's tick sizes", "Demo", ["Place a waiting bet near 2.00 and press + or − repeatedly across 2.00 and across 3.00."], "Steps are 0.01 below 2.00, 0.02 from 2.00 to 3.00 and 0.05 from 3.00 to 4.00. Only valid Betfair prices ever appear."),
    c("Double-click mode", "Either", ["Settings → clicking → double click.", "Single-click a price, then double-click one."], "A single click places nothing; a double click places one bet."),
    c("Toast tags make the side obvious", "Either", ["Place a back and a lay."], "Each confirmation shows BACK in blue or LAY in pink."),
])

sec("Waiting bets: cancel, move, edit, persistence", "Managing unmatched bets (the 'Unmatched bets' panel and the ladder).", [
    c("Cancel a waiting bet by clicking it on the ladder", "Demo", ["Click your own-bet chip."], "The bet disappears from the ladder and from Unmatched bets."),
    c("Drag a waiting bet to a new price", "Demo", ["Drag the chip to another price row."], "The bet moves to the new price; with several bets at one price they all move."),
    c("Unmatched panel lists every waiting bet", "Demo", ["Place two waiting bets on different runners."], "Both appear with side, runner, placed time, price, stake, matched and at-the-off setting."),
    c("± tick buttons change the price", "Demo", ["Click + then − on a waiting bet."], "The price moves one valid tick each time; the bet stays waiting."),
    c("Edit the stake in place", "Demo", ["Change the stake in the panel and press Enter."], "The waiting amount changes. Anything already matched is untouched."),
    c("Cancel and Cancel all", "Demo", ["Cancel one bet, then press Cancel all."], "One bet cancels; then all remaining waiting bets cancel."),
    c("Cancel back / cancel lay hotkeys", "Demo", ["Hover a ladder with a waiting back and lay; press Z, then X."], "Z cancels that runner's waiting backs; X cancels its waiting lays."),
    c("At-the-off setting per bet and for all", "Demo", ["Choose Keep / Cancel / Take SP on a bet.", "Use the 'At the off, all' buttons."], "The selection changes immediately and is shown in the table."),
    c("At the off: Cancel lapses the bet", "Demo", ["Set a waiting bet to Cancel.", "Use Demo controls → Go in play."], "The waiting bet is cancelled when the market goes in play."),
    c("At the off: Keep leaves the bet on", "Demo", ["Set a waiting bet to Keep.", "Go in play."], "The bet stays waiting in play."),
    c("At the off: Take SP removes the bet (practice does not simulate SP)", "Demo", ["Set Take SP and go in play."], "The bet leaves the list. (Starting Price is not simulated in practice.)"),
    c("Default 'at the off' setting", "Either", ["Settings → unmatched bets when the match starts: choose Cancel / Keep / Take SP; place a waiting bet."], "The new bet starts with the chosen setting."),
    c("Fill or kill", "Demo", ["Settings → fill or kill 10 seconds.", "Place a waiting bet and wait."], "After about 10 seconds the unmatched part is cancelled and the log says so."),
])

sec("Positions and P&L", "What the screen says you have and what it is worth.", [
    c("Position in words", "Either", ["Lay £10 on a runner."], "The ladder shows a pink 'LAY £10.00 @ price' tag, then 'if <runner> wins -£x · if <runner> loses +£10.00'."),
    c("Back position wording", "Either", ["Back £10 on a runner."], "A blue 'BACK £10.00 @ price' tag; profit if it wins, -£10 if it loses."),
    c("The numbers are right for a lay", "Either", ["Lay £10 at 1.50."], "If the runner wins you lose £5.00; if it loses you win £10.00."),
    c("P&L column shows what hedging at each price would lock", "Either", ["With a position, read the left column."], "For a lay it rises as the price rises; for a back it falls. Green is profit, red is loss."),
    c("Clicking a P&L figure places the hedge", "Either", ["Click a figure in the P&L column."], "The hedging bet is placed (side and stake shown in the tooltip), locking that figure."),
    c("P&L basis: runner or market", "Demo", ["Toolbar chip 'P&L: runner' → market. Compare the column on a 3-runner market."], "Runner mode shows this runner's lock; market mode shows the worst case across all runners after that hedge. On a 2-runner market they match."),
    c("P&L column on the left or right", "Either", ["Settings → P&L column on the right."], "The column moves to the right edge. Clicking behaves the same."),
    c("Close a runner", "Either", ["Press Close on a ladder (or C)."], "The runner's position is closed with a hedging bet. The Close button is disabled with no position."),
    c("Cancel a runner's orders from the ladder", "Demo", ["Press Cancel on a ladder with waiting bets."], "All that runner's waiting bets cancel."),
    c("Matched bets panel", "Either", ["Place several bets, back and lay."], "Each appears newest first with time, side, runner, asked price, matched price, stake, 'Runner wins', 'Runner loses' and who placed it."),
    c("Header total P&L and exposure", "Either", ["Look at the top right with a position."], "A P&L chip and the exposure update as positions change."),
])

sec("Market block header and the big button", "The Geeks Toy-style market panel above the ladders.", [
    c("Clock, status and book percentages", "Either", ["Look at a market block header."], "Pre-match shows a countdown; in play shows 'In play'. Back and lay book percentages are shown either side of the button."),
    c("Outcome boxes", "Either", ["With a position look at the two (or three) boxes."], "One box per runner shows your profit or loss if that runner wins."),
    c("The big button shows the market P&L", "Either", ["Hold a position and watch the button."], "Green when the market is at or above £0.00, red below. It always shows the figure, including after it is pressed."),
    c("Hard close", "Either", ["Click the big button (or press G)."], "Waiting bets cancel, then the bets that level every outcome are placed. The button then shows the locked figure."),
    c("Soft green keeping waiting bets", "Demo", ["Open the ▾ menu → green up, keep my unmatched bets."], "The market is levelled but waiting bets stay."),
    c("Partial hedge", "Demo", ["Menu → 50%."], "About half of the hedge is placed; outcomes are closer but not level; waiting bets stay."),
    c("Auto-green at a profit level", "Demo", ["Menu → enter a level above the current figure → Set.", "Wait for the market to reach it."], "A chip 'Auto-green at £x' shows. When the level is reached the market hard-closes. Click the chip to remove it."),
    c("Right-click the big button", "Either", ["Right-click it."], "The same menu opens."),
    c("Big button with no position", "Either", ["Look at the button with nothing matched."], "It is greyed out; nothing happens when clicked."),
])

sec("Stops and take-profit", "Triggers set from the ladder.", [
    c("Right-click a price on a ladder with a position", "Either", ["Right-click a price below (or above) the market."], "A menu offers 'Stop loss' or 'Take profit' at that price, showing what it would lock."),
    c("A stop shows on the ladder", "Either", ["Set one."], "An 'SL' or 'TP' marker appears at that price in your own-bets column."),
    c("A trigger fires and greens up", "Demo", ["Set a take profit one or two ticks away and wait."], "When the last price reaches it, the runner is greened up and the log says so."),
    c("Remove a stop", "Either", ["Click its marker, or use the right-click menu 'Remove'."], "The marker disappears and it never fires."),
    c("A stop waits while the market is suspended", "Demo", ["Set a stop.", "Suspend the market via Demo controls."], "It does not fire while suspended; it resumes when the market reopens."),
])

sec("Offset and stop on entry", "Bets that place their own closing bet and stop.", [
    c("Offset places the closing bet", "Demo", ["Toolbar Offset 3.", "Back £10 at the best back."], "When it matches, a LAY for the equalising stake is placed 3 ticks away (shown waiting). The log says 'Offset: …'."),
    c("Stop is armed on entry", "Demo", ["Offset 3 and Stop 4.", "Place a back."], "A stop is armed 4 ticks against the entry price (an 'SL' marker). The log says 'Stop armed'."),
    c("Stop fires and cancels the offset bet", "Demo", ["Let the price move 4 ticks against you."], "The position is closed and the waiting offset bet is cancelled."),
    c("Offset matching removes the stop", "Demo", ["Let the price move 3 ticks in your favour."], "The offset bet matches, the position is closed and the stop disappears."),
    c("Offset applies to lays as well", "Demo", ["Offset 3; lay £10."], "A BACK is placed 3 ticks above the lay price."),
    c("Offset and stop from settings", "Either", ["Set the same values in Ladder settings."], "The toolbar boxes show the same numbers (they are one setting)."),
    c("Zero means off", "Either", ["Set both to 0 and bet."], "No extra orders are placed."),
])

sec("Market states", "Suspended, closed, removed runners and the start of play.", [
    c("Suspended market blocks betting", "Demo", ["Demo controls → Suspend."], "A banner says SUSPENDED; ladders dim; clicking places nothing; the status tag shows."),
    c("Reopen resumes trading", "Demo", ["Demo controls → Reopen."], "The banner clears and bets work again."),
    c("Closed market", "Demo", ["Demo controls → Close."], "MARKET CLOSED banner; no bets, no green-up."),
    c("Hard close refuses on a suspended market", "Demo", ["Suspend, then press the big button."], "A message explains the market is suspended; nothing is placed."),
    c("Going in play", "Demo", ["Pre-match → Go in play."], "The header changes to 'In play'; waiting bets follow their at-the-off setting."),
    c("Waiting bets do not match while suspended", "Demo", ["Place a waiting bet near the market, suspend, wait, reopen."], "It does not fill during the suspension."),
])

sec("Price chart", "The chart under each ladder.", [
    c("Chart shows price and volume", "Either", ["Look under a ladder."], "A line for the last price, a band between best back and lay, volume bars, and the last price tag."),
    c("Time ranges", "Either", ["Click 5m, 15m, 1h, 3h."], "The window changes; the 'shown' label updates."),
    c("History backfills for markets the price logger has seen", "Practice", ["Open a market the logger already tracks."], "The chart opens with earlier history (one point a minute), not empty."),
    c("Drag the bar to resize", "Either", ["Drag the grip under the price rows down, then up."], "Down adds price rows and shrinks the chart; up does the reverse."),
    c("Each ladder resizes on its own", "Either", ["Drag the right-hand ladder's bar."], "Only that ladder changes."),
    c("The chart can be shrunk away completely", "Either", ["Drag the bar all the way down."], "The chart disappears; only the grip remains. Drag back up to restore it."),
    c("No scrollbar inside a ladder", "Either", ["Resize the browser window taller and shorter."], "The ladder always fits; it never shows its own scrollbar; chart and rows share the space."),
    c("Rows setting", "Either", ["Settings → price rows 0 (auto), then 15."], "0 fits the window and leaves room for a chart; 15 fixes the count (capped to what fits)."),
    c("Chart on/off", "Either", ["Settings → show chart off."], "The chart and its drag bar disappear from every ladder."),
])

sec("Hotkeys", "Keyboard control.", [
    c("Default keys", "Either", ["Hover a ladder and try S, Z, X, C, G, R, Enter, 1–8."], "S stake box; Z cancel backs; X cancel lays; C close runner; G hard close market; R reverse; Enter recentre; 1–8 stake presets."),
    c("Keys are ignored while typing in a box", "Either", ["Click a text box and type z, x, c."], "No bets or cancels happen."),
    c("Rebind a key", "Either", ["Settings → hotkeys → click 'Hard close' → press H."], "The box shows H; pressing H now hard-closes; the help line under the toolbar shows H."),
    c("Conflicting keys are refused", "Either", ["Try to give two actions the same key."], "A message names the action already using that key; nothing changes."),
    c("Reset to defaults restores keys", "Either", ["Settings → Reset to defaults."], "Keys return to S, Z, X, C, G, R, Enter."),
])

sec("Ladder settings and saved layouts", "Every option in the settings dialog.", [
    c("Settings dialog opens and closes", "Either", ["Click Ladder settings; press Done; reopen; press Esc."], "It opens, closes with Done and with Esc."),
    c("Settings are remembered", "Either", ["Change a few settings and reload."], "They are still set (stored in this browser)."),
    c("Recent volume windows", "Either", ["Set short 30s, long 10 minutes."], "The recent volume column's tooltip and bars reflect the new windows."),
    c("Weight of money levels", "Either", ["Change WoM levels to 1, then 5."], "The WoM percentages change."),
    c("Stake presets editable", "Either", ["Change the preset list."], "The toolbar and per-ladder chips show the new presets; keys 1–8 follow."),
    c("Reset to defaults", "Either", ["Press Reset to defaults and confirm."], "Every setting returns to its default; the Cancel on the confirm leaves things alone."),
    c("Save a layout", "Either", ["Name it 'Tennis scalping' and press Save current settings."], "It appears in the saved list."),
    c("Load a layout", "Either", ["Change settings, then press Load on the saved layout."], "Settings return to what was saved."),
    c("Delete a layout", "Either", ["Delete it and confirm."], "It disappears."),
    c("Layouts survive a reload", "Either", ["Reload."], "Saved layouts are still listed."),
])

sec("Switch runner", "The ⇄ control in a ladder's header.", [
    c("Swap two ladders", "Either", ["On the left ladder pick the other runner from ⇄."], "The two ladders trade places; both recentre."),
    c("Orders and positions follow the runner", "Either", ["Place a bet, then switch."], "The bet and position stay with their runner, not their screen position."),
])

sec("Info panels", "The tabbed panel at the bottom: P&L all runners, Market info, Runner info, Traded & available, Log.", [
    c("P&L of all runners", "Either", ["Open the tab with a position."], "Each runner shows the profit if it wins, your position, and a market line (worst case or green-up level)."),
    c("Market info", "Either", ["Hover a ladder and open the tab."], "Event, market, competition, start time, status, runners, matched in market, back and lay book."),
    c("Runner info follows the hovered ladder", "Either", ["Hover each ladder in turn."], "Runner, last price, best back and lay, spread in ticks, matched and share, weight of money, your position."),
    c("Traded & available", "Either", ["Open the tab."], "A price table with available to back, available to lay and traded at each price."),
    c("Log", "Either", ["Place a bet, then open the Log tab."], "The order appears with its time. Stops, offsets, greens and restarts are logged too."),
    c("Panels collapse", "Either", ["Click ▾ on each panel."], "Each folds to its header and reopens."),
])

sec("Dutching", "Spread a total over several runners.", [
    c("Back dutch gives equal outcomes", "Demo", ["Dutching tab → tick both runners → total 100."], "Stakes are shown and 'If it wins' is the same (within a few pence) for each runner. Total stake is £100."),
    c("Custom price per runner", "Demo", ["Type a price in a runner's price box."], "The preview uses that price (not the market's)."),
    c("Lay dutch", "Demo", ["Switch to Lay."], "Stakes are laid; outcomes are equal for the chosen runners."),
    c("Three-runner dutch", "Demo", ["Football: tick two of three."], "The third runner shows the loss of the whole stake (or gain for lay)."),
    c("Needs two runners and £1", "Either", ["Tick one runner; or enter 0.50."], "No preview and the Place button is disabled (or a clear message)."),
    c("Stakes under £1 are left out", "Demo", ["Choose a long-odds runner with a small total."], "The preview says how many bets are under £1 and left out."),
    c("Place asks for confirmation and places all legs", "Demo", ["Press Place."], "A confirm lists every leg; after OK each leg appears in Matched bets (or Unmatched bets if waiting) and the toast says N of N placed."),
    c("Book percentage shown", "Demo", ["Look under the table."], "The book % for the chosen prices is shown."),
])

sec("Bookmaking", "Choose the profit you want on every outcome.", [
    c("Even (green-up) quick fill", "Demo", ["With a position, Bookmaking tab → Even."], "Every target fills with the green-up level; the preview shows the bets that level the market."),
    c("Custom targets", "Demo", ["Enter +£10 on A and +£5 on B."], "The preview shows the bets to place and 'After' equals your targets (within pence)."),
    c("Current / Clear", "Demo", ["Press Current, then Clear."], "Current copies today's outcomes (no bets needed); Clear empties the targets."),
    c("Targets needed for every runner", "Either", ["Fill only one target."], "A prompt says to enter a target for every runner; Place is disabled."),
    c("Place and verify", "Demo", ["Place the plan, then open P&L all runners."], "The outcomes shown match your targets."),
    c("Unreachable targets are explained", "Demo", ["Try targets far above what the book can give."], "Either large stakes are shown clearly in the preview (you decide) or a clear message explains it; nothing is placed without confirmation."),
])

sec("Restart safety", "Nothing held in memory may be lost on a restart or deploy.", [
    c("Stops, offsets and auto-greens survive a restart", "Practice", ["Set a stop and an auto-green.", "Ask for the service to be restarted.", "Reload the app."], "The stop and auto-green are still there; the log says 'Restarted: restored …'."),
    c("Practice orders and positions survive a restart", "Practice", ["Place a bet and leave a waiting bet; restart; reload."], "The position, matched bets and waiting bet are all still present."),
    c("A deploy does not interrupt trading", "Practice", ["Push a harmless change while holding stops or waiting bets."], "The deploy is held until nothing is waiting (or completes with everything restored)."),
    c("A corrupt state file starts clean and says so", "Practice", ["(Admin) damage the state file and restart."], "The app starts empty, the log says it could not restore, and nothing crashes."),
])

sec("Safety, errors and limits", "How the app behaves when things go wrong.", [
    c("Never live", "Either", ["Look for any way to place a real bet."], "None exists: practice mode only simulates orders and live mode is not built."),
    c("Exchange or network error is readable", "Practice", ["Disconnect the network briefly while using the app."], "A readable message appears; the app recovers when the network returns."),
    c("Guardrail warnings are shown", "Either", ["Place very large or rapid bets."], "Any guardrail warning appears in a message instead of failing silently."),
    c("Rejected orders say why", "Demo", ["Try to bet on a suspended market."], "The reason is shown ('the market is suspended')."),
    c("Esc closes dialogs and menus", "Either", ["Open the confirm card, the settings and a menu; press Esc."], "Each closes."),
])

sec("Layout and performance", "The app in different situations.", [
    c("Four ladders at once", "Demo", ["Open both tennis matches (two ladders each)."], "Four ladders fit on screen and all stay readable."),
    c("Window sizes", "Either", ["Try a laptop width and a wide monitor."], "Nothing overlaps; the panels reflow; ladders stay usable."),
    c("Browsers", "Either", ["Repeat a short run in Chrome and in Safari/Edge."], "Same behaviour, including drag and drop."),
    c("Stays responsive over time", "Practice", ["Leave two markets open for 30 minutes."], "Prices keep updating, no slow-down, no growing memory use in the tab."),
    c("Hover tooltips", "Either", ["Hover buttons, cells and chips."], "Tooltips explain each control."),
])

sec("Ladder size and scrolling (added 4 Nov)", "How many ticks you see, and how the mouse wheel behaves.", [
    c("Default is about 25 ticks", "Either", ["Open Ladder settings and note 'Ticks in view'.", "Open a market with the chart open on a normal laptop or monitor window."], "The setting reads 25. Ladders show up to 25 price rows (fewer only if the window is too small), rows are compressed neatly, text stays readable."),
    c("Change ticks in view", "Either", ["Set Ticks in view to 15, then 35, then 0."], "15: bigger rows and a bigger chart. 35: smaller rows, chart squeezed or hidden, no scrollbar on the ladder. 0: as many normal-size rows as fit."),
    c("Chart gives way to rows", "Either", ["Set 40 ticks with the chart open."], "The chart shrinks (then disappears) before the rows get unreadable. Prices stay clickable."),
    c("Drag bar still works", "Either", ["Drag the bar under a ladder up and down."], "Rows are added or removed and the chart resizes. Dragging one ladder does not move another."),
    c("Wheel over price rows moves only the ladder", "Either", ["Put the cursor over the price rows of each ladder in turn (left, middle, right on a football match).", "Scroll the mouse wheel."], "The prices move. The page does not scroll. Same for every ladder."),
    c("Wheel elsewhere scrolls the page", "Either", ["Put the cursor on the chart, the market header or the panels and scroll."], "The page scrolls normally to reach the panels below the ladders."),
    c("Reverse ladders and wheel direction", "Either", ["Turn Reverse on and scroll over a ladder."], "Prices still move in the direction you scroll (consistent with the reversed layout)."),
])

sec("Market list: search, filters, grouping (added 4 Nov)", "The left-hand list of markets.", [
    c("Free-text search", "Either", ["Type part of a player, team, competition or market name in the search box."], "The list filters as you type. A search with no match says so and tells you how to clear it."),
    c("Search matches both names in an event", "Either", ["Search for one team, then for the other team in the same match."], "The same match appears for either name."),
    c("In-play, Next hour and Mine filters", "Either", ["Turn each filter on in turn, then combine them."], "In-play shows live events only. Next hour shows events starting within an hour. Mine shows markets you have open. Combined filters narrow further."),
    c("Competition grouping and folding", "Either", ["Click a competition heading to fold it, again to unfold."], "Headings show a count. Folding hides that competition's matches."),
    c("Sort by start or name", "Either", ["Toggle the sort chip."], "The order changes between start time and name."),
    c("Open markets are marked", "Either", ["Open a market."], "Its row gets a coloured edge in the list."),
])

sec("Open-market tabs (added 4 Nov)", "More markets open than fit on screen.", [
    c("Tabs appear with two or more markets open", "Demo", ["Open both tennis matches, then a football match."], "A tab bar appears above the ladders with one tab per open market."),
    c("Two matches stay on screen; the rest wait behind tabs", "Demo", ["Open three tennis or football markets in a row."], "The market shown longest steps back to its tab so the new one fits. Nothing is closed."),
    c("Click a tab to bring a market on screen", "Demo", ["Click a tab that is not shown."], "Its ladders appear; the oldest shown market goes back to its tab."),
    c("Tab shows position, orders and state", "Demo", ["Place a bet and leave an unmatched bet in a market, then switch to another tab.", "Use the demo controls to suspend a market."], "The tab of the market with a position shows its worst-case P&L (green/red). Unmatched bets show a count badge. A suspended market's tab is outlined."),
    c("Hidden markets stay live", "Demo", ["With a market hidden behind a tab, place a bet or let a stop trigger on it."], "It still matches, triggers and counts in Orders, Matched bets and exposure."),
    c("Close from a tab", "Demo", ["Click the x on a tab."], "A warning if you hold a position or unmatched bets; otherwise the market closes and the tab disappears."),
])

sec("All markets on an event (added 4 Nov)", "Half time, goal lines, correct score and the rest, from the + button in the market list.", [
    c("Expand an event", "Either", ["In the football list, click the + beside an event."], "The event's other markets appear, grouped (Result, Match goals, Team goals, Score, Corners, Cards, Other). Clicking again collapses them."),
    c("Open a goal line market", "Either", ["Expand an event and open Over/Under 2.5 Goals."], "Two ladders (Under and Over) open. The tab and header name the market."),
    c("Match goals are separate from team goals", "Practice", ["Expand an event and compare 'Over/Under 2.5 Goals' with '<Team> Over/Under 2.5 Goals'."], "The match line is under Match goals; each team's own goals lines are under Team goals. Lines are in order (0.5, 1.5, 2.5 ...)."),
    c("Half-time and first-half markets", "Practice", ["Open Half Time and First Half Goals markets."], "Ladders open with the right runners and update."),
    c("Runner picker for big markets", "Either", ["Open Correct Score."], "A picker lists every runner. You can choose up to 4; the rest are disabled once four are chosen."),
    c("Swap a ladder to another runner", "Either", ["In a correct score market, use the selector at the top of a ladder to switch runner."], "The ladder shows the chosen runner. Positions are kept per runner."),
    c("Several markets of one match together", "Either", ["Open Match Odds, Over/Under 2.5 and Half Time of the same match."], "All are open as tabs; you can bring any on screen. The live score line shows on each."),
    c("Market-level P&L and green-up on a goals market", "Demo", ["Place back and lay bets in an Over/Under market.", "Use Green up from the market header."], "P&L if each runner wins is correct and green-up locks an equal profit."),
    c("Tennis event markets", "Practice", ["Expand a tennis event with +."], "Set betting, total games and similar markets are listed and open correctly."),
])

sec("Live score and match line (added 4 Nov)", "Score, clock and serve under the market name. Needs the data collectors, so Practice mode only.", [
    c("Tennis scoreboard", "Practice", ["Open a live ATP, WTA or Challenger match."], "A scoreboard shows a row per player: set scores, current game score and a dot by the server. It updates within about 5 seconds of a point."),
    c("Players in the same order as the ladders", "Practice", ["Compare the scoreboard rows with the two ladders' runner names."], "The first row is the first Betfair runner, not whichever player the data feed lists first."),
    c("Football clock and score", "Practice", ["Open a live match in a covered league (England, Scotland, Germany, Spain, Italy, France)."], "The match minute and score show and update. Before kick-off it shows the status instead."),
    c("Other markets of the same match", "Practice", ["Open Over/Under or Correct Score for a live match."], "The same score line appears."),
    c("No match found means no line", "Practice", ["Open a market from a competition we do not collect (for example a lower league or ITF)."], "No score line is shown and nothing is guessed. No error."),
    c("Doubles and name oddities", "Practice", ["Open a doubles market, and a match with a hyphenated or accented name."], "Doubles show no line. Unusual names either match correctly or show nothing. Report any wrong match."),
])

sec("Data collection health (added 4 Nov)", "Checks on the server's football and tennis data collection. These use the status addresses until the Data screen exists.", [
    c("Football status", "Practice", ["Call /api/football/status (with the token)."], "Fixtures in the thousands, with_details rising day by day, last_error null (a rate-limit message that clears itself is fine)."),
    c("Tennis status", "Practice", ["Call /api/tennis/status."], "matches in the thousands, history_days_done rising to 730, live_now counts live matches, last_error null."),
    c("Live matches are logged", "Practice", ["During a live match check live_snapshots in either status."], "The count rises as scores change."),
    c("App survives a collector failure", "Practice", ["After any deploy check the app starts and ladders load."], "The app is up even if a collector reports an error."),
])

sec("Access and deploys (added 4 Nov)", "Reaching the server and getting changes onto it.", [
    c("HTTPS address", "Practice", ["Open https://159-65-20-243.sslip.io/ from a tablet or phone."], "The app loads over HTTPS with a valid certificate and asks for the token."),
    c("Token works and wrong token is refused", "Practice", ["Enter the current token, then try a wrong one in a private window."], "Right token: app loads. Wrong: refused."),
    c("Push deploys itself", "Practice", ["After a change is pushed, wait 3 minutes and reload with Ctrl+F5."], "The change is live. The GitHub Actions run is green."),
    c("Restart keeps your state", "Practice", ["Leave an unmatched bet and a stop in place, then trigger a deploy that restarts the app."], "After it comes back your unmatched bets, stops and matched bets are still shown."),
])

sec("Safety, limits and Stop all automation (added 5 Nov)", "The strip under the header and Settings > Safety and limits. Everything here is practice money.", [
    c("Status strip shows Today and Automation", "Either", ["Look at the strip under the navbar."], "Today's profit/loss, the Automation on/off button and any limit warnings are visible on every screen."),
    c("Stop all automation", "Either", ["Click Automation, then Stop all automation.", "Read the dialog and confirm."], "Dialog explains what stops (scripts, AI, plan entries) and what does not (your manual trading, existing stops). After confirming the strip shows Automation OFF and scripts fire nothing."),
    c("Resume automation", "Either", ["Open Alerts or the strip and resume."], "Automation shows ON again and scripts can fire."),
    c("Default loss limit is not set", "Either", ["Open Settings > Safety and limits on a fresh install."], "Daily and weekly loss limits show 0 / not set. Nothing is blocked."),
    c("Daily loss limit stops automation, not manual trading", "Demo", ["Set a small daily loss limit (e.g. 5).", "Lose more than that with an enabled script or by trading manually.", "Try a manual bet, then wait for a script to try to enter."], "Manual losses count towards the limit but manual bets are never blocked. Script entries are refused with a clear reason and an alert is raised. Exit orders (:exit) from scripts still work."),
    c("Open liability limit", "Demo", ["Set a low open liability limit.", "Let a script try to enter a large stake."], "The entry is refused and says why. Tick 'include manual' to count manual positions too."),
    c("Lay stakes default to stake basis", "Either", ["Place a lay bet from the ladder."], "The amount typed is the stake, not the liability, unless you changed the setting."),
    c("Settings survive a restart", "Practice", ["Change a limit.", "Wait for a deploy or restart."], "The setting is unchanged afterwards."),
    c("Full AI mode is locked", "Either", ["Try to select Full AI in the AI mode setting."], "It is refused with 'not available yet'. Advisor stays available."),
])

sec("Scripts (added 5 Nov)", "Rules that enter and exit trades for you. Written as JSON; Claude can draft them.", [
    c("Create a script from a template", "Either", ["Open Scripts, click New, pick a template."], "A script appears in the library with its entry, exit and safety rules shown as readable cards."),
    c("Validation catches mistakes", "Either", ["Edit the JSON so a rule uses an unknown condition or a stake of 0.", "Save."], "Save is refused with a specific message pointing at the problem."),
    c("Import a script", "Either", ["Paste valid script JSON into Import."], "It appears in the library, disabled."),
    c("Enable, disable and clone", "Either", ["Enable a script, disable it, then clone it."], "State changes immediately; the clone is a separate disabled script."),
    c("Version history", "Either", ["Edit and save a script twice.", "Open History."], "Each save is a version with a timestamp. You can view earlier versions."),
    c("Build a script with the Copilot", "Practice", ["Open the Copilot panel on the right of Scripts (it opens in Build a script mode) and describe a strategy in plain English."], "A draft script is returned, validated, and can be saved. Invalid drafts are not saved."),
    c("Add to Plan", "Either", ["From a script, click Add to Plan and pick a market and runner."], "A Plan row is created binding the script to that market and runner."),
    c("Script fires on a live demo market", "Demo", ["Enable a simple price-based entry script, add it to the Plan on a demo market, let the price cross the condition."], "An order is placed with source script:<name>, appears on the ladder and in the activity log, and the exit rule closes it as defined."),
    c("Discuss with Claude", "Practice", ["Click Discuss with Claude on a script."], "The copilot opens with the script as context."),
])

sec("Plan (added 5 Nov)", "Which scripts are armed on which markets.", [
    c("Plan lists rows with status", "Either", ["Open Plan."], "Each row shows market, runner, script, status (waiting, in position, done, stopped) and bets taken."),
    c("Edit and remove a row", "Either", ["Change a row's stake or remove it."], "Change is saved; removed rows stop acting immediately."),
    c("Row bets view", "Either", ["Open a row's bets."], "Orders placed by that row with price, size and result."),
    c("Attach from the market list", "Either", ["Click the plan button next to a market in the list.", "Choose a script."], "The attach dialog adds a Plan row."),
])

sec("Recommendations (added 5 Nov)", "Model vs market edges. Practice only; shown for your judgement.", [
    c("Recommendations appear for real pre-match markets", "Practice", ["Open Recommendations after a few minutes of Practice running."], "Cards list the pick, model price vs market price, edge, reasoning and the current price. Confidence is never High. There may be none if no edge is found."),
    c("Apply a recommendation", "Practice", ["Click Apply on a card."], "A Plan row or order is created for the chosen script; the card moves to Applied."),
    c("Dismiss a recommendation", "Practice", ["Click Dismiss."], "The card is removed from pending and does not return for that market."),
    c("Scan now", "Practice", ["Click Scan."], "A fresh scan runs; the list updates."),
    c("Auto-apply is locked", "Practice", ["Look for the auto-apply option."], "It is locked with the message that it needs 300 recommendations with positive CLV."),
])

sec("Alerts and health (added 5 Nov)", "What the system tells you, and the Health badge.", [
    c("Alerts list and mark read", "Either", ["Open Alerts.", "Mark one read."], "Unread count in the navbar drops. Duplicate alerts are not repeated."),
    c("Health badge", "Practice", ["Click the Health badge."], "A panel lists Betfair, tennis feed, football feed, price log and Claude with a dot colour and plain-English detail."),
    c("Feed outage raises an alert", "Practice", ["(If practical) temporarily break a feed key on the server."], "Within about 2 minutes the Health badge turns amber/red and an alert is raised."),
])

sec("Home (added 5 Nov)", "The first screen.", [
    c("Home shows the day at a glance", "Either", ["Open Home."], "Today and week P&L, automation state, open positions, pending recommendations, recent alerts and upcoming markets are visible."),
    c("Home cards link through", "Either", ["Click each card."], "Each goes to the right screen (Recommendations, Plan, Alerts, Manual Trading)."),
])

sec("Analyse and Backtesting (added 5 Nov)", "Performance, strategies, models and replay tests.", [
    c("Performance tab", "Either", ["Open Analyse > Performance."], "Today, this week, month and last 7 days with profit, ROI and win rate, plus a chart. With no settled trades it shows empty states, not errors."),
    c("Strategies tab attribution", "Either", ["Open Strategies after some script and manual trades have settled."], "Profit is split by script and by manual, with staked amount and ROI."),
    c("Models tab", "Either", ["Open Models."], "A table of offline model results (tennis v1, v2, Elo, v3 and football 1X2) against the market, with the note that models are trading guidance, not winner-picking."),
    c("AI learning tab", "Practice", ["Open AI learning."], "Shows recommendation count, CLV evidence so far and the gate to auto-apply."),
    c("Run a backtest", "Practice", ["Open Backtesting, choose a strategy, target and date range, run."], "Result shows trades, profit, ROI, win rate with a train/out-of-sample split. If there are not enough recorded results it says so plainly."),
    c("Backtest data grows", "Practice", ["Check the price log result counts over a few days."], "Markets with recorded winners increase, making more backtests possible."),
])

sec("Settings (added 5 Nov)", "One place for configuration.", [
    c("Settings sections", "Either", ["Open Settings and visit each section."], "Safety and limits, Connections and feeds, Credentials, Trading defaults, AI and costs, Alerts, Versions and models, Appearance all load."),
    c("Credentials show presence only", "Practice", ["Open Settings > Credentials."], "Each key shows Set or Not set. No key value is ever displayed."),
    c("Connections and data counts", "Practice", ["Open Connections and feeds."], "Health items plus counts of football and tennis matches and price log markets/ticks."),
    c("Theme switch", "Either", ["Open Appearance and switch theme."], "The whole app changes between dark and light and remembers it."),
    c("Alerts channels", "Either", ["Open Alerts section."], "Browser is on; email and push are shown as not set up yet."),
])

sec("Real orders safety (added 5 Nov)", "Real order placing exists in code but is switched off.", [
    c("Mode badge never reads LIVE", "Practice", ["Look at the header badge and Health."], "It reads PRACTICE MODE. Orders are simulated and nothing is sent to Betfair."),
    c("Live mode does not start", "Practice", ["(Server) confirm AUTOBETS_MODE is practice."], "Setting live is refused at start-up with an explanation. Real orders are only enabled later with your live key."),
])

sec("Market list on Home and Plan, bulk add, AI panel (added 5 Nov)", "The same market list as the ladder screen, now on Home and Plan.", [
    c("Market list on Home and Plan", "Either", ["Open Home, then Plan."], "The market list (Tennis / Football tabs, search, In-play, Next hour, sort) is on the left of both. Home also has the Copilot panel docked on the right."),
    c("All markets on an event", "Practice", ["On Football, click 'All markets on this event' under a match."], "Half time, goal lines, correct score and other markets appear grouped, each with a tick box (not only Match Odds)."),
    c("Tick and bulk add, watch only", "Either", ["Tick three markets.", "Click Add 3 to Plan.", "Leave script as None and confirm."], "A message says 3 markets were added. They show on the Plan as Watching and as 'in Plan' in the list. The tick boxes clear."),
    c("Select a whole competition / select all shown", "Either", ["Tick a competition heading, then try Select all shown after a search."], "Every market under that heading (or every market shown after the search) is ticked; the counter matches."),
    c("Selection survives tab and search changes", "Either", ["Tick a tennis market, switch to Football, tick one, search, then switch back."], "The selected count still includes both."),
    c("Bulk add with a script", "Either", ["Tick several markets.", "Add to Plan, choose a script and the rule Favourite, set a stake."], "Each market gets a Plan row with the favourite (shortest back price) as its runner. Markets where the rule cannot apply (e.g. Draw on tennis) are skipped and listed."),
    c("Open a ladder from the list", "Either", ["Click the ladder icon on a market row on Home or Plan."], "Manual Trading opens with that market's ladders."),
    c("Scripts > Add to Plan uses the same list", "Either", ["On Scripts, click Add to Plan."], "The picker shows the full list including all-markets-on-event; choosing a market then asks which runner."),
    c("Home AI panel", "Practice", ["Ask the docked Copilot about your Plan markets."], "It answers about the markets in your Plan and any open ladders. It cannot place bets in Advisor mode."),
    c("Narrow screens", "Either", ["Open Home on a phone or narrow window."], "A 'Market list' button reveals the list above the screen; the AI panel is available from the Copilot button in the header."),
])

sec("Script chooser and Copilot script builder (added 5 Nov)", "Scales as the number of scripts grows; scripts can be created from the Copilot beside Plan and Home.", [
    c("Copilot is on Plan as well as Home", "Either", ["Open Plan on a wide screen."], "The Copilot panel is docked on the right of both Home and Plan."),
    c("Build a script from the Copilot", "Practice", ["Click Build a script in the Copilot.", "Describe a strategy in plain English and send."], "A draft appears with Entry / Exit / Safety rule cards. An invalid draft shows a clear error and cannot be saved."),
    c("Refine a draft", "Practice", ["With an unsaved draft showing, type a change (e.g. 'make the stake 5 and add a 10 pound stop')."], "A full updated draft replaces it, keeping the earlier rules unless you changed them."),
    c("Save the draft and use it straight away", "Practice", ["Click Save as draft script.", "Tick a market in the list, Add to Plan, open the script chooser."], "The new script is in the chooser (off, tagged AI draft) without reloading the page."),
    c("Chooser search", "Either", ["Open the script chooser and type part of a name or description."], "The list narrows as you type; with no match it says so."),
    c("Chooser sport filter", "Either", ["Choose Tennis, then Football."], "Only scripts for that sport (plus 'Any sport' scripts) are shown."),
    c("Recently used and On/Off sections", "Either", ["Add a script to the Plan, then reopen the chooser."], "It appears under Recently used at the top; the rest are grouped On then Off."),
    c("Chooser in all three places", "Either", ["Check Add to Plan from the list, the market ▤ button on Manual Trading, and Edit on a Plan row."], "Each uses the same searchable chooser."),
    c("Scripts library filters", "Either", ["On Scripts use the All / On / Off / AI drafts / Tennis / Football chips and the search box."], "The library narrows and its heading shows 'N of M'."),
])

sec("Scalping scripts: ticks from entry and repeat (added 5 Nov)", "Scripts can now exit relative to where they were matched, and re-arm.", [
    c("Scalp example loads and saves", "Either", ["On Scripts click Scalp example, then Save."], "The script saves; its cards read: back at best price, exit green when 2 ticks in profit from where you were matched, repeat up to 10 times, safety at 6 ticks against."),
    c("Copilot builds a scalp", "Practice", ["Ask the Copilot (Build a script): football Under 2.5 goals scalper, back £10 at best price, green 2 ticks in profit, repeat 10 times."], "A valid draft with repeat 10 and a ticks-from-entry exit is returned."),
    c("One at a time", "Demo", ["Add the scalp to an Over/Under 2.5 market on the Under runner and enable it."], "Only one entry order exists until its green-up has matched; the Plan row shows 'Run 1 of 10'."),
    c("Exit 2 ticks from where you were matched", "Practice", ["Watch a run where the Lay price drops 2 ticks below your matched price."], "The script greens (not before) and logs the profit."),
    c("Re-arm and stop after the last run", "Practice", ["Let several runs complete."], "The run counter advances after each green-up and the row ends Done after run 10."),
    c("Stop at 6 ticks against", "Practice", ["If the price moves 6 ticks against the entry."], "The position is closed, the script stops and does not re-arm."),
])

cases = []
for si, (name, intro, cs) in enumerate(S, 1):
    for ci, k in enumerate(cs, 1):
        cases.append({"id": f"{si}.{ci}", "section": name, "intro": intro, **k})

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    json.dump(cases, open(os.path.join(here, "uat_cases.json"), "w"), indent=1)
    out = ["# AutoBets: User Acceptance Test script", "", "Run in **Demo** first (fake prices, demo controls strip for suspending and closing markets), then repeat the 'Practice' cases on real delayed prices. Record Pass / Fail / Blocked and notes against each case.", ""]
    for si, (name, intro, cs) in enumerate(S, 1):
        out += [f"## {si}. {name}", "", f"_{intro}_", ""]
        for ci, k in enumerate(cs, 1):
            out += [f"### {si}.{ci} {k['title']}  \\[{k['mode']}\\]", "", "Steps:"] + [f"{n}. {s}" for n, s in enumerate(k["steps"], 1)] + ["", f"**Expected:** {k['expected']}", "", "Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: ", ""]
    open(os.path.join(here, "UAT.md"), "w").write("\n".join(out))
    print(len(cases), "cases in", len(S), "sections")
