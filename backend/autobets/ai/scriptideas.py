"""Claude proposes NEW automation scripts: hypotheses about how Betfair prices over- or under-react, written as ordinary scripts. It only proposes.
A proposal is a recommendation the trader can discuss, save to the Scripts library (switched off) or dismiss; the AI never enables or runs anything."""
from __future__ import annotations

import json
import re

from ..scripts import ScriptError, describe, headline, validate
from . import scriptbuilder
from .claude import AiError, Claude
from .usage import Usage

PREFACE = """You are the strategy research partner for a trader on the Betfair Exchange (tennis and football, trading price movement, not predicting winners: Betfair's prices are
far more accurate than any model). Propose NEW automation scripts, each testing one distinct, plausible hypothesis about how the market over- or under-reacts to an event
(a break of serve, a set won, a goal, the clock, a quiet spell, a price spike). They must differ from the existing library and from each other. Be specific and conservative:
small stakes (GBP 10 or less), always a loss limit, only the conditions listed below. You cannot backtest; say so plainly in WHY if the idea is unproven.

Reply with exactly the number of ideas asked for, each in this form and nothing else:
IDEA: <short title>
WHY: <one or two sentences: the hypothesis, in plain English>
RISK: <one sentence: how it loses>
```script
<the script JSON>
```

"""
SYSTEM = PREFACE + scriptbuilder.SYSTEM[scriptbuilder.SYSTEM.index("A script:"):]


def propose(claude: Claude, usage: Usage, library: list[dict], results: list[str], n: int = 3) -> dict:
    if not claude.enabled:
        raise AiError("Script proposals need ANTHROPIC_API_KEY on the server.")
    if not usage.allowed():
        raise AiError(f"The monthly AI spend limit (£{usage.cap:g}, estimated) has been reached.")
    lib = "\n".join(f"- {s['name']} ({s['sport']}): {s['headline']}" for s in library[:40]) or "(empty)"
    res = "\n".join(f"- {r}" for r in results[:20]) or "(nothing settled yet)"
    prompt = f"Existing library:\n{lib}\n\nHow accepted trade setups have done so far (practice mode):\n{res}\n\nPropose {n} new scripts."
    out = claude.message(SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3500)
    gbp = usage.record("script-ideas", out["model"], out["input_tokens"], out["output_tokens"])
    return {"ideas": parse(out["text"]), "cost_gbp": round(gbp, 4)}


def parse(text: str) -> list[dict]:
    ideas = []
    for block in re.split(r"(?m)^IDEA:", text)[1:]:
        title = block.split("\n", 1)[0].strip()
        why = (re.search(r"WHY:\s*(.*?)(?=\nRISK:|\n```|\Z)", block, re.S) or [None, ""])[1].strip()
        risk = (re.search(r"RISK:\s*(.*?)(?=\n```|\Z)", block, re.S) or [None, ""])[1].strip()
        m = re.search(r"```script\s*(.*?)```", block, re.S)
        if not (title and m):
            continue
        try:
            script = validate(json.loads(m.group(1)))
        except (json.JSONDecodeError, ScriptError):
            continue
        ideas.append({"title": title[:120], "why": why, "risk": risk, "script": script, "text": describe(script), "headline": headline(script)})
    return ideas
