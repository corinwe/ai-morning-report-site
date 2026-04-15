# 工程知识库 — 踩坑沉淀 & 最佳实践

> 本文档记录实际项目中踩过的坑和验证过的最佳实践，供未来同类场景直接复用。

---

## 一、静态网站部署（面向中国用户）

### ✅ 最终结论：GitHub Pages 是国内用户最可靠的免费方案

| 平台 | 国内访问 | 门槛 | 结论 |
|------|---------|------|------|
| **GitHub Pages** | 🟡 较慢但稳定，不需翻墙 | 无额外要求 | ✅ **首选** |
| **Vercel** | 🔴 需翻墙才能访问 | 需登录Vercel账号 | ❌ 不可用 |
| **Gitee Pages** | 🟢 最快 | 需手持身份证实名认证，审核数天 | ❌ 门槛过高 |
| **Cloudflare Pages** | 🔴 国内不稳定 | 无 | ❌ 不可靠 |

**踩坑记录：**
- Vercel 部署成功且国内能访问的前提是**翻墙**，对普通中国用户不友好
- Gitee Pages 从2022年起强制实名认证（手持身份证拍照），审核慢且可能失败
- GitHub Pages 虽然国内偶尔慢，但**从不需要翻墙、不需要额外注册、不需要实名**，是最省心的选择

**部署步骤（一次操作）：**
```bash
# 1. 创建 GitHub 仓库（API方式）
curl -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/user/repos -d '{"name":"repo-name","public":true}'

# 2. 推送代码
git init && git add -A && git commit -m "init" && git push

# 3. 启用 GitHub Pages（API方式，legacy模式最可靠）
curl -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/repos/user/repo/pages -d '{"build_type":"legacy","source":{"branch":"main","path":"/"}}'

# 4. 如果 Pages 不生效，用空 commit 触发重建
git commit --allow-empty -m "trigger Pages rebuild" && git push
```

**注意事项：**
- GitHub Pages 首次生效需要 1-2 分钟
- `build_type` 用 `legacy` 而非 `workflow`（后者需要 GitHub Actions，而 Token 可能缺 workflow 权限）
- 如果 API 启用 Pages 失败，可以手动去仓库 Settings → Pages 开启

---

## 二、静态网站构建系统（Template 机制）

### ❌ 踩坑：直接在 .html 文件中替换占位符

**问题：** build.py 把 `PLACEHOLDER` 替换为实际数据写入 `.html`，替换后占位符消失，下次 build 无法再次替换。

**表现：** `report.html` 的 `REPORTS_JSON_PLACEHOLDER` 没被注入数据，页面一直显示"加载中"。

### ✅ 正确方案：模板 + 输出分离

```
index.template.html  →  build.py  →  index.html
report.template.html  →  build.py  →  report.html
```

**规则：**
- `.template.html` 是源文件，包含 `REPORTS_JSON_PLACEHOLDER` 占位符，**永远不被 build 修改**
- `.html` 是输出文件，由 build.py 每次从模板重新生成
- `.gitignore` 不忽略 `.template.html`（要纳入版本控制）
- build.py 的逻辑：读模板 → 替换占位符 → 写输出文件

**build.py 核心逻辑：**
```python
def build(template_path, output_path, reports_json):
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    html = html.replace('REPORTS_JSON_PLACEHOLDER', reports_json)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
```

---

## 三、AI 晨报 Markdown 模板结构

### 标准五板块结构（已验证可落地）

```markdown
# 全球AI晨报 | YYYY年MM月DD日

---

## 一、全球最新AI/Agent热门技术、知识和应用动态
### 1.1 今日重磅（最重要新闻置顶）
### 1.2 其他重要模型与产品
### 1.3 开源生态动态
### 1.4 前沿研究发现

## 二、AI相关创业项目
### 2.1 全球AI融资全景（表格+数据）
### 2.2 AI Agent创业赛道
### 2.3 OPC项目（必须单独列出）

## 三、全球使用AI做投资分析的成功项目和案例
### 3.1 顶级量化基金
### 3.2 AI投资分析关键能力
### 3.3 创业机会

## 四、【重点板块】中国AI/Agent创业机会深度分析
### A) 美国模式中国化机会（4-5个方向，每个含：美国模式→中国现实→本土化改造→可落地方向→壁垒）
### B) 中国场景创新机会（4-5个独有场景，每个含：场景描述→痛点→壁垒→千万路径）
### C) 创业落地行动建议（赛道选择表+MVP路径+获客策略+变现模型+时间线+壁垒构建+避坑指南）

## 五、今日关键信号
| 信号 | 含义 |
|------|------|

> **本期晨报核心结论：** （一段话总结，build.py 自动提取为首页摘要）
```

### build.py 元数据提取规则

