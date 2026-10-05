// Progressive enhancement for "Mark day complete": POST via fetch, show the
// server's compliment, celebrate. Without JS the form posts normally.
import { postForm } from "./api.js";
import { confetti } from "./confetti.js";

const live = document.querySelector("[data-live-region]");

function renderDone(status, message) {
  status.innerHTML = "";
  const done = document.createElement("p");
  done.className = "btn-done";
  done.innerHTML = '<span aria-hidden="true">✓</span> Done';
  status.appendChild(done);
  if (message) {
    const p = document.createElement("p");
    p.className = "mt-3 text-center";
    p.textContent = message; // textContent: never inject HTML
    status.appendChild(p);
  }
}

document.querySelectorAll("[data-complete-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const data = await postForm(form);
      const status = form.closest("[data-day-status]");
      renderDone(status, data.message);
      if (live) live.textContent = data.message;
      if (!data.already_done) confetti();
      if (data.milestone_url) {
        const wrap = document.querySelector("[data-milestone-link]");
        if (wrap) {
          wrap.querySelector("a").href = data.milestone_url;
          wrap.hidden = false;
        }
      }
      if (data.block_done) {
        const done = document.querySelector("[data-block-done]");
        if (done) done.hidden = false;
        document.querySelector("[data-done-early]")?.remove();
      }
    } catch (err) {
      // Fall back to a normal form post so the action still works.
      form.submit();
    }
  });
});
