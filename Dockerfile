FROM python:3.11

WORKDIR /app

# System binaries:
#   tesseract-ocr + tesseract-ocr-eng → OCR for scanned PDFs and image
#     uploads (DOT/FMCSA, medical, smartphone-photo policies). Without
#     these, services/evidence_intelligence/ocr.py degrades to
#     ocr_binary_unavailable for every customer scan -- losing the
#     single biggest quality lift in extraction.
#   poppler-utils → pdf2image rasteriser (pdftoppm). Required to feed
#     scanned PDFs into tesseract page-by-page.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bake the git commit into the image at build time. Render auto-exposes
# RENDER_GIT_COMMIT as a build arg for Docker services; we cascade
# through several sources so any of them satisfies the chain:
#   1. RENDER_GIT_COMMIT  (Render auto build-arg)
#   2. KYC_GIT_COMMIT     (explicit override)
#   3. git rev-parse HEAD (only works if .git survived the build context)
# A diagnostic file (.build_diagnostic) records which source won, so
# /healthz/build-diagnostic can explain "unknown" without ssh.
ARG RENDER_GIT_COMMIT=
ARG KYC_GIT_COMMIT=
RUN set -eu; \
    resolved=""; source=""; \
    if [ -n "${KYC_GIT_COMMIT}" ]; then \
      resolved="${KYC_GIT_COMMIT}"; source="arg:KYC_GIT_COMMIT"; \
    elif [ -n "${RENDER_GIT_COMMIT}" ]; then \
      resolved="${RENDER_GIT_COMMIT}"; source="arg:RENDER_GIT_COMMIT"; \
    elif [ -d .git ] && command -v git >/dev/null 2>&1; then \
      if v="$(git rev-parse HEAD 2>/dev/null)"; then \
        resolved="${v}"; source="file:.git/HEAD"; \
      fi; \
    fi; \
    if [ -z "${resolved}" ]; then resolved="unknown"; source="fallback:unknown"; fi; \
    printf '%s' "${resolved}" > /app/.build_commit; \
    printf 'resolved=%s\nsource=%s\nhad_git_dir=%s\nhad_git_binary=%s\nrender_git_commit_set=%s\nkyc_git_commit_set=%s\n' \
      "${resolved}" \
      "${source}" \
      "$([ -d .git ] && echo yes || echo no)" \
      "$(command -v git >/dev/null 2>&1 && echo yes || echo no)" \
      "$([ -n "${RENDER_GIT_COMMIT}" ] && echo yes || echo no)" \
      "$([ -n "${KYC_GIT_COMMIT}" ] && echo yes || echo no)" \
      > /app/.build_diagnostic; \
    cat /app/.build_diagnostic
ENV KYC_GIT_COMMIT=${KYC_GIT_COMMIT}

ENV PORT=10000

EXPOSE 10000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "120", "--limit-concurrency", "80"]
