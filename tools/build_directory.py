#!/usr/bin/env python3
"""Build static, crawlable directory pages from churches.json.

Runs in GitHub Actions before each Firebase deploy (see .github/workflows),
so the pages are rebuilt automatically whenever churches.json changes.

Output (not committed): browse/index.html, browse/us/<state>.html,
browse/<country>.html, browse/sitemap.xml, plus robots.txt at the site root.
"""
import html
import json
import os
import re
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "browse")
BASE = os.environ.get("DIRECTORY_BASE_URL", "https://churches.truthscalling.com/browse").rstrip("/")
MAIN = "https://www.truthscalling.com"
TODAY = date.today().isoformat()

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
}
CA_PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}
COUNTRIES = {
    "US": "United States", "GB": "United Kingdom", "BR": "Brazil", "CA": "Canada",
    "NL": "Netherlands", "AU": "Australia", "ZA": "South Africa", "SE": "Sweden",
    "DE": "Germany", "ES": "Spain", "CH": "Switzerland", "NZ": "New Zealand", "FR": "France",
    "AR": "Argentina", "IT": "Italy", "IE": "Ireland", "AT": "Austria", "PH": "Philippines",
    "SG": "Singapore", "PL": "Poland", "RO": "Romania", "JP": "Japan", "MY": "Malaysia",
    "KR": "South Korea", "BE": "Belgium", "CL": "Chile", "HN": "Honduras", "ID": "Indonesia",
    "DK": "Denmark", "UG": "Uganda", "FI": "Finland", "GT": "Guatemala", "CR": "Costa Rica",
    "KE": "Kenya", "UY": "Uruguay", "TW": "Taiwan", "BB": "Barbados", "IS": "Iceland",
    "MD": "Moldova", "MU": "Mauritius", "ZM": "Zambia", "BS": "Bahamas", "CZ": "Czechia",
    "HU": "Hungary", "NO": "Norway", "PA": "Panama", "HR": "Croatia", "LB": "Lebanon",
    "DO": "Dominican Republic", "MX": "Mexico", "PT": "Portugal", "IN": "India",
    "NG": "Nigeria", "GH": "Ghana", "KY": "Cayman Islands", "JM": "Jamaica", "PE": "Peru",
    "CO": "Colombia", "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania", "SK": "Slovakia",
    "SI": "Slovenia", "GR": "Greece", "CY": "Cyprus", "MT": "Malta", "LU": "Luxembourg",
    "UA": "Ukraine", "RS": "Serbia", "BG": "Bulgaria", "HK": "Hong Kong", "TH": "Thailand",
    "EC": "Ecuador", "PY": "Paraguay", "BO": "Bolivia", "VE": "Venezuela", "NA": "Namibia",
    "BW": "Botswana", "MW": "Malawi", "TZ": "Tanzania", "ZW": "Zimbabwe", "FJ": "Fiji",
    "PG": "Papua New Guinea", "TT": "Trinidad and Tobago", "BM": "Bermuda",
}

e = lambda s: html.escape(str(s or "").strip(), quote=True)


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s or "other"


def country_of(c):
    cc = (c.get("country") or "").strip().upper()
    if not cc:
        st = (c.get("state") or "").strip().upper()
        return "CA" if st in CA_PROVINCES else "US"
    return cc


def region_name(cc, st):
    st = (st or "").strip()
    if cc == "US":
        return US_STATES.get(st.upper(), st)
    if cc == "CA":
        return CA_PROVINCES.get(st.upper(), st)
    return st


def us_zip(z):
    z = str(z or "").strip()
    return z.zfill(5) if z.isdigit() and len(z) < 5 else z


