// Handles the login and register forms: talks to the REST auth API,
// shows inline feedback in the DOM, and redirects on success.

function showFormMsg(text, type) {
  const el = document.getElementById('formMsg');
  if (!el) return;
  el.textContent = text;
  el.className = 'form-msg ' + type;
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const identifier = document.getElementById('identifier').value.trim();
    const password = document.getElementById('password').value;

    const submitBtn = loginForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Signing in…';

    const { ok, data } = await postJSON('/api/login', { username: identifier, password });

    if (ok) {
      showFormMsg('Signed in — redirecting…', 'success');
      window.location.href = '/dashboard';
    } else {
      showFormMsg(data.error || 'Could not sign in.', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Sign in';
    }
  });
}

const registerForm = document.getElementById('registerForm');
if (registerForm) {
  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    const submitBtn = registerForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating account…';

    const { ok, data } = await postJSON('/api/register', { username, email, password });

    if (ok) {
      showFormMsg('Account created — redirecting…', 'success');
      window.location.href = '/dashboard';
    } else {
      showFormMsg(data.error || 'Could not create account.', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Create account';
    }
  });
}