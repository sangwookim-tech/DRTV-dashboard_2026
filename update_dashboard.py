"""
DRTV 대시보드 자동 업데이트 스크립트
--------------------------------------
사용법:
  python update_dashboard.py

  - data/ 폴더 안의 모든 CSV를 읽어 index.html을 자동 갱신합니다.
  - CSV 파일명은 무관하며, 여러 달치를 함께 넣어도 됩니다.
  - 월별로 데이터를 분리해 MONTHS_DATA 구조로 출력합니다.

폴더 구조:
  drtv-dashboard/
  ├── index.html              ← 대시보드 (자동 갱신)
  ├── update_dashboard.py     ← 이 스크립트
  └── data/                   ← CSV 파일 넣는 폴더
      ├── DRTV일별효율_20260329_DATA.csv
      └── DRTV일별효율_20260330_DATA.csv
"""

import csv
import re
import os
import sys
from collections import defaultdict
from datetime import datetime

# ── 설정 ─────────────────────────────────
CSV_FOLDER  = "data"        # CSV 파일 폴더
TEMPLATE    = "index.html"  # 입력 HTML (덮어쓰기)
OUTPUT      = "index.html"  # 출력 HTML
# ─────────────────────────────────────────

SVC_CHANNELS = {"JTBC2 (SVC)", "SPOTV G&H (SVC)", "히스토리 (SVC)", "기타 TV채널", "발신", "애니원_애니박스 (SVC)"}
SVC_ORDER    = ["발신", "히스토리 (SVC)", "SPOTV G&H (SVC)", "JTBC2 (SVC)", "애니원_애니박스 (SVC)", "기타 TV채널"]
WEEKDAYS     = ["월", "화", "수", "목", "금", "토", "일"]


def to_num(s):
    if not s:
        return 0.0
    s = re.sub(r"[,\s%]", "", str(s))
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_js_obj(obj):
    """Python dict → JS 객체 리터럴"""
    parts = []
    for k, v in obj.items():
        if isinstance(v, str):
            parts.append(f'{k}:"{v}"')
        else:
            parts.append(f"{k}:{v}")
    return "{" + ",".join(parts) + "}"


def load_csvs(folder):
    rows = []
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".csv"))
    if not files:
        print(f"[오류] {folder}/ 폴더에 CSV 파일이 없습니다.")
        sys.exit(1)
    for fname in files:
        path = os.path.join(folder, fname)
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append(r)
        print(f"  로드: {fname}")
    print(f"  → 총 {len(rows)}행 ({len(files)}개 파일)")
    return rows


def group_by_month(rows):
    """rows를 월별로 그룹핑 → {"2026-03": [...], "2026-04": [...]}"""
    grouped = defaultdict(list)
    for r in rows:
        d_str = r.get("상담일자", "").strip()
        try:
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            key = dt.strftime("%Y-%m")
            grouped[key].append(r)
        except ValueError:
            continue
    return dict(sorted(grouped.items()))


def build_daily(rows):
    agg = defaultdict(lambda: {
        "광고비": 0, "광고횟수": 0, "인입콜": 0, "응대콜": 0,
        "정기건수": 0, "정기금액": 0, "일시금액": 0,
    })
    for r in rows:
        d_str = r.get("상담일자", "").strip()
        try:
            dt  = datetime.strptime(d_str, "%Y-%m-%d")
            key = f"{dt.month}/{dt.day}"
        except ValueError:
            continue
        a = agg[key]
        a["_dt"]      = dt
        a["요일"]     = WEEKDAYS[dt.weekday()]
        a["광고비"]   += to_num(r.get("광고비"))
        a["광고횟수"] += to_num(r.get("광고횟수"))
        a["인입콜"]   += to_num(r.get("I/B콜수"))
        a["응대콜"]   += to_num(r.get("응대호"))
        a["정기건수"] += to_num(r.get("정기건수"))
        a["정기금액"] += to_num(r.get("정기금액"))
        raw_isi = r.get("일시금액", "").strip()
        a["일시금액"] += to_num(raw_isi) if raw_isi not in ("", "-") else 0

    result = []
    for key, v in sorted(agg.items(), key=lambda x: x[1]["_dt"]):
        ad   = v["광고비"]
        inc  = v["인입콜"]
        resp = v["응대콜"]
        reg  = v["정기건수"]
        jg   = v["정기금액"]
        roi  = round((jg * 12) / ad, 2)       if ad   else 0
        cpr  = round(ad / inc)                 if inc  else 0
        cpa  = round(ad / (jg / 20000))        if jg   else 0
        응대율  = round(resp / inc  * 100, 1)  if inc  else 0
        전환율  = round(reg  / resp * 100, 1)  if resp else 0
        result.append({
            "date":   key,
            "요일":   v["요일"],
            "광고비": int(ad),
            "송출":   0,
            "인입콜": int(inc),
            "응대콜": int(resp),
            "정기건수": int(reg),
            "정기금액": int(jg),
            "일시금액": int(v["일시금액"]),
            "총후원금": int(jg + v["일시금액"]),
            "ROI":   roi,
            "CPR":   cpr,
            "CPA":   cpa,
            "응대율":  응대율,
            "전환율":  전환율,
        })
    return result


