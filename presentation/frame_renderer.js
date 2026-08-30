/* TangTang V10 FrameRenderer (browser).
 *
 * Always clearRect the visible canvas before drawing. Cross-fade is composited
 * onto a freshly cleared offscreen buffer so the previous dog never sits under
 * the next one on-screen. Previous-frame opacity is capped so a fade cannot
 * read as a second dog.
 */
(function (root) {
  const FADE_CAP = 0.4;

  function wipe(ctx) {
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "copy";
    ctx.clearRect(0, 0, w, h);
    ctx.globalCompositeOperation = "source-over";
    ctx.clearRect(0, 0, w, h);
    ctx.restore();
  }

  function createFrameRenderer(canvas) {
    const ctx = canvas.getContext("2d", { alpha: true });
    const off = document.createElement("canvas");
    off.width = canvas.width;
    off.height = canvas.height;
    const octx = off.getContext("2d", { alpha: true });

    function draw(currentImg, previousImg, fadeT) {
      const w = canvas.width;
      const h = canvas.height;
      if (off.width !== w || off.height !== h) {
        off.width = w;
        off.height = h;
      }
      wipe(octx);
      const fading =
        previousImg &&
        typeof fadeT === "number" &&
        fadeT > 0 &&
        fadeT < 1;
      if (fading) {
        const prevA = Math.min(FADE_CAP, Math.max(0, 1 - fadeT));
        octx.globalAlpha = prevA;
        octx.drawImage(previousImg, 0, 0, w, h);
        octx.globalAlpha = Math.max(fadeT, 1 - prevA);
        octx.drawImage(currentImg, 0, 0, w, h);
      } else if (currentImg) {
        octx.globalAlpha = 1;
        octx.drawImage(currentImg, 0, 0, w, h);
      }
      octx.globalAlpha = 1;
      wipe(ctx);
      ctx.drawImage(off, 0, 0);
    }

    function clear() {
      wipe(ctx);
      wipe(octx);
    }

    return { draw, clear, fadeCap: FADE_CAP };
  }

  root.TangTangFrameRenderer = { create: createFrameRenderer, FADE_CAP };
})(typeof window !== "undefined" ? window : globalThis);
