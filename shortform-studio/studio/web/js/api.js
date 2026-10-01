// api.js — thin JSON fetch wrappers used by every view.

async function handle(res) {
  let json = null;
  try {
    json = await res.json();
  } catch (e) {
    json = null;
  }
  if (!res.ok) {
    const msg = (json && json.error) || res.statusText || `HTTP ${res.status}`;
    const err = new Error(msg);
    if (json && Array.isArray(json.errors)) err.errors = json.errors;
    throw err;
  }
  return json;
}

export async function get(path) {
  const res = await fetch(path);
  return handle(res);
}

export async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  return handle(res);
}

export async function put(path, body) {
  const res = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  return handle(res);
}

export async function patch(path, body) {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  return handle(res);
}

export async function del(path) {
  const res = await fetch(path, { method: 'DELETE' });
  return handle(res);
}
