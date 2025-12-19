// auth.js
console.log('[auth] auth.js loaded');

// ✅ use the client we create in supabaseClient.js
const supabase = window.supabaseClient;

if (!supabase) {
  console.error(
    '[auth] supabaseClient is missing. ' +
    'Make sure supabaseClient.js is loaded BEFORE auth.js on every page.'
  );
}

/**
 * Get current user, redirect to login if not authenticated.
 * Used on protected pages like dashboard.html, flyers.html, etc.
 */
async function getCurrentUserOrRedirect() {
  console.log('[auth] getCurrentUserOrRedirect');

  const { data, error } = await supabase.auth.getUser();

  if (error) {
    console.error('[auth] getUser error', error);
  }

  const user = data?.user;

  if (!user) {
    console.warn('[auth] no user, redirecting to login');

    // remember where we were trying to go
    const params = new URLSearchParams({
      redirect: window.location.pathname,
    });

    window.location.href = `login.html?${params.toString()}`;
    throw new Error('Not authenticated');
  }

  return { user };
}

/**
 * Get current user without redirect (optional helper).
 */
async function getCurrentUser() {
  console.log('[auth] getCurrentUser');

  const { data, error } = await supabase.auth.getUser();

  if (error) {
    console.error('[auth] getUser error', error);
    return null;
  }

  return data?.user ?? null;
}
