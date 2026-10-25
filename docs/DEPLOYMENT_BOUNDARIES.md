# JKY 数据链路路径与数据边界

版本：2026-10-25

本文是采集代码仓库的路径边界说明。真实认证材料、业务数据和运行产物不进入 GitHub。

## 1. 唯一代码事实源

```text
Windows Git 根目录：D:\code\jike-cloud-data-pipeline
GitHub：a490280536/jike-cloud-data-pipeline
```

该目录只保存：

- 采集脚本、公共代码和测试；
- 脱敏配置模板；
- 数据表契约、字段映射和运行文档；
- 不含真实业务内容的验证脚本。

禁止把以下内容写入 GitHub：

- 真实订单、客户、商品、售后和库存数据；
- Excel、CSV、下载文件和运行日志；
- cookie、authorization、token、`commonVerify`、密码和连接字符串；
- 真实请求体或能恢复登录态的 cURL。

## 2. 本机受控运行区

```text
D:\JKY\auth       # cURL/登录态材料；仅本机使用
D:\JKY\secrets    # .env.local 等凭据；仅本机/容器挂载
D:\JKY\staging    # 原始业务输入和导入前校验产物
D:\JKY\output     # 本地运行输出
D:\JKY\scripts    # 本机运行辅助脚本
D:\JKY\_replay    # 受控回放和证据；不得进 GitHub
```

本次网店订单文件位于：

```text
D:\JKY\staging\网店订单_20261025.xlsx
```

该目录与 Git 根目录物理分离。仓库内的 `curl/`、`manual_inputs/`、`output/` 等仅用于兼容旧运行方式，真实生产材料以 `D:\JKY` 为准。

## 3. 数据流唯一方向

```text
吉客云登录态
  → 本机/Worker 采集流程
  → D:\JKY\staging（原始输入与校验）
  → MySQL 容器内 ods
  → DWD/ADS
  → AI-BOS 只读 ODS 读取器
```

Excel 不是 AI-BOS 的长期数据源，也不是 GitHub 的数据源。Excel 只能作为受控采集流程的输入证据，经过字段名映射、质量校验和批次审计后进入数据库。

## 4. 数据库边界

```text
容器：jky_mysql
网络：jky_internal
主机 3306：不暴露
```

采集 Worker 通过容器内部网络访问 MySQL。不得为了让宿主机脚本方便连接而擅自发布主机 `3306`。

AI-BOS 通过环境变量配置 ODS 只读连接，不在代码中写凭据。AI-BOS 代码目录与采集数据目录分离：

```text
AI-BOS 代码副本：C:\q82-order-fdcc90da-clean
采集代码副本：D:\code\jike-cloud-data-pipeline
真实数据/凭据：D:\JKY\...
```

## 5. 当前运行态差异

2026-10-25 只读核查发现：

- 采集 Git 根目录是 `D:\code\jike-cloud-data-pipeline`；
- 旧文档引用的 `D:\code\anzhuanghaitun\ds_resources\...` 路径当前不存在；
- `jky_worker` 当前挂载 Docker 卷到 `/opt/jky_work`，没有直接挂载 Git 根目录；
- 因此当前 Worker 代码来源尚未完成 GitHub → 部署目录的机械证明。

这属于**部署溯源缺口**，不是数据泄漏。修复要求：先保留现有 Worker 和数据库不动，建立从 GitHub commit 到独立 Worker 运行目录的可验证发布/回滚流程，再切换采集任务。

## 6. 采集与导入规则

- 采集脚本按字段名读取，不按 Excel 列位置读取；
- 每个批次保留源文件名、批次时间、行数、字段指纹和质量报告；
- 真实数据先进入受控 staging，再进入 MySQL；
- 现有 ODS 表口径不匹配时，必须建立独立表或显式适配器，不得强行覆盖；
- `退运费`形式的优惠、补贴、赔偿必须保留业务解释，不能按简单金额不等式直接判脏；
- AI-BOS 只读取数据库，不读取下载目录、认证目录或 Excel 原文件。

## 7. 发布前检查

```bash
git status --short
git diff --check
python -m compileall -q config.py common.py scripts
# 检查仓库是否意外包含敏感文件
git ls-files | grep -Ei 'xlsx|csv|\.env|cookie|token|secret|output|logs|manual_inputs' || true
```

最后一条只允许命中脱敏模板和说明文件；出现真实材料必须停止发布并清理、轮换凭据。
