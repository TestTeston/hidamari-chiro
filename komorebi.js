/* ひだまり 木漏れ日アニメの共有スクリプト（index.html以外の各ページ用） */
/* canvasの data-density="low" で控えめ版（記事ページ用）になる */
(() => {
  const cv = document.getElementById('komorebi');
  if (!cv || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx = cv.getContext('2d');
  const mobile = innerWidth < 600;
  const low = cv.dataset.density === 'low';   // 記事ページ＝読みやすさ優先で控えめ
  const k = low ? 0.45 : 1;                    // 控えめ係数
  const CONFIG = {
    motes:   Math.round((mobile ? 28 : 70) * k),
    moteR:   [4, 11],
    moteA:   [.5, .85],
    patches: Math.max(1, Math.round((mobile ? 2 : 4) * k)),
    shafts:  low ? 1 : (mobile ? 2 : 3),
    shaftA:  low ? .08 : .14,
    leaves:  low ? 2 : (mobile ? 3 : 5),
    leafA:   .09,
    speed:   .2,
    sway:    .5,
    scroll:  .25,
    light:   '232,201,168',
    shade:   '100,70,40',
    pointerR: 190,
    pointerA: .55,
    core:    '255,250,242',
    deep:    '202,146,97',
  };
  let W, H, motes = [], leaves = [], shafts = [], raf, lastSY = scrollY, sVel = 0;
  const rnd = (a, b) => a + Math.random() * (b - a);

  const fine = matchMedia('(pointer: fine)').matches;
  let mx = -9999, my = -9999, gx = 0, gy = 0, hasG = false;
  if (fine) {
    addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
    document.documentElement.addEventListener('mouseleave', () => { mx = -9999; hasG = false; });
  }

  // 光芒は1枚のスプライトに事前描画して使い回す（軽量化）
  const beam = (() => {
    const s = document.createElement('canvas'); s.width = 300; s.height = 1200;
    const c = s.getContext('2d');
    const gx2 = c.createLinearGradient(0, 0, 300, 0);
    gx2.addColorStop(0, `rgba(${CONFIG.light},0)`);
    gx2.addColorStop(.5, `rgba(${CONFIG.light},1)`);
    gx2.addColorStop(1, `rgba(${CONFIG.light},0)`);
    c.fillStyle = gx2; c.fillRect(0, 0, 300, 1200);
    const gy = c.createLinearGradient(0, 0, 0, 1200);
    gy.addColorStop(0, 'rgba(0,0,0,1)'); gy.addColorStop(.85, 'rgba(0,0,0,0)');
    c.globalCompositeOperation = 'destination-in';
    c.fillStyle = gy; c.fillRect(0, 0, 300, 1200);
    return s;
  })();

  function resize() { W = cv.width = innerWidth; H = cv.height = innerHeight; }
  function makeMote(big) { return {
    x: rnd(0, W), y: rnd(0, H),
    r: big ? rnd(40, 90) : rnd(CONFIG.moteR[0], CONFIG.moteR[1]),
    a: big ? rnd(.08, .14) : rnd(CONFIG.moteA[0], CONFIG.moteA[1]),
    vy: rnd(.3, 1) * CONFIG.speed, ph: rnd(0, 6.28), big
  };}
  function init() {
    motes = [
      ...Array.from({length: CONFIG.patches}, () => makeMote(true)),
      ...Array.from({length: CONFIG.motes},   () => makeMote(false))
    ];
    leaves = Array.from({length: CONFIG.leaves}, () => ({
      x: rnd(0, W), y: rnd(0, H * .8), r: rnd(60, 140),
      a: rnd(.5, 1) * CONFIG.leafA, ph: rnd(0, 6.28)
    }));
    shafts = Array.from({length: CONFIG.shafts}, (_, i) => ({
      x: (i + rnd(.3, .7)) / CONFIG.shafts,
      ang: .26 + rnd(-.06, .06), w: rnd(140, 320), ph: rnd(0, 6.28)
    }));
  }
  function tick(t) {
    ctx.clearRect(0, 0, W, H);
    sVel += ((scrollY - lastSY) - sVel) * .12; lastSY = scrollY;
    const pull = sVel * CONFIG.scroll;

    for (const s of shafts) {
      ctx.save();
      ctx.translate(s.x * W, -40);
      ctx.rotate(s.ang + Math.sin(t / 9000 + s.ph) * .025);
      ctx.globalAlpha = CONFIG.shaftA * (.55 + .45 * Math.sin(t / 5000 + s.ph));
      ctx.drawImage(beam, -s.w / 2, 0, s.w, H * 1.4);
      ctx.restore();
    }
    ctx.globalAlpha = 1;

    for (const l of leaves) {
      const lx = l.x + Math.sin(t / 3200 + l.ph) * 22;
      const lr = l.r * (1 + .08 * Math.sin(t / 2400 + l.ph * 2));
      l.y -= pull * .5;
      if (l.y < -l.r) l.y = H + l.r; else if (l.y > H + l.r) l.y = -l.r;
      const g = ctx.createRadialGradient(lx, l.y, 0, lx, l.y, lr);
      g.addColorStop(0, `rgba(${CONFIG.shade},${l.a})`);
      g.addColorStop(1, `rgba(${CONFIG.shade},0)`);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(lx, l.y, lr, 0, 6.28); ctx.fill();
    }

    for (const p of motes) {
      p.y -= p.vy + pull * (p.big ? .4 : 1);
      p.x += Math.sin(t / 4000 + p.ph) * CONFIG.sway;
      if (fine && hasG && !p.big) {
        const dx = p.x - gx, dy = p.y - gy, d2 = dx * dx + dy * dy;
        if (d2 < 28900) { const d = Math.sqrt(d2) || 1, f = (170 - d) / 170 * 3; p.x += dx / d * f; p.y += dy / d * f; }
      }
      if (p.y < -p.r) { p.y = H + p.r; p.x = rnd(0, W); }
      else if (p.y > H + p.r) { p.y = -p.r; p.x = rnd(0, W); }
      const tw = p.big ? 1 : .6 + .4 * Math.sin(t / 1200 + p.ph);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
      if (p.big) {
        g.addColorStop(0, `rgba(${CONFIG.light},${p.a * tw})`);
        g.addColorStop(1, `rgba(${CONFIG.light},0)`);
      } else {
        g.addColorStop(0, `rgba(${CONFIG.core},${p.a * tw})`);
        g.addColorStop(.55, `rgba(${CONFIG.deep},${p.a * tw * .55})`);
        g.addColorStop(1, `rgba(${CONFIG.deep},0)`);
      }
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.28); ctx.fill();
    }

    if (fine && mx > -999) {
      if (!hasG) { gx = mx; gy = my; hasG = true; }
      gx += (mx - gx) * .07; gy += (my - gy) * .07;
      const g = ctx.createRadialGradient(gx, gy, 0, gx, gy, CONFIG.pointerR);
      g.addColorStop(0, `rgba(${CONFIG.core},${CONFIG.pointerA})`);
      g.addColorStop(.4, `rgba(${CONFIG.deep},${CONFIG.pointerA * .45})`);
      g.addColorStop(1, `rgba(${CONFIG.deep},0)`);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(gx, gy, CONFIG.pointerR, 0, 6.28); ctx.fill();
    }
    raf = requestAnimationFrame(tick);
  }
  addEventListener('resize', () => { resize(); init(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else raf = requestAnimationFrame(tick);
  });
  resize(); init(); raf = requestAnimationFrame(tick);
})();

// カード：ポインター位置に合わせてわずかに傾く（マウス環境のみ）
if (matchMedia('(pointer: fine)').matches) {
  document.querySelectorAll('.blog-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.transition = 'transform .06s ease-out, box-shadow .25s ease, border-color .25s ease';
    });
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      const ry = ((e.clientX - r.left) / r.width  - .5) *  16;
      const rx = ((e.clientY - r.top)  / r.height - .5) * -16;
      card.style.transform = `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px)`;
    });
    card.addEventListener('mouseleave', () => { card.style.transition = ''; card.style.transform = ''; });
  });
}