def build_channel(rows):
    agg = defaultdict(lambda: {
        "광고비": 0, "광고횟수": 0, "인입콜": 0,
        "응대콜": 0, "정기건수": 0, "정기금액": 0,
    })
    for r in rows:
        ch = r.get("Channel", "").strip()
        if not ch or ch in SVC_CHANNELS:
            continue
        a = agg[ch]
        a["광고비"]   += to_num(r.get("광고비"))
        a["광고횟수"] += to_num(r.get("광고횟수"))
        a["인입콜"]   += to_num(r.get("I/B콜수"))
        a["응대콜"]   += to_num(r.get("응대호"))
        a["정기건수"] += to_num(r.get("정기건수"))
        a["정기금액"] += to_num(r.get("정기금액"))

    result = []
    for ch, v in sorted(agg.items(),
                        key=lambda x: -(x[1]["정기금액"] * 12 / x[1]["광고비"]
                                        if x[1]["광고비"] else 0)):
        ad   = v["광고비"]
        cnt  = v["광고횟수"]
        inc  = v["인입콜"]
        resp = v["응대콜"]
        reg  = v["정기건수"]
        jg   = v["정기금액"]
        roi  = round((jg * 12) / ad, 2)       if ad   else 0
        cpr  = round(ad / inc)                 if inc  else 0
        cpa  = round(ad / (jg / 20000))        if jg   else 0
        응대율    = round(resp / inc  * 100, 1) if inc  else 0
        콜전환율  = round(inc  / cnt  * 100, 1) if cnt  else 0
        정기전환율 = round(reg  / resp * 100, 1) if resp else 0
        result.append({
            "ch":   ch,
            "광고비": int(ad),
            "인입콜": int(inc),
            "응대콜": int(resp),
            "정기건수": int(reg),
            "정기금액": int(jg),
            "ROI":   roi,
            "CPR":   cpr,
            "CPA":   cpa,
            "응대율":    응대율,
            "콜전환율":  콜전환율,
            "정기전환율": 정기전환율,
        })
    return result


def build_other(rows):
    agg = defaultdict(lambda: {
        "인입콜": 0, "응대콜": 0, "정기건수": 0, "정기금액": 0, "days": set(),
    })
    for r in rows:
        ch = r.get("Channel", "").strip()
        if ch not in SVC_CHANNELS:
            continue
        a   = agg[ch]
        inc = to_num(r.get("I/B콜수"))
        a["인입콜"]   += inc
        a["응대콜"]   += to_num(r.get("응대호"))
        a["정기건수"] += to_num(r.get("정기건수"))
        a["정기금액"] += to_num(r.get("정기금액"))
        if inc > 0:
            a["days"].add(r.get("상담일자", ""))

    result = []
    for ch in SVC_ORDER:
        if ch not in agg:
            continue
        v    = agg[ch]
        inc  = v["인입콜"]
        resp = v["응대콜"]
        응대율 = round(resp / inc * 100, 1) if inc else 0
        result.append({
            "ch":     ch,
            "인입콜":   int(inc),
            "응대콜":   int(resp),
            "정기건수": int(v["정기건수"]),
            "정기금액": int(v["정기금액"]),
            "유효일수": len(v["days"]),
            "응대율":   응대율,
        })
    return result


def build_material(rows):
    agg = defaultdict(lambda: {
        "광고비": 0, "광고횟수": 0, "인입콜": 0,
        "응대콜": 0, "정기건수": 0, "정기금액": 0,
    })
    for r in rows:
        mat = r.get("소재", "").strip()
        if not mat or mat == "-":
            continue
        a = agg[mat]
        a["광고비"]   += to_num(r.get("광고비"))
        a["광고횟수"] += to_num(r.get("광고횟수"))
        a["인입콜"]   += to_num(r.get("I/B콜수"))
        a["응대콜"]   += to_num(r.get("응대호"))
        a["정기건수"] += to_num(r.get("정기건수"))
        a["정기금액"] += to_num(r.get("정기금액"))

    result = []
    for mat, v in sorted(agg.items(), key=lambda x: -x[1]["정기금액"]):
        ad   = v["광고비"]
        inc  = v["인입콜"]
        resp = v["응대콜"]
        reg  = v["정기건수"]
        jg   = v["정기금액"]
        roi  = round((jg * 12) / ad, 2)  if ad   else 0
        cpr  = round(ad / inc)            if inc  else 0
        cpa  = round(ad / (jg / 20000))   if jg   else 0
        응대율 = round(resp / inc * 100, 1) if inc  else 0
        result.append({
            "name":   mat,
            "정기건수": int(reg),
            "인입콜":   int(inc),
            "응대콜":   int(resp),
            "ROI":   roi,
            "CPR":   cpr,
            "CPA":   cpa,
            "응대율":  응대율,
            "광고비":   int(ad),
            "정기금액": int(jg),
        })
    return result


