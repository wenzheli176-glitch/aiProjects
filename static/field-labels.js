/* 全站字段标签：中文（english_key） */
window.FieldLabels = window.FieldLabels || {};

(function() {
  let registry = { fields: {}, elementIds: {} };

  function load(cb) {
    if (registry.fields && Object.keys(registry.fields).length) {
      if (cb) cb();
      return Promise.resolve(registry);
    }
    return fetch('/static/field-labels.json')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        registry = d || { fields: {}, elementIds: {} };
        if (cb) cb();
        return registry;
      })
      .catch(function() {
        registry = { fields: {}, elementIds: {} };
        if (cb) cb();
        return registry;
      });
  }

  function meta(key) {
    return (registry.fields && registry.fields[key]) || { label: key, group: 'crawl', type: 'text', help: '' };
  }

  function renderFieldLabel(key) {
    const m = meta(key);
    return m.label + ' (' + key + ')';
  }

  function applyFieldLabels(root) {
    root = root || document;
    Object.keys(registry.elementIds || {}).forEach(function(id) {
      const key = registry.elementIds[id];
      const el = root.getElementById(id);
      if (!el) return;
      const label = el.closest('.field, .field-row, .field-grid') &&
        el.closest('.field, .field-row') &&
        (el.closest('.field') || el.parentElement).querySelector('label');
      if (label && !label.dataset.fieldKey) {
        label.dataset.fieldKey = key;
        label.textContent = renderFieldLabel(key);
      }
    });
    root.querySelectorAll('[data-field-key]').forEach(function(el) {
      const key = el.getAttribute('data-field-key');
      if (el.tagName === 'LABEL') {
        el.textContent = renderFieldLabel(key);
      } else if (el.tagName === 'TH') {
        el.textContent = meta(key).label;
      }
    });
  }

  FieldLabels.load = load;
  FieldLabels.meta = meta;
  FieldLabels.renderFieldLabel = renderFieldLabel;
  FieldLabels.applyFieldLabels = applyFieldLabels;
})();
