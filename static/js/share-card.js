// Draws a milestone share card on a <canvas> and offers Download / Share. No libraries.
const SIZE = 1080;
const FONT = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

function wrap(ctx, text, maxWidth) {
  const words = text.split(" ");
  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

export function drawCard(canvas, { emoji, text, date, site }) {
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#FBF7F0";
  ctx.fillRect(0, 0, SIZE, SIZE);
  ctx.fillStyle = "#FFEDD5";
  ctx.beginPath();
  ctx.arc(SIZE / 2, 360, 220, 0, Math.PI * 2);
  ctx.fill();

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = `220px ${FONT}`;
  ctx.fillText(emoji, SIZE / 2, 370);

  ctx.fillStyle = "#1F2933";
  ctx.font = `bold 76px ${FONT}`;
  const lines = wrap(ctx, text, SIZE - 160);
  lines.forEach((line, i) => ctx.fillText(line, SIZE / 2, 700 + i * 92 - (lines.length - 1) * 46));

  ctx.fillStyle = "#52606D";
  ctx.font = `40px ${FONT}`;
  ctx.fillText(date, SIZE / 2, 880);

  ctx.fillStyle = "#C2410C";
  ctx.fillRect(0, SIZE - 110, SIZE, 110);
  ctx.fillStyle = "#FFFFFF";
  ctx.font = `bold 44px ${FONT}`;
  ctx.fillText(`👟 First5K · ${site}`, SIZE / 2, SIZE - 55);
}

function toBlob(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

const root = document.querySelector("[data-share-card]");
if (root) {
  const canvas = root.querySelector("canvas");
  const data = root.dataset;
  drawCard(canvas, { emoji: data.emoji, text: data.text, date: data.date, site: data.site });

  const filename = `first5k-${data.key}.png`;
  root.querySelector("[data-download]").addEventListener("click", async () => {
    const blob = await toBlob(canvas);
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  const shareBtn = root.querySelector("[data-share]");
  const probe = new File([new Blob()], filename, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [probe] })) {
    shareBtn.hidden = false;
    shareBtn.addEventListener("click", async () => {
      const file = new File([await toBlob(canvas)], filename, { type: "image/png" });
      try {
        await navigator.share({ files: [file], text: `${data.text} #First5K` });
      } catch (err) {
        /* user cancelled: nothing to do */
      }
    });
  }
  root.hidden = false;
}
