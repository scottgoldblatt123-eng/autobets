# AutoBets: User Acceptance Test script

Run in **Demo** first (fake prices, demo controls strip for suspending and closing markets), then repeat the 'Practice' cases on real delayed prices. Record Pass / Fail / Blocked and notes against each case.

## 1. Setup and access

_Before anything else. Demo mode is the safe place to run most of this script._

### 1.1 Open the app and see the mode badge  \[Either\]

Steps:
1. Open the AutoBets address in a browser.

**Expected:** The header badge reads DEMO — FAKE PRICES or PRACTICE MODE. It never reads LIVE.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 1.2 Token prompt appears when no token is stored  \[Either\]

Steps:
1. Open the app in a private window.
2. Do not enter a token.

**Expected:** A token prompt is shown. Nothing else is usable.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 1.3 Wrong token is refused  \[Practice\]

Steps:
1. Enter a wrong token and submit.

**Expected:** A clear 'try again' message. No market list loads.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 1.4 Right token is accepted and remembered  \[Practice\]

Steps:
1. Enter the right token.
2. Reload the page.

**Expected:** Markets load. The token is not asked for again on reload.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 1.5 Backend unreachable shows a message, not a blank page  \[Either\]

Steps:
1. Stop the service (or disconnect the network) and reload.

**Expected:** A readable error with a Try again button.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 2. Markets list and opening ladders

_The left-hand market list and what opening a market does._

### 2.1 Tennis and Football tabs list markets  \[Either\]

Steps:
1. Click Tennis, then Football.

**Expected:** Each tab lists its own matches with competition and start time.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.2 Opening a market opens ALL its runners together  \[Either\]

Steps:
1. Click a tennis match.

**Expected:** Two ladders (A and B) appear in one market block, side by side.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.3 Football match odds opens three ladders  \[Demo\]

Steps:
1. Click the football match with a draw.

**Expected:** Three ladders open: home, away and the draw, in one block.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.4 Four-ladder cap with a clear message  \[Demo\]

Steps:
1. Open the football match (3 ladders).
2. Open a tennis match (needs 2).

**Expected:** A message says it needs 2 ladders but only 1 slot is free. Nothing half-opens.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.5 Opening the same market twice is refused  \[Either\]

Steps:
1. Open a market.
2. Click the same market again.

**Expected:** A message says it is already open. No duplicate ladders.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.6 Closing one market with the X closes all its ladders  \[Either\]

Steps:
1. Click the X at the top right of a market block.

**Expected:** All ladders of that market close together. You cannot close just one runner's ladder.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 2.7 Closing a market with a position or open orders asks first  \[Demo\]

Steps:
1. Place a bet and leave an unmatched bet.
2. Click the market's X.

**Expected:** A confirm dialog warns about the position and the unmatched orders. Cancel keeps the market open.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 3. Ladder display

_How a ladder looks and what each column means (Bet Angel is the reference)._

### 3.1 Column order and colours  \[Either\]

Steps:
1. Look at any ladder.

**Expected:** Left to right: P&L column, my back bets, back (blue), price (dark blue), lay (pink), my lay bets, recent volume.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.2 Back is blue and on the left, lay is pink and on the right  \[Either\]

Steps:
1. Hover each side and read the tooltips.

**Expected:** Left cells say 'Back at x', right cells say 'Lay at x'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.3 Back prices sit at or below the best back; lay prices at or above the best lay  \[Either\]

Steps:
1. Compare the blue and pink cells with the price column.

**Expected:** Blue numbers appear on prices up to the best back price; pink numbers from the best lay price upwards; one tick between them when the spread is a tick.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.4 Tinted empty zones  \[Either\]

Steps:
1. Look at the empty cells beyond the best prices.

**Expected:** Empty cells in the back zone and the lay zone are tinted; cells in between are plain.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.5 Last traded price is highlighted  \[Either\]

Steps:
1. Find the orange outlined price.

**Expected:** The last traded price row is outlined in orange and updates as the market moves.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.6 Recent volume column  \[Either\]

Steps:
1. Watch the right-hand bars for a minute.

**Expected:** Bars show volume matched at each price in the short window (solid) and long window (lighter). Numbers appear for the short window.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.7 Total matched column (optional)  \[Either\]

Steps:
1. Ladder settings → show the total matched column.

**Expected:** An extra column appears with the total matched at each price. Switching it off removes it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.8 Weight of money bar  \[Either\]

Steps:
1. Look at the bar above the ladder.

**Expected:** Blue and pink shares add to 100%, with an arrow showing which side is heavier, and the number of bets each side.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.9 Footer shows matched volume and market share  \[Practice\]

Steps:
1. Look at the line under the price rows.

**Expected:** It shows £ matched on that runner and its % of the market. If Betfair sends none it says 'volume not available' (expected on a delayed key).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 3.10 Light and dark themes  \[Either\]

Steps:
1. Click Dark / Light in the header.

**Expected:** Both themes are readable: colours, price column, chips and panels.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 4. Ladder movement

_Scrolling, recentring and reversing the ladder._

### 4.1 Mouse wheel moves the prices  \[Either\]

Steps:
1. Hover the price rows and use the wheel.

**Expected:** The ladder moves up and down the price ladder one tick per notch.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 4.2 Wheel outside the price rows does not move prices  \[Either\]

Steps:
1. Hover the chart or the header and use the wheel.

**Expected:** The prices do not move.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 4.3 Ladder stays put when the price moves (auto-centre off)  \[Demo\]

Steps:
1. Leave auto-centre off.
2. Wait for the price to drift.

**Expected:** The ladder holds its position and shows ▲ or ▼ with the price when the market has moved out of view.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 4.4 Recentre with Enter and the ⌖ button  \[Either\]

Steps:
1. Scroll away, then press Enter.
2. Scroll away, then click ⌖ on one ladder.

**Expected:** Enter recentres every ladder; ⌖ recentres just that one.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 4.5 Auto-centre setting  \[Either\]

Steps:
1. Ladder settings → auto-recentre on.
2. Let the price drift.

**Expected:** The ladder follows the price by itself.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 4.6 Reverse ladders (R key and button)  \[Either\]

Steps:
1. Press R, then press it again.

**Expected:** Lowest price moves to the top, then back. Back stays on the left and lay on the right; clicking still places the side of the column you clicked.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 5. Stakes

_Every way of choosing how much to bet._

### 5.1 Preset stake buttons  \[Either\]

Steps:
1. Click 2, 5, 10, 20 in the toolbar.

**Expected:** The chosen preset is highlighted and used for the next bet.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.2 Free-form stake box  \[Either\]

Steps:
1. Press S, type 65, press Enter.

**Expected:** The stake box shows 65 and the next bet is £65. Clearing the box goes back to the preset.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.3 Pound sign and commas accepted  \[Either\]

Steps:
1. Type £1,250 in the stake box.

**Expected:** It is read as £1,250.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.4 Stakes under £1 are refused  \[Either\]

Steps:
1. Type 0.50 in the stake box and click a price.

**Expected:** A message says the minimum is £1. No bet is placed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.5 Invalid text is flagged  \[Either\]

Steps:
1. Type abc in the stake box.

**Expected:** The box turns red with 'min £1'. Clicking a price places nothing.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.6 Per-ladder stake  \[Either\]

Steps:
1. On one ladder click a stake chip or type in its own stake box.
2. Place a bet on each ladder.

**Expected:** Each ladder uses its own stake. A ladder with an empty box uses the toolbar stake.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.7 Number keys 1–8 act on the hovered ladder  \[Either\]

Steps:
1. Hover one ladder and press 3.

**Expected:** That ladder's stake becomes the 3rd preset. The other ladder is unchanged. With no ladder hovered it changes the toolbar stake.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.8 Lay stake or liability  \[Either\]

Steps:
1. Ladder settings → lay stakes entered as liability.
2. Stake 10, lay at 3.0.

**Expected:** The bet placed is a lay of £5 (liability £10). Switching back to 'a stake' lays £10.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.9 Confirm large orders  \[Either\]

