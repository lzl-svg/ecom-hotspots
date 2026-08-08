# 电商热点台 · Shopee 情报中心

面向跨境电商独立运营者的自用热点情报站：每天自动采集 Shopee 印尼 / 马来 / 越南三个市场的类目热度与热搜词，网页展示类目热点榜、涨跌曲线与子类目下钻。

## 数据来源（全免费，已实测）

- Shopee 公开类目树接口（含完整子类目层级）
- Shopee 公开搜索联想词接口（反映买家真实搜索需求）

热度分为相对值（联想词热度加权），用于站内排序，不代表真实销量。

## 目录结构

```text
collector/        Python 采集器（纯标准库，无需安装依赖）
  run.py          每日采集：类目树 + 联想词 -> SQLite
  export.py       导出前端 JSON 到 web/data/
web/              静态网站（HTML + ECharts，零构建）
  data/           每日导出的数据文件
.github/workflows/ 每日自动更新 + 发布配置
```

## 本地运行

```bash
python collector/run.py
python collector/export.py
```

预览网站：

```bash
python -m http.server 8899 --directory web
# 浏览器打开 http://127.0.0.1:8899
```

## 发布到 GitHub Pages（免费、其他电脑可访问）

1. 注册 GitHub 账号（github.com，免费）
2. 新建一个仓库（Repository，选择 Public），例如 `ecom-hotspots`
3. 把本目录内容推送到该仓库（或提供仓库地址，由我协助推送）
4. 在仓库 Settings → Pages → Source 选择 **GitHub Actions**
5. 之后每天 08:00（北京时间）自动采集并更新网站，网址为
   `https://<用户名>.github.io/<仓库名>/`

## 访问口令

- 网站打开会先要求输入访问口令，输对才能查看（私人授权用途）
- 当前口令在对话中提供；修改口令：`python tools/gen_hash.py 你的新口令`，
  把输出的加密值替换到 `web/assets/config.js` 的 `hash` 中，然后重新提交发布
- 说明：口令门用于防止路人随意浏览；由于 GitHub Pages 仓库是公开的，
  数据文件本身对懂技术的人仍可下载。介意的话可后续升级为
  Tailscale 私人网络或 Cloudflare 邮箱验证

## 说明

- 数据每天更新一次，历史曲线随天数积累逐渐变准
- 商品级数据（热销商品、价格带）暂未接入，计划 P1 通过卖家中心 / 浏览器自动采集实现
- 后续可扩展 Amazon / Ozon / Wildberries、飞书推送、AI 周报