def safe_url(u):
    u = str(u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


CSS = """
:root{--navy:#0b1a30;--panel:#10213a;--cream:#ede6d6;--head:#f3ecdd;--gold:#c9a75c;--muted:#b9b1a0}
*{box-sizing:border-box}body{margin:0;background:var(--navy);color:var(--cream);font:16px/1.6 "DM Sans",system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--gold)}a:hover{text-decoration:none}
header,main,footer{max-width:960px;margin:0 auto;padding:0 20px}
header{padding-top:22px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
header .brand{font:600 1.4rem "Cormorant Garamond",Georgia,serif;color:var(--head);text-decoration:none}
nav.crumbs{font-size:.9rem;color:var(--muted);margin:18px 0 0}
h1,h2,h3{font-family:"Cormorant Garamond",Georgia,serif;color:var(--head);line-height:1.15}
h1{font-size:2.4rem;margin:.4em 0 .2em}h2{font-size:1.7rem;margin:1.6em 0 .4em;border-bottom:1px solid rgba(201,167,92,.35);padding-bottom:.2em}
h3{font-size:1.25rem;margin:.2em 0}
.lead{color:var(--cream);max-width:760px}
.cta{display:inline-block;background:var(--gold);color:#14213a;font-weight:600;padding:10px 18px;border-radius:999px;text-decoration:none;margin:6px 8px 6px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:6px 18px;padding:0;list-style:none}
.church{background:var(--panel);border-radius:10px;padding:14px 16px;margin:10px 0}
.church p{margin:.15em 0;font-size:.95rem}.church .denom{color:var(--gold);font-size:.85rem;text-transform:uppercase;letter-spacing:.04em}
footer{color:var(--muted);font-size:.85rem;padding-top:30px;padding-bottom:40px}
"""


def page(title, desc, canonical, body, crumbs="", ld=None):
    lds = ""
    for obj in (ld or []):
        lds += '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=DM+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
{lds}</head>
<body>
<header><a class="brand" href="{MAIN}/">Truths Calling</a><a href="{MAIN}/">Search the church map</a></header>
<main>
{crumbs}
{body}
</main>
<footer>
<p>Truths Calling lists churches that publicly affirm the gospel of Jesus Christ, based on their own websites and conservative, confessional church directories. A listing is not an endorsement; please visit a church's website and talk with its leaders. See something that should change? <a href="{MAIN}/#connect">Let us know</a>.</p>
<p><a href="{MAIN}/what-is-the-gospel">What is the gospel?</a> · <a href="{MAIN}/statement-of-faith">Statement of Faith</a> · <a href="{MAIN}/privacy-policy">Privacy Policy</a> · Updated {TODAY}</p>
</footer>
</body>
</html>
"""


def church_card(c, cc):
    name = e(c.get("name"))
    web = safe_url(c.get("website"))
    title = f'<a href="{e(web)}" rel="noopener">{name}</a>' if web else name
    st = (c.get("state") or "").strip()
    z = us_zip(c.get("zip")) if cc == "US" else str(c.get("zip") or "").strip()
    line2 = ", ".join(x for x in [e(c.get("city")), " ".join(x for x in [e(st), e(z)] if x)] if x)
    parts = [f'<div class="church"><h3>{title}</h3>']
    if c.get("denom"):
        parts.append(f'<p class="denom">{e(c["denom"])}</p>')
    addr = e(c.get("address"))
    if addr or line2:
        parts.append("<p>" + "<br>".join(x for x in [addr, line2] if x) + "</p>")
    if c.get("times"):
        parts.append(f"<p>Service times: {e(c['times'])}</p>")
    if c.get("phone"):
        ph = str(c["phone"]).strip()
        parts.append(f'<p>Phone: <a href="tel:{e(re.sub(r"[^0-9+]", "", ph))}">{e(ph)}</a></p>')
    if web:
        parts.append(f'<p><a href="{e(web)}" rel="noopener">Church website</a></p>')
    parts.append("</div>")
    return "".join(parts)


def church_ld(c, cc):
    o = {"@type": "Church", "name": str(c.get("name") or "").strip()}
    web = safe_url(c.get("website"))
    if web:
        o["url"] = web
    addr = {"@type": "PostalAddress", "addressCountry": cc}
    for k, f in (("streetAddress", "address"), ("addressLocality", "city"), ("addressRegion", "state")):
        if c.get(f):
            addr[k] = str(c[f]).strip()
    if c.get("zip"):
        addr["postalCode"] = us_zip(c["zip"]) if cc == "US" else str(c["zip"]).strip()
    o["address"] = addr
    if c.get("phone"):
        o["telephone"] = str(c["phone"]).strip()
    try:
        o["geo"] = {"@type": "GeoCoordinates", "latitude": float(c["lat"]), "longitude": float(c["lng"])}
    except (KeyError, TypeError, ValueError):
        pass
    return o


def listing_body(churches, cc, group_key):
    groups = defaultdict(list)
    for c in churches:
        groups[group_key(c)].append(c)
    keys = sorted(groups, key=lambda k: (k == "", k.lower()))
    out = []
    if len(keys) > 1:
        out.append('<h2>Jump to</h2><ul class="grid">')
        for k in keys:
            out.append(f'<li><a href="#{slug(k or "other")}">{e(k or "Other")}</a> ({len(groups[k])})</li>')
        out.append("</ul>")
    for k in keys:
        out.append(f'<h2 id="{slug(k or "other")}">{e(k or "Location not listed")}</h2>')
        for c in sorted(groups[k], key=lambda c: str(c.get("name") or "").lower()):
            out.append(church_card(c, cc))
    return "\n".join(out)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    with open(os.path.join(ROOT, "churches.json"), encoding="utf-8") as f:
        churches = json.load(f)["churches"]

    by_country = defaultdict(list)
    for c in churches:
        by_country[country_of(c)].append(c)

    urls = [f"{BASE}/"]
    org = {"@id": f"{MAIN}/#organization"}

    # US: one page per state
    us = by_country.pop("US", [])
    by_state = defaultdict(list)
    for c in us:
        st = (c.get("state") or "").strip().upper()
        by_state[st if st in US_STATES else ""].append(c)
    state_links = []
    for st in sorted(by_state, key=lambda s: (s == "", US_STATES.get(s, s))):
        items = by_state[st]
        name = US_STATES.get(st, "Other locations")
        fn = slug(name) if st else "other"
        url = f"{BASE}/us/{fn}.html"
        urls.append(url)
        state_links.append(f'<li><a href="us/{fn}.html">{e(name)}</a> ({len(items)})</li>')
        cities = len({(c.get("city") or "").strip().lower() for c in items})
        title = f"Gospel-preaching churches in {name}" if st else "Gospel-preaching churches in the United States (other locations)"
        desc = f"{len(items)} Bible-teaching churches in {cities} cities in {name} that publicly affirm the gospel of Jesus Christ, with addresses, phone numbers and websites." if st else f"{len(items)} Bible-teaching churches in the United States that publicly affirm the gospel of Jesus Christ."
        crumbs = f'<nav class="crumbs"><a href="../index.html">All locations</a> › United States › {e(name)}</nav>'
        body = (f"<h1>{e(title)}</h1>"
                f'<p class="lead">{e(desc)} Each church has its own website; please visit it and speak with the church\'s leaders before you go.</p>'
                f'<p><a class="cta" href="{MAIN}/">Search the map near you</a><a class="cta" href="{MAIN}/what-is-the-gospel">What is the gospel?</a></p>'
                + listing_body(items, "US", lambda c: (c.get("city") or "").strip().title()))
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc,
               "url": url, "isPartOf": {"@id": f"{MAIN}/#website"}, "publisher": org,
               "mainEntity": {"@type": "ItemList", "numberOfItems": len(items),
                              "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": church_ld(c, "US")}
                                                  for i, c in enumerate(sorted(items, key=lambda c: str(c.get("name") or "").lower()))]}}]
        write(os.path.join(OUT, "us", fn + ".html"), page(f"{title} – Truths Calling", desc, url, body, crumbs, ld))

    # Other countries: one page each
    country_links = []
    for cc in sorted(by_country, key=lambda k: COUNTRIES.get(k, k)):
        items = by_country[cc]
        name = COUNTRIES.get(cc, cc)
        fn = slug(name)
        url = f"{BASE}/{fn}.html"
        urls.append(url)
        country_links.append(f'<li><a href="{fn}.html">{e(name)}</a> ({len(items)})</li>')
        title = f"Gospel-preaching churches in {name}"
        desc = f"{len(items)} Bible-teaching {'church' if len(items) == 1 else 'churches'} in {name} that publicly affirm the gospel of Jesus Christ, with addresses and websites."
        crumbs = f'<nav class="crumbs"><a href="index.html">All locations</a> › {e(name)}</nav>'
        group = (lambda c, cc=cc: region_name(cc, c.get("state"))) if len(items) > 25 else (lambda c: (c.get("city") or "").strip().title())
        body = (f"<h1>{e(title)}</h1>"
                f'<p class="lead">{e(desc)} Each church has its own website; please visit it and speak with the church\'s leaders before you go.</p>'
                f'<p><a class="cta" href="{MAIN}/">Search the map near you</a><a class="cta" href="{MAIN}/what-is-the-gospel">What is the gospel?</a></p>'
                + listing_body(items, cc, group))
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc,
               "url": url, "isPartOf": {"@id": f"{MAIN}/#website"}, "publisher": org,
               "mainEntity": {"@type": "ItemList", "numberOfItems": len(items),
                              "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": church_ld(c, cc)}
                                                  for i, c in enumerate(items)]}}]
        write(os.path.join(OUT, fn + ".html"), page(f"{title} – Truths Calling", desc, url, body, crumbs, ld))

    total = len(churches)
    n_countries = len(by_country) + (1 if us else 0)
    title = "Browse gospel-preaching churches by state and country"
    desc = f"A free directory of {total:,} churches in {n_countries} countries that publicly affirm the gospel of Jesus Christ. Browse by U.S. state or by country."
    body = (f"<h1>{e(title)}</h1>"
            f'<p class="lead">Truths Calling is a free directory of {total:,} churches in {n_countries} countries that publicly affirm the gospel of Jesus Christ. '
            "Each church is listed from conservative, confessional church directories and has its own website. Choose a state or country below, "
            f'or <a href="{MAIN}/">search the map</a> by city, postcode or your location.</p>'
            f'<h2>United States</h2><ul class="grid">{"".join(state_links)}</ul>'
            f'<h2>Other countries</h2><ul class="grid">{"".join(country_links)}</ul>')
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc,
           "url": f"{BASE}/", "isPartOf": {"@id": f"{MAIN}/#website"}, "publisher": org}]
    crumbs = f'<nav class="crumbs"><a href="{MAIN}/">Truths Calling</a> › Browse churches</nav>'
    write(os.path.join(OUT, "index.html"), page(f"{title} – Truths Calling", desc, f"{BASE}/", body, crumbs, ld))

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{e(u)}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    write(os.path.join(OUT, "sitemap.xml"), "\n".join(sm) + "\n")
    write(os.path.join(ROOT, "robots.txt"), f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    print(f"Built {len(urls)} directory pages for {total} churches into {OUT}")


if __name__ == "__main__":
    main()
