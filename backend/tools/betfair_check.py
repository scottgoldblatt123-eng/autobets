"""Betfair connection check. Reads credentials from a protected env file and never prints them.

Usage: python3 backend/tools/betfair_check.py /opt/autobets/secrets/betfair.env
Env file lines: BETFAIR_APP_KEY=..., BETFAIR_USERNAME=..., BETFAIR_PASSWORD=...
Optional (certificate login, recommended for the live system): BETFAIR_CERT=/path/client.crt, BETFAIR_KEY=/path/client.key
"""
import json, ssl, sys, time, urllib.parse, urllib.request, urllib.error


def load(path):
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def post(url, data=None, headers=None, body=None, ctx=None):
    h = dict(headers or {})
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        body = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return json.loads(r.read()), (time.time() - t) * 1000
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "reason": e.reason}, (time.time() - t) * 1000


def main():
    env = load(sys.argv[1])
    app, user, pw = env.get("BETFAIR_APP_KEY"), env.get("BETFAIR_USERNAME"), env.get("BETFAIR_PASSWORD")
    if not (app and user and pw):
        sys.exit("Missing BETFAIR_APP_KEY, BETFAIR_USERNAME or BETFAIR_PASSWORD in the env file.")
    hdr = {"X-Application": app, "Accept": "application/json"}
    if env.get("BETFAIR_CERT") and env.get("BETFAIR_KEY"):
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(env["BETFAIR_CERT"], env["BETFAIR_KEY"])
        res, ms = post("https://identitysso-cert.betfair.com/api/certlogin", {"username": user, "password": pw}, hdr, ctx=ctx)
        token, how = res.get("sessionToken"), "certificate login"
        status = f'{res.get("loginStatus") or res}'
    else:
        res, ms = post("https://identitysso.betfair.com/api/login", {"username": user, "password": pw}, hdr)
        token, how = res.get("token"), "interactive login"
        status = f'{res.get("status")} / reason: {res.get("error") or res.get("http_error") or "none given"}'
    print(f"Login ({how}): {status}  [{ms:.0f} ms]")
    if not token:
        sys.exit("No session token. If the status mentions a security code or 2FA, we will switch to certificate login.")
    api = "https://api.betfair.com/exchange/betting/rest/v1.0/"
    h = {"X-Application": app, "X-Authentication": token, "Accept": "application/json"}
    res, ms = post(api + "listEventTypes/", headers=h, body={"filter": {}})
    if isinstance(res, list):
        names = {r["eventType"]["name"]: r["marketCount"] for r in res}
        print(f"API call OK [{ms:.0f} ms]. Football markets: {names.get('Soccer')}, Tennis markets: {names.get('Tennis')}")
    else:
        sys.exit(f"API call failed: {res}")
    res, ms = post(api + "listMarketCatalogue/", headers=h, body={
        "filter": {"eventTypeIds": ["1"], "marketTypeCodes": ["MATCH_ODDS"]}, "maxResults": "5",
        "marketProjection": ["EVENT", "COMPETITION", "MARKET_START_TIME"]})
    if isinstance(res, list):
        print(f"Sample football Match Odds markets [{ms:.0f} ms]:")
        for m in res:
            print("  ", m["marketStartTime"][:16], "|", m.get("competition", {}).get("name", "?"), "|", m["event"]["name"])
    else:
        print("Market list failed:", res)
    print("CHECK-COMPLETE")


main()
