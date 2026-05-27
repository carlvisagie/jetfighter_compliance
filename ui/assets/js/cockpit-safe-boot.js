/**
 * Cockpit safe boot — stubs load before feature scripts so a failed asset never
 * leaves ReferenceError on OrgIntel / OperatorCockpit / OperatorGuidance.
 */
(function (global) {
  'use strict';

  function noop() {}
  function noopAsync() {
    return Promise.resolve({});
  }

  if (!global.OrgIntel) {
    global.OrgIntel = {
      api: function (path) {
        return fetch(path, { credentials: 'same-origin' }).then(function (r) {
          if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
          return r.json();
        });
      },
      fetchOrganismSnapshot: noopAsync,
      refreshControl: noopAsync,
      refreshMemory: noopAsync,
      renderControl: noop,
      renderMemoryPage: noop,
      observabilityLabel: function () {
        return { text: 'Unavailable', level: 'warn' };
      },
      memoryIntegrity: function () {
        return { level: 'warn', summary: 'Scripts not loaded' };
      },
      __stub: true,
    };
  }

  if (!global.OperatorCockpit) {
    global.OperatorCockpit = {
      init: noopAsync,
      refreshCockpit: noopAsync,
      loadTopic: noopAsync,
      api: global.OrgIntel.api,
      __stub: true,
    };
  }

  if (!global.OperatorGuidance) {
    global.OperatorGuidance = {
      refreshGuidance: noopAsync,
      api: global.OrgIntel.api,
      renderPriority: noop,
      __stub: true,
    };
  }

  if (!global.KnowledgeOverlay) {
    global.KnowledgeOverlay = {
      initAuto: noop,
      setPanelSnapshot: noop,
      __stub: true,
    };
  }

  global.reportCockpitScriptError = function (name) {
    global.__cockpitScriptErrors = global.__cockpitScriptErrors || [];
    global.__cockpitScriptErrors.push(name);
    var health = document.getElementById('health');
    var pulse = document.getElementById('org-pulse-label');
    if (health) {
      health.textContent = 'Degraded — script load failed';
      health.className = 'kyc-pill kyc-pill--bad';
    }
    if (pulse) {
      pulse.textContent = 'Missing: ' + name + ' (check network / 502)';
    }
  };
})(typeof window !== 'undefined' ? window : globalThis);
