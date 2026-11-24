"""PS5-vakt: sjekker Power og NetOnNet og sender pushvarsel til mobilen (ntfy) naar en PS5 er paa lager.

Henrik vil ha: PS5 Slim MED plate (ikke Digital). Pro bare hvis prisen er under PRO_MAKSPRIS.
Kjoeres av GitHub Actions hvert ~5. min. Lokal test: python3 vakt.py --test
"""
import json, os, re, sys, urllib.request, urllib.parse

PRO_MAKSPRIS = int(os.environ.get("PRO_MAKSPRIS", "7000"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def hent(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nb-NO"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "ignore")


def vil_ha(tittel, pris):
    t = tittel.lower()
    if "digital" in t:
        return False  # kan ikke spille fysiske spill
    if "pro" in t.split() or "pro " in t or t.endswith(" pro"):
        return pris is not None and pris <= PRO_MAKSPRIS
    return True


def power():
    funn = []
    for q in ["playstation 5 konsoll", "ps5 pro konsoll"]:
        d = json.loads(hent("https://www.power.no/api/v2/productlists?size=30&q=" + urllib.parse.quote(q)))
        for p in d.get("products", []):
            if "konsoll" not in (p.get("categoryName") or "").lower():
                continue
            if (p.get("stockCount") or 0) > 0 and vil_ha(p["title"], p.get("price")):
                funn.append(("Power", p["title"], p.get("price"), "https://www.power.no" + p["url"]))
    return funn


def netonnet():
    funn = []
    kat = hent("https://www.netonnet.no/art/gaming/spillogkonsoll/playstation/playstation-konsoll")
    lenker = sorted(set(re.findall(r'/art/gaming/spillogkonsoll/playstation/playstation-konsoll/[a-z0-9\-]+/[0-9.]+/', kat)))
    for l in lenker:
        if "digital" in l or "refurb" in l:
            continue
        side = hent("https://www.netonnet.no" + l)
        m = re.search(r'"availability":"([A-Za-z]+)"', side)
        tilg = m.group(1) if m else "?"
        pm = re.search(r'"price":"?([0-9.]+)', side)
        pris = float(pm.group(1)) if pm else None
        navn = l.split("/")[-3].replace("-", " ")
        if tilg in ("InStock", "LimitedAvailability", "OnlineOnly") and vil_ha(navn, pris):
            funn.append(("NetOnNet", navn, pris, "https://www.netonnet.no" + l))
    return funn


def varsle(funn):
    for butikk, navn, pris, url in funn:
        tekst = f"{navn} - {pris:.0f} kr" if pris else navn
        print("VARSEL:", butikk, tekst, url)
        if not NTFY_TOPIC:
            continue
        req = urllib.request.Request(
            "https://ntfy.sh/" + NTFY_TOPIC, data=tekst.encode(), method="POST",
            headers={"Title": f"PS5 paa lager: {butikk}", "Priority": "urgent",
                     "Tags": "video_game,rotating_light", "Click": url})
        urllib.request.urlopen(req, timeout=15)


def main():
    funn, feil = [], []
    for navn, f in [("Power", power), ("NetOnNet", netonnet)]:
        try:
            r = f()
            print(f"{navn}: {len(r)} treff")
            funn += r
        except Exception as e:
            feil.append(f"{navn}: {e}")
            print(f"{navn}: FEIL {e}")
    if "--test" in sys.argv and not funn:
        funn = [("Test", "Dette er en testvarsel fra PS5-vakt", None, "https://www.power.no")]
    varsle(funn)
    if len(feil) == 2:
        sys.exit("Alle butikker feilet: " + "; ".join(feil))


if __name__ == "__main__":
    main()
