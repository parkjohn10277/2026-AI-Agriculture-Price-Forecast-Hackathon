# -*- coding: utf-8 -*-
"""README graphics in the competition poster palette (mint / deep green / teal / straw)."""
import math, sys, html
OUT = sys.argv[1]

FONT = "-apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Pretendard', 'Noto Sans KR', 'Segoe UI', sans-serif"
MONO = "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

T = {
    "light": dict(bg1="#F2FCF9", bg2="#C9F0E6", wave="#0E5B52", wave2="#1F7A6A", ink="#0F3D2E", title1="#1A8A5F", title2="#0B4D36",
                  muted="#4E6F64", glass="#FFFFFF", glass_op="0.78", stroke="#9ED9C8", accent="#12805A", straw="#C98E52",
                  line="#B9E3D7", naive="#C7D9D2", card="#FFFFFF", chip="#E3F6F0", red="#C8402E", shadow="#0B4D36"),
    "dark":  dict(bg1="#0A221E", bg2="#0F3A33", wave="#071815", wave2="#0D2D28", ink="#E6F6F0", title1="#7FE3B8", title2="#3FBF8A",
                  muted="#93B8AC", glass="#12332D", glass_op="0.85", stroke="#2E6A5C", accent="#5FD3A0", straw="#E0AE74",
                  line="#1E4A41", naive="#355A50", card="#11302A", chip="#173F37", red="#E2644F", shadow="#000000"),
}


# ---------- vegetable icons (centered at 0,0, ~ 80px tall) ----------
def cabbage(c):
    return (f'<ellipse cx="0" cy="8" rx="34" ry="30" fill="#7CC36A"/>'
            f'<ellipse cx="-12" cy="4" rx="20" ry="28" fill="#A9DB8C"/>'
            f'<ellipse cx="12" cy="4" rx="20" ry="28" fill="#93D17A"/>'
            f'<ellipse cx="0" cy="0" rx="14" ry="30" fill="#E9F7D9"/>'
            f'<path d="M0,-28 C-3,-5 -3,20 0,36" stroke="#C7E6B0" stroke-width="2.5" fill="none"/>'
            f'<path d="M-30,10 C-20,30 20,30 30,10" stroke="#5DA850" stroke-width="3" fill="none"/>')


def radish(c):
    return (f'<path d="M-8,-30 C-20,-50 -26,-44 -20,-34 M0,-32 C0,-56 8,-56 6,-34 M8,-30 C22,-48 28,-40 18,-30" stroke="#5DA850" stroke-width="6" stroke-linecap="round" fill="none"/>'
            f'<path d="M-18,-30 C-22,0 -12,30 0,44 C12,30 22,0 18,-30 Z" fill="#F6F3EA" stroke="#D9D2BF" stroke-width="2"/>'
            f'<path d="M-17,-28 C-14,-20 14,-20 17,-28" fill="#BFE3A6"/>'
            f'<path d="M-8,0 h6 M4,12 h6 M-6,24 h5" stroke="#D9D2BF" stroke-width="2" stroke-linecap="round"/>')


def onion(c):
    return (f'<path d="M0,-40 C4,-26 34,-14 32,12 C30,34 12,40 0,40 C-12,40 -30,34 -32,12 C-34,-14 -4,-26 0,-40 Z" fill="#D9A56B"/>'
            f'<path d="M0,-38 C-2,-20 -14,0 -12,36 M0,-38 C2,-20 14,0 12,36 M0,-38 V38" stroke="#B9844C" stroke-width="2" fill="none"/>'
            f'<path d="M-2,-40 C-4,-50 4,-52 2,-40" stroke="#8C6A3F" stroke-width="3" fill="none"/>'
            f'<path d="M-6,40 l-4,8 M0,40 v9 M6,40 l4,8" stroke="#B9844C" stroke-width="2"/>')


def garlic(c):
    return (f'<path d="M0,-40 C2,-30 6,-26 12,-22 C34,-12 36,20 22,34 C12,42 -12,42 -22,34 C-36,20 -34,-12 -12,-22 C-6,-26 -2,-30 0,-40 Z" fill="#F7F1E6" stroke="#DCCFB8" stroke-width="2"/>'
            f'<path d="M0,-20 C-8,0 -8,24 0,40 M0,-20 C8,0 8,24 0,40 M-14,-14 C-24,6 -20,28 -12,38 M14,-14 C24,6 20,28 12,38" stroke="#E2D5BF" stroke-width="2" fill="none"/>'
            f'<path d="M-4,-40 h8" stroke="#C9B48F" stroke-width="3" stroke-linecap="round"/>')