Steps:
1. Set 'confirm orders of £50 or more'.
2. Bet £60.

**Expected:** A confirm card shows side, runner, price and size. Place sends it; Cancel (or Esc) does not.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.10 Percentage-of-bank stakes  \[Either\]

Steps:
1. Settings → stakes as % of bank; bank £500.
2. Look at the preset chips; click a 4% chip and place a bet.

**Expected:** Chips show %; a 4% bet is £20.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.11 Type 2% in a stake box  \[Either\]

Steps:
1. With bank £500 type 2% in the stake box.

**Expected:** The next bet is £10, whatever the stake mode.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 5.12 Separate lay stake  \[Either\]

Steps:
1. Settings → separate stake for lay bets.
2. Enter a lay stake of 20, back stake 10.

**Expected:** A Lay £ box appears. Back bets use £10, lay bets use £20. Blank lay box uses the back stake.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 6. Placing and matching bets

_Clicks, sides, prices and what 'matched' means._

### 6.1 Click blue = BACK, click pink = LAY  \[Either\]

Steps:
1. Click a blue cell, then a pink cell, both with stake £2.

**Expected:** Confirmation says BACK (blue tag) then LAY (pink tag) at the prices you clicked. The Matched bets panel lists them with the same sides.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.2 A bet at the best price matches immediately  \[Either\]

Steps:
1. Click the best back price (the highest blue number).

**Expected:** Status 'matched'. Your position line appears.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.3 A bet at a worse price takes the better price  \[Demo\]

Steps:
1. Click a lay cell above the best lay price.

**Expected:** The bet matches at the best lay price, not the price you clicked. The Matched bets panel shows both 'Asked' and 'Matched at'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.4 A bet at a better price waits (unmatched)  \[Demo\]

Steps:
1. Lay at a price well below the best back, or back at a price well above the best lay.

**Expected:** Status 'waiting (unmatched)'. It appears in Unmatched bets and on the ladder.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.5 Waiting bets are summed at their price  \[Demo\]

Steps:
1. Place three £10 lays at the same low price.

**Expected:** That row shows '£30 ×3' in your own-bets column and 'LAY £30 waiting' over the volume bar; BACK shows blue. Hover shows the count and total.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.6 A waiting bet matches when the price reaches it  \[Demo\]

Steps:
1. Wait with a lay waiting just below the market until the price drops to it (or place it one tick away).

**Expected:** The bet moves from Unmatched bets to Matched bets and your position updates.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.7 Price steps follow Betfair's tick sizes  \[Demo\]

Steps:
1. Place a waiting bet near 2.00 and press + or − repeatedly across 2.00 and across 3.00.

**Expected:** Steps are 0.01 below 2.00, 0.02 from 2.00 to 3.00 and 0.05 from 3.00 to 4.00. Only valid Betfair prices ever appear.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.8 Double-click mode  \[Either\]

Steps:
1. Settings → clicking → double click.
2. Single-click a price, then double-click one.

**Expected:** A single click places nothing; a double click places one bet.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 6.9 Toast tags make the side obvious  \[Either\]

Steps:
1. Place a back and a lay.

**Expected:** Each confirmation shows BACK in blue or LAY in pink.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 7. Waiting bets: cancel, move, edit, persistence

_Managing unmatched bets (the 'Unmatched bets' panel and the ladder)._

### 7.1 Cancel a waiting bet by clicking it on the ladder  \[Demo\]

Steps:
1. Click your own-bet chip.

**Expected:** The bet disappears from the ladder and from Unmatched bets.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.2 Drag a waiting bet to a new price  \[Demo\]

Steps:
1. Drag the chip to another price row.

**Expected:** The bet moves to the new price; with several bets at one price they all move.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.3 Unmatched panel lists every waiting bet  \[Demo\]

Steps:
1. Place two waiting bets on different runners.

**Expected:** Both appear with side, runner, placed time, price, stake, matched and at-the-off setting.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.4 ± tick buttons change the price  \[Demo\]

Steps:
1. Click + then − on a waiting bet.

**Expected:** The price moves one valid tick each time; the bet stays waiting.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.5 Edit the stake in place  \[Demo\]

Steps:
1. Change the stake in the panel and press Enter.

**Expected:** The waiting amount changes. Anything already matched is untouched.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.6 Cancel and Cancel all  \[Demo\]

Steps:
1. Cancel one bet, then press Cancel all.

**Expected:** One bet cancels; then all remaining waiting bets cancel.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.7 Cancel back / cancel lay hotkeys  \[Demo\]

Steps:
1. Hover a ladder with a waiting back and lay; press Z, then X.

**Expected:** Z cancels that runner's waiting backs; X cancels its waiting lays.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.8 At-the-off setting per bet and for all  \[Demo\]

Steps:
1. Choose Keep / Cancel / Take SP on a bet.
2. Use the 'At the off, all' buttons.

**Expected:** The selection changes immediately and is shown in the table.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.9 At the off: Cancel lapses the bet  \[Demo\]

Steps:
1. Set a waiting bet to Cancel.
2. Use Demo controls → Go in play.

**Expected:** The waiting bet is cancelled when the market goes in play.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.10 At the off: Keep leaves the bet on  \[Demo\]

Steps:
1. Set a waiting bet to Keep.
2. Go in play.

**Expected:** The bet stays waiting in play.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.11 At the off: Take SP removes the bet (practice does not simulate SP)  \[Demo\]

Steps:
1. Set Take SP and go in play.

**Expected:** The bet leaves the list. (Starting Price is not simulated in practice.)

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.12 Default 'at the off' setting  \[Either\]

Steps:
1. Settings → unmatched bets when the match starts: choose Cancel / Keep / Take SP; place a waiting bet.

**Expected:** The new bet starts with the chosen setting.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 7.13 Fill or kill  \[Demo\]

Steps:
1. Settings → fill or kill 10 seconds.
2. Place a waiting bet and wait.

**Expected:** After about 10 seconds the unmatched part is cancelled and the log says so.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 8. Positions and P&L

_What the screen says you have and what it is worth._

### 8.1 Position in words  \[Either\]

Steps:
1. Lay £10 on a runner.

**Expected:** The ladder shows a pink 'LAY £10.00 @ price' tag, then 'if <runner> wins -£x · if <runner> loses +£10.00'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.2 Back position wording  \[Either\]

Steps:
1. Back £10 on a runner.

**Expected:** A blue 'BACK £10.00 @ price' tag; profit if it wins, -£10 if it loses.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.3 The numbers are right for a lay  \[Either\]

Steps:
1. Lay £10 at 1.50.

**Expected:** If the runner wins you lose £5.00; if it loses you win £10.00.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.4 P&L column shows what hedging at each price would lock  \[Either\]

Steps:
1. With a position, read the left column.

**Expected:** For a lay it rises as the price rises; for a back it falls. Green is profit, red is loss.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.5 Clicking a P&L figure places the hedge  \[Either\]

Steps:
1. Click a figure in the P&L column.

**Expected:** The hedging bet is placed (side and stake shown in the tooltip), locking that figure.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.6 P&L basis: runner or market  \[Demo\]

Steps:
1. Toolbar chip 'P&L: runner' → market. Compare the column on a 3-runner market.

**Expected:** Runner mode shows this runner's lock; market mode shows the worst case across all runners after that hedge. On a 2-runner market they match.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.7 P&L column on the left or right  \[Either\]

Steps:
1. Settings → P&L column on the right.

**Expected:** The column moves to the right edge. Clicking behaves the same.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.8 Close a runner  \[Either\]

Steps:
1. Press Close on a ladder (or C).

**Expected:** The runner's position is closed with a hedging bet. The Close button is disabled with no position.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.9 Cancel a runner's orders from the ladder  \[Demo\]

Steps:
1. Press Cancel on a ladder with waiting bets.

**Expected:** All that runner's waiting bets cancel.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.10 Matched bets panel  \[Either\]

Steps:
1. Place several bets, back and lay.

