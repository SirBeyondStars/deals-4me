// auth/scripts/user-greeting.js

export async function initUserGreeting(supabase) {
  const nameSpan = document.getElementById('userName');
  if (!nameSpan || !supabase) return;

  try {
    // Get logged-in user
    const { data: userData, error: userError } = await supabase.auth.getUser();
    if (userError || !userData?.user) {
      nameSpan.textContent = "Guest";
      return;
    }

    const userId = userData.user.id;

    // Load profile row (profiles.id == auth user id)
    const { data: profileData, error: profileError } = await supabase
      .from('profiles')
      .select('full_name')
      .eq('id', userId)
      .single();

    if (profileError || !profileData) {
      nameSpan.textContent = "Guest";
      return;
    }

    nameSpan.textContent = profileData.full_name || "Guest";
  } catch (err) {
    console.error("Error initializing greeting:", err);
    nameSpan.textContent = "Guest";
  }
}