def build_kpi(channel_list, other_list, daily_list):
    total_ad  = sum(c["광고비"]   for c in channel_list)
    total_inc = (sum(c["인입콜"]  for c in channel_list)
               + sum(o["인입콜"]  for o in other_list))
    total_reg = (sum(c["정기건수"] for c in channel_list)
               + sum(o["정기건수"] for o in other_list))
    total_jg  = (sum(c["정기금액"] for c in channel_list)
               + sum(o["정기금액"] for o in other_list))
    total_resp= (sum(c["응대콜"]  for c in channel_list)
               + sum(o["응대콜"]  for o in other_list))
    roi  = round((total_jg * 12) / total_ad, 2)     if total_ad  else 0
    cpr  = round(total_ad / total_inc)               if total_inc else 0
    cpa  = round(total_ad / (total_jg / 20000))      if total_jg  else 0
    resp = round(total_resp / total_inc * 100, 1)    if total_inc else 0
    return {
        "총광고비":   total_ad,
        "총인입콜":   total_inc,
        "총정기건수": total_reg,
        "총정기금액": total_jg,
        "ROI":   roi,
        "CPR":   cpr,
        "CPA":   cpa,
        "평균응대율": resp,
    }


def build_months_js(months_data):
    """월별 데이터 dict → JS MONTHS_DATA 리터럴 문자열"""
    month_parts = []
    for month_key, data in sorted(months_data.items()):
        daily_js    = "[\n"    + ",\n".join(" " + to_js_obj(d) for d in data["daily"])    + "\n]"
        channel_js  = "[\n"    + ",\n".join(" " + to_js_obj(c) for c in data["channel"])  + "\n]"
        other_js    = "[\n"    + ",\n".join(" " + to_js_obj(o) for o in data["other"])    + "\n]"
        material_js = "[\n"    + ",\n".join(" " + to_js_obj(m) for m in data["material"]) + "\n]"
        kpi_js      = to_js_obj(data["kpi"])
        month_parts.append(
            f'"{month_key}":'
            + '{daily:' + daily_js
            + ',channel:' + channel_js
            + ',other:' + other_js
            + ',material:' + material_js
            + ',kpi:' + kpi_js
            + '}'
        )
    return "const MONTHS_DATA={" + ",\n".join(month_parts) + "};"


def update_html(months_js, template, output):
    with open(template, encoding="utf-8") as f:
        html = f.read()

    # MONTHS_DATA 블록 교체
    html = re.sub(r"const MONTHS_DATA=\{[\s\S]*?\};\nlet DAILY",
                  months_js + "\nlet DAILY",
                  html)

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    csv_folder = sys.argv[1] if len(sys.argv) > 1 else CSV_FOLDER
    template   = sys.argv[2] if len(sys.argv) > 2 else TEMPLATE
    output     = sys.argv[3] if len(sys.argv) > 3 else OUTPUT

    print(f"\n[1] CSV 로드 중 ({csv_folder}/)")
    rows = load_csvs(csv_folder)

    print("[2] 월별 데이터 집계 중...")
    grouped = group_by_month(rows)
    months_data = {}
    for month_key, month_rows in grouped.items():
        daily    = build_daily(month_rows)
        channel  = build_channel(month_rows)
        other    = build_other(month_rows)
        material = build_material(month_rows)
        kpi      = build_kpi(channel, other, daily)
        months_data[month_key] = {
            "daily": daily, "channel": channel,
            "other": other, "material": material, "kpi": kpi,
        }
        print(f"  {month_key}: {len(daily)}일, 광고비 ₩{kpi['총광고비']:,}, ROI {kpi['ROI']}")

    print("[3] HTML 업데이트 중...")
    months_js = build_months_js(months_data)
    update_html(months_js, template, output)

    print(f"\n✅ 완료! → {output}")
    print(f"   포함된 월: {', '.join(sorted(months_data.keys()))}")
    for mk, data in sorted(months_data.items()):
        kpi = data["kpi"]
        daily = data["daily"]
        period = f"{daily[0]['date']}~{daily[-1]['date']}" if daily else "-"
        print(f"   [{mk}] {period} | 총광고비 ₩{kpi['총광고비']:,} | ROI {kpi['ROI']} | 정기건수 {kpi['총정기건수']}건")


if __name__ == "__main__":
    main()