**Expected:** Each appears newest first with time, side, runner, asked price, matched price, stake, 'Runner wins', 'Runner loses' and who placed it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 8.11 Header total P&L and exposure  \[Either\]

Steps:
1. Look at the top right with a position.

**Expected:** A P&L chip and the exposure update as positions change.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 9. Market block header and the big button

_The Geeks Toy-style market panel above the ladders._

### 9.1 Clock, status and book percentages  \[Either\]

Steps:
1. Look at a market block header.

**Expected:** Pre-match shows a countdown; in play shows 'In play'. Back and lay book percentages are shown either side of the button.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.2 Outcome boxes  \[Either\]

Steps:
1. With a position look at the two (or three) boxes.

**Expected:** One box per runner shows your profit or loss if that runner wins.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.3 The big button shows the market P&L  \[Either\]

Steps:
1. Hold a position and watch the button.

**Expected:** Green when the market is at or above £0.00, red below. It always shows the figure, including after it is pressed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.4 Hard close  \[Either\]

Steps:
1. Click the big button (or press G).

**Expected:** Waiting bets cancel, then the bets that level every outcome are placed. The button then shows the locked figure.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.5 Soft green keeping waiting bets  \[Demo\]

Steps:
1. Open the ▾ menu → green up, keep my unmatched bets.

**Expected:** The market is levelled but waiting bets stay.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.6 Partial hedge  \[Demo\]

Steps:
1. Menu → 50%.

**Expected:** About half of the hedge is placed; outcomes are closer but not level; waiting bets stay.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.7 Auto-green at a profit level  \[Demo\]

Steps:
1. Menu → enter a level above the current figure → Set.
2. Wait for the market to reach it.

**Expected:** A chip 'Auto-green at £x' shows. When the level is reached the market hard-closes. Click the chip to remove it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.8 Right-click the big button  \[Either\]

Steps:
1. Right-click it.

**Expected:** The same menu opens.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 9.9 Big button with no position  \[Either\]

Steps:
1. Look at the button with nothing matched.

**Expected:** It is greyed out; nothing happens when clicked.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 10. Stops and take-profit

_Triggers set from the ladder._

### 10.1 Right-click a price on a ladder with a position  \[Either\]

Steps:
1. Right-click a price below (or above) the market.

**Expected:** A menu offers 'Stop loss' or 'Take profit' at that price, showing what it would lock.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 10.2 A stop shows on the ladder  \[Either\]

Steps:
1. Set one.

**Expected:** An 'SL' or 'TP' marker appears at that price in your own-bets column.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 10.3 A trigger fires and greens up  \[Demo\]

Steps:
1. Set a take profit one or two ticks away and wait.

**Expected:** When the last price reaches it, the runner is greened up and the log says so.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 10.4 Remove a stop  \[Either\]

Steps:
1. Click its marker, or use the right-click menu 'Remove'.

**Expected:** The marker disappears and it never fires.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 10.5 A stop waits while the market is suspended  \[Demo\]

Steps:
1. Set a stop.
2. Suspend the market via Demo controls.

**Expected:** It does not fire while suspended; it resumes when the market reopens.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 11. Offset and stop on entry

_Bets that place their own closing bet and stop._

### 11.1 Offset places the closing bet  \[Demo\]

Steps:
1. Toolbar Offset 3.
2. Back £10 at the best back.

**Expected:** When it matches, a LAY for the equalising stake is placed 3 ticks away (shown waiting). The log says 'Offset: …'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.2 Stop is armed on entry  \[Demo\]

Steps:
1. Offset 3 and Stop 4.
2. Place a back.

**Expected:** A stop is armed 4 ticks against the entry price (an 'SL' marker). The log says 'Stop armed'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.3 Stop fires and cancels the offset bet  \[Demo\]

Steps:
1. Let the price move 4 ticks against you.

**Expected:** The position is closed and the waiting offset bet is cancelled.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.4 Offset matching removes the stop  \[Demo\]

Steps:
1. Let the price move 3 ticks in your favour.

**Expected:** The offset bet matches, the position is closed and the stop disappears.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.5 Offset applies to lays as well  \[Demo\]

Steps:
1. Offset 3; lay £10.

**Expected:** A BACK is placed 3 ticks above the lay price.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.6 Offset and stop from settings  \[Either\]

Steps:
1. Set the same values in Ladder settings.

**Expected:** The toolbar boxes show the same numbers (they are one setting).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 11.7 Zero means off  \[Either\]

Steps:
1. Set both to 0 and bet.

**Expected:** No extra orders are placed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 12. Market states

_Suspended, closed, removed runners and the start of play._

### 12.1 Suspended market blocks betting  \[Demo\]

Steps:
1. Demo controls → Suspend.

**Expected:** A banner says SUSPENDED; ladders dim; clicking places nothing; the status tag shows.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 12.2 Reopen resumes trading  \[Demo\]

Steps:
1. Demo controls → Reopen.

**Expected:** The banner clears and bets work again.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 12.3 Closed market  \[Demo\]

Steps:
1. Demo controls → Close.

**Expected:** MARKET CLOSED banner; no bets, no green-up.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 12.4 Hard close refuses on a suspended market  \[Demo\]

Steps:
1. Suspend, then press the big button.

**Expected:** A message explains the market is suspended; nothing is placed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 12.5 Going in play  \[Demo\]

Steps:
1. Pre-match → Go in play.

**Expected:** The header changes to 'In play'; waiting bets follow their at-the-off setting.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 12.6 Waiting bets do not match while suspended  \[Demo\]

Steps:
1. Place a waiting bet near the market, suspend, wait, reopen.

**Expected:** It does not fill during the suspension.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 13. Price chart

_The chart under each ladder._

### 13.1 Chart shows price and volume  \[Either\]

Steps:
1. Look under a ladder.

**Expected:** A line for the last price, a band between best back and lay, volume bars, and the last price tag.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.2 Time ranges  \[Either\]

Steps:
1. Click 5m, 15m, 1h, 3h.

**Expected:** The window changes; the 'shown' label updates.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.3 History backfills for markets the price logger has seen  \[Practice\]

Steps:
1. Open a market the logger already tracks.

**Expected:** The chart opens with earlier history (one point a minute), not empty.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.4 Drag the bar to resize  \[Either\]

Steps:
1. Drag the grip under the price rows down, then up.

**Expected:** Down adds price rows and shrinks the chart; up does the reverse.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.5 Each ladder resizes on its own  \[Either\]

Steps:
1. Drag the right-hand ladder's bar.

**Expected:** Only that ladder changes.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.6 The chart can be shrunk away completely  \[Either\]

Steps:
1. Drag the bar all the way down.

**Expected:** The chart disappears; only the grip remains. Drag back up to restore it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.7 No scrollbar inside a ladder  \[Either\]

Steps:
1. Resize the browser window taller and shorter.

**Expected:** The ladder always fits; it never shows its own scrollbar; chart and rows share the space.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.8 Rows setting  \[Either\]

Steps:
1. Settings → price rows 0 (auto), then 15.

**Expected:** 0 fits the window and leaves room for a chart; 15 fixes the count (capped to what fits).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 13.9 Chart on/off  \[Either\]

Steps:
1. Settings → show chart off.

**Expected:** The chart and its drag bar disappear from every ladder.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 14. Hotkeys

_Keyboard control._

### 14.1 Default keys  \[Either\]

Steps:
1. Hover a ladder and try S, Z, X, C, G, R, Enter, 1–8.

**Expected:** S stake box; Z cancel backs; X cancel lays; C close runner; G hard close market; R reverse; Enter recentre; 1–8 stake presets.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 14.2 Keys are ignored while typing in a box  \[Either\]

Steps:
1. Click a text box and type z, x, c.

**Expected:** No bets or cancels happen.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 14.3 Rebind a key  \[Either\]

Steps:
1. Settings → hotkeys → click 'Hard close' → press H.

**Expected:** The box shows H; pressing H now hard-closes; the help line under the toolbar shows H.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 14.4 Conflicting keys are refused  \[Either\]

Steps:
1. Try to give two actions the same key.

