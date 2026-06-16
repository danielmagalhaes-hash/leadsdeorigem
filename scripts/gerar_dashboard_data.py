"""
Gera dashboard_data.json com dados reais do Supabase.
Uso: python scripts/gerar_dashboard_data.py
"""
import sys, json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
sys.path.insert(0, ".")

from src.config import settings
from supabase import create_client

BRT = ZoneInfo("America/Sao_Paulo")

CHANNEL_CONFIG = {
    "Meta Ads":             {"id": "meta",          "name": "Meta Ads",             "color": "#1877f2"},
    "Google":               {"id": "google",        "name": "Google",               "color": "#ea4335"},
    "Google Institucional": {"id": "google-inst",   "name": "Google Institucional", "color": "#fbbc04"},
    "Social":               {"id": "social",        "name": "Social",               "color": "#e1306c"},
    "Influenciadores":      {"id": "influ",         "name": "Influenciadores",      "color": "#06b6d4"},
    "B2B":                  {"id": "b2b",           "name": "B2B",                  "color": "#7c3aed"},
    "WhatsApp Fluxo":       {"id": "wpp-fluxo",     "name": "WhatsApp Fluxo",       "color": "#10b981"},
    "WhatsApp Campanha":    {"id": "wpp-camp",      "name": "WhatsApp Campanha",    "color": "#ec4899"},
    "WhatsApp Comunidade":  {"id": "wpp-com",       "name": "WhatsApp Comunidade",  "color": "#25d366"},
    "E-mail Fluxo":         {"id": "email-fluxo",   "name": "E-mail Fluxo",         "color": "#a855f7"},
    "E-mail Campanha":      {"id": "email-camp",    "name": "E-mail Campanha",      "color": "#6366f1"},
    "Comercial":            {"id": "comercial",     "name": "Comercial",            "color": "#8b5cf6"},
    "Outros canais":        {"id": "outros",        "name": "Outros canais",        "color": "#d1d5db"},
    "Direto":               {"id": "direto",        "name": "Direto",               "color": "#94a3b8"},
}


def brt_date(ts_str: str) -> str:
    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return ts.astimezone(BRT).date().isoformat()


def fetch_leads(client, start_ts: str, end_ts: str | None = None) -> list[dict]:
    results, offset, PAGE = [], 0, 1000
    while True:
        q = (client.table("leads_v2")
             .select("criado_em,origem,utm_source,utm_medium,utm_campaign,utm_content,utm_term")
             .gte("criado_em", start_ts)
             .not_.in_("metodo_atribuicao", ["integracao_hubspot", "integracao_tiktok"]))
        if end_ts:
            q = q.lt("criado_em", end_ts)
        chunk = q.range(offset, offset + PAGE - 1).execute().data
        results.extend(chunk)
        if len(chunk) < PAGE:
            break
        offset += PAGE
    return results


def main() -> None:
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    today_brt = date.today()
    start_90  = datetime(today_brt.year, today_brt.month, today_brt.day, tzinfo=BRT) - timedelta(days=89)
    start_180 = start_90 - timedelta(days=90)

    start_90_ts  = start_90.astimezone(timezone.utc).isoformat()
    start_180_ts = start_180.astimezone(timezone.utc).isoformat()

    print(f"Buscando leads periodo atual ({start_90.date()} ate {today_brt})...")
    leads_atual = fetch_leads(client, start_90_ts)
    print(f"  -> {len(leads_atual):,} leads")

    print(f"Buscando leads periodo anterior ({start_180.date()} ate {start_90.date()})...")
    leads_prev = fetch_leads(client, start_180_ts, start_90_ts)
    print(f"  -> {len(leads_prev):,} leads")

    origem_to_id = {k: v["id"] for k, v in CHANNEL_CONFIG.items()}

    # Canais presentes nos dados
    origens_vistas: set[str] = {l["origem"] or "Unassigned" for l in leads_atual}
    channels_usados: list[dict] = []
    seen_ids: set[str] = set()
    for origem, cfg in CHANNEL_CONFIG.items():
        if origem in origens_vistas and cfg["id"] not in seen_ids:
            channels_usados.append({**cfg, "share": 0, "volatility": 0})
            seen_ids.add(cfg["id"])

    # Agregação diária
    daily_map: dict[str, dict[str, int]] = {}
    for lead in leads_atual:
        d = brt_date(lead["criado_em"])
        ch_id = origem_to_id.get(lead["origem"] or "Unassigned", "outros")
        daily_map.setdefault(d, {})[ch_id] = daily_map.get(d, {}).get(ch_id, 0) + 1

    all_days: list[dict] = []
    cur = start_90.date()
    while cur <= today_brt:
        ds = cur.isoformat()
        chs = daily_map.get(ds, {})
        all_days.append({"date": ds, "channels": chs, "total": sum(chs.values())})
        cur += timedelta(days=1)

    # UTM rows — agrega por canal + todos os campos UTM
    utm_atual: dict[tuple, int] = {}
    for lead in leads_atual:
        ch_id = origem_to_id.get(lead["origem"] or "Unassigned", "outros")
        key = (ch_id,
               lead.get("utm_source") or "—", lead.get("utm_medium") or "—",
               lead.get("utm_campaign") or "—", lead.get("utm_content") or "—",
               lead.get("utm_term") or "—")
        utm_atual[key] = utm_atual.get(key, 0) + 1

    utm_prev: dict[tuple, int] = {}
    for lead in leads_prev:
        ch_id = origem_to_id.get(lead["origem"] or "Unassigned", "outros")
        key = (ch_id,
               lead.get("utm_source") or "—", lead.get("utm_medium") or "—",
               lead.get("utm_campaign") or "—", lead.get("utm_content") or "—",
               lead.get("utm_term") or "—")
        utm_prev[key] = utm_prev.get(key, 0) + 1

    utm_rows = [
        {"channelId": k[0], "source": k[1], "medium": k[2],
         "campaign": k[3], "content": k[4], "term": k[5],
         "leads": v, "leadsPrev": utm_prev.get(k, 0)}
        for k, v in sorted(utm_atual.items(), key=lambda x: -x[1])[:300]
    ]

    # Baseline e meta
    last60 = [d["total"] for d in all_days[-60:] if d["total"] > 0]
    baseline = int(sorted(last60)[len(last60) // 2]) if last60 else 0
    meta_daily = round(baseline * 1.5)
    meta_90d = meta_daily * 90

    output = {
        "generated_at": datetime.now().isoformat(),
        "channels": channels_usados,
        "daily": all_days,
        "utm_rows": utm_rows,
        "baseline": baseline,
        "meta_daily": meta_daily,
        "meta_90d": meta_90d,
    }

    with open("dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, default=str)

    print(f"\nOK dashboard_data.json gerado")
    print(f"  Periodo : {start_90.date()} ate {today_brt} ({len(all_days)} dias)")
    print(f"  Leads   : {len(leads_atual):,} | Canais: {len(channels_usados)}")
    print(f"  Baseline: {baseline}/dia | Meta: {meta_daily}/dia")


if __name__ == "__main__":
    main()
