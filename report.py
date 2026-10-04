"""Weekly report (Mondays): one page for the owner, published as a GitHub Issue (GitHub emails it to the repo
owner automatically) and saved as weekly_report.md. Read-only: it never changes anything.

Optional: AC_API_URL + AC_API_KEY (+ AC_ORGANIC_TAG, default "organic-instagram") to count leads in ActiveCampaign
tagged as coming from the organic reels.
"""
import datetime, json, os, statistics, requests

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, default):
    p = os.path.join(HERE, name)
    try:
        return json.load(open(p))
    except Exception:
        return default


def _log():
    out = []
    try:
        for line in open(os.path.join(HERE, "log.jsonl")):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return out


def _ac_leads(days=7):
    url, key = os.environ.get("AC_API_URL"), os.environ.get("AC_API_KEY")
    if not (url and key):
        return None
    tag = os.environ.get("AC_ORGANIC_TAG", "organic-instagram")
    h = {"Api-Token": key}
    try:
        tags = requests.get(f"{url}/api/3/tags", params={"search": tag}, headers=h, timeout=30).json().get("tags", [])
        tid = next((t["id"] for t in tags if t["tag"].lower() == tag.lower()), None)
        if not tid:
            return f"tag '{tag}' not found"
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(f"{url}/api/3/contacts", params={"tagid": tid, "filters[created_after]": since, "limit": 1},
                         headers=h, timeout=30).json()
        return int(r.get("meta", {}).get("total", 0))
    except Exception as e:
        return f"error: {str(e)[:80]}"


def build():
    import strategy
    perf = _load("performance.json", {})
    log = _log()
    today = datetime.date.today()
    wk = [e for e in log if e.get("date") and (today - datetime.date.fromisoformat(e["date"])).days <= 7]
    rows = [dict(v, id=k) for k, v in perf.items() if v.get("date")]
    last7 = [r for r in rows if (today - datetime.date.fromisoformat(r["date"])).days <= 8]
    last30 = [r for r in rows if (today - datetime.date.fromisoformat(r["date"])).days <= 31]
    def tot(rs, k): return sum((r.get(k) or 0) for r in rs)
    L = [f"# Informe semanal de reels · {today:%d/%m/%Y}", ""]
    paused = _load("paused.json", None)
    if paused:
        L += [f"> ⚠️ **Publicación en pausa automática:** {paused.get('reason')}. Para reanudar, borra `paused.json` "
              "en el repo (o ejecuta el workflow con *force*).", ""]
    eng = {}
    for e in wk:
        eng[e.get("engine")] = eng.get(e.get("engine"), 0) + 1
    L += ["## Resumen", "",
          f"- Reels publicados en 7 días: **{len(wk)}** ({', '.join(f'{k}: {v}' for k, v in eng.items()) or 'ninguno'})",
          f"- Con métricas (publicados hace 1-8 días): {len(last7)}",
          f"- Views: **{tot(last7, 'views'):,}** · alcance: {tot(last7, 'reach'):,} · shares: {tot(last7, 'shares')} · guardados: {tot(last7, 'saved')}",
          f"- Visitas al perfil: **{tot(last7, 'profile_visits')}** · follows: **{tot(last7, 'follows')}** "
          "(si salen 0, Instagram no da esas métricas para reels en tu cuenta)",
          f"- DMs con el vídeo gratis enviados (total acumulado): {_load('handled_comments.json', {}).get('kw_dms', 0)}"]
    ac = _ac_leads()
    if ac is not None:
        L.append(f"- Leads nuevos en ActiveCampaign con origen orgánico (7 días): **{ac}**")
    ranked = sorted(last30, key=strategy.reward, reverse=True)
    def line(r):
        return (f"| {r.get('date')} | {(r.get('pillar') or r.get('engine') or '')} | {(r.get('hook') or r.get('story') or '')[:60]} | "
                f"{r.get('views') or '-'} | {r.get('profile_visits') or '-'} | {r.get('follows') or '-'} | "
                f"[ver]({r.get('permalink')}) |")
    if ranked:
        hdr = ["| Fecha | Pilar | Gancho | Views | Visitas perfil | Follows | Enlace |", "|---|---|---|---|---|---|---|"]
        L += ["", "## Mejores reels (30 días)", ""] + hdr + [line(r) for r in ranked[:3]]
        L += ["", "## Peores reels (30 días)", ""] + hdr + [line(r) for r in ranked[-3:][::-1]]
        best = sorted(last30, key=lambda r: (r.get("profile_visits") or 0, strategy.reward(r)), reverse=True)[:3]
        L += ["", "## Recomendados para fijar en el perfil, anuncios y emails", ""]
        L += [f"- {r.get('permalink')} ({(r.get('hook') or '')[:70]})" for r in best]
    st, mu, sd, n = strategy.stats()
    if n:
        L += ["", "## Qué está ganando (piloto automático)", ""]
        for lever in ("cta", "hook_style", "theme"):
            opts = sorted(st.get(lever, {}).items(), key=lambda kv: kv[1][1] if kv[1][0] else -9, reverse=True)
            tried = [(k, v) for k, v in opts if v[0]]
            if tried:
                L.append(f"- **{lever}**: mejor = {strategy.short(tried[0][0])} ({tried[0][1][0]} reels)"
                         + (f"; peor = {strategy.short(tried[-1][0])}" if len(tried) > 1 else ""))
        by_p = {}
        for r in last30:
            if r.get("pillar"):
                by_p.setdefault(r["pillar"], []).append(strategy.reward(r))
        if by_p:
            L.append("- **pilares**: " + ", ".join(f"{p} {statistics.mean(v):.2f} ({len(v)})" for p, v in
                                                  sorted(by_p.items(), key=lambda kv: -statistics.mean(kv[1]))))
    errs = [e for e in wk if (e.get("engine") == "hype")]
    fails = _load("failures.json", {})
    if errs or fails.get("consecutive"):
        L += ["", "## Incidencias", ""]
        if errs:
            L.append(f"- {len(errs)} reels salieron con el formato de respaldo (Gemini falló o el revisor rechazó).")
        if fails.get("consecutive"):
            L.append(f"- Ejecuciones fallidas seguidas: {fails['consecutive']} · último error: `{fails.get('last_error', '')[:150]}`")
    L += ["", "_Generado automáticamente. No requiere ninguna acción salvo que veas una pausa arriba._"]
    return "\n".join(L)


def publish(md):
    open(os.path.join(HERE, "weekly_report.md"), "w").write(md)
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and tok):
        print(md); return "printed"
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                      json={"title": f"Informe semanal de reels · {datetime.date.today():%d/%m/%Y}", "body": md})
    print("issue:", r.status_code, r.json().get("html_url") if r.ok else r.text[:200])
    return r.status_code


if __name__ == "__main__":
    publish(build())
