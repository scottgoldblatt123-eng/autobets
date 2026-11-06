"""Claude drafts an automation script from plain English. It can only produce script data; the same validator as a hand-written script
checks it, and a draft is never enabled or applied by the AI."""
from __future__ import annotations

import json
import re

from ..scripts import CONDITIONS, ScriptError, describe, headline, validate
from .claude import AiError, Claude
from .usage import Usage

SYSTEM = f"""You turn a trader's plain-English idea into an AutoBets automation script, as JSON. You only draft; the trader reviews, backtests and enables it.
Reply with one short sentence of explanation, then the script in a ```script fenced block. If the idea cannot be expressed, say why and write no block.

A script: {{"name": str, "sport": "tennis"|"football"|"any", "description": str, "rules": [rule, ...]}}
A rule: {{"id": "r1", "kind": "entry"|"exit"|"safety", "when": [condition, ...] (all must be true), "then": [action, ...]}}
- entry opens a position (action back or lay) and fires once per run. An entry rule may carry "repeat": N (1-100): after its exit has greened and the position is level, the script re-arms and runs again, one run at a time, N runs in total. Use this for scalping or "repeat" requests. exit must include {{"type":"rule_matched","rule":"<earlier id>"}} and acts with green (hedge to level) or close.
  safety can close and stop. Rules only refer to earlier rules.
Conditions ({", ".join(CONDITIONS)}):
 {{"type":"price","op":">=","value":2.2,"ref":"last"|"back"|"lay"}}  price of the runner the script is attached to
 {{"type":"in_play","value":true}}  {{"type":"set_number","op":"<","value":3}} (tennis)  {{"type":"goals_total","op":"<=","value":1}}  {{"type":"score_is","home":0,"away":0}}
 {{"type":"minute","op":">=","value":45}} (football)  {{"type":"position_loss","op":">=","value":15}} (pounds)  {{"type":"clock","start":"19:30","end":"19:45"}} (UK time)
 {{"type":"rule_matched","rule":"r1"}}
 {{"type":"ticks_from_peak","value":3}}  trailing stop: the exit price has given back 3 ticks from its best since you were matched (use with a close action)
 {{"type":"minutes_to_start","op":"<=","value":30}}  minutes until the scheduled start (negative after it)
 {{"type":"spread_ticks","op":"<=","value":2}}  ticks between best back and best lay on the runner (use to avoid wide, illiquid books)
 {{"type":"market_matched","op":">=","value":50000}}  £ matched on the whole market so far
 {{"type":"price_move","op":"<=","value":-3,"seconds":60}}  ticks the runner's price moved in the last N seconds (+ drifted out, - shortened)
 {{"type":"set_games_diff","op":"<=","value":-1}} (tennis) games won by the runner the script is on, minus the opponent's, in the current set (-1 = a game behind, e.g. just broken; +1 = a game ahead)
 {{"type":"sets_diff","op":">=","value":1}} (tennis) sets won by this runner minus the opponent's
 {{"type":"ticks_from_entry","op":">=","value":2}}  ticks of profit available to exit versus where THIS script was matched (negative value = against you). Use it for "take N ticks" and "stop at N ticks against". An entry at the best price and an exit at ticks_from_entry >= 2 with action green is a 2-tick scalp.
 op is one of >=, <=, ==, >, <.
Actions: {{"type":"lay"|"back","price":2.2 or "best","stake":10,"basis":"stake"|"liability","persistence":"CANCEL"|"KEEP"|"TAKE_SP"}}, {{"type":"green"}}, {{"type":"close"}}, {{"type":"stop"}}.
Lay bets default to basis "stake". Default stake £10 unless told otherwise; always include a safety rule that limits the loss when the idea is open-ended.
Prices are Betfair decimal odds. Do not invent conditions that are not listed; if the idea needs one, say so. There is no Betfair SP price option; "best" takes the best available price now. A scalp should also get a safety rule, e.g. ticks_from_entry <= -6 then close and stop, unless the trader says otherwise."""


def draft(claude: Claude, usage: Usage, prompt: str) -> dict:
    if not claude.enabled:
        raise AiError("The script builder needs ANTHROPIC_API_KEY on the server.")
    if not usage.allowed():
        raise AiError(f"The monthly AI spend limit (£{usage.cap:g}, estimated) has been reached.")
    res = claude.message(SYSTEM, [{"role": "user", "content": prompt[:6000]}], max_tokens=1500)
    gbp = usage.record("script-builder", res["model"], res["input_tokens"], res["output_tokens"])
    text = res["text"]
    m = re.search(r"```script\s*(.*?)```", text, re.S)
    explanation = (text[:m.start()] if m else text).strip()
    if not m:
        return {"explanation": explanation, "script": None, "error": None, "cost_gbp": round(gbp, 4)}
    try:
        script = validate(json.loads(m.group(1)))
    except (json.JSONDecodeError, ScriptError) as e:
        return {"explanation": explanation, "script": None, "error": f"Claude's draft was not a valid script ({e}). Try rewording the idea.", "cost_gbp": round(gbp, 4)}
    return {"explanation": explanation, "script": script, "text": describe(script), "headline": headline(script), "error": None, "cost_gbp": round(gbp, 4)}
