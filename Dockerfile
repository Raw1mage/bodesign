# bodesign — MCP server for AI PCB design (G10c).
#
# Bundles the toolchain the bodesign tools genuinely need (monolith = core + ee + me):
#   - KiCad 9 (kicad-cli + the pcbnew Python module + symbol/footprint libs)
#   - ngspice for C06 SPICE circuit simulation
#   - freerouting (default-jre + xvfb) for C04 DSN/SES autorouting
#   - atopile 0.12.5 (ato) + Node 22 / elkjs 0.12.0 for C03 declarative & layered schematics
#   - LibreOffice (soffice) for docx/pdf companions
#   - pygerber for Gerber raster companions
#   - OpenSCAD (STL) + build123d/OCP (STEP) + pyrender (3D board render) for C02 CAD
#   - the mcp SDK + starlette/uvicorn for the MCP Streamable-HTTP transport
#
# The image is intentionally heavy (~GB) because circuit design needs real EDA
# tools; that is the cost of the portability the container provides.
#
# Build:   docker build -t bodesign:latest .
# Run:     mcpctl.sh start          (docker compose, HTTP-over-UDS at ./.run/bodesign.sock)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1

# KiCad 9 (PPA) + LibreOffice + python. --no-install-recommends keeps kicad to
# kicad-cli + pcbnew + libs (no GUI demos); symbols/footprints added explicitly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        software-properties-common gnupg ca-certificates curl \
        python3 python3-venv python3-pip \
        poppler-utils \
        libreoffice-core libreoffice-writer libreoffice-calc \
 && add-apt-repository -y ppa:kicad/kicad-9.0-releases \
 && apt-get update \
 && apt-get install -y --no-install-recommends kicad kicad-symbols kicad-footprints openscad \
 && rm -rf /var/lib/apt/lists/*

# LibreDWG: build dxf2dwg/dwg2dxf/dwgread statically from source so DXF<->DWG
# conversion has no runtime shared-lib deps. build-essential/pkg-config are
# purged in the same layer to keep the binaries without the toolchain weight.
ARG LIBREDWG_VERSION=0.13.3
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential pkg-config curl ca-certificates \
 && curl -fsSL "https://ftp.gnu.org/gnu/libredwg/libredwg-${LIBREDWG_VERSION}.tar.xz" -o /tmp/libredwg.tar.xz \
 && mkdir -p /tmp/libredwg && tar -xf /tmp/libredwg.tar.xz -C /tmp/libredwg --strip-components=1 \
 && cd /tmp/libredwg \
 && ./configure --disable-bindings --disable-python --disable-shared --enable-static --disable-dependency-tracking \
 && make -j"$(nproc)" \
 && install -m 0755 programs/dxf2dwg programs/dwg2dxf programs/dwgread /usr/local/bin/ \
 && cd / && rm -rf /tmp/libredwg /tmp/libredwg.tar.xz \
 && apt-get purge -y build-essential pkg-config \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# venv with system site-packages so the apt-installed pcbnew module is importable
# alongside the pip-installed mcp/uvicorn/pygerber.
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY services/mcp/requirements.txt /app/services/mcp/requirements.txt
RUN pip install --no-cache-dir -r /app/services/mcp/requirements.txt

# Monolith parity with Dockerfile.ee + Dockerfile.me:
# - ngspice (C06 SPICE simulation)
# - default-jre + xvfb + freerouting.jar (C04 autoroute)
# - GL/X runtime libs + requirements-me.txt (build123d/OCP STEP export + pyrender 3D board render)
# - atopile 0.12.5 (C03 declarative DSL)
# - Node 22.23.3 + elkjs 0.12.0 (C03 layered presentation engine)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ngspice \
        default-jre xvfb wget xz-utils \
        libgl1 libglx-mesa0 libglu1-mesa libx11-6 libxext6 libxrender1 libxcb1 libsm6 libexpat1 \
 && wget -q -O /opt/freerouting.jar https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar \
 && test -s /opt/freerouting.jar \
 && rm -rf /var/lib/apt/lists/*

COPY services/mcp/requirements-me.txt /app/services/mcp/requirements-me.txt
RUN pip install --no-cache-dir -r /app/services/mcp/requirements-me.txt \
 && kicad-cli version \
 && ngspice --version \
 && python3 -c "import build123d; print('build123d', build123d.__version__)"

RUN pip install --no-cache-dir uv \
 && UV_TOOL_BIN_DIR=/usr/local/bin uv tool install --python 3.13 atopile==0.12.5 \
 && ato --version

ARG NODE_VERSION=22.23.3
ARG NODE_SHA256_LINUX_X64=df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de
RUN set -eu; \
    arch="$(uname -m)"; \
    case "$arch" in x86_64) node_arch=x64; node_sha="${NODE_SHA256_LINUX_X64}" ;; \
      *) echo "E_NODE_ARCH_UNSUPPORTED: no pinned Node ${NODE_VERSION} digest for ${arch}" >&2; exit 1 ;; esac; \
    curl -fsSLo /opt/node.tar.xz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    echo "${node_sha}  /opt/node.tar.xz" | sha256sum -c -; \
    mkdir -p /opt/node && tar -xJf /opt/node.tar.xz -C /opt/node --strip-components=1; \
    rm /opt/node.tar.xz; \
    /opt/node/bin/node --version; PATH="/opt/node/bin:$PATH" /opt/node/bin/npm --version
ENV PATH="/opt/node/bin:$PATH" BODESIGN_NODE_BIN=/opt/node/bin/node

WORKDIR /app/packages/eda-bridge/elk
COPY packages/eda-bridge/elk/package.json packages/eda-bridge/elk/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
 && test "$(npm ls --all --parseable --omit=dev | grep -c node_modules)" = "1"
WORKDIR /app

COPY packages /app/packages
RUN cd /app/packages/eda-bridge/elk \
 && test "$(npm ls --all --parseable --omit=dev | grep -c node_modules)" = "1" \
 && node -e "const p=require('elkjs/package.json'); if (p.version!=='0.12.0') throw new Error('elkjs '+p.version); require('elkjs/lib/elk.bundled.js'); console.log('elkjs', p.version, 'ok')"
COPY services /app/services

# R9 skill-shipping contract, BOTH halves from ONE source (BR_20260730).
# `mcp.json` carries the R9.1 declaration (`skillPaths`) and `skills/` is the tree
# it declares; the R9.2 remote half builds its archives from that same tree at
# request time. Both MUST be in the image: server.py asserts their parity at
# startup (assert_skill_source_parity) and REFUSES TO BIND otherwise, so a
# half-shipping image cannot boot green.
#
# This supersedes the previous single-file `COPY skills/bodesign/doctrine.md`.
# That line existed because the raw tree was deliberately not bundled — a choice
# that made the served companion a hand-frozen tarball which then drifted 7 weeks
# out of date (losing doctrine.md and the whole scripts/ dir) with nothing able to
# notice. Shipping the declared tree removes the second artifact entirely.
# _DOCTRINE_PATH = <app>/skills/bodesign/doctrine.md is satisfied by this COPY.
COPY mcp.json /app/mcp.json
COPY skills /app/skills

# Bundle the analyzer engine SCRIPTS (kicad/spice/emc) the C06 verification tools
# resolve via resolve_skill(). The image already ships the BINARIES (kicad-cli /
# ngspice); these are the engine scripts that drive them. Without them,
# simulate / analyze_emc / analyze_thermal return `skipped-no-skills` and C06
# SPICE/EMC/thermal can never run.
#
# kicad comes from the in-repo tree (the same source /skills serves, and fresher
# than the retired tarball: 78 files vs 50). spice + emc have NO in-repo source —
# they are vendored EDA companions — so they still come from their tarballs; that
# asymmetry is deliberate and is why those two are NOT advertised as R9 skills.
# Build FAILS LOUD if any scripts/ dir is missing, so a silently-broken image is
# never produced.
RUN set -eu; \
    mkdir -p /opt/bodesign-engines/bodesign/engines; \
    cp -r /app/skills/bodesign/engines/kicad /opt/bodesign-engines/bodesign/engines/kicad; \
    tar xzf /app/services/mcp/assets/skills/spice.tar.gz    -C /opt/bodesign-engines spice; \
    tar xzf /app/services/mcp/assets/skills/emc.tar.gz      -C /opt/bodesign-engines emc; \
    test -d /opt/bodesign-engines/bodesign/engines/kicad/scripts; \
    test -d /opt/bodesign-engines/spice/scripts; \
    test -d /opt/bodesign-engines/emc/scripts

# All bodesign namespace packages + the MCP server on the path.
ENV PYTHONPATH="/app/packages/shared:/app/packages/design-ir:/app/packages/component-knowledge:/app/packages/component-kb:/app/packages/doc-core:/app/packages/source-core:/app/packages/reverse-core:/app/packages/gerber-core:/app/packages/eda-bridge:/app/packages/workflow-core:/app/packages/storage-core:/app/packages/kicad-plugin:/app/services/mcp:/app" \
    KICAD_SYMBOL_DIR=/usr/share/kicad/symbols \
    KICAD_FOOTPRINT_DIR=/usr/share/kicad/footprints \
    BODESIGN_SESSIONS_ROOT=/var/cache/bodesign/sessions \
    BODESIGN_KICAD_SKILL=/opt/bodesign-engines/bodesign/engines/kicad \
    BODESIGN_SPICE_SKILL=/opt/bodesign-engines/spice \
    BODESIGN_EMC_SKILL=/opt/bodesign-engines/emc \
    FREEROUTING_JAR=/opt/freerouting.jar \
    JAVA_BIN=java

# uid-aligned privilege drop (BR_20260705_work_dir_root_owned): start as root,
# chown the writable mounts to HOST_UID/HOST_GID, re-exec dropped via setpriv.
ENTRYPOINT ["sh", "/app/services/mcp/docker-entrypoint.sh"]
CMD ["--transport", "stdio"]