- **summary**：从 `> **本期晨报核心结论：**` 后的 blockquote 提取，截取200字
- **highlights**：从"## 五、今日关键信号"的表格中提取信号列
- **sections**：从所有 `## ` 标题提取，自动生成锚点
- **word_count**：中文字符数 + 英文单词数

---

## 四、Git 操作最佳实践

### Token 安全
```bash
# 推送时临时注入 token
git remote set-url origin https://user:TOKEN@github.com/user/repo.git
git push
# 推送后立即移除 token
git remote set-url origin https://github.com/user/repo.git
```

### 双仓库同步
```bash
# 添加多个 remote
git remote add origin https://github.com/user/repo.git
git remote add gitee https://gitee.com/user/repo.git

# 推送时分别推送
git push origin main
git push gitee main
```

### GitHub API 操作
```bash
# 创建仓库
curl -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/user/repos -d '{"name":"repo","public":true}'

# 启用 Pages
curl -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  https://api.github.com/repos/user/repo/pages -d '{"build_type":"legacy","source":{"branch":"main","path":"/"}}'

# gh CLI 可能报 read:org 权限不足，但 git push 和 curl API 不受影响
```

### Gitee API 操作
```bash
# 创建仓库
curl -X POST -H "Content-Type: application/json" \
  "https://gitee.com/api/v5/user/repos" \
  -d '{"access_token":"TOKEN","name":"repo","private":false}'

# Pages 无法通过 API 开启，需手动在网页操作（且需实名认证）
```

---

## 五、晨报网站设计规范（已验证）

### 首页（index.html）
- **必须有搜索框**：按日期/关键词/信号/板块标题搜索，200ms 防抖
- **必须有分类过滤**：全部/技术动态/创业项目/投资分析/中国机会
- **月份分组**：按年月自动分组，每月标注期数
- **增强卡片**：日期+星期+字数+板块数+信号数+摘要+信号芯片+板块标签
- **LATEST 标记**：最新一期高亮

### 报告页（report.html）
- **侧边目录导航**：自动提取 h2/h3，滚动高亮当前位置
- **前后日切换**：顶栏左右箭头，基于 REPORT_LIST 数组
- **回到顶部**：滚动超过 400px 出现浮动按钮
- **Markdown 排版**：h2 带背景色条、表格圆角+hover、代码块暗色主题、引用块蓝色边框

### 颜色体系
```css
--bg: #0a0e17;       /* 深色背景 */
--surface: #111827;  /* 卡片背景 */
--border: #1e2d3d;   /* 边框 */
--accent: #3b82f6;   /* 主色（蓝） */
--green: #10b981;    /* 正面指标 */
--orange: #f59e0b;   /* 警告/信号 */
--purple: #a78bfa;   /* 辅助色 */
```

---

## 六、信息源速查

### 全球AI动态（每日必查）
| 来源 | URL | 用途 |
|------|-----|------|
| AIToolly AI日报 | aitoolly.com/ai-news | 每日AI新闻汇总 |
| Anthropic 官网 | anthropic.com/news | Claude/Mythos 最新动态 |
| OpenAI 官网 | openai.com | GPT系列发布 |
| AI Agent Store | aiagentstore.ai | Agent 领域新闻 |
| BotMemo | botmemo.com | AI融资追踪 |
| a16z Big Ideas | a16z.com | 行业趋势报告 |

### 中国AI创业
| 来源 | URL | 用途 |
|------|-----|------|
| 36氪 | 36kr.com | 国内AI融资/创业 |
| 清华大学 | tsinghua.edu.cn | 政策解读 |
| 北京市政府 | beijing.gov.cn | OPC/政策原文 |
| 新浪财经 | finance.sina.com.cn | 量化/AI投资 |

### AI投资分析
| 来源 | URL | 用途 |
|------|-----|------|
| The AI University | theaiuniversity.com | AI+金融深度 |
| Two Sigma | twosigma.com | 量化基金AI应用 |
| Linitics | linitics.com | 量化交易趋势 |

---

## 七、常见问题速查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 网页一直"加载中" | `.html` 文件中占位符没被替换 | 运行 `python3 build.py`，确认从 `.template.html` 重新生成 |
| GitHub Pages 404 | Pages 未启用或正在构建 | API 启用 Pages，等1-2分钟，或空 commit 触发重建 |
| git push 报错 | Token 权限不足或 remote URL 含 token 失效 | 检查 Token 的 repo 权限；push 后清理 remote URL |
| report.html 前后日按钮不可用 | REPORT_LIST 数据为空 | build.py 必须同时注入 index.html 和 report.html |
| 新增晨报后首页没更新 | 只放了 .md 没运行 build | `python3 build.py && git add -A && git commit && git push` |

---

*最后更新：2026-04-15*
