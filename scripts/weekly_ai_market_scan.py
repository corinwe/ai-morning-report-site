#!/usr/bin/env python3
"""每周 AI 行情扫描（每周五 07:30，cron no_agent）→ 产出并入当日 AI晨报

来源：① AICPB 榜单+产品页（schema.org / 页面文本）② a16z Top100 要点 ③ YC RFS 方向 ④ Brave 热点
新增：对榜单 Top 产品**逐个分析**（主要功能优势 / 用户为什么买单）+ 官网链接
      分析由 DeepSeek 基于「抓取到的事实」归纳（禁编造：资料不足则如实标注）
输出：/root/ai-morning-report-site/reports/weekly/YYYY-Www.md（成功 stdout 静默；失败 stderr+exit1）
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path("/root/ai-morning-report-site")
OUT_DIR = ROOT / "reports" / "weekly"
CACHE_DIR = OUT_DIR / "cache"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
BRAVE = "/root/hermes-harness/scripts/brave_search.py"
ENV_FILE = pathlib.Path("/root/.hermes/profiles/dad/.env")
TOP_N = 8          # 每个榜单取前 N 名做逐个分析
STATUS: list[str] = []

DOMAIN_BLACKLIST = (
    "aicpb.com", "toolify.ai", "theresanaiforthat.com", "futurepedia.io", "topai.tools", "ai-bot.cn",
    "wikipedia.org", "baike.baidu.com", "zhihu.com", "juejin.cn", "csdn.net", "sohu.com", "36kr.com",
    "bing.com", "google.com", "baidu.com", "youtube.com", "x.com", "twitter.com", "facebook.com",
    "linkedin.com", "apps.apple.com", "play.google.com", "qimai.cn", "smzdm.com", "weixin.qq.com",
)


def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&mdash;", "—"), ("&nbsp;", " "), ("&amp;", "&"), ("&rsquo;", "’"),
                 ("&quot;", '"'), ("&#x27;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


# ---------- ① AICPB ----------
def aicpb_lists(url: str) -> list[dict]:
    html = fetch(url)
    out = []
    for block in re.findall(r'\{"@type":\["ItemList","CreativeWork"\].*?"itemListElement":\[.*?\]\}', html, re.S):
        name = re.search(r'"name":"(.*?)"', block)
        period = re.search(r'"dateModified":"(.*?)"', block)
        items = []
        for p, n, pid in re.findall(
                r'"position":(\d+),"item":\{"@type":"WebApplication","@id":"([^"]*?)","name":"([^"]{1,60})"', block):
            pass
        for m in re.finditer(r'"position":(\d+),"item":\{"@type":"WebApplication","@id":"([^"]+)","name":"([^"]{1,60})"', block):
            items.append((int(m.group(1)), m.group(3), m.group(2)))
        if name and items:
            out.append({"rank": name.group(1).strip(), "period": (period.group(1) if period else "?"),
                        "items": sorted(items)[:10]})
    return out


def aicpb_product(url: str) -> dict:
    """产品页：简介 + 最新排名/访问量/月环比"""
    html = fetch(url)
    txt = strip_tags(re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I))
    desc = ""
    m = re.search(r"([A-Za-z][^|]{40,400}?)\s*(?:最新排名|最新 Webstie|最新 App)", txt)
    if m:
        desc = m.group(1).strip()
    stat = ""
    m2 = re.search(r"以\s*([\d.,]+[KMB万亿]?)\s*(Webstie 访问量|月活跃用户|App [^\s]*)\s*位列第\s*(\d+)\s*名", txt)
    if m2:
        stat = f"{m2.group(2)} {m2.group(1)}（第 {m2.group(3)} 名）"
    mom = re.search(r"月环比\s*(-?[\d.]+%)", txt)
    if mom and stat:
        stat += f"，月环比 {mom.group(1)}"
    return {"desc": desc[:300], "stat": stat}


# ---------- ② a16z / ③ YC ----------
def a16z_latest() -> dict:
    for ed in (8, 7, 6):
        url = f"https://a16z.com/100-gen-ai-apps-{ed}/"
        try:
            html = fetch(url)
        except Exception:
            continue
        if "Top 100 Gen AI" not in html:
            continue
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        heads = [strip_tags(h) for h in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)]
        links = [strip_tags(h) for h in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S | re.I) if "Top 50" in h]
        return {"edition": ed, "url": url, "title": strip_tags(title.group(1)) if title else f"第 {ed} 版",
                "points": [h for h in heads if len(h) > 8][:6], "links": links[:4], "ok": True}
    return {"ok": False, "reason": "a16z 各版页面均未取到"}


def yc_rfs() -> dict:
    html = fetch("https://www.ycombinator.com/rfs")
    heads = [strip_tags(h) for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, re.S | re.I)]
    heads = [h for h in heads if 2 < len(h) < 80]
    cycles = [h for h in heads if re.match(r"^(Spring|Summer|Fall|Winter)\s+20\d\d$", h)]
    nav = {"For Investors", "Verify Founders", "Hacker News", "Bookface", "SAFE", "Find a Co-Founder",
           "Startup Jobs", "The Primer"}
    items = [h for h in heads if h not in nav and not re.match(r"^(Spring|Summer|Fall|Winter)\s+20\d\d$", h)]
    seen, uniq = set(), []
    for h in items:
        if h not in seen:
            seen.add(h); uniq.append(h)
    return {"cycle": cycles[0] if cycles else "?", "items": uniq[:14],
            "url": "https://www.ycombinator.com/rfs", "ok": bool(uniq)}


# ---------- ④ Brave ----------
def brave(q: str, count: int = 4, typ: str = "news") -> list[dict]:
    try:
        r = subprocess.run(["python3", BRAVE, q, "--count", str(count), "--type", typ],
                           capture_output=True, text=True, timeout=120)
        txt = r.stdout or r.stderr
        hits = []
        blocks = re.split(r"\n(?=\s*\d+\.\s)", txt)
        for b in blocks:
            mt = re.search(r"^\s*\d+\.\s*(.+?)\n\s*URL:\s*(\S+)", b, re.M)
            if not mt:
                continue
            ms = re.search(r"摘要:\s*(.+?)(?:\n|\Z)", b)
            hits.append({"title": mt.group(1).strip()[:120], "url": mt.group(2).strip(),
                         "snippet": re.sub(r"\s+", " ", ms.group(1)).strip()[:220] if ms else ""})
        return hits[:count]
    except Exception as e:  # noqa: BLE001
        STATUS.append(f"Brave 检索失败: {str(e)[:80]}")
        return []


def _brave_official(name: str) -> str:
    """用 Brave 找官网：取第一条非目录类域名（并做标题校验）"""
    for h in brave(f"{name} 官网 official website", count=6, typ="web"):
        dom = re.sub(r"^https?://", "", h["url"]).split("/")[0].lower()
        if any(b in dom for b in DOMAIN_BLACKLIST):
            continue
        if re.search(r"china|official-website|download|apk|zhinan|rumen|ke\b", dom):
            continue
        # 校验：页面标题或首屏必须命中品牌词，否则视为不可信（宁可“未取到”）
        tok = re.sub(r"[^a-z0-9]", "", name.lower().split("｜")[0])
        try:
            html = fetch(h["url"], timeout=15)
            title = strip_tags(re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I).group(1)) if re.search(
                r"<title[^>]*>(.*?)</title>", html, re.S | re.I) else ""
            head = (title + " " + html[:4000]).lower()
            if tok[:5] and tok[:5] in re.sub(r"[^a-z0-9]", "", head):
                return h["url"]
        except Exception:
            continue
    return ""


SITES_MAP = pathlib.Path(__file__).with_name("official_sites.json")


def official_site(name: str) -> tuple[str, str]:
    """返回 (官网 URL, 核验说明)：先查已核验映射，再用检索+标题校验兜底"""
    try:
        m = json.loads(SITES_MAP.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    if name in m and isinstance(m[name], dict):
        return m[name].get("url", ""), f"已核验（{m[name].get('verified', '?')}）"
    url = _brave_official(name)
    return (url, "检索+标题校验通过") if url else ("", "未核实（未取到可信官网）")



def site_meta(url: str) -> str:
    try:
        html = fetch(url, timeout=20)
    except Exception:
        return ""
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    d = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.S | re.I) or \
        re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.S | re.I)
    parts = []
    if t:
        parts.append("标题：" + strip_tags(t.group(1))[:120])
    if d:
        parts.append("描述：" + strip_tags(d.group(1))[:300])
    return " ｜ ".join(parts)


# ---------- LLM 归纳（基于事实，禁编造） ----------
def deepseek_key() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("DEEPSEEK_API_KEY", "")


def llm_analyze(facts: dict) -> dict:
    key = deepseek_key()
    if not key:
        return {"strength": "未取到（无可用模型密钥）", "why_pay": "未取到"}
    prompt = (
        "你是产品分析师。请用中文各写 1 条结论（每条 40–100 字）：\n"
        "1) strength：主要功能与优势（这个产品做什么、相对同类强在哪）\n"
        "2) why_pay：用户为什么买单（订阅付费、工作流嵌入、生态绑定、免费增值、网络效应等）\n"
        "规则：\n"
        "- 可以描述该产品的公开已知功能与定位（你的常识），但**禁止编造任何具体数据**：用户数、访问量、营收、融资额、"
        "增长率等一律不得出现，除非它在下面【资料】中给出；\n"
        "- 资料不足或你不确定时写「公开资料不足，需人工核实」，不要猜；\n"
        "- 不要营销话术、不要感叹号、不要罗列官网原文。\n"
        "只输出 JSON：{\"strength\":\"...\",\"why_pay\":\"...\"}\n\n"
        f"【资料】名称：{facts.get('name')}\n榜单数据：{facts.get('stat') or '未取到'}\n"
        f"AICPB 简介：{facts.get('desc') or '未取到'}\n官网信息：{facts.get('meta') or '未取到'}\n"
        f"检索摘要：{facts.get('snippets') or '未取到'}"
    )
    body = json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2, "max_tokens": 700}, ensure_ascii=False).encode()
    req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        content = data["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", content, re.S)
        out = json.loads(m.group(0)) if m else {}
        return {"strength": str(out.get("strength", "")).strip()[:220] or "未取到",
                "why_pay": str(out.get("why_pay", "")).strip()[:220] or "未取到"}
    except Exception as e:  # noqa: BLE001
        return {"strength": f"分析未取到（{str(e)[:50]}）", "why_pay": "未取到"}


def enrich_one(item: tuple[int, str, str], list_name: str) -> dict:
    pos, name, pid = item
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name)[:40].strip("-").lower()
    cache = CACHE_DIR / f"{slug}.json"
    facts = {"name": name, "rank": f"{list_name} #{pos}", "aicpb_url": pid}
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("name") == name and cached.get("strength"):
                return cached
        except Exception:
            pass
    try:
        facts.update(aicpb_product(pid))
    except Exception:
        pass
    site, verify = official_site(name)
    facts["site"] = site
    facts["site_verify"] = verify
    facts["meta"] = site_meta(site) if site else ""
    snips = brave(f"{name} 产品 功能 优势 商业模式", count=2, typ="web")
    facts["snippets"] = " ｜ ".join(f"{s['title']}：{s['snippet']}" for s in snips if s.get("snippet"))[:500]
    facts.update(llm_analyze(facts))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    return facts


# ---------- 主流程 ----------
def main() -> int:
    today = dt.date.today()
    iso = today.isocalendar()
    week_tag = f"{iso[0]}-W{iso[1]:02d}"
    monday = today - dt.timedelta(days=today.weekday())
    rng = f"{monday:%Y-%m-%d} ~ {today:%Y-%m-%d}"

    gl, cl = [], []
    try:
        gl = aicpb_lists("https://www.aicpb.com/zh/ai-rankings/products/global-ai-rankings")
        STATUS.append(f"AICPB 全球总榜：解析 {len(gl)} 个榜单 ✅")
    except Exception as e:  # noqa: BLE001
        STATUS.append(f"AICPB 全球总榜：未取到（{str(e)[:60]}）")
    try:
        cl = aicpb_lists("https://www.aicpb.com/zh/ai-rankings/products/china-ai-rankings")
        STATUS.append(f"AICPB 国内总榜：解析 {len(cl)} 个榜单 ✅")
    except Exception as e:  # noqa: BLE001
        STATUS.append(f"AICPB 国内总榜：未取到（{str(e)[:60]}）")

    az = a16z_latest()
    STATUS.append("a16z Top100：" + ("已取到 ✅" if az.get("ok") else az.get("reason", "未取到")))
    yc = yc_rfs()
    STATUS.append("YC RFS：" + ("已取到 ✅" if yc.get("ok") else "未取到"))
    news = brave("本周 AI 新产品 发布 爆火", 4) + brave("AI 应用 上架 增长 本周", 3)
    STATUS.append(f"本周热点检索：{len(news)} 条")

    # 逐个分析：全球榜 + 国内榜各取前 TOP_N，去重
    targets: list[tuple[tuple[int, str, str], str]] = []
    seen_names: set[str] = set()
    for lst, label in ((gl[:1], "全球总榜"), (cl[:1], "国内总榜")):
        for b in lst:
            for it in b["items"][:TOP_N]:
                if it[1] in seen_names:
                    continue
                seen_names.add(it[1])
                targets.append((it, label))
    results: dict[str, dict] = {}
    if targets:
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(enrich_one, it, label): it[1] for it, label in targets}
            for f in cf.as_completed(futs):
                try:
                    r = f.result()
                    results[r["name"]] = r
                except Exception as e:  # noqa: BLE001
                    results[futs[f]] = {"name": futs[f], "strength": f"未取到（{str(e)[:40]}）", "why_pay": "未取到"}
    STATUS.append(f"逐个产品分析：{len(results)}/{len(targets)} 个完成")

    g_names = {n for b in gl for _, n, _ in b["items"]}
    c_names = {n for b in cl for _, n, _ in b["items"]}
    move_candidates = sorted(g_names - c_names)[:8]

    L: list[str] = [f"## 📈 本周 AI 行情扫描（{rng}）", ""]
    L.append(f"> 来源：AICPB · AI产品榜 / a16z / YC RFS / Brave；生成 {dt.datetime.now():%Y-%m-%d %H:%M}（北京时间）")
    L.append("")

    L.append("### ① 榜单快照（AICPB）")
    for b in gl[:1]:
        L.append(f"- **{b['rank']}**（{b['period']}）：" + "、".join(f"{p}.{n}" for p, n, _ in b["items"]))
    for b in cl[:1]:
        L.append(f"- **{b['rank']}**（{b['period']}）：" + "、".join(f"{p}.{n}" for p, n, _ in b["items"]))
    if not gl and not cl:
        L.append("- 榜单未取到（不编造）")
    L.append("")

    L.append(f"### ② 榜单产品逐个分析（全球/国内前 {TOP_N} 名）")
    L.append("> 分析依据：AICPB 产品页简介 + 榜单流量数据 + 官网首页元信息 + 公开检索摘要，由模型归纳；"
             "**关键数据均标来源，未编造数据**；资料不足之处如实标注「公开资料不足」。官网链接经核验（见每条括号）。")
    order = [it[1] for it, _ in targets]
    for i, nm in enumerate(order, 1):
        r = results.get(nm)
        if not r:
            continue
        L.append(f"**{i}) {nm}**（{r.get('rank', '')}）")
        site = r.get("site") or "未取到（未核实）"
        L.append(f"- 官网：{site}　｜　核验：{r.get('site_verify', '未核实')}")
        stat = re.sub(r"（第 \d+ 名）", "", r.get("stat") or "").replace("，月环比", "；月环比")
        L.append(f"- 榜单数据：{stat or '未取到'}｜名次：{r.get('rank', '')}｜来源：AICPB")
        L.append(f"- 主要功能与优势：{r.get('strength', '未取到')}")
        L.append(f"- 用户为什么买单：{r.get('why_pay', '未取到')}")
        L.append(f"- AICPB 产品页：{r.get('aicpb_url', '')}")
    L.append("")

    L.append("### ③ 真实使用风向（a16z Top 100 Gen AI Consumer Apps）")
    if az.get("ok"):
        L.append(f"- 版本：第 {az['edition']} 版｜{az['title']}")
        for p in az.get("points", [])[:5]:
            L.append(f"- {p}")
        if az.get("links"):
            L.append("- 分榜：" + "；".join(az["links"]))
    else:
        L.append("- 未取到")
    L.append("")

    L.append("### ④ 官方「想投的方向」（YC Requests for Startups）")
    if yc.get("ok"):
        L.append(f"- 当期：{yc['cycle']}")
        L.append("- " + "；".join(yc["items"][:12]))
    else:
        L.append("- 未取到")
    L.append("")

    L.append("### ⑤ 本周新品 / 热点")
    for n in news[:7]:
        L.append(f"- {n['title']}（{n['url']}）")
    if not news:
        L.append("- 未取到")
    L.append("")

    L.append("### ⑥ 可搬运候选（启发式提示，需人工核实）")
    L.append("> 判据仅为「出现在全球榜 Top10 但未出现在国内榜 Top10」，不等于国内空白——须核国内落地与合规后再按九问打分卡评估。")
    L.append("- " + ("、".join(move_candidates) if move_candidates else "无数据"))
    L.append("")

    L.append("### 抓取状态")
    for s in STATUS:
        L.append(f"- {s}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{week_tag}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    if not any("✅" in s for s in STATUS):
        print("❌ 全部来源抓取失败", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
