/** 监测任务 Cron 可视化选择器（生成五段 cron，禁止手输） */
(function (global) {
  const DOW_LABELS = [
    { v: 1, l: '一' },
    { v: 2, l: '二' },
    { v: 3, l: '三' },
    { v: 4, l: '四' },
    { v: 5, l: '五' },
    { v: 6, l: '六' },
    { v: 0, l: '日' },
  ];

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function buildCron(freq, hour, minute, weekdays, intervalHours) {
    const m = parseInt(minute, 10) || 0;
    const h = parseInt(hour, 10) || 0;
    if (freq === 'interval') {
      const n = Math.max(1, parseInt(intervalHours, 10) || 6);
      return '0 */' + n + ' * * *';
    }
    if (freq === 'weekly') {
      const days = (weekdays && weekdays.length) ? weekdays.slice().sort((a, b) => a - b) : [1, 2, 3, 4, 5];
      const dow = days.join(',');
      return m + ' ' + h + ' * * ' + dow;
    }
    return m + ' ' + h + ' * * *';
  }

  function describeCron(freq, hour, minute, weekdays, intervalHours, cron) {
    const h = pad2(parseInt(hour, 10) || 0);
    const mi = pad2(parseInt(minute, 10) || 0);
    if (freq === 'interval') {
      const n = Math.max(1, parseInt(intervalHours, 10) || 6);
      return '每 ' + n + ' 小时 · cron: ' + (cron || buildCron(freq, hour, minute, weekdays, intervalHours));
    }
    if (freq === 'weekly') {
      const labels = (weekdays || []).map(d => {
        const f = DOW_LABELS.find(x => x.v === d);
        return f ? '周' + f.l : d;
      }).join('、') || '工作日';
      return '每周 ' + labels + ' ' + h + ':' + mi + ' · cron: ' + (cron || buildCron(freq, hour, minute, weekdays, intervalHours));
    }
    return '每天 ' + h + ':' + mi + ' · cron: ' + (cron || buildCron(freq, hour, minute, weekdays, intervalHours));
  }

  function parseCronToUi(cron) {
    const out = {
      enabled: false,
      freq: 'daily',
      hour: 8,
      minute: 0,
      weekdays: [1, 2, 3, 4, 5],
      intervalHours: 6,
      cron: cron || '',
      preset_id: 'daily_08',
    };
    if (!cron || typeof cron !== 'string') return out;
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5) return out;
    const [min, hour, dom, mon, dow] = parts;
    if (dom === '*' && mon === '*' && hour.startsWith('*/')) {
      out.freq = 'interval';
      out.intervalHours = parseInt(hour.slice(2), 10) || 6;
      out.preset_id = 'every_' + out.intervalHours + 'h';
      return out;
    }
    out.minute = parseInt(min, 10) || 0;
    out.hour = parseInt(hour, 10) || 0;
    if (dow !== '*') {
      out.freq = 'weekly';
      out.weekdays = dow.split(',').map(x => parseInt(x, 10)).filter(x => !Number.isNaN(x));
      out.preset_id = 'weekly_custom';
    } else {
      out.freq = 'daily';
      out.preset_id = 'daily_' + pad2(out.hour) + pad2(out.minute);
    }
    return out;
  }

  function getScheduleFromDom() {
    const enabled = !!document.getElementById('tScheduleEnabled')?.checked;
    const freq = document.getElementById('tScheduleFreq')?.value || 'daily';
    const hour = document.getElementById('tScheduleHour')?.value || '8';
    const minute = document.getElementById('tScheduleMinute')?.value || '0';
    const intervalHours = document.getElementById('tScheduleInterval')?.value || '6';
    const weekdays = Array.from(document.querySelectorAll('input[name=tScheduleDow]:checked')).map(el => parseInt(el.value, 10));
    const cron = buildCron(freq, hour, minute, weekdays, intervalHours);
    const preset_id = freq === 'daily'
      ? ('daily_' + pad2(hour) + pad2(minute))
      : (freq === 'interval' ? ('every_' + intervalHours + 'h') : 'weekly_custom');
    return {
      enabled,
      cron,
      timezone: 'Asia/Shanghai',
      preset_id,
      skip_if_running: true,
      _preview: describeCron(freq, hour, minute, weekdays, intervalHours, cron),
    };
  }

  function fillScheduleForm(schedule) {
    const s = schedule || {};
    const ui = parseCronToUi(s.cron || '');
    ui.enabled = !!s.enabled;
    const en = document.getElementById('tScheduleEnabled');
    if (en) en.checked = ui.enabled;
    const freq = document.getElementById('tScheduleFreq');
    if (freq) freq.value = ui.freq;
    const hour = document.getElementById('tScheduleHour');
    if (hour) hour.value = String(ui.hour);
    const minute = document.getElementById('tScheduleMinute');
    if (minute) minute.value = String(ui.minute);
    const interval = document.getElementById('tScheduleInterval');
    if (interval) interval.value = String(ui.intervalHours);
    document.querySelectorAll('input[name=tScheduleDow]').forEach(el => {
      el.checked = ui.weekdays.includes(parseInt(el.value, 10));
    });
    updateSchedulePreview();
    toggleScheduleFields();
  }

  function toggleScheduleFields() {
    const enabled = !!document.getElementById('tScheduleEnabled')?.checked;
    const box = document.getElementById('scheduleFields');
    if (box) box.style.display = enabled ? 'block' : 'none';
    const freq = document.getElementById('tScheduleFreq')?.value || 'daily';
    const weekly = document.getElementById('scheduleWeeklyRow');
    const interval = document.getElementById('scheduleIntervalRow');
    const time = document.getElementById('scheduleTimeRow');
    if (weekly) weekly.style.display = freq === 'weekly' ? 'flex' : 'none';
    if (interval) interval.style.display = freq === 'interval' ? 'flex' : 'none';
    if (time) time.style.display = freq === 'interval' ? 'none' : 'flex';
  }

  function updateSchedulePreview() {
    const s = getScheduleFromDom();
    const el = document.getElementById('tSchedulePreview');
    if (el) el.textContent = s.enabled ? s._preview : '定时未启用';
  }

  function initSchedulePicker() {
    const hourEl = document.getElementById('tScheduleHour');
    const minEl = document.getElementById('tScheduleMinute');
    if (hourEl && !hourEl.options.length) {
      for (let h = 0; h < 24; h++) {
        const o = document.createElement('option');
        o.value = String(h);
        o.textContent = pad2(h);
        hourEl.appendChild(o);
      }
      hourEl.value = '8';
    }
    if (minEl && !minEl.options.length) {
      for (let m = 0; m < 60; m += 5) {
        const o = document.createElement('option');
        o.value = String(m);
        o.textContent = pad2(m);
        minEl.appendChild(o);
      }
    }
    ['tScheduleEnabled', 'tScheduleFreq', 'tScheduleHour', 'tScheduleMinute', 'tScheduleInterval'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', () => { toggleScheduleFields(); updateSchedulePreview(); });
    });
    document.querySelectorAll('input[name=tScheduleDow]').forEach(el => {
      el.addEventListener('change', updateSchedulePreview);
    });
    toggleScheduleFields();
    updateSchedulePreview();
  }

  global.SchedulePicker = {
    buildCron,
    describeCron,
    parseCronToUi,
    getScheduleFromDom,
    fillScheduleForm,
    initSchedulePicker,
    updateSchedulePreview,
  };
})(window);