**Expected:** A message names the action already using that key; nothing changes.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 14.5 Reset to defaults restores keys  \[Either\]

Steps:
1. Settings → Reset to defaults.

**Expected:** Keys return to S, Z, X, C, G, R, Enter.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 15. Ladder settings and saved layouts

_Every option in the settings dialog._

### 15.1 Settings dialog opens and closes  \[Either\]

Steps:
1. Click Ladder settings; press Done; reopen; press Esc.

**Expected:** It opens, closes with Done and with Esc.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.2 Settings are remembered  \[Either\]

Steps:
1. Change a few settings and reload.

**Expected:** They are still set (stored in this browser).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.3 Recent volume windows  \[Either\]

Steps:
1. Set short 30s, long 10 minutes.

**Expected:** The recent volume column's tooltip and bars reflect the new windows.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.4 Weight of money levels  \[Either\]

Steps:
1. Change WoM levels to 1, then 5.

**Expected:** The WoM percentages change.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.5 Stake presets editable  \[Either\]

Steps:
1. Change the preset list.

**Expected:** The toolbar and per-ladder chips show the new presets; keys 1–8 follow.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.6 Reset to defaults  \[Either\]

Steps:
1. Press Reset to defaults and confirm.

**Expected:** Every setting returns to its default; the Cancel on the confirm leaves things alone.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.7 Save a layout  \[Either\]

Steps:
1. Name it 'Tennis scalping' and press Save current settings.

**Expected:** It appears in the saved list.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.8 Load a layout  \[Either\]

Steps:
1. Change settings, then press Load on the saved layout.

**Expected:** Settings return to what was saved.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.9 Delete a layout  \[Either\]

Steps:
1. Delete it and confirm.

**Expected:** It disappears.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 15.10 Layouts survive a reload  \[Either\]

Steps:
1. Reload.

**Expected:** Saved layouts are still listed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 16. Switch runner

_The ⇄ control in a ladder's header._

### 16.1 Swap two ladders  \[Either\]

Steps:
1. On the left ladder pick the other runner from ⇄.

**Expected:** The two ladders trade places; both recentre.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 16.2 Orders and positions follow the runner  \[Either\]

Steps:
1. Place a bet, then switch.

**Expected:** The bet and position stay with their runner, not their screen position.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 17. Info panels

_The tabbed panel at the bottom: P&L all runners, Market info, Runner info, Traded & available, Log._

### 17.1 P&L of all runners  \[Either\]

Steps:
1. Open the tab with a position.

**Expected:** Each runner shows the profit if it wins, your position, and a market line (worst case or green-up level).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 17.2 Market info  \[Either\]

Steps:
1. Hover a ladder and open the tab.

**Expected:** Event, market, competition, start time, status, runners, matched in market, back and lay book.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 17.3 Runner info follows the hovered ladder  \[Either\]

Steps:
1. Hover each ladder in turn.

**Expected:** Runner, last price, best back and lay, spread in ticks, matched and share, weight of money, your position.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 17.4 Traded & available  \[Either\]

Steps:
1. Open the tab.

**Expected:** A price table with available to back, available to lay and traded at each price.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 17.5 Log  \[Either\]

Steps:
1. Place a bet, then open the Log tab.

**Expected:** The order appears with its time. Stops, offsets, greens and restarts are logged too.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 17.6 Panels collapse  \[Either\]

Steps:
1. Click ▾ on each panel.

**Expected:** Each folds to its header and reopens.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 18. Dutching

_Spread a total over several runners._

### 18.1 Back dutch gives equal outcomes  \[Demo\]

Steps:
1. Dutching tab → tick both runners → total 100.

**Expected:** Stakes are shown and 'If it wins' is the same (within a few pence) for each runner. Total stake is £100.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.2 Custom price per runner  \[Demo\]

Steps:
1. Type a price in a runner's price box.

