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

# Bake the git commit into the image at build time so /api/public/build-info
# can always answer "what's actually running" — independent of whether the
# host has set RENDER_GIT_COMMIT (the live service on Render was hand-
# created, not Blueprint-managed, and the runtime env var wasn't being
# injected, so build-info returned "unknown" for every deploy). The git
# directory is in the build context, so `git rev-parse HEAD` works.
# Fallback to the build-arg / "unknown" so non-git build contexts still
# pass through cleanly.
ARG KYC_GIT_COMMIT=unknown
RUN if [ -d .git ]; then \
      git rev-parse HEAD > /app/.build_commit 2>/dev/null || echo "${KYC_GIT_COMMIT}" > /app/.build_commit; \
    else \
      echo "${KYC_GIT_COMMIT}" > /app/.build_commit; \
    fi
ENV KYC_GIT_COMMIT=${KYC_GIT_COMMIT}

ENV PORT=10000

EXPOSE 10000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "120", "--limit-concurrency", "80"]
