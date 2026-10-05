// Small fetch helpers. Server stays the source of truth; we only POST and render the reply.

export function csrfTokenFrom(form) {
  const input = form.querySelector('input[name="csrfmiddlewaretoken"]');
  return input ? input.value : "";
}

export async function postForm(form, body = new FormData(form)) {
  const response = await fetch(form.action, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRFToken": csrfTokenFrom(form) },
    body,
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}
