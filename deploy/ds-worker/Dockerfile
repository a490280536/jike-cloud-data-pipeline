# JKY DolphinScheduler 恢复 Worker 运行镜像
#
# 用途：在 DolphinScheduler worker 容器内运行本仓库的同步脚本。
#
# 溯源要求（见 docs/DEPLOYMENT_BOUNDARIES.md）：
#   * 基础镜像必须用 digest 固定，不允许用浮动 tag
#   * Python 依赖必须用锁定文件，不允许用范围版本
#   * 镜像必须带 source commit label，使镜像可回溯到 exact commit
#   * 锁文件必须与本仓库同 commit 管理，不得散落在仓库外
#
# 构建：
#   docker build -t jky-ds-worker:<commit> -f deploy/ds-worker/Dockerfile deploy/ds-worker
#
# cryptography 的必要性：
#   生产 MySQL 8.0 默认认证插件是 caching_sha2_password。
#   PyMySQL 在该插件下需要 cryptography 才能完成 sha2 认证交换；
#   缺包时报 "'cryptography' package is required for sha256_password ..."。

FROM apache/dolphinscheduler-standalone-server@sha256:f364676c9ab30cfa6829d4628316f2c654e187dd41deac9f779b34fd5fb91793

ARG DEBIAN_FRONTEND=noninteractive
COPY requirements.runtime.lock.txt /tmp/requirements.runtime.lock.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && python3 -m pip install --no-cache-dir -r /tmp/requirements.runtime.lock.txt \
    && python3 -m pip check \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip /tmp/requirements.runtime.lock.txt

LABEL org.opencontainers.image.title="JKY DolphinScheduler recovery worker"
# 该 label 必须指向【包含本 Dockerfile 的那个 commit】本身。
# 之前写死 c0dda28（引入 Dockerfile 的那个 commit），导致在其后修正依赖的
# commit 构建出的镜像仍然声称自己是 c0dda28，provenance 不可证。
# 正确做法：构建时用 --build-arg SOURCE_COMMIT=<exact commit sha> 传入，
# 默认值仅作为本地构建的兜底，且必须与实际构建上下文一致。
ARG SOURCE_COMMIT="c0dda2847537a925ea2fa6e0cc648c10d0bf2d6f"
LABEL org.opencontainers.image.source.commit="${SOURCE_COMMIT}"
LABEL org.opencontainers.image.base.digest="sha256:f364676c9ab30cfa6829d4628316f2c654e187dd41deac9f779b34fd5fb91793"
