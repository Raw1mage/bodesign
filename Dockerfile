# bodesign — MCP server for AI PCB design (G10c).
#
# Bundles the toolchain the bodesign tools genuinely need:
#   - KiCad 9 (kicad-cli + the pcbnew Python module + symbol/footprint libs)
#   - LibreOffice (soffice) for docx/pdf companions
#   - pygerber for Gerber raster companions
#   - OpenSCAD for C02 prototype enclosure STL export
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

COPY packages /app/packages
COPY services /app/services

# Bundle the analyzer engine SCRIPTS (kicad/spice/emc) the C06 verification tools
# resolve via resolve_skill(). The image already ships the BINARIES (kicad-cli /
# ngspice); these are the engine scripts that drive them. Without them,
# simulate / analyze_emc / analyze_thermal return `skipped-no-skills` and C06
# SPICE/EMC/thermal can never run. Source = the cleaned, distribution-ready
# tarballs (NOT the raw skills/ tree, which is incomplete + unscrubbed). Only the
# engine subtrees are extracted. Build FAILS LOUD if any scripts/ dir is missing,
# so a silently-broken image is never produced.
RUN set -eu; \
    mkdir -p /opt/bodesign-engines; \
    tar xzf /app/services/mcp/assets/skills/bodesign.tar.gz -C /opt/bodesign-engines bodesign/engines/kicad; \
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
    BODESIGN_EMC_SKILL=/opt/bodesign-engines/emc

ENTRYPOINT ["python", "/app/services/mcp/server.py"]
CMD ["--transport", "stdio"]
