# -*- coding: utf-8 -*-
"""
월별 미세먼지 농도 증가 지역 분석 (Streamlit, GitHub 데이터 버전)

data2 파일 구조: 행 = 지역(구분(1), 구분(2)), 열 = 월(예: 202503, 2025.03)

실행 방법 (cmd):
    cd Desktop
    streamlit run dust_github_app.py

배포: dust_github_app.py, requirements.txt, data2.csv 를 GitHub 저장소에 올리고
      Streamlit Community Cloud에서 dust_github_app.py 를 선택
"""
import io
import re
import urllib.request
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="월별 미세먼지 분석", layout="wide")
st.title("🌫️ 월별 미세먼지 농도 증가 지역 분석")


# ------------------------------------------------------------------
# 1. GitHub에 있는 data2 파일 자동으로 불러오기
# ------------------------------------------------------------------
# ★ 여기를 내 GitHub 파일 주소로 바꾸세요 (github.com 주소를 그대로 붙여넣어도 됩니다)
#   예) https://github.com/내아이디/2026dataWeb/blob/main/data2.csv
GITHUB_URL = "https://raw.githubusercontent.com/내아이디/2026dataWeb/main/data2.csv"


def to_raw_url(url):
    """github.com/.../blob/... 주소를 raw 주소로 바꿈"""
    url = url.strip()
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


def decode_bytes(b):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 읽을 수 없습니다.")


def read_table(data, name):
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), dtype=str)
    return pd.read_csv(io.StringIO(decode_bytes(data)), dtype=str)


@st.cache_data(ttl=600)
def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def local_file():
    """이 파이썬 파일과 같은 폴더(GitHub 저장소)에 있는 data2* 파일"""
    try:
        folder = Path(__file__).resolve().parent
    except NameError:
        folder = Path.cwd()
    found = [p for p in folder.glob("data2*")
             if p.is_file() and p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0] if found else None


st.sidebar.header("데이터 주소")
url_in = st.sidebar.text_input("GitHub 파일 주소", value=GITHUB_URL)
url = to_raw_url(url_in)

raw, source = None, ""
if url and "내아이디" not in url:
    try:
        raw = read_table(download(url), url.split("?")[0])
        source = f"GitHub: {url}"
    except Exception as e:
        st.warning(f"GitHub에서 파일을 불러오지 못했습니다. 주소와 저장소 공개 여부를 확인하세요. ({e})")

if raw is None:
    p = local_file()
    if p is not None:
        raw = read_table(p.read_bytes(), p.name)
        source = f"같은 폴더의 파일: {p.name}"

if raw is None:
    st.info("GitHub 주소가 설정되지 않았거나 파일을 찾지 못했습니다. "
            "사이드바에 주소를 입력하거나 아래에서 파일을 올려주세요.")
    up = st.file_uploader("data2 파일 업로드", type=["csv", "xlsx", "xls"])
    if up is None:
        st.stop()
    raw = read_table(up.getvalue(), up.name)
    source = f"업로드한 파일: {up.name}"

st.caption(f"📂 {source}")

# ------------------------------------------------------------------
# 2. 월 열 찾기 + 숫자 칸 정리
# ------------------------------------------------------------------
MONTH_RE = re.compile(r"^\s*(\d{4})\s*[.\-/년]?\s*(\d{1,2})\s*월?\s*$")


def month_label(col):
    m = MONTH_RE.match(str(col))
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return None


month_cols = [c for c in raw.columns if month_label(c)]
label_cols = [c for c in raw.columns if c not in month_cols]

if not month_cols:
    st.error("월 형태(예: 202503, 2025.03)의 열을 찾지 못했습니다. 열 이름: " + ", ".join(map(str, raw.columns)))
    st.stop()
if len(month_cols) < 2:
    st.error("월이 2개 이상 있어야 증가 여부를 분석할 수 있습니다.")
    st.stop()


def to_number(s):
    """'31*' -> 31, '-' -> 빈칸(NaN)"""
    return pd.to_numeric(s.astype(str).str.extract(r"(\d+(?:\.\d+)?)", expand=False),
                         errors="coerce")


clean = raw.copy()
fixed_cells = 0
for c in month_cols:
    before = pd.to_numeric(raw[c], errors="coerce")
    fixed_cells += int((before.isna() & raw[c].notna()).sum())
    clean[c] = to_number(raw[c])

st.subheader("1. 데이터 표")
st.write(f"행 {len(clean):,}개 × 열 {len(clean.columns)}개")
if fixed_cells:
    st.caption(f"숫자 칸에 문자(*, - 등)가 있던 {fixed_cells}칸을 자동으로 정리했습니다. "
               "('-'처럼 숫자가 없는 칸은 빈칸으로 처리)")