def pepper(c):
    return (f'<path d="M-6,-34 C-14,-44 -6,-52 4,-46" stroke="#4E8A3A" stroke-width="5" stroke-linecap="round" fill="none"/>'
            f'<path d="M-12,-34 C-4,-40 12,-38 16,-30 C22,-8 14,22 -8,44 C-10,46 -12,44 -10,40 C2,16 -2,-10 -16,-24 C-20,-28 -18,-32 -12,-34 Z" fill="{c["red"]}"/>'
            f'<path d="M6,-28 C12,-14 10,6 2,22" stroke="#F08A74" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.7"/>')


ICONS = [("배추", cabbage), ("무", radish), ("양파", onion), ("깐마늘", garlic), ("건고추", pepper)]


def defs(c, key):
    return (f'<defs>'
            f'<linearGradient id="bg{key}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["bg1"]}"/><stop offset="1" stop-color="{c["bg2"]}"/></linearGradient>'
            f'<linearGradient id="tt{key}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["title1"]}"/><stop offset="1" stop-color="{c["title2"]}"/></linearGradient>'
            f'<linearGradient id="gl{key}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["glass"]}" stop-opacity="0.95"/><stop offset="1" stop-color="{c["glass"]}" stop-opacity="0.55"/></linearGradient>'
            f'<filter id="sh{key}" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="{c["shadow"]}" flood-opacity="0.14"/></filter>'
            f'</defs>')


