(function () {
      'use strict';

      var BOOT_ID  = 'vio-boot';
      var MARK_ID  = 'vio-boot-mark';
      var LINE_ID  = 'vio-boot-line';
      var DIAG_ID  = 'vio-boot-diagnostic';
      var errors   = [];
      var bootedAt = (new Date()).getTime();

      function bootHtml() {
        return '' +
          '<div id="' + BOOT_ID + '" role="status" aria-live="polite"' +
          '  style="position:fixed;top:0;left:0;right:0;bottom:0;' +
          '  background:#07070d;color:#e6e8ef;display:flex;flex-direction:column;' +
          '  align-items:center;justify-content:center;text-align:center;padding:24px;' +
          '  z-index:99998;' +
          '  font:13px/1.4 ui-sans-serif,system-ui,-apple-system,&quot;Segoe UI&quot;,Roboto,sans-serif;">' +
          '  <div id="' + MARK_ID + '"' +
          '    style="font-size:32px;color:#4dc4d6;letter-spacing:0.12em;' +
          '    margin-bottom:18px;font-weight:600;' +
          '    animation:vio-boot-pulse 1.8s ease-in-out infinite;">◉ VIO</div>' +
          '  <div id="' + LINE_ID + '"' +
          '    style="color:#7d8190;font-size:11px;letter-spacing:0.08em;' +
          '    text-transform:uppercase;">initialising…</div>' +
          '  <div id="' + DIAG_ID + '"' +
          '    style="max-width:640px;margin-top:24px;padding:14px 16px;' +
          '    color:#d8a24a;background:#0c0c16;border:1px solid #d8a24a;' +
          '    border-radius:4px;font-size:11px;line-height:1.6;' +
          '    text-align:left;display:none;white-space:pre-wrap;' +
          '    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"></div>' +
          '  <style>@keyframes vio-boot-pulse{0%,100%{opacity:0.55}50%{opacity:1}}</style>' +
          '</div>';
      }

      function paint() {
        if (document.getElementById(BOOT_ID)) return;
        if (!document.body) return;
        document.body.insertAdjacentHTML('afterbegin', bootHtml());
      }

      function setLine(text, color) {
        var line = document.getElementById(LINE_ID);
        if (!line) return;
        line.textContent = text;
        if (color) line.style.color = color;
      }

      function showDiag() {
        var diag = document.getElementById(DIAG_ID);
        if (!diag) return;
        diag.style.display = 'block';
        var rows = [];
        for (var i = 0; i < errors.length; i++) {
          var e = errors[i];
          rows.push('[' + e.at + ']  ' + e.where + '\n  ' + e.message);
        }
        rows.push('');
        rows.push('Open DevTools (F12) → Console for stack traces.');
        rows.push('Hard-refresh (Ctrl+Shift+R) to bypass any cached bad JS.');
        diag.textContent = rows.join('\n');
      }

      function fault(where, message) {
        errors.push({
          where:   String(where || 'unknown'),
          message: String(message == null ? '(no message)' : message).slice(0, 600),
          at:      (new Date()).toISOString()
        });
        setLine('VIO FAILED TO BOOT', '#ef4444');
        showDiag();
        var mark = document.getElementById(MARK_ID);
        if (mark) {
          mark.style.animation = 'none';
          mark.style.color = '#ef4444';
        }
      }

      // Public API for the rest of VIO.
      window.VIO_BOOT = {
        ready: function () {
          var el = document.getElementById(BOOT_ID);
          if (el && el.parentNode) el.parentNode.removeChild(el);
        },
        progress: function (text) {
          setLine(text);
        },
        fault: fault,
        elapsed: function () {
          return (new Date()).getTime() - bootedAt;
        },
        errors: function () {
          return errors.slice();
        }
      };

      // Global error trap — anything that escapes try/catch in any
      // script lands here and becomes visible to the operator.
      window.addEventListener('error', function (e) {
        var src = e.filename ? String(e.filename).split('/').pop() : 'inline';
        var loc = src + (e.lineno ? (':' + e.lineno) : '');
        var msg = e.message || (e.error && e.error.message) || String(e.error || e);
        fault('uncaught:' + loc, msg);
      });
      window.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        var msg = (r && r.message) ? r.message : String(r);
        fault('unhandled-promise', msg);
      });

      // Paint as soon as body is available.
      if (document.body) {
        paint();
      } else {
        document.addEventListener('DOMContentLoaded', paint);
      }

      // Soft watchdog: 2 seconds in, if VIO hasn't called ready(),
      // gently tell the operator we're still working.
      setTimeout(function () {
        if (document.getElementById(BOOT_ID)) {
          setLine('still initialising — fetching the field…');
        }
      }, 2000);

      // Hard watchdog: 10 seconds in, if STILL not ready AND no errors
      // were captured, surface a "did not complete first render"
      // diagnostic. This catches the slow-API and the silent-no-render
      // failure modes that error handlers can't see.
      setTimeout(function () {
        if (!document.getElementById(BOOT_ID)) return;
        if (errors.length === 0) {
          fault('boot-timeout',
            'VIO did not complete first render within 10 seconds. ' +
            'Most likely the /api/operator/vio/overview call hung, or ' +
            'a render path never called window.VIO_BOOT.ready(). ' +
            'Network tab will show the actual API status.');
        }
      }, 10000);
    })();