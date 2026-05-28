/**
 * Founding Beta intake funnel — upload + success card copy link.
 */
(function () {
  'use strict';

  var COPY_LABEL = 'Copy magic upload link';
  var COPIED_LABEL = 'Magic link copied';
  var COPY_SUCCESS_MS = 1500;

  var params = new URLSearchParams(location.search);
  var intakeInput = document.getElementById('fbIntakeId');
  var tokenInput = document.getElementById('fbToken');
  if (params.get('intake_id') && intakeInput) intakeInput.value = params.get('intake_id');
  if (params.get('token') && tokenInput) tokenInput.value = params.get('token');

  var drop = document.getElementById('fbDrop');
  var fileInput = document.getElementById('fbFiles');
  var fileList = document.getElementById('fbFileList');
  var progressBox = document.getElementById('fbProgress');
  var statusEl = document.getElementById('fbStatus');
  var form = document.getElementById('fbForm');
  var uploadCard = document.getElementById('fbUploadCard');
  var confirmCard = document.getElementById('fbConfirmCard');
  var copyBtn = document.getElementById('fbCopyLink');
  var selectedFiles = [];
  var magicLink = '';

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatSize(n) {
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function renderFileList() {
    if (!fileList) return;
    fileList.innerHTML = selectedFiles
      .map(function (f) {
        return '<li>' + escapeHtml(f.name) + ' (' + formatSize(f.size) + ')</li>';
      })
      .join('');
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '0';
      ta.style.left = '0';
      ta.style.width = '2em';
      ta.style.height = '2em';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) resolve();
        else reject(new Error('execCommand failed'));
      } catch (err) {
        document.body.removeChild(ta);
        reject(err);
      }
    });
  }

  function resetCopyButton() {
    if (!copyBtn) return;
    copyBtn.classList.remove('is-copied', 'is-copy-flash');
    copyBtn.textContent = COPY_LABEL;
    copyBtn.disabled = !magicLink;
    copyBtn.setAttribute('aria-disabled', magicLink ? 'false' : 'true');
  }

  function showCopySuccess() {
    if (!copyBtn) return;
    copyBtn.classList.add('is-copied');
    copyBtn.textContent = COPIED_LABEL;
    window.setTimeout(function () {
      resetCopyButton();
    }, COPY_SUCCESS_MS);
  }

  function bindCopyButton() {
    if (!copyBtn) return;
    resetCopyButton();
    copyBtn.onclick = function () {
      if (!magicLink) return;
      copyBtn.classList.add('is-copy-flash');
      window.requestAnimationFrame(function () {
        copyBtn.classList.remove('is-copy-flash');
      });
      copyToClipboard(magicLink)
        .then(function () {
          showCopySuccess();
          var hint = document.getElementById('fbLinkHint');
          if (hint) hint.textContent = 'Magic link copied — bookmark for more uploads.';
        })
        .catch(function () {
          var hint = document.getElementById('fbLinkHint');
          if (hint) {
            hint.textContent = 'Could not copy automatically — select and copy from your browser.';
          }
        });
    };
  }

  function addFiles(fileListObj) {
    Array.from(fileListObj || []).forEach(function (f) {
      selectedFiles.push(f);
    });
    renderFileList();
  }

  if (fileInput) {
    fileInput.addEventListener('change', function () {
      addFiles(fileInput.files);
      fileInput.value = '';
    });
  }

  if (drop) {
    ['dragenter', 'dragover'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) {
        e.preventDefault();
        drop.classList.add('is-dragover');
      });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) {
        e.preventDefault();
        drop.classList.remove('is-dragover');
        if (ev === 'drop' && e.dataTransfer && e.dataTransfer.files) {
          addFiles(e.dataTransfer.files);
        }
      });
    });
  }

  function contactOk() {
    var email = document.getElementById('fbEmail').value.trim();
    var phone = document.getElementById('fbPhone').value.trim();
    if (email && email.indexOf('@') > 0) return true;
    if (phone.replace(/\D/g, '').length >= 7) return true;
    return false;
  }

  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!selectedFiles.length) {
        statusEl.textContent = 'Add at least one file.';
        return;
      }
      if (!contactOk() && !intakeInput.value) {
        statusEl.textContent = 'Enter your email or phone so we can follow up.';
        return;
      }
      var fd = new FormData();
      selectedFiles.forEach(function (f) {
        fd.append('files', f);
      });
      if (intakeInput.value) fd.append('intake_id', intakeInput.value);
      if (tokenInput.value) fd.append('token', tokenInput.value);
      fd.append('email', document.getElementById('fbEmail').value);
      fd.append('phone', document.getElementById('fbPhone').value);
      fd.append('company', document.getElementById('fbCompany').value);
      fd.append('context', document.getElementById('fbContext').value);
      fd.append('deadline', document.getElementById('fbDeadline').value);

      var xhr = new XMLHttpRequest();
      progressBox.hidden = false;
      progressBox.innerHTML =
        '<div class="kyc-fb-progress-item"><span>Uploading…</span>' +
        '<div class="kyc-fb-progress-bar"><div class="kyc-fb-progress-fill" id="fbProgFill"></div></div></div>';
      var fill = document.getElementById('fbProgFill');
      statusEl.textContent = 'Uploading securely…';
      document.getElementById('fbSubmit').disabled = true;

      xhr.upload.addEventListener('progress', function (ev) {
        if (ev.lengthComputable && fill) {
          fill.style.width = Math.round((ev.loaded / ev.total) * 100) + '%';
        }
      });
      xhr.addEventListener('load', function () {
        document.getElementById('fbSubmit').disabled = false;
        var j = {};
        try {
          j = JSON.parse(xhr.responseText);
        } catch (err) {}
        if (
          xhr.status >= 200 &&
          xhr.status < 300 &&
          j.ok &&
          j.durability_verified !== false &&
          (j.durable_receipt_created || !j.files_saved || !j.files_saved.length)
        ) {
          showConfirm(j);
          return;
        }
        if (xhr.status >= 200 && xhr.status < 300 && j.ok && !j.durable_receipt_created) {
          msg =
            'Upload could not be verified on secure storage. Please try again or contact support@keepyourcontracts.com.';
          statusEl.textContent = msg;
          progressBox.hidden = true;
          return;
        }
        var msg = j.detail || j.message || 'Upload failed (' + xhr.status + ')';
        if (xhr.status === 503) {
          msg =
            j.detail ||
            'Paperwork upload is not available right now. Please contact support@keepyourcontracts.com.';
        }
        statusEl.textContent = msg;
        progressBox.hidden = true;
      });
      xhr.addEventListener('error', function () {
        document.getElementById('fbSubmit').disabled = false;
        statusEl.textContent = 'Network error — try again.';
        progressBox.hidden = true;
      });
      xhr.open('POST', '/api/founding-beta/upload');
      xhr.send(fd);
    });
  }

  function showConfirm(j) {
    uploadCard.classList.add('kyc-fb-hidden');
    confirmCard.classList.remove('kyc-fb-hidden');
    document.getElementById('fbConfirmId').textContent = j.intake_id || '—';
    var verified = document.getElementById('fbConfirmVerified');
    if (verified) {
      var n = j.verified_file_count != null ? j.verified_file_count : j.file_count;
      verified.textContent =
        n != null
          ? String(n) + ' file(s) verified on secure storage.'
          : '';
    }
    var receipt = document.getElementById('fbConfirmReceipt');
    if (receipt) {
      receipt.textContent = j.durable_receipt_created
        ? 'Durable audit receipt created for this intake.'
        : '';
    }
    intakeInput.value = j.intake_id || '';
    tokenInput.value = j.token || '';
    magicLink = j.magic_link || j.upload_url || '';
    var hint = document.getElementById('fbLinkHint');
    if (hint) {
      hint.textContent = magicLink
        ? 'Magic link ready — bookmark or copy for more uploads.'
        : '';
    }
    if (j.qr_png_base64) {
      document.getElementById('fbConfirmQr').src = 'data:image/png;base64,' + j.qr_png_base64;
    } else if (j.intake_id && j.token) {
      document.getElementById('fbConfirmQr').src =
        '/api/founding-beta/qr.png?intake_id=' +
        encodeURIComponent(j.intake_id) +
        '&token=' +
        encodeURIComponent(j.token);
    }
    bindCopyButton();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  bindCopyButton();
})();
