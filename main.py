"""
나만의 키워드 MCP 서버
- 도구: keyword_research(seed_keywords, top_n)
  → 연관키워드 + PC/모바일 검색량 + 블로그 포화도
- 키 5개는 '환경변수'에서 읽음 (코드/깃허브엔 절대 안 들어감 = 안전)
  Render 대시보드의 Environment에 아래 5개를 등록하세요:
    NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID,
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""
import os, time, hmac, hashlib, base64, requests
from fastmcp import FastMCP

API_KEY        = os.environ["NAVER_AD_API_KEY"]
SECRET_KEY     = os.environ["NAVER_AD_SECRET_KEY"]
CUSTOMER_ID    = os.environ["NAVER_AD_CUSTOMER_ID"]
CLIENT_ID      = os.environ["NAVER_CLIENT_ID"]
CLIENT_SECRET  = os.environ["NAVER_CLIENT_SECRET"]

SEARCHAD_BASE = "https://api.searchad.naver.com"
mcp = FastMCP("naver-keyword-tool")

def _headers(method, uri):
    ts = str(int(time.time() * 1000))
    msg = f"{ts}.{method}.{uri}"
    sig = base64.b64encode(
        hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()
    return {"X-Timestamp": ts, "X-API-KEY": API_KEY,
            "X-Customer": str(CUSTOMER_ID), "X-Signature": sig}

def _to_int(v):
    if isinstance(v, str):
        v = v.replace("<", "").replace(",", "").strip()
        try:
            return int(v)
        except ValueError:
            return 0
    return int(v)

def _blog_total(keyword):
    r = requests.get(
        "https://openapi.naver.com/v1/search/blog.json",
        params={"query": keyword, "display": 1},
        headers={"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("total", 0)

@mcp.tool
def keyword_research(seed_keywords: list[str], top_n: int = 20) -> list[dict]:
    """네이버 키워드 분석. 연관키워드 + PC/모바일 검색량 + 블로그 포화도를 돌려줌.

    seed_keywords: 분석할 키워드 목록 (최대 5개 권장)
    top_n: 블로그 포화도를 계산할 상위 키워드 개수 (총검색량 많은 순)
    포화도 = 블로그 글 수 / 총검색량 (낮을수록 수요 대비 글이 적어 노릴 만함)
    """
    uri = "/keywordstool"
    params = {"hintKeywords": ",".join(s.replace(" ", "") for s in seed_keywords), "showDetail": 1}
    r = requests.get(SEARCHAD_BASE + uri, params=params, headers=_headers("GET", uri), timeout=15)
    r.raise_for_status()

    rows = []
    for kw in r.json().get("keywordList", []):
        pc = _to_int(kw.get("monthlyPcQcCnt", 0))
        mo = _to_int(kw.get("monthlyMobileQcCnt", 0))
        rows.append({"키워드": kw.get("relKeyword", ""), "총검색량": pc + mo,
                     "PC": pc, "모바일": mo, "경쟁": kw.get("compIdx", "")})
    rows.sort(key=lambda x: x["총검색량"], reverse=True)

    for r2 in rows[:top_n]:
        try:
            docs = _blog_total(r2["키워드"])
            r2["블로그문서수"] = docs
            r2["포화도"] = round(docs / r2["총검색량"], 1) if r2["총검색량"] > 0 else None
        except Exception:
            r2["블로그문서수"] = None
            r2["포화도"] = None
    return rows[:top_n]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))   # Render가 PORT를 넣어줌
    mcp.run(transport="http", host="0.0.0.0", port=port)
