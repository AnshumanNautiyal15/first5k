// Feedback: POST via fetch, show the acknowledgement briefly, then follow the server's redirect.
// Without JS the form posts normally and the server redirects.
import { postForm } from "./api.js";

document.querySelectorAll("[data-feedback-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const choice = event.submitter;
    const data = new FormData(form);
    if (choice && choice.name) data.set(choice.name, choice.value);
    form.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      const result = await postForm(form, data);
      if (result.message) {
        const note = document.createElement("p");
        note.className = "tip mt-4 text-center";
        note.setAttribute("role", "status");
        note.textContent = result.message;
        form.appendChild(note);
      }
      setTimeout(() => window.location.assign(result.redirect), result.message ? 1400 : 0);
    } catch (err) {
      // Fallback: resubmit natively with the chosen value.
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "feedback";
      hidden.value = choice ? choice.value : "";
      form.appendChild(hidden);
      form.submit();
    }
  });
});