st.dataframe(clean)

# ------------------------------------------------------------------
# 3. 지역 정보 만들기 (시도 / 지역명 / 구분)
# ------------------------------------------------------------------
months = [month_label(c) for c in month_cols]

if len(label_cols) >= 2:
    l1 = clean[label_cols[0]].fillna("").astype(str).str.strip()
    l2 = clean[label_cols[1]].fillna("").astype(str).str.strip()
elif len(label_cols) == 1:
    l1 = clean[label_cols[0]].fillna("").astype(str).str.strip()
    l2 = l1.copy()
else:
    l1 = pd.Series([f"행{i + 1}" for i in range(len(clean))], index=clean.index)
    l2 = l1.copy()

name = l1.where(l1 == l2, l1 + " " + l2)
kind = pd.Series("지역", index=clean.index)
kind[l1.isin(["총계", "전국", "합계"]) | l2.isin(["소계", "총계", "합계"])] = "총계"
kind[l2.str.contains("평균")] = "평균"

info = pd.DataFrame({"시도": l1, "지역": name, "구분": kind})
values = clean[month_cols].copy()
values.columns = months
table = pd.concat([info, values], axis=1)

# 같은 이름이 있으면 번호를 붙여 구분
dup = table["지역"].duplicated(keep=False)
if dup.any():
    table.loc[dup, "지역"] = table.loc[dup, "지역"] + "_" + table[dup].groupby("지역").cumcount().astype(str)

# ------------------------------------------------------------------
# 4. 사이드바 옵션
# ------------------------------------------------------------------
st.sidebar.header("분석 옵션")
include_avg = st.sidebar.checkbox("총계·도평균 행도 포함", value=False)
zero_missing = st.sidebar.checkbox("0은 측정값 없음으로 보고 제외", value=True,
                                   help="'-'를 0으로 채운 파일이면 0→15처럼 가짜 증가가 생깁니다.")
sido_all = list(dict.fromkeys(table.loc[table["구분"] == "지역", "시도"]))
sido_sel = st.sidebar.multiselect("시도 선택", sido_all, default=sido_all)

use = table["구분"].eq("지역")
if include_avg:
    use = use | table["구분"].isin(["총계", "평균"])
use = use & table["시도"].isin(sido_sel + ["총계", "전국", "합계"])
target = table[use]

m = target.set_index("지역")[months]
n_zero = int((m == 0).sum().sum())
if zero_missing:
    m = m.mask(m == 0)
m = m.dropna(how="all")
sido_of = target.set_index("지역")["시도"]

if m.shape[0] == 0:
    st.error("분석할 지역이 없습니다. 사이드바에서 시도를 선택해 주세요.")
    st.stop()

# ------------------------------------------------------------------
# 5. 증가 분석
# ------------------------------------------------------------------
diff = m.diff(axis=1)
inc = diff > 0

result = pd.DataFrame(index=m.index)
result.insert(0, "시도", sido_of.reindex(m.index))
result["증가한 달 수"] = inc.sum(axis=1)
result["비교한 달 수"] = diff.notna().sum(axis=1)
result["증가 비율(%)"] = (result["증가한 달 수"] / result["비교한 달 수"].replace(0, np.nan) * 100).round(1)


def slope(row):
    y = row.dropna()
    if len(y) < 2:
        return np.nan
    return np.polyfit(np.arange(len(y)), y.values, 1)[0]


def first_last(row):
    y = row.dropna()
    return y.iloc[-1] - y.iloc[0] if len(y) >= 2 else np.nan


result["월평균 변화량"] = m.apply(slope, axis=1).round(2)
result["처음→마지막 변화"] = m.apply(first_last, axis=1).round(2)
mx = diff.max(axis=1)
result["최대 상승폭"] = mx.where(mx > 0)
result["가장 많이 오른 달"] = diff.fillna(-np.inf).idxmax(axis=1).where(mx > 0, "-")
result = result.sort_values(["증가한 달 수", "월평균 변화량"], ascending=False)

if zero_missing and n_zero:
    st.info(f"값이 0인 {n_zero}칸은 측정값이 없는 것으로 보고 분석에서 제외했습니다. "
            "(사이드바에서 해제할 수 있습니다)")

st.subheader("2. 지역별 월 농도")
st.caption("색이 진할수록 농도가 높습니다.")
try:
    st.dataframe(m.style.background_gradient(cmap="OrRd", axis=None).format("{:.0f}", na_rep="-"))
except Exception:  # matplotlib가 없는 경우
    st.dataframe(m)