# ---------- hero banner ----------
def banner(c, key):
    W, H = 1280, 500
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="IMPACT Lab — 경계를 지키는 농산물 가격 예보">', defs(c, key)]
    s.append(f'<clipPath id="cl{key}"><rect width="{W}" height="{H}" rx="28"/></clipPath><g clip-path="url(#cl{key})">')
    s.append(f'<rect width="{W}" height="{H}" fill="url(#bg{key})"/>')
    # teal waves (poster-like)
    s.append(f'<path d="M560,{H} C760,420 900,440 1040,360 C1140,300 1210,250 {W},230 L{W},{H} Z" fill="{c["wave2"]}" opacity="0.9"/>')
    s.append(f'<path d="M680,{H} C840,456 980,470 1110,410 C1190,372 1240,340 {W},330 L{W},{H} Z" fill="{c["wave"]}"/>')
    # soft blobs
    s.append(f'<circle cx="1180" cy="70" r="120" fill="{c["glass"]}" opacity="0.25"/><circle cx="520" cy="-40" r="140" fill="{c["glass"]}" opacity="0.18"/>')
    # glass chart panel (rising line, dashed forecast after D)
    px, py, pw, ph = 770, 70, 400, 220
    s.append(f'<g filter="url(#sh{key})" transform="rotate(-4 {px+pw/2} {py+ph/2})">')
    s.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="20" fill="url(#gl{key})" stroke="{c["stroke"]}" stroke-width="2"/>')
    pts = []
    for i in range(25):
        x = px + 28 + i * 13.5
        y = py + ph - 46 - i * 4.2 - 16 * math.sin(i / 2.2) - 6 * math.sin(i * 1.7)
        pts.append((x, y))
    hist = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts[:17])
    fut = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts[16:])
    s.append(f'<path d="{hist} L{pts[16][0]:.1f},{py+ph-24} L{pts[0][0]:.1f},{py+ph-24} Z" fill="{c["accent"]}" opacity="0.12"/>')
    s.append(f'<path d="{hist}" fill="none" stroke="{c["accent"]}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
    s.append(f'<path d="{fut}" fill="none" stroke="{c["straw"]}" stroke-width="4" stroke-dasharray="3 9" stroke-linecap="round"/>')
    dx = pts[16][0]
    s.append(f'<line x1="{dx:.1f}" y1="{py+26}" x2="{dx:.1f}" y2="{py+ph-24}" stroke="{c["muted"]}" stroke-width="1.5" stroke-dasharray="4 5"/>')
    s.append(f'<circle cx="{dx:.1f}" cy="{pts[16][1]:.1f}" r="7" fill="{c["glass"]}" stroke="{c["accent"]}" stroke-width="3"/>')
    s.append(f'<text x="{dx-8:.1f}" y="{py+40}" text-anchor="end" font-family="{MONO}" font-size="13" fill="{c["muted"]}">관측 &lt; D</text>')
    s.append(f'<text x="{dx+8:.1f}" y="{py+40}" font-family="{MONO}" font-size="13" fill="{c["straw"]}">예측 →</text>')
    for k, (lx, label) in enumerate([(px + 28, "2020"), (dx - 40, "2024"), (px + pw - 70, "D+3순")]):
        s.append(f'<text x="{lx:.1f}" y="{py+ph-8}" font-family="{MONO}" font-size="11" fill="{c["muted"]}">{label}</text>')
    s.append('</g>')
    # vegetables along the wave
    pos = [(800, 420, 1.15, -6), (905, 398, 1.0, 8), (1010, 420, 1.0, -4), (1105, 408, 0.95, 6), (1200, 400, 1.0, 14)]
    for (name, fn), (x, y, sc, rot) in zip(ICONS, pos):
        s.append(f'<g transform="translate({x},{y}) rotate({rot}) scale({sc})" filter="url(#sh{key})">{fn(c)}</g>')
    # left text
    s.append(f'<rect x="60" y="54" width="300" height="32" rx="16" fill="{c["chip"]}" stroke="{c["stroke"]}"/>')
    s.append(f'<text x="80" y="76" font-family="{FONT}" font-size="15" font-weight="700" fill="{c["accent"]}">IMPACT Lab · 본선 최종 제출 모델</text>')
    s.append(f'<text x="62" y="128" font-family="{FONT}" font-size="22" font-weight="700" fill="{c["ink"]}">2026 AI 농산물 가격예측 온라인 해커톤</text>')
    for txt, y in (("경계를 지키는", 196), ("농산물 가격 예보", 262)):
        s.append(f'<text x="64" y="{y+4}" font-family="{FONT}" font-size="58" font-weight="900" fill="{c["shadow"]}" opacity="0.18">{txt}</text>')
        s.append(f'<text x="60" y="{y}" font-family="{FONT}" font-size="58" font-weight="900" fill="url(#tt{key})">{txt}</text>')
    s.append(f'<text x="62" y="304" font-family="{FONT}" font-size="19" fill="{c["muted"]}">2020–2024로만 배우고, 기준일 이전만 읽는 5품목 · 3트랙 예측</text>')
    x = 60
    for label, val in (("10일 예측", "9.12%"), ("2순 후", "11.46%"), ("3순 후", "10.84%")):
        s.append(f'<g filter="url(#sh{key})"><rect x="{x}" y="336" width="164" height="92" rx="18" fill="{c["card"]}" fill-opacity="{c["glass_op"]}" stroke="{c["stroke"]}"/></g>')
        s.append(f'<text x="{x+18}" y="366" font-family="{FONT}" font-size="14" fill="{c["muted"]}">{label} · MAPE</text>')
        s.append(f'<text x="{x+18}" y="408" font-family="{FONT}" font-size="32" font-weight="900" fill="{c["accent"]}">{val}</text>')
        x += 178
    s.append(f'<text x="62" y="466" font-family="{MONO}" font-size="12" fill="{c["muted"]}">종합 9.73% · naive 12.07% 대비 −2.34pt · hackathon-ensemble-v11-zero</text>')
    s.append('</g></svg>')
    return "\n".join(s)


# ---------- item cards ----------
ITEMS = [
    ("배추", "10kg", "×2.0", "et + 감쇠·앵커", "HGB pooled_mw", "설날·추석 배율"),
    ("무", "20kg", "×2.0", "6항 로그 혼합", "ET 산지 기상", "추석·설날 배율"),
    ("양파", "1kg", "×2.0", "h1last · 거리별 ET", "3항 혼합 / clip", "—"),
    ("깐마늘", "1kg", "×1.2", "last", "last", "변동 0.1–0.4%"),
    ("건고추", "600g", "×1.2", "last", "last", "변동 0.1–0.4%"),
]


def items(c, key):
    W, H = 1280, 300
    cw, gap, x0 = 232, 15, 22
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="예측 대상 5품목">', defs(c, key)]
    for i, ((name, fn), (_, unit, w, short, long_, note)) in enumerate(zip(ICONS, ITEMS)):
        x = x0 + i * (cw + gap)
        s.append(f'<g filter="url(#sh{key})"><rect x="{x}" y="14" width="{cw}" height="{H-34}" rx="22" fill="{c["card"]}" stroke="{c["stroke"]}"/></g>')
        s.append(f'<rect x="{x}" y="14" width="{cw}" height="112" rx="22" fill="url(#bg{key})"/><rect x="{x}" y="104" width="{cw}" height="22" fill="url(#bg{key})"/>')
        s.append(f'<g transform="translate({x+cw/2},{72}) scale(0.95)">{fn(c)}</g>')
        s.append(f'<text x="{x+20}" y="160" font-family="{FONT}" font-size="22" font-weight="800" fill="{c["ink"]}">{name}</text>')
        s.append(f'<text x="{x+cw-20}" y="160" text-anchor="end" font-family="{MONO}" font-size="13" fill="{c["muted"]}">{unit} · 가중 {w}</text>')
        s.append(f'<line x1="{x+20}" y1="174" x2="{x+cw-20}" y2="174" stroke="{c["line"]}"/>')
        for j, (lab, val) in enumerate((("10일", short), ("2·3순", long_), ("특이", note))):
            y = 200 + j * 26
            s.append(f'<text x="{x+20}" y="{y}" font-family="{FONT}" font-size="12.5" font-weight="700" fill="{c["accent"]}">{lab}</text>')
            s.append(f'<text x="{x+66}" y="{y}" font-family="{FONT}" font-size="13" fill="{c["ink"]}">{html.escape(val)}</text>')
    s.append('</svg>')
    return "\n".join(s)


# ---------- timeline ----------
EVENTS = [("09.07", "참가 신청", "아이디어 기술서 접수"), ("10.18", "예선 마감", "‘네 번째 신호’ 제출"),
          ("10.23", "본선 진출", "15팀 선발"), ("10.26 – 11.08", "본선", "4파일 × 3트랙 제출"),
          ("11.09 – 11.12", "재현 검증", "원본 추론 · 재학습"), ("11.20", "시상", "잠정")]


def timeline(c, key):
    W, H = 1280, 210
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="대회 일정">', defs(c, key)]
    s.append(f'<rect width="{W}" height="{H}" rx="24" fill="url(#bg{key})"/>')
    x0, x1, y = 90, 1190, 92
    s.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{c["stroke"]}" stroke-width="4" stroke-linecap="round"/>')
    done = 4
    step = (x1 - x0) / (len(EVENTS) - 1)
    s.append(f'<line x1="{x0}" y1="{y}" x2="{x0+step*(done-0.5):.1f}" y2="{y}" stroke="{c["accent"]}" stroke-width="4" stroke-linecap="round"/>')
    for i, (d, t, sub) in enumerate(EVENTS):
        x = x0 + i * step
        filled = i < done
        s.append(f'<circle cx="{x:.1f}" cy="{y}" r="13" fill="{c["accent"] if filled else c["card"]}" stroke="{c["accent"]}" stroke-width="3"/>')
        if filled:
            s.append(f'<path d="M{x-5:.1f},{y} l3.5,4 l7,-8" stroke="{c["card"]}" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        if i == done:
            s.append(f'<circle cx="{x:.1f}" cy="{y}" r="21" fill="none" stroke="{c["straw"]}" stroke-width="2" stroke-dasharray="3 4"/>')
        s.append(f'<text x="{x:.1f}" y="{y-30}" text-anchor="middle" font-family="{MONO}" font-size="14" font-weight="700" fill="{c["muted"]}">{d}</text>')
        s.append(f'<text x="{x:.1f}" y="{y+46}" text-anchor="middle" font-family="{FONT}" font-size="18" font-weight="800" fill="{c["ink"]}">{t}</text>')
        s.append(f'<text x="{x:.1f}" y="{y+70}" text-anchor="middle" font-family="{FONT}" font-size="13" fill="{c["muted"]}">{html.escape(sub)}</text>')
    s.append(f'<text x="{W-40}" y="{H-18}" text-anchor="end" font-family="{FONT}" font-size="12" fill="{c["muted"]}">2026 · 한국 시간 기준</text>')
    s.append('</svg>')
    return "\n".join(s)


# ---------- results chart ----------
def results(c, key):
    W, H = 1280, 420
    rows = [("10일 예측", "70%", 10.20, 9.1231), ("2순 후", "15%", 15.73, 11.4627), ("3순 후", "15%", 17.14, 10.8410), ("종합", "가중", 12.07, 9.7317)]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="본선 MAPE와 naive 비교">', defs(c, key)]
    s.append(f'<rect width="{W}" height="{H}" rx="24" fill="url(#bg{key})"/>')
    s.append(f'<text x="48" y="58" font-family="{FONT}" font-size="24" font-weight="800" fill="{c["ink"]}">본선 MAPE — 최근값 유지(naive) 대비</text>')
    s.append(f'<text x="48" y="86" font-family="{FONT}" font-size="14" fill="{c["muted"]}">낮을수록 좋음 · 모델 = 본선 리더보드 최고 기록 · naive = 같은 12개 기준일 자체 채점</text>')
    s.append(f'<rect x="{W-300}" y="42" width="16" height="16" rx="4" fill="{c["naive"]}"/><text x="{W-276}" y="55" font-family="{FONT}" font-size="14" fill="{c["muted"]}">naive</text>')
    s.append(f'<rect x="{W-200}" y="42" width="16" height="16" rx="4" fill="{c["accent"]}"/><text x="{W-176}" y="55" font-family="{FONT}" font-size="14" fill="{c["muted"]}">v11-zero</text>')
    x0, x1, vmax = 250, 1020, 18
    sx = lambda v: x0 + (x1 - x0) * v / vmax
    for v in range(0, 19, 3):
        s.append(f'<line x1="{sx(v):.1f}" y1="112" x2="{sx(v):.1f}" y2="{H-50}" stroke="{c["line"]}"/>')
        s.append(f'<text x="{sx(v):.1f}" y="{H-26}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{c["muted"]}">{v}%</text>')
    y = 122
    for label, wt, nv, mv in rows:
        last = label == "종합"
        if last:
            s.append(f'<rect x="30" y="{y-6}" width="{W-60}" height="64" rx="14" fill="{c["card"]}" fill-opacity="0.6"/>')
        s.append(f'<text x="48" y="{y+24}" font-family="{FONT}" font-size="18" font-weight="{900 if last else 700}" fill="{c["ink"]}">{label}</text>')
        s.append(f'<text x="48" y="{y+44}" font-family="{MONO}" font-size="12" fill="{c["muted"]}">비중 {wt}</text>')
        s.append(f'<rect x="{x0}" y="{y+2}" width="{sx(nv)-x0:.1f}" height="18" rx="9" fill="{c["naive"]}"/>')
        s.append(f'<text x="{sx(nv)+10:.1f}" y="{y+16}" font-family="{MONO}" font-size="13" fill="{c["muted"]}">{nv:.2f}</text>')
        s.append(f'<rect x="{x0}" y="{y+26}" width="{sx(mv)-x0:.1f}" height="22" rx="11" fill="{c["accent"]}"/>')
        s.append(f'<text x="{sx(mv)+10:.1f}" y="{y+43}" font-family="{MONO}" font-size="15" font-weight="800" fill="{c["accent"]}">{mv:.2f}</text>')
        pct = (nv - mv) / nv * 100
        s.append(f'<rect x="{W-210}" y="{y+8}" width="170" height="36" rx="18" fill="{c["chip"]}" stroke="{c["stroke"]}"/>')
        s.append(f'<text x="{W-125}" y="{y+32}" text-anchor="middle" font-family="{FONT}" font-size="15" font-weight="800" fill="{c["accent"]}">−{nv-mv:.2f}pt · −{pct:.0f}%</text>')
        y += 66
    s.append('</svg>')
    return "\n".join(s)


for key, c in T.items():
    for name, fn in (("banner", banner), ("items", items), ("timeline", timeline), ("results", results)):
        open(f"{OUT}/{name}-{key}.svg", "w", encoding="utf-8").write(fn(c, key))
print("ok")


# ---------- team avatars ----------
MEMBERS = [("park-jun", "박", "#12805A", "#5FD3A0"), ("max", "M", "#0E5B52", "#C98E52"), ("lee-yeongyu", "이", "#C98E52", "#12805A")]


def avatar(initial, a, b, slug):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160" role="img" aria-label="{initial}">'
            f'<defs><linearGradient id="g{slug}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>'
            f'<circle cx="80" cy="80" r="76" fill="url(#g{slug})"/><circle cx="80" cy="80" r="76" fill="none" stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="4"/>'
            f'<path d="M24,110 C60,92 100,128 136,104" stroke="#FFFFFF" stroke-opacity="0.18" stroke-width="10" fill="none" stroke-linecap="round"/>'
            f'<text x="80" y="101" text-anchor="middle" font-family="{FONT}" font-size="64" font-weight="900" fill="#FFFFFF">{initial}</text></svg>')


for slug, initial, a, b in MEMBERS:
    open(f"{OUT}/avatar-{slug}.svg", "w", encoding="utf-8").write(avatar(initial, a, b, slug))