**Expected:** The preview uses that price (not the market's).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.3 Lay dutch  \[Demo\]

Steps:
1. Switch to Lay.

**Expected:** Stakes are laid; outcomes are equal for the chosen runners.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.4 Three-runner dutch  \[Demo\]

Steps:
1. Football: tick two of three.

**Expected:** The third runner shows the loss of the whole stake (or gain for lay).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.5 Needs two runners and £1  \[Either\]

Steps:
1. Tick one runner; or enter 0.50.

**Expected:** No preview and the Place button is disabled (or a clear message).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.6 Stakes under £1 are left out  \[Demo\]

Steps:
1. Choose a long-odds runner with a small total.

**Expected:** The preview says how many bets are under £1 and left out.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.7 Place asks for confirmation and places all legs  \[Demo\]

Steps:
1. Press Place.

**Expected:** A confirm lists every leg; after OK each leg appears in Matched bets (or Unmatched bets if waiting) and the toast says N of N placed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 18.8 Book percentage shown  \[Demo\]

Steps:
1. Look under the table.

**Expected:** The book % for the chosen prices is shown.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 19. Bookmaking

_Choose the profit you want on every outcome._

### 19.1 Even (green-up) quick fill  \[Demo\]

Steps:
1. With a position, Bookmaking tab → Even.

**Expected:** Every target fills with the green-up level; the preview shows the bets that level the market.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 19.2 Custom targets  \[Demo\]

Steps:
1. Enter +£10 on A and +£5 on B.

**Expected:** The preview shows the bets to place and 'After' equals your targets (within pence).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 19.3 Current / Clear  \[Demo\]

Steps:
1. Press Current, then Clear.

**Expected:** Current copies today's outcomes (no bets needed); Clear empties the targets.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 19.4 Targets needed for every runner  \[Either\]

Steps:
1. Fill only one target.

**Expected:** A prompt says to enter a target for every runner; Place is disabled.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 19.5 Place and verify  \[Demo\]

Steps:
1. Place the plan, then open P&L all runners.

**Expected:** The outcomes shown match your targets.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 19.6 Unreachable targets are explained  \[Demo\]

Steps:
1. Try targets far above what the book can give.

**Expected:** Either large stakes are shown clearly in the preview (you decide) or a clear message explains it; nothing is placed without confirmation.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 20. Restart safety

_Nothing held in memory may be lost on a restart or deploy._

### 20.1 Stops, offsets and auto-greens survive a restart  \[Practice\]

Steps:
1. Set a stop and an auto-green.
2. Ask for the service to be restarted.
3. Reload the app.

**Expected:** The stop and auto-green are still there; the log says 'Restarted: restored …'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 20.2 Practice orders and positions survive a restart  \[Practice\]

Steps:
1. Place a bet and leave a waiting bet; restart; reload.

**Expected:** The position, matched bets and waiting bet are all still present.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 20.3 A deploy does not interrupt trading  \[Practice\]

Steps:
1. Push a harmless change while holding stops or waiting bets.

**Expected:** The deploy is held until nothing is waiting (or completes with everything restored).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 20.4 A corrupt state file starts clean and says so  \[Practice\]

Steps:
1. (Admin) damage the state file and restart.

**Expected:** The app starts empty, the log says it could not restore, and nothing crashes.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 21. Safety, errors and limits

_How the app behaves when things go wrong._

### 21.1 Never live  \[Either\]

Steps:
1. Look for any way to place a real bet.

**Expected:** None exists: practice mode only simulates orders and live mode is not built.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 21.2 Exchange or network error is readable  \[Practice\]

Steps:
1. Disconnect the network briefly while using the app.

**Expected:** A readable message appears; the app recovers when the network returns.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 21.3 Guardrail warnings are shown  \[Either\]

Steps:
1. Place very large or rapid bets.

**Expected:** Any guardrail warning appears in a message instead of failing silently.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 21.4 Rejected orders say why  \[Demo\]

Steps:
1. Try to bet on a suspended market.

**Expected:** The reason is shown ('the market is suspended').

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 21.5 Esc closes dialogs and menus  \[Either\]

Steps:
1. Open the confirm card, the settings and a menu; press Esc.

**Expected:** Each closes.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 22. Layout and performance

_The app in different situations._

### 22.1 Four ladders at once  \[Demo\]

Steps:
1. Open both tennis matches (two ladders each).

**Expected:** Four ladders fit on screen and all stay readable.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 22.2 Window sizes  \[Either\]

Steps:
1. Try a laptop width and a wide monitor.

**Expected:** Nothing overlaps; the panels reflow; ladders stay usable.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 22.3 Browsers  \[Either\]

Steps:
1. Repeat a short run in Chrome and in Safari/Edge.

**Expected:** Same behaviour, including drag and drop.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 22.4 Stays responsive over time  \[Practice\]

Steps:
1. Leave two markets open for 30 minutes.

**Expected:** Prices keep updating, no slow-down, no growing memory use in the tab.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 22.5 Hover tooltips  \[Either\]

Steps:
1. Hover buttons, cells and chips.

**Expected:** Tooltips explain each control.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 23. Ladder size and scrolling (added 4 Nov)

_How many ticks you see, and how the mouse wheel behaves._

### 23.1 Default is about 25 ticks  \[Either\]

Steps:
1. Open Ladder settings and note 'Ticks in view'.
2. Open a market with the chart open on a normal laptop or monitor window.

**Expected:** The setting reads 25. Ladders show up to 25 price rows (fewer only if the window is too small), rows are compressed neatly, text stays readable.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.2 Change ticks in view  \[Either\]

Steps:
1. Set Ticks in view to 15, then 35, then 0.

**Expected:** 15: bigger rows and a bigger chart. 35: smaller rows, chart squeezed or hidden, no scrollbar on the ladder. 0: as many normal-size rows as fit.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.3 Chart gives way to rows  \[Either\]

Steps:
1. Set 40 ticks with the chart open.

**Expected:** The chart shrinks (then disappears) before the rows get unreadable. Prices stay clickable.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.4 Drag bar still works  \[Either\]

Steps:
1. Drag the bar under a ladder up and down.

**Expected:** Rows are added or removed and the chart resizes. Dragging one ladder does not move another.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.5 Wheel over price rows moves only the ladder  \[Either\]

Steps:
1. Put the cursor over the price rows of each ladder in turn (left, middle, right on a football match).
2. Scroll the mouse wheel.

**Expected:** The prices move. The page does not scroll. Same for every ladder.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.6 Wheel elsewhere scrolls the page  \[Either\]

Steps:
1. Put the cursor on the chart, the market header or the panels and scroll.

**Expected:** The page scrolls normally to reach the panels below the ladders.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 23.7 Reverse ladders and wheel direction  \[Either\]

Steps:
1. Turn Reverse on and scroll over a ladder.

**Expected:** Prices still move in the direction you scroll (consistent with the reversed layout).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 24. Market list: search, filters, grouping (added 4 Nov)

_The left-hand list of markets._

### 24.1 Free-text search  \[Either\]

Steps:
1. Type part of a player, team, competition or market name in the search box.

**Expected:** The list filters as you type. A search with no match says so and tells you how to clear it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 24.2 Search matches both names in an event  \[Either\]

Steps:
1. Search for one team, then for the other team in the same match.

**Expected:** The same match appears for either name.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 24.3 In-play, Next hour and Mine filters  \[Either\]

Steps:
1. Turn each filter on in turn, then combine them.

**Expected:** In-play shows live events only. Next hour shows events starting within an hour. Mine shows markets you have open. Combined filters narrow further.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 24.4 Competition grouping and folding  \[Either\]

Steps:
1. Click a competition heading to fold it, again to unfold.

**Expected:** Headings show a count. Folding hides that competition's matches.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 24.5 Sort by start or name  \[Either\]

Steps:
1. Toggle the sort chip.

**Expected:** The order changes between start time and name.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 24.6 Open markets are marked  \[Either\]

Steps:
1. Open a market.

**Expected:** Its row gets a coloured edge in the list.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 25. Open-market tabs (added 4 Nov)

_More markets open than fit on screen._

### 25.1 Tabs appear with two or more markets open  \[Demo\]

Steps:
1. Open both tennis matches, then a football match.

**Expected:** A tab bar appears above the ladders with one tab per open market.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 25.2 Two matches stay on screen; the rest wait behind tabs  \[Demo\]

Steps:
1. Open three tennis or football markets in a row.

**Expected:** The market shown longest steps back to its tab so the new one fits. Nothing is closed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 25.3 Click a tab to bring a market on screen  \[Demo\]

Steps:
1. Click a tab that is not shown.

**Expected:** Its ladders appear; the oldest shown market goes back to its tab.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 25.4 Tab shows position, orders and state  \[Demo\]

Steps:
1. Place a bet and leave an unmatched bet in a market, then switch to another tab.
2. Use the demo controls to suspend a market.

**Expected:** The tab of the market with a position shows its worst-case P&L (green/red). Unmatched bets show a count badge. A suspended market's tab is outlined.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 25.5 Hidden markets stay live  \[Demo\]

Steps:
1. With a market hidden behind a tab, place a bet or let a stop trigger on it.

**Expected:** It still matches, triggers and counts in Orders, Matched bets and exposure.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 25.6 Close from a tab  \[Demo\]

Steps:
1. Click the x on a tab.

**Expected:** A warning if you hold a position or unmatched bets; otherwise the market closes and the tab disappears.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 26. All markets on an event (added 4 Nov)

_Half time, goal lines, correct score and the rest, from the + button in the market list._

### 26.1 Expand an event  \[Either\]

Steps:
1. In the football list, click the + beside an event.

**Expected:** The event's other markets appear, grouped (Result, Match goals, Team goals, Score, Corners, Cards, Other). Clicking again collapses them.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.2 Open a goal line market  \[Either\]

Steps:
1. Expand an event and open Over/Under 2.5 Goals.

**Expected:** Two ladders (Under and Over) open. The tab and header name the market.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.3 Match goals are separate from team goals  \[Practice\]

Steps:
1. Expand an event and compare 'Over/Under 2.5 Goals' with '<Team> Over/Under 2.5 Goals'.

**Expected:** The match line is under Match goals; each team's own goals lines are under Team goals. Lines are in order (0.5, 1.5, 2.5 ...).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.4 Half-time and first-half markets  \[Practice\]

Steps:
1. Open Half Time and First Half Goals markets.

**Expected:** Ladders open with the right runners and update.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.5 Runner picker for big markets  \[Either\]

Steps:
1. Open Correct Score.

**Expected:** A picker lists every runner. You can choose up to 4; the rest are disabled once four are chosen.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.6 Swap a ladder to another runner  \[Either\]

Steps:
1. In a correct score market, use the selector at the top of a ladder to switch runner.

**Expected:** The ladder shows the chosen runner. Positions are kept per runner.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.7 Several markets of one match together  \[Either\]

Steps:
1. Open Match Odds, Over/Under 2.5 and Half Time of the same match.

**Expected:** All are open as tabs; you can bring any on screen. The live score line shows on each.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.8 Market-level P&L and green-up on a goals market  \[Demo\]

Steps:
1. Place back and lay bets in an Over/Under market.
2. Use Green up from the market header.

**Expected:** P&L if each runner wins is correct and green-up locks an equal profit.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 26.9 Tennis event markets  \[Practice\]

Steps:
1. Expand a tennis event with +.

**Expected:** Set betting, total games and similar markets are listed and open correctly.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 27. Live score and match line (added 4 Nov)

_Score, clock and serve under the market name. Needs the data collectors, so Practice mode only._

### 27.1 Tennis scoreboard  \[Practice\]

Steps:
1. Open a live ATP, WTA or Challenger match.

**Expected:** A scoreboard shows a row per player: set scores, current game score and a dot by the server. It updates within about 5 seconds of a point.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 27.2 Players in the same order as the ladders  \[Practice\]

Steps:
1. Compare the scoreboard rows with the two ladders' runner names.

**Expected:** The first row is the first Betfair runner, not whichever player the data feed lists first.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 27.3 Football clock and score  \[Practice\]

Steps:
1. Open a live match in a covered league (England, Scotland, Germany, Spain, Italy, France).

**Expected:** The match minute and score show and update. Before kick-off it shows the status instead.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 27.4 Other markets of the same match  \[Practice\]

Steps:
1. Open Over/Under or Correct Score for a live match.

**Expected:** The same score line appears.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 27.5 No match found means no line  \[Practice\]

Steps:
1. Open a market from a competition we do not collect (for example a lower league or ITF).

**Expected:** No score line is shown and nothing is guessed. No error.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 27.6 Doubles and name oddities  \[Practice\]

Steps:
1. Open a doubles market, and a match with a hyphenated or accented name.

**Expected:** Doubles show no line. Unusual names either match correctly or show nothing. Report any wrong match.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 28. Data collection health (added 4 Nov)

_Checks on the server's football and tennis data collection. These use the status addresses until the Data screen exists._

### 28.1 Football status  \[Practice\]

Steps:
1. Call /api/football/status (with the token).

**Expected:** Fixtures in the thousands, with_details rising day by day, last_error null (a rate-limit message that clears itself is fine).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 28.2 Tennis status  \[Practice\]

Steps:
1. Call /api/tennis/status.

**Expected:** matches in the thousands, history_days_done rising to 730, live_now counts live matches, last_error null.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 28.3 Live matches are logged  \[Practice\]

Steps:
1. During a live match check live_snapshots in either status.

**Expected:** The count rises as scores change.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 28.4 App survives a collector failure  \[Practice\]

Steps:
1. After any deploy check the app starts and ladders load.

**Expected:** The app is up even if a collector reports an error.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 29. Access and deploys (added 4 Nov)

_Reaching the server and getting changes onto it._

### 29.1 HTTPS address  \[Practice\]

Steps:
1. Open https://159-65-20-243.sslip.io/ from a tablet or phone.

**Expected:** The app loads over HTTPS with a valid certificate and asks for the token.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 29.2 Token works and wrong token is refused  \[Practice\]

Steps:
1. Enter the current token, then try a wrong one in a private window.

**Expected:** Right token: app loads. Wrong: refused.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 29.3 Push deploys itself  \[Practice\]

Steps:
1. After a change is pushed, wait 3 minutes and reload with Ctrl+F5.

**Expected:** The change is live. The GitHub Actions run is green.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 29.4 Restart keeps your state  \[Practice\]

Steps:
1. Leave an unmatched bet and a stop in place, then trigger a deploy that restarts the app.

**Expected:** After it comes back your unmatched bets, stops and matched bets are still shown.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 30. Safety, limits and Stop all automation (added 5 Nov)

_The strip under the header and Settings > Safety and limits. Everything here is practice money._

### 30.1 Status strip shows Today and Automation  \[Either\]

Steps:
1. Look at the strip under the navbar.

**Expected:** Today's profit/loss, the Automation on/off button and any limit warnings are visible on every screen.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.2 Stop all automation  \[Either\]

Steps:
1. Click Automation, then Stop all automation.
2. Read the dialog and confirm.

**Expected:** Dialog explains what stops (scripts, AI, plan entries) and what does not (your manual trading, existing stops). After confirming the strip shows Automation OFF and scripts fire nothing.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.3 Resume automation  \[Either\]

Steps:
1. Open Alerts or the strip and resume.

**Expected:** Automation shows ON again and scripts can fire.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.4 Default loss limit is not set  \[Either\]

Steps:
1. Open Settings > Safety and limits on a fresh install.

**Expected:** Daily and weekly loss limits show 0 / not set. Nothing is blocked.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.5 Daily loss limit stops automation, not manual trading  \[Demo\]

Steps:
1. Set a small daily loss limit (e.g. 5).
2. Lose more than that with an enabled script or by trading manually.
3. Try a manual bet, then wait for a script to try to enter.

**Expected:** Manual losses count towards the limit but manual bets are never blocked. Script entries are refused with a clear reason and an alert is raised. Exit orders (:exit) from scripts still work.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.6 Open liability limit  \[Demo\]

Steps:
1. Set a low open liability limit.
2. Let a script try to enter a large stake.

**Expected:** The entry is refused and says why. Tick 'include manual' to count manual positions too.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.7 Lay stakes default to stake basis  \[Either\]

Steps:
1. Place a lay bet from the ladder.

**Expected:** The amount typed is the stake, not the liability, unless you changed the setting.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.8 Settings survive a restart  \[Practice\]

Steps:
1. Change a limit.
2. Wait for a deploy or restart.

**Expected:** The setting is unchanged afterwards.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 30.9 Full AI mode is locked  \[Either\]

Steps:
1. Try to select Full AI in the AI mode setting.

**Expected:** It is refused with 'not available yet'. Advisor stays available.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 31. Scripts (added 5 Nov)

_Rules that enter and exit trades for you. Written as JSON; Claude can draft them._

### 31.1 Create a script from a template  \[Either\]

Steps:
1. Open Scripts, click New, pick a template.

**Expected:** A script appears in the library with its entry, exit and safety rules shown as readable cards.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.2 Validation catches mistakes  \[Either\]

Steps:
1. Edit the JSON so a rule uses an unknown condition or a stake of 0.
2. Save.

**Expected:** Save is refused with a specific message pointing at the problem.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.3 Import a script  \[Either\]

Steps:
1. Paste valid script JSON into Import.

**Expected:** It appears in the library, disabled.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.4 Enable, disable and clone  \[Either\]

Steps:
1. Enable a script, disable it, then clone it.

**Expected:** State changes immediately; the clone is a separate disabled script.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.5 Version history  \[Either\]

Steps:
1. Edit and save a script twice.
2. Open History.

**Expected:** Each save is a version with a timestamp. You can view earlier versions.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.6 Build a script with the Copilot  \[Practice\]

Steps:
1. Open the Copilot panel on the right of Scripts (it opens in Build a script mode) and describe a strategy in plain English.

**Expected:** A draft script is returned, validated, and can be saved. Invalid drafts are not saved.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.7 Add to Plan  \[Either\]

Steps:
1. From a script, click Add to Plan and pick a market and runner.

**Expected:** A Plan row is created binding the script to that market and runner.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.8 Script fires on a live demo market  \[Demo\]

Steps:
1. Enable a simple price-based entry script, add it to the Plan on a demo market, let the price cross the condition.

**Expected:** An order is placed with source script:<name>, appears on the ladder and in the activity log, and the exit rule closes it as defined.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 31.9 Discuss with Claude  \[Practice\]

Steps:
1. Click Discuss with Claude on a script.

**Expected:** The copilot opens with the script as context.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 32. Plan (added 5 Nov)

_Which scripts are armed on which markets._

### 32.1 Plan lists rows with status  \[Either\]

Steps:
1. Open Plan.

**Expected:** Each row shows market, runner, script, status (waiting, in position, done, stopped) and bets taken.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 32.2 Edit and remove a row  \[Either\]

Steps:
1. Change a row's stake or remove it.

**Expected:** Change is saved; removed rows stop acting immediately.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 32.3 Row bets view  \[Either\]

Steps:
1. Open a row's bets.

**Expected:** Orders placed by that row with price, size and result.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 32.4 Attach from the market list  \[Either\]

Steps:
1. Click the plan button next to a market in the list.
2. Choose a script.

**Expected:** The attach dialog adds a Plan row.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 33. Recommendations (added 5 Nov)

_Model vs market edges. Practice only; shown for your judgement._

### 33.1 Recommendations appear for real pre-match markets  \[Practice\]

Steps:
1. Open Recommendations after a few minutes of Practice running.

**Expected:** Cards list the pick, model price vs market price, edge, reasoning and the current price. Confidence is never High. There may be none if no edge is found.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 33.2 Apply a recommendation  \[Practice\]

Steps:
1. Click Apply on a card.

**Expected:** A Plan row or order is created for the chosen script; the card moves to Applied.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 33.3 Dismiss a recommendation  \[Practice\]

Steps:
1. Click Dismiss.

**Expected:** The card is removed from pending and does not return for that market.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 33.4 Scan now  \[Practice\]

Steps:
1. Click Scan.

**Expected:** A fresh scan runs; the list updates.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 33.5 Auto-apply is locked  \[Practice\]

Steps:
1. Look for the auto-apply option.

**Expected:** It is locked with the message that it needs 300 recommendations with positive CLV.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 34. Alerts and health (added 5 Nov)

_What the system tells you, and the Health badge._

### 34.1 Alerts list and mark read  \[Either\]

Steps:
1. Open Alerts.
2. Mark one read.

**Expected:** Unread count in the navbar drops. Duplicate alerts are not repeated.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 34.2 Health badge  \[Practice\]

Steps:
1. Click the Health badge.

**Expected:** A panel lists Betfair, tennis feed, football feed, price log and Claude with a dot colour and plain-English detail.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 34.3 Feed outage raises an alert  \[Practice\]

Steps:
1. (If practical) temporarily break a feed key on the server.

**Expected:** Within about 2 minutes the Health badge turns amber/red and an alert is raised.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 35. Home (added 5 Nov)

_The first screen._

### 35.1 Home shows the day at a glance  \[Either\]

Steps:
1. Open Home.

**Expected:** Today and week P&L, automation state, open positions, pending recommendations, recent alerts and upcoming markets are visible.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 35.2 Home cards link through  \[Either\]

Steps:
1. Click each card.

**Expected:** Each goes to the right screen (Recommendations, Plan, Alerts, Manual Trading).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 36. Analyse and Backtesting (added 5 Nov)

_Performance, strategies, models and replay tests._

### 36.1 Performance tab  \[Either\]

Steps:
1. Open Analyse > Performance.

**Expected:** Today, this week, month and last 7 days with profit, ROI and win rate, plus a chart. With no settled trades it shows empty states, not errors.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 36.2 Strategies tab attribution  \[Either\]

Steps:
1. Open Strategies after some script and manual trades have settled.

**Expected:** Profit is split by script and by manual, with staked amount and ROI.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 36.3 Models tab  \[Either\]

Steps:
1. Open Models.

**Expected:** A table of offline model results (tennis v1, v2, Elo, v3 and football 1X2) against the market, with the note that models are trading guidance, not winner-picking.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 36.4 AI learning tab  \[Practice\]

Steps:
1. Open AI learning.

**Expected:** Shows recommendation count, CLV evidence so far and the gate to auto-apply.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 36.5 Run a backtest  \[Practice\]

Steps:
1. Open Backtesting, choose a strategy, target and date range, run.

**Expected:** Result shows trades, profit, ROI, win rate with a train/out-of-sample split. If there are not enough recorded results it says so plainly.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 36.6 Backtest data grows  \[Practice\]

Steps:
1. Check the price log result counts over a few days.

**Expected:** Markets with recorded winners increase, making more backtests possible.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 37. Settings (added 5 Nov)

_One place for configuration._

### 37.1 Settings sections  \[Either\]

Steps:
1. Open Settings and visit each section.

**Expected:** Safety and limits, Connections and feeds, Credentials, Trading defaults, AI and costs, Alerts, Versions and models, Appearance all load.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 37.2 Credentials show presence only  \[Practice\]

Steps:
1. Open Settings > Credentials.

**Expected:** Each key shows Set or Not set. No key value is ever displayed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 37.3 Connections and data counts  \[Practice\]

Steps:
1. Open Connections and feeds.

**Expected:** Health items plus counts of football and tennis matches and price log markets/ticks.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 37.4 Theme switch  \[Either\]

Steps:
1. Open Appearance and switch theme.

**Expected:** The whole app changes between dark and light and remembers it.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 37.5 Alerts channels  \[Either\]

Steps:
1. Open Alerts section.

**Expected:** Browser is on; email and push are shown as not set up yet.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 38. Real orders safety (added 5 Nov)

_Real order placing exists in code but is switched off._

### 38.1 Mode badge never reads LIVE  \[Practice\]

Steps:
1. Look at the header badge and Health.

**Expected:** It reads PRACTICE MODE. Orders are simulated and nothing is sent to Betfair.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 38.2 Live mode does not start  \[Practice\]

Steps:
1. (Server) confirm AUTOBETS_MODE is practice.

**Expected:** Setting live is refused at start-up with an explanation. Real orders are only enabled later with your live key.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 39. Market list on Home and Plan, bulk add, AI panel (added 5 Nov)

_The same market list as the ladder screen, now on Home and Plan._

### 39.1 Market list on Home and Plan  \[Either\]

Steps:
1. Open Home, then Plan.

**Expected:** The market list (Tennis / Football tabs, search, In-play, Next hour, sort) is on the left of both. Home also has the Copilot panel docked on the right.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.2 All markets on an event  \[Practice\]

Steps:
1. On Football, click 'All markets on this event' under a match.

**Expected:** Half time, goal lines, correct score and other markets appear grouped, each with a tick box (not only Match Odds).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.3 Tick and bulk add, watch only  \[Either\]

Steps:
1. Tick three markets.
2. Click Add 3 to Plan.
3. Leave script as None and confirm.

**Expected:** A message says 3 markets were added. They show on the Plan as Watching and as 'in Plan' in the list. The tick boxes clear.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.4 Select a whole competition / select all shown  \[Either\]

Steps:
1. Tick a competition heading, then try Select all shown after a search.

**Expected:** Every market under that heading (or every market shown after the search) is ticked; the counter matches.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.5 Selection survives tab and search changes  \[Either\]

Steps:
1. Tick a tennis market, switch to Football, tick one, search, then switch back.

**Expected:** The selected count still includes both.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.6 Bulk add with a script  \[Either\]

Steps:
1. Tick several markets.
2. Add to Plan, choose a script and the rule Favourite, set a stake.

**Expected:** Each market gets a Plan row with the favourite (shortest back price) as its runner. Markets where the rule cannot apply (e.g. Draw on tennis) are skipped and listed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.7 Open a ladder from the list  \[Either\]

Steps:
1. Click the ladder icon on a market row on Home or Plan.

**Expected:** Manual Trading opens with that market's ladders.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.8 Scripts > Add to Plan uses the same list  \[Either\]

Steps:
1. On Scripts, click Add to Plan.

**Expected:** The picker shows the full list including all-markets-on-event; choosing a market then asks which runner.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.9 Home AI panel  \[Practice\]

Steps:
1. Ask the docked Copilot about your Plan markets.

**Expected:** It answers about the markets in your Plan and any open ladders. It cannot place bets in Advisor mode.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 39.10 Narrow screens  \[Either\]

Steps:
1. Open Home on a phone or narrow window.

**Expected:** A 'Market list' button reveals the list above the screen; the AI panel is available from the Copilot button in the header.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 40. Script chooser and Copilot script builder (added 5 Nov)

_Scales as the number of scripts grows; scripts can be created from the Copilot beside Plan and Home._

### 40.1 Copilot is on Plan as well as Home  \[Either\]

Steps:
1. Open Plan on a wide screen.

**Expected:** The Copilot panel is docked on the right of both Home and Plan.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.2 Build a script from the Copilot  \[Practice\]

Steps:
1. Click Build a script in the Copilot.
2. Describe a strategy in plain English and send.

**Expected:** A draft appears with Entry / Exit / Safety rule cards. An invalid draft shows a clear error and cannot be saved.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.3 Refine a draft  \[Practice\]

Steps:
1. With an unsaved draft showing, type a change (e.g. 'make the stake 5 and add a 10 pound stop').

**Expected:** A full updated draft replaces it, keeping the earlier rules unless you changed them.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.4 Save the draft and use it straight away  \[Practice\]

Steps:
1. Click Save as draft script.
2. Tick a market in the list, Add to Plan, open the script chooser.

**Expected:** The new script is in the chooser (off, tagged AI draft) without reloading the page.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.5 Chooser search  \[Either\]

Steps:
1. Open the script chooser and type part of a name or description.

**Expected:** The list narrows as you type; with no match it says so.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.6 Chooser sport filter  \[Either\]

Steps:
1. Choose Tennis, then Football.

**Expected:** Only scripts for that sport (plus 'Any sport' scripts) are shown.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.7 Recently used and On/Off sections  \[Either\]

Steps:
1. Add a script to the Plan, then reopen the chooser.

**Expected:** It appears under Recently used at the top; the rest are grouped On then Off.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.8 Chooser in all three places  \[Either\]

Steps:
1. Check Add to Plan from the list, the market ▤ button on Manual Trading, and Edit on a Plan row.

**Expected:** Each uses the same searchable chooser.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 40.9 Scripts library filters  \[Either\]

Steps:
1. On Scripts use the All / On / Off / AI drafts / Tennis / Football chips and the search box.

**Expected:** The library narrows and its heading shows 'N of M'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 41. Scalping scripts: ticks from entry and repeat (added 5 Nov)

_Scripts can now exit relative to where they were matched, and re-arm._

### 41.1 Scalp example loads and saves  \[Either\]

Steps:
1. On Scripts click Scalp example, then Save.

**Expected:** The script saves; its cards read: back at best price, exit green when 2 ticks in profit from where you were matched, repeat up to 10 times, safety at 6 ticks against.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 41.2 Copilot builds a scalp  \[Practice\]

Steps:
1. Ask the Copilot (Build a script): football Under 2.5 goals scalper, back £10 at best price, green 2 ticks in profit, repeat 10 times.

**Expected:** A valid draft with repeat 10 and a ticks-from-entry exit is returned.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 41.3 One at a time  \[Demo\]

Steps:
1. Add the scalp to an Over/Under 2.5 market on the Under runner and enable it.

**Expected:** Only one entry order exists until its green-up has matched; the Plan row shows 'Run 1 of 10'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 41.4 Exit 2 ticks from where you were matched  \[Practice\]

Steps:
1. Watch a run where the Lay price drops 2 ticks below your matched price.

**Expected:** The script greens (not before) and logs the profit.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 41.5 Re-arm and stop after the last run  \[Practice\]

Steps:
1. Let several runs complete.

**Expected:** The run counter advances after each green-up and the row ends Done after run 10.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 41.6 Stop at 6 ticks against  \[Practice\]

Steps:
1. If the price moves 6 ticks against the entry.

**Expected:** The position is closed, the script stops and does not re-arm.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 42. Compact scripts: headlines and expandable rules (added 5 Nov)

_Plan, Scripts and Copilot show one headline per script; the full rules expand on demand._

### 42.1 Plan rows show a headline  \[Either\]

Steps:
1. Open Plan with a script attached to a market.

**Expected:** Each row shows the strategy name and a one-line headline (e.g. 'Back £10 at best · exit: green · 1 safety rule · ×10') on one line, with Edit and Remove still visible.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 42.2 Expand a row's rules  \[Either\]

Steps:
1. Click the arrow at the start of a Plan row.

**Expected:** The entry trigger and the Entry / Exit / Safety rules open under the row; clicking again collapses them.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 42.3 Expand all / collapse all  \[Either\]

Steps:
1. Click the arrow in the Plan table header.

**Expected:** All rows with a script expand or collapse together.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 42.4 Scripts library headlines  \[Either\]

Steps:
1. Open Scripts.

**Expected:** Each library entry shows its name, a one-line headline, sport, version and origin, so more scripts fit on screen.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 42.5 Copilot drafts are folded  \[Practice\]

Steps:
1. Ask the Copilot to build a script.

**Expected:** The draft shows a one-line headline you can open to read every rule.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 43. New script conditions (added 6 Nov)

_More ways to say when a script acts. Build them with the Copilot or in the JSON editor._

### 43.1 Trailing stop  \[Demo\]

Steps:
1. Ask the Copilot for a script that backs, then closes and stops if the exit price gives back 3 ticks from its best.

**Expected:** The draft uses ticks_from_peak and reads 'given back 3 ticks from its best since you were matched'. In use, the stop only fires after the price has gone your way and then retreated.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 43.2 Time to kick-off  \[Practice\]

Steps:
1. Create a script that enters only when minutes to the scheduled start is 30 or less.

**Expected:** It does not enter earlier than 30 minutes before the start.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 43.3 Spread filter  \[Practice\]

Steps:
1. Create an entry that needs a spread of 2 ticks or less.

**Expected:** It does not enter on a wide book and does when the book tightens.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 43.4 Market matched  \[Practice\]

Steps:
1. Create an entry that needs at least 50,000 matched on the market.

**Expected:** It waits for a liquid market.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 43.5 Price move over time  \[Practice\]

Steps:
1. Create an entry for a price shortening 3 ticks or more in 60 seconds.

**Expected:** It only acts after the price has been watched for a minute (no action immediately after a restart) and fires on a genuine move.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 43.6 Invalid values are refused  \[Either\]

Steps:
1. Save a script with a price move of 1 second or a negative spread.

**Expected:** The save is refused with a message saying what is wrong.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 44. Live trading safeguards (added 6 Nov)

_Built and mock-tested only. Test for real once on the live key, starting with the smallest stakes._

### 44.1 Live mode needs a deliberate server setting  \[Live\]

Steps:
1. Start the service with AUTOBETS_MODE=live but without AUTOBETS_LIVE_CONFIRM.

**Expected:** The service refuses to start and says why.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.2 Starts not armed  \[Live\]

Steps:
1. Start in live mode and open Settings > Live trading.

**Expected:** The header shows LIVE — REAL MONEY and NOT ARMED. Trying to place a bet is refused with 'live trading is not armed'.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.3 Arming needs the phrase  \[Live\]

Steps:
1. Type something other than SEND-REAL-ORDERS, then the exact phrase.

**Expected:** The Arm button stays disabled until the exact phrase is typed. The header then shows ARMED.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.4 Disarm still lets you cancel  \[Live\]

Steps:
1. Place a small order, disarm, then cancel it.

**Expected:** New orders are refused after disarming; the cancel works.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.5 Orders match Betfair  \[Live\]

Steps:
1. Place a £1 bet from the ladder and check the Betfair website.

**Expected:** The same bet appears on Betfair with the same price and size; fills show in AutoBets within a couple of seconds.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.6 Start-up check  \[Live\]

Steps:
1. Place an order on the Betfair website, then restart the service.

**Expected:** An alert says an order Betfair holds was not in AutoBets; it appears as an external order.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.7 Stop all automation cancels real unmatched orders  \[Live\]

Steps:
1. Let a script rest an unmatched order, then Stop all automation.

**Expected:** The order is cancelled on Betfair.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.8 Result check against Betfair  \[Live\]

Steps:
1. Let a small market settle.

**Expected:** No warning if AutoBets' result matches what Betfair cleared; a warning if they differ by more than 10p.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 44.9 Betfair orders health row  \[Live\]

Steps:
1. Open the Health panel.

**Expected:** Shows 'Betfair orders sync' with the last check time and whether you are armed.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

## 45. Backups and monitoring (added 6 Nov)

_Server-side safety nets._

### 45.1 Daily backup runs  \[Practice\]

Steps:
1. After a day, open the Health panel.

**Expected:** A 'Daily backup' row shows a recent backup time; the server keeps 7 days plus 4 Sundays under the data folder.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 45.2 Backup restores  \[Practice\]

Steps:
1. On the server, gunzip a backup of journal.db and open it with sqlite3.

**Expected:** It opens and holds your orders and journal.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 45.3 Disk space row  \[Practice\]

Steps:
1. Open the Health panel.

**Expected:** Shows free space and the database size, and turns red below 10% free.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 45.4 Restart alert  \[Practice\]

Steps:
1. Restart the service.

**Expected:** An alert 'AutoBets restarted at HH:MM' appears with what was restored.

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 

### 45.5 Uptime check  \[Either\]

Steps:
1. In GitHub, Actions > uptime > Run workflow.

**Expected:** It passes while the server is up. If the server is stopped it fails (and GitHub emails you).

Result: ☐ Pass ☐ Fail ☐ Blocked  Notes: 
