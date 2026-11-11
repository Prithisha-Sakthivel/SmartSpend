document.addEventListener('DOMContentLoaded', () => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const toggle = document.getElementById('menuToggle');
  const sidebar = document.getElementById('sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
      toggle.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');
    });
    sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      sidebar.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.focus();
      }
    });
  }

  document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));

  document.querySelectorAll('form.auth-form').forEach(form => form.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    const submitter = event.submitter;
    if (submitter) {
      submitter.classList.add('is-loading');
      submitter.setAttribute('aria-busy', 'true');
    }
  }));

  // Animate only INR amounts: runway days, dates and unavailable values stay literal.
  if (!reduceMotion) {
    const currencyPattern = /^(-?)₹([\d,]+)\.(\d{2})$/;
    document.querySelectorAll('.balance-number, .safe-number, .metric strong, .report-summary strong').forEach(node => {
      const original = node.textContent.trim();
      const match = original.match(currencyPattern);
      if (!match) return;
      const target = (Number(match[2].replace(/,/g, '')) * 100 + Number(match[3])) * (match[1] ? -1 : 1);
      if (!Number.isFinite(target) || target === 0) return;
      const start = performance.now();
      const duration = 520;
      const draw = now => {
        const progress = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = Math.round(target * eased);
        const sign = value < 0 ? '-' : '';
        const whole = Math.floor(Math.abs(value) / 100);
        const cents = String(Math.abs(value) % 100).padStart(2, '0');
        node.textContent = `${sign}₹${whole.toLocaleString('en-IN')}.${cents}`;
        if (progress < 1) requestAnimationFrame(draw);
        else node.textContent = original;
      };
      requestAnimationFrame(draw);
    });

    // Start from zero only for a frame, then transition to the server-rendered value.
    document.querySelectorAll('.progress-fill, .safe-meter span, .streak-track span').forEach(fill => {
      const targetWidth = fill.style.width;
      if (!targetWidth) return;
      fill.classList.add('motion-ready');
      fill.style.width = '0%';
      requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = targetWidth; }));
    });
  }

  // Keep the selected CTAs easy to click; the pointer response is capped at 3 px.
  const finePointer = window.matchMedia('(pointer: fine)').matches;
  if (finePointer && !reduceMotion) {
    document.querySelectorAll('.page-heading > .button-primary, .auth-form .button-primary').forEach(button => {
      button.classList.add('magnetic-button');
      button.addEventListener('pointermove', event => {
        const rect = button.getBoundingClientRect();
        const x = Math.max(-3, Math.min(3, (event.clientX - rect.left - rect.width / 2) / rect.width * 3));
        const y = Math.max(-3, Math.min(3, (event.clientY - rect.top - rect.height / 2) / rect.height * 3));
        button.style.setProperty('--mag-x', `${x.toFixed(1)}px`);
        button.style.setProperty('--mag-y', `${y.toFixed(1)}px`);
      });
      button.addEventListener('pointerleave', () => {
        button.style.setProperty('--mag-x', '0px');
        button.style.setProperty('--mag-y', '0px');
      });
    });

    const hero = document.querySelector('.hero-finance');
    if (hero) hero.addEventListener('pointermove', event => {
      const rect = hero.getBoundingClientRect();
      hero.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`);
      hero.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`);
    });
  }

  document.querySelectorAll('.password-toggle').forEach(button => button.addEventListener('click', () => {
    const input = button.closest('.password-field')?.querySelector('input');
    if (!input) return;
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.textContent = visible ? 'Hide' : 'Show';
    button.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
    button.setAttribute('aria-pressed', String(visible));
    input.focus();
  }));

  const kind = document.getElementById('challengeType');
  const target = document.getElementById('challengeTarget');
  const installment = document.getElementById('challengeInstallment');
  function updateChallenge() {
    if (!kind) return;
    const noSpend = kind.value === 'no_spend';
    const fixed = kind.value === 'fixed_cadence';
    if (target) { target.required = !noSpend; target.disabled = noSpend; }
    if (installment) { installment.required = fixed; installment.disabled = !fixed; }
    document.querySelectorAll('.no-spend-category').forEach(label => {
      const select = label.querySelector('select');
      label.hidden = !noSpend;
      if (select) select.required = noSpend;
    });
  }
  if (kind) { kind.addEventListener('change', updateChallenge); updateChallenge(); }

  const impact = document.getElementById('purchaseImpact');
  const amountInput = document.querySelector('.purchase-form input[name="amount"]');
  if (impact && amountInput) {
    const formatINR = paise => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const funds = impact.dataset.funds === '' ? null : Number(impact.dataset.funds);
    const safe = impact.dataset.safe === '' ? null : Number(impact.dataset.safe);
    const budget = impact.dataset.budget === '' ? null : Number(impact.dataset.budget);
    const updateImpact = () => {
      const raw = Number(amountInput.value);
      const purchase = Number.isFinite(raw) && raw > 0 ? Math.round(raw * 100) : 0;
      const submittedAmount = impact.querySelector('form input[name="amount"]');
      if (submittedAmount) submittedAmount.value = amountInput.value;
      const price = document.getElementById('impactPrice');
      const balance = document.getElementById('impactBalance');
      const safeAfter = document.getElementById('impactSafe');
      const budgetAfter = document.getElementById('impactBudget');
      if (price) price.textContent = formatINR(purchase);
      if (balance && funds !== null) balance.textContent = formatINR(funds - purchase);
      if (safeAfter && safe !== null) safeAfter.textContent = formatINR(Math.max(0, safe - purchase));
      if (budgetAfter && budget !== null) budgetAfter.textContent = `${formatINR(budget - purchase)} remaining`;
    };
    amountInput.addEventListener('input', updateImpact);
    updateImpact();
  }
});
