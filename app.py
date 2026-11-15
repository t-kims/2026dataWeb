from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

# 분석할 CSV 파일의 GitHub 주소입니다.
GITHUB_URL = "https://github.com/t-kims/2026dataWeb/blob/main/sample_data.csv"
DATA_NOTE = "이 데이터는 수업용으로 만든 가상 데이터입니다."

st.set_page_config(page_title="수면·스마트폰·공부 분석", page_icon="📊", layout="wide")


# ---------------------------------------------------------------
# 1. 데이터를 불러오는 함수
# ---------------------------------------------------------------
def to_raw_url(url):
    """GitHub 파일 페이지 주소를 'raw' 주소(파일 내용만 있는 주소)로 바꿉니다."""
    url = url.strip()
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com")
        url = url.replace("/blob/", "/")
    return url


def read_csv_any_encoding(source):
    # CSV는 utf-8 또는 cp949(엑셀에서 저장한 한글) 글자 방식이 많아서 둘 다 시도합니다.
    for enc in ["utf-8-sig", "cp949"]:
        try:
            return pd.read_csv(source, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("글자 방식을 읽을 수 없는 파일입니다.")


@st.cache_data(ttl=600)
def load_data(url):
    try:
        df = read_csv_any_encoding(to_raw_url(url))
        where = "GitHub"
    except Exception:
        # GitHub에서 못 읽으면 저장소 안에 함께 올려 둔 파일을 사용합니다.
        local = Path(__file__).parent / "sample_data.csv"
        df = read_csv_any_encoding(str(local))
        where = "저장소 안의 파일"

    # 그래프에서 다루기 쉽도록 열 이름에서 단위(괄호)를 뺍니다.
    df = df.rename(
        columns={
            "수면시간(시간)": "수면시간",
            "스마트폰사용(시간)": "스마트폰사용시간",
            "공부시간(시간)": "공부시간",
            "키(cm)": "키",
        }
    )
    return df, where


# ---------------------------------------------------------------
# 2. 글을 자연스럽게 쓰기 위한 도우미 함수
# ---------------------------------------------------------------
def josa(word, with_final, without_final):
    """단어 끝 글자에 받침이 있으면 앞의 조사를, 없으면 뒤의 조사를 붙입니다."""
    last = word[-1]
    has_final = "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0
    return word + (with_final if has_final else without_final)


def relation_label(r):
    """상관계수 r의 크기와 부호를 말로 바꿉니다."""
    a = abs(r)
    if a < 0.2:
        return "상관관계 거의 없음"
    size = "매우 강한" if a >= 0.7 else "뚜렷한" if a >= 0.4 else "약한"
    sign = "양(+)의" if r > 0 else "음(-)의"
    return f"{size} {sign} 상관관계"


GROUP_NAMES = ["적은 그룹", "중간 그룹", "많은 그룹"]


# ---------------------------------------------------------------
# 3. 두 항목의 관계를 분석하고 보여주는 함수
# ---------------------------------------------------------------
def show_relation(df, x, y, x_unit, y_unit):
    # 두 항목 모두 값이 있는 학생만 사용합니다.
    pair = df[[x, y]].dropna().copy()
    n = len(pair)
    r = pair[x].corr(pair[y])  # 상관계수
    slope, intercept = np.polyfit(pair[x], pair[y], 1)  # 추세선(직선)의 기울기
    a = abs(r)

    # (1) 숫자 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("분석에 쓴 학생 수", f"{n}명")
    c2.metric("상관계수 (r)", f"{r:.2f}")
    c3.metric("관계의 강도", relation_label(r))

    # (2) 세 그룹으로 나눠 평균 구하기 (그룹별 막대그래프용)
    pair["그룹"] = pd.qcut(pair[x].rank(method="first"), 3, labels=GROUP_NAMES)
    stat = (
        pair.groupby("그룹", observed=True)
        .agg(평균=(y, "mean"), 최소=(x, "min"), 최대=(x, "max"))
        .reset_index()
    )
    stat["이름"] = [
        f"{g} ({lo:.1f}~{hi:.1f}{x_unit})"
        for g, lo, hi in zip(stat["그룹"], stat["최소"], stat["최대"])
    ]
    order = list(stat["이름"])
    low_mean = stat["평균"].iloc[0]
    high_mean = stat["평균"].iloc[-1]

    # (3) 그래프
    left, right = st.columns(2)
    with left:
        st.markdown("**① 산점도와 추세선** (점 하나가 학생 한 명)")
        base = alt.Chart(pair).encode(
            x=alt.X(f"{x}:Q", title=f"{x} ({x_unit})", scale=alt.Scale(zero=False)),
            y=alt.Y(f"{y}:Q", title=f"{y} ({y_unit})", scale=alt.Scale(zero=False)),
        )
        points = base.mark_circle(size=60, opacity=0.6).encode(
            tooltip=[x, y],
        )
        line = base.transform_regression(x, y).mark_line(color="red", size=3)
        st.altair_chart(points + line)

    with right:
        st.markdown(f"**② {x} 그룹별 평균 {y}**")
        bars = (
            alt.Chart(stat)
            .mark_bar()
            .encode(
                x=alt.X("이름:N", sort=order, title=f"{x} 그룹", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("평균:Q", title=f"평균 {y} ({y_unit})"),
                tooltip=["이름", alt.Tooltip("평균:Q", format=".2f")],
            )
        )
        labels = (
            alt.Chart(stat)
            .mark_text(dy=-8)
            .encode(
                x=alt.X("이름:N", sort=order),
                y="평균:Q",
                text=alt.Text("평균:Q", format=".1f"),
            )
        )
        st.altair_chart(bars + labels)

    # (4) 글로 쓴 분석
    lines = [
        f"분석에 사용한 학생은 **{n}명**입니다. (값이 비어 있는 학생은 뺐어요.)",
        f"{josa(x, '과', '와')} {y}의 상관계수는 **{r:.2f}**입니다.",
    ]
    if a < 0.2:
        lines.append(
            "상관계수가 0에 가까워서 **두 항목 사이에 뚜렷한 관계가 없다**고 볼 수 있어요. "
            "산점도의 점들이 한 방향으로 모이지 않고 넓게 퍼져 있는 것도 같은 뜻이에요."
        )
        lines.append(
            f"빨간 추세선의 기울기는 {x} 1{x_unit}당 {slope:+.2f}{y_unit}이지만, "
            "점들이 넓게 퍼져 있어서 믿을 만한 차이라고 보기는 어려워요."
        )
    else:
        trend = "늘어나는" if r > 0 else "줄어드는"
        lines.append(
            f"**{relation_label(r)}**로, {josa(x, '이', '가')} 늘어날수록 "
            f"{josa(y, '은', '는')} {trend} 경향이 있어요."
        )
        lines.append(
            f"빨간 추세선을 보면 {josa(x, '이', '가')} 1{x_unit} 늘어날 때 "
            f"{josa(y, '은', '는')} 평균 약 **{abs(slope):.2f}{y_unit}** "
            f"{'늘어나는' if slope > 0 else '줄어드는'} 경향이에요."
        )
    lines.append(
        f"{josa(x, '을', '를')} 기준으로 학생을 3그룹으로 나눠 보면, 평균 {josa(y, '은', '는')} "
        f"**{GROUP_NAMES[0]} {low_mean:.1f}{y_unit}** → "
        f"**{GROUP_NAMES[-1]} {high_mean:.1f}{y_unit}** "
        f"(차이 {abs(high_mean - low_mean):.1f}{y_unit})입니다."
    )
    lines.append(
        f"{x}의 변화가 {y}의 차이를 설명하는 정도(결정계수 R²)는 약 **{r ** 2 * 100:.0f}%**이고, "
        f"나머지 {100 - r ** 2 * 100:.0f}%는 다른 요인과 우연의 영향이에요."
    )
    st.markdown("**📝 분석 결과**")
    st.markdown("\n".join(f"- {line}" for line in lines))

    if a >= 0.4:
        conclusion = (
            f"✅ **결론**: {josa(x, '과', '와')} {y} 사이에는 관계가 있는 것으로 보여요. "
            "다만 관계가 있다고 해서 한쪽이 다른 쪽의 '원인'이라고 단정할 수는 없어요."
        )
    elif a >= 0.2:
        conclusion = (
            f"✅ **결론**: {josa(x, '과', '와')} {y} 사이에는 약한 관계가 보이지만, "
            "분명하게 말하려면 더 많은 데이터가 필요해요."
        )
    else:
        conclusion = (
            f"✅ **결론**: {josa(x, '과', '와')} {y}는 서로 거의 관련이 없는 것으로 보여요."
        )
    st.info(conclusion)

    return {"r": r, "n": n}


# ---------------------------------------------------------------
# 4. 화면 구성
# ---------------------------------------------------------------
st.title("📊 수면·스마트폰 사용과 생활 데이터 분석")
st.write(
    "GitHub에 올려 둔 CSV 파일을 읽어서 다음 두 가지 질문에 답해 봅니다.\n\n"
    "1. 수면시간이 길수록 키가 클까?\n"
    "2. 스마트폰을 많이 쓸수록 공부시간이 줄어들까?"
)

try:
    df, where = load_data(GITHUB_URL)
except Exception:
    st.error("데이터를 불러오지 못했습니다. GitHub 주소와 파일 이름을 확인해 주세요.")
    st.stop()

needed = ["수면시간", "키", "스마트폰사용시간", "공부시간"]
missing = [c for c in needed if c not in df.columns]
if missing:
    st.error(f"CSV 파일에 다음 항목이 없습니다: {', '.join(missing)}")
    st.stop()

for c in needed:
    df[c] = pd.to_numeric(df[c], errors="coerce")

if where == "GitHub":
    st.success("GitHub에서 데이터를 불러왔어요.")
else:
    st.warning("GitHub에서 불러오지 못해 저장소 안의 sample_data.csv를 사용했어요.")
st.caption(f"데이터 주소: {GITHUB_URL}  |  {DATA_NOTE}")

with st.expander("📄 불러온 데이터 미리 보기"):
    st.dataframe(df)
    st.write(f"전체 {len(df)}명, 항목 {len(df.columns)}개")

st.header("1️⃣ 수면시간과 키의 관계")
result1 = show_relation(df, "수면시간", "키", "시간", "cm")

st.header("2️⃣ 스마트폰 사용과 공부시간의 관계")
result2 = show_relation(df, "스마트폰사용시간", "공부시간", "시간", "시간")

# ---------------------------------------------------------------
# 5. 종합 정리
# ---------------------------------------------------------------
st.header("📌 종합 정리")
summary = pd.DataFrame(
    {
        "관계": ["수면시간 ↔ 키", "스마트폰 사용 ↔ 공부시간"],
        "상관계수": [round(result1["r"], 2), round(result2["r"], 2)],
    }
)
summary["관계의 강도"] = [relation_label(r) for r in summary["상관계수"]]
summary["방향"] = ["양(+)" if r > 0 else "음(-)" for r in summary["상관계수"]]

col_a, col_b = st.columns(2)
with col_a:
    st.dataframe(summary[["관계", "상관계수", "관계의 강도"]], hide_index=True)
with col_b:
    chart = (
        alt.Chart(summary)
        .mark_bar()
        .encode(
            y=alt.Y("관계:N", sort=None, title=None),
            x=alt.X("상관계수:Q", scale=alt.Scale(domain=[-1, 1])),
            color=alt.Color("방향:N", title="방향"),
            tooltip=["관계", "상관계수", "관계의 강도"],
        )
    )
    st.altair_chart(chart)

stronger = summary.loc[summary["상관계수"].abs().idxmax(), "관계"]
st.write(
    f"두 관계 중 **{stronger}** 쪽이 상관계수의 크기가 더 커서 더 뚜렷한 관계를 보였어요. "
    "상관계수가 1이나 -1에 가까울수록 관계가 강하고, 0에 가까울수록 관계가 약해요."
)

st.subheader("🤔 생각해 볼 점")
st.markdown(
    f"""
- 스마트폰을 많이 쓰면 공부를 덜 하는 걸까요, 공부를 덜 해서 스마트폰을 더 쓰는 걸까요? 그래프만으로는 **원인과 결과를 알 수 없어요.**
- 눈에 보이지 않는 **제3의 요인**(예: 시험 기간, 성격, 생활 습관)이 두 항목에 함께 영향을 줬을 수도 있어요.
- 이 분석은 {len(df)}명의 자료에 대한 것이에요. 다른 학생들에게도 똑같이 나타난다고 말하려면 더 많은 자료가 필요해요.
- {DATA_NOTE} 실제 학생들의 모습으로 받아들이지 말고, 분석 방법을 익히는 연습으로 생각해 주세요.
"""
)
