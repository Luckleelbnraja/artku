/* =========================================================
   hero.js
   Lukisan di bagian hero + lensa "pandangan model".
   Lukisan digambar sekali ke canvas tersembunyi (base),
   lalu setiap frame lensa ditumpuk di posisi kursor.
   ========================================================= */
(() => {
  // ---------- Pengaturan (silakan ubah) ----------
  const SEED = 42;          // angka acak tetap, supaya lukisan selalu sama
  const STROKE_COUNT = 2600; // jumlah sapuan kuas
  const PIXEL_SIZE = 14;    // ukuran kotak piksel di dalam lensa
  const LENS_RATIO = 0.11;  // radius lensa dibanding lebar canvas

  // Warna sapuan per lapisan: langit, senja, laut
  const PALETTES = {
    sky:   ["#3A2E7A", "#5B3F9C", "#8E4A9E", "#C8567A"],
    dusk:  ["#F2A65A", "#F7D27A", "#E8795B", "#C8567A"],
    water: ["#1F6F78", "#2B8A8C", "#154B5A", "#0E3A4A"],
  };

  // ---------- Elemen dan state ----------
  const canvas = document.getElementById("lens");
  const ctx = canvas.getContext("2d");
  const base = document.createElement("canvas");   // lukisan asli
  const pixelated = document.createElement("canvas"); // versi resolusi rendah

  let width, height, radius;
  let lensX = null, lensY = 0;  // null = lensa disembunyikan
  let time = 0;                 // untuk menggerakkan peta panas

  // Generator angka acak sederhana dengan seed
  function seededRandom(seed) {
    return () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  }

  function paletteAt(yRatio) {
    if (yRatio < 0.5) return PALETTES.sky;
    if (yRatio < 0.72) return PALETTES.dusk;
    return PALETTES.water;
  }

  // ---------- 1. Menggambar lukisan ----------
  function paintCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.getBoundingClientRect();
    width = canvas.width = Math.round(rect.width * dpr);
    height = canvas.height = Math.round(rect.height * dpr);
    radius = Math.max(70, width * LENS_RATIO);

    base.width = width;
    base.height = height;
    const b = base.getContext("2d");
    const random = seededRandom(SEED);

    // Latar gradasi
    const bg = b.createLinearGradient(0, 0, 0, height);
    bg.addColorStop(0, "#2B2358");
    bg.addColorStop(0.5, "#C8567A");
    bg.addColorStop(0.72, "#F2A65A");
    bg.addColorStop(1, "#1F6F78");
    b.fillStyle = bg;
    b.fillRect(0, 0, width, height);

    // Sapuan kuas acak
    b.lineCap = "round";
    for (let i = 0; i < STROKE_COUNT; i++) {
      const x = random() * width;
      const y = random() * height;
      const palette = paletteAt(y / height);
      const angle = (random() - 0.5) * 0.9;
      const length = (18 + random() * 40) * dpr / 1.5;

      b.strokeStyle = palette[Math.floor(random() * palette.length)];
      b.globalAlpha = 0.55 + random() * 0.4;
      b.lineWidth = (3 + random() * 8) * dpr / 1.5;
      b.beginPath();
      b.moveTo(x, y);
      b.quadraticCurveTo(
        x + Math.cos(angle) * length * 0.5,
        y + Math.sin(angle) * length * 0.5 - 6,
        x + Math.cos(angle) * length,
        y + Math.sin(angle) * length
      );
      b.stroke();
    }

    // Cahaya matahari
    b.globalAlpha = 1;
    const sun = b.createRadialGradient(width * 0.3, height * 0.3, 0, width * 0.3, height * 0.3, width * 0.12);
    sun.addColorStop(0, "#FFF3C4");
    sun.addColorStop(1, "#F7D27A00");
    b.fillStyle = sun;
    b.fillRect(0, 0, width, height);

    // Versi resolusi rendah, dipakai untuk efek piksel di lensa
    const cell = PIXEL_SIZE * dpr;
    pixelated.width = Math.ceil(width / cell);
    pixelated.height = Math.ceil(height / cell);
    pixelated.getContext("2d").drawImage(base, 0, 0, pixelated.width, pixelated.height);
  }

  // ---------- 2. Menggambar lensa ----------
  function drawLens() {
    const x = lensX, y = lensY, r = radius;

    ctx.save();
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.clip(); // semua yang digambar setelah ini hanya tampak di dalam lensa

    // a) lukisan versi piksel + tint ungu
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(pixelated, 0, 0, width, height);
    ctx.imageSmoothingEnabled = true;
    ctx.fillStyle = "#8493FF55";
    ctx.fillRect(x - r, y - r, r * 2, r * 2);

    // b) garis kisi mengikuti kotak piksel
    const cell = width / pixelated.width;
    ctx.strokeStyle = "#ffffff30";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let gx = Math.floor((x - r) / cell) * cell; gx < x + r; gx += cell) {
      ctx.moveTo(gx, y - r);
      ctx.lineTo(gx, y + r);
    }
    for (let gy = Math.floor((y - r) / cell) * cell; gy < y + r; gy += cell) {
      ctx.moveTo(x - r, gy);
      ctx.lineTo(x + r, gy);
    }
    ctx.stroke();

    // c) peta panas yang bergeser pelan
    const hx = x + Math.sin(time) * r * 0.25;
    const hy = y + Math.cos(time * 0.8) * r * 0.2;
    const heat = ctx.createRadialGradient(hx, hy, 0, hx, hy, r * 0.7);
    heat.addColorStop(0, "#E5322DE6");
    heat.addColorStop(0.45, "#F2A33AAA");
    heat.addColorStop(1, "#F2A33A00");
    ctx.fillStyle = heat;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
    ctx.restore();

    // d) cincin dan label
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = "#fff";
    ctx.font = `600 ${Math.round(r * 0.13)}px Figtree, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("pandangan model", x, y + r * 1.22);
  }

  // ---------- 3. Animasi dan input ----------
  function frame() {
    time += 0.03;
    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(base, 0, 0);
    if (lensX !== null) drawLens();
    requestAnimationFrame(frame);
  }

  function moveLens(e) {
    const rect = canvas.getBoundingClientRect();
    const scale = width / rect.width; // CSS pixel -> pixel canvas
    lensX = (e.clientX - rect.left) * scale;
    lensY = (e.clientY - rect.top) * scale;
  }

  canvas.addEventListener("pointermove", moveLens);
  canvas.addEventListener("pointerdown", moveLens);
  canvas.addEventListener("pointerleave", () => { lensX = null; });

  // Gambar ulang saat ukuran layar berubah (ditunda supaya tidak berat)
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { paintCanvas(); lensX = null; }, 150);
  });

  // Mulai: lensa muncul di tengah-kanan sebagai petunjuk
  paintCanvas();
  lensX = width * 0.62;
  lensY = height * 0.5;
  frame();
})();