st.subheader("3. 월별 증가 분석 결과")
st.caption("증가한 달 수 = 바로 앞의 달보다 농도가 높아진 횟수")
st.dataframe(result)

# ------------------------------------------------------------------
# 6. 분석 요약
# ------------------------------------------------------------------
monthly_up = inc.iloc[:, 1:].sum()          # 월별 '증가한 지역 수'
ever_up = result[result["증가한 달 수"] > 0]

st.markdown("### 📝 분석 요약")
st.write(f"- 분석 대상 **{len(result)}개 지역**, 기간 **{months[0]} ~ {months[-1]}** "
         f"({len(months)}개월)")
st.write(f"- 한 번이라도 전달보다 농도가 오른 지역: **{len(ever_up)}개** / "
         f"한 번도 오르지 않고 계속 감소한 지역: **{len(result) - len(ever_up)}개**")

if len(ever_up):
    top_n = ever_up["증가한 달 수"].max()
    top_names = list(ever_up.index[ever_up["증가한 달 수"] == top_n])
    shown = ", ".join(top_names[:6]) + (f" 외 {len(top_names) - 6}곳" if len(top_names) > 6 else "")
    st.write(f"- 가장 자주 오른 지역({top_n}번): **{shown}**")
    big = ever_up["최대 상승폭"].idxmax()
    st.write(f"- 한 달 사이 가장 크게 오른 지역: **{big}** "
             f"({result.loc[big, '가장 많이 오른 달']}, +{result.loc[big, '최대 상승폭']:.0f})")

best_month = monthly_up.idxmax()
st.write(f"- 전달보다 오른 지역이 가장 많았던 달: **{best_month}** ({int(monthly_up.max())}개 지역)")

total_change = m.mean().iloc[-1] - m.mean().iloc[0]
trend = "증가" if total_change > 0 else "감소"
st.write(f"- 전체 평균 농도는 {months[0]} {m.mean().iloc[0]:.1f} → {months[-1]} "
         f"{m.mean().iloc[-1]:.1f}로 **{abs(total_change):.1f} {trend}**했습니다.")

# ------------------------------------------------------------------
# 7. 차트
# ------------------------------------------------------------------
st.subheader("4. 차트")


def show_chart(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:  # 예전 streamlit 버전
        st.altair_chart(chart, use_container_width=True)


def hbar(series, x_title, color="#e4572e"):
    d = series.reset_index()
    d.columns = ["지역", "값"]
    return (alt.Chart(d).mark_bar(color=color)
            .encode(x=alt.X("값:Q", title=x_title),
                    y=alt.Y("지역:N", sort=None, title=None),
                    tooltip=["지역", "값"])
            .properties(height=max(150, 26 * len(d))))


c1, c2 = st.columns(2)
with c1:
    st.markdown("**월별로 전달보다 농도가 오른 지역 수**")
    st.bar_chart(monthly_up.rename("증가한 지역 수"))
with c2:
    st.markdown("**전체 평균 농도 변화**")
    st.line_chart(m.mean().rename("전체 평균"))

st.markdown("**증가한 달 수가 많은 지역 TOP 15**")
top15 = result[result["증가한 달 수"] > 0]["증가한 달 수"].head(15)
if len(top15):
    show_chart(hbar(top15, "증가한 달 수"))
else:
    st.info("전달보다 농도가 오른 지역이 없습니다.")

st.markdown("**월 선택: 전달보다 농도가 오른 지역**")
sel_month = st.selectbox("월 선택", months[1:], index=len(months) - 2)
change = diff[sel_month].dropna()
rose = change[change > 0].sort_values(ascending=False)
prev_month = months[months.index(sel_month) - 1]
if len(rose):
    detail = pd.DataFrame({
        "시도": sido_of.reindex(rose.index),
        f"{prev_month}": m.loc[rose.index, prev_month],
        f"{sel_month}": m.loc[rose.index, sel_month],
        "증가량": rose,
    })
    st.write(f"{prev_month} → {sel_month}: **{len(rose)}개 지역**에서 농도가 올랐습니다.")
    st.dataframe(detail)
    show_chart(hbar(rose.head(15), "증가량", color="#c0392b"))
else:
    st.info(f"{sel_month}에는 전달보다 농도가 오른 지역이 없습니다.")

st.markdown("**지역별 월 농도 변화 (지역 선택)**")
default_sel = list(top15.index[:5]) if len(top15) else list(m.index[:5])
selected = st.multiselect("지역 선택", list(m.index), default=default_sel)
if selected:
    st.line_chart(m.loc[selected].T)
else:
    st.info("지역을 하나 이상 선택하세요.")
