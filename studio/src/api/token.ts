/**
 * The Studio token (ui-ux-spec §9). It arrives once as ?token= in the link that
 * `etalon studio` prints; we keep it in localStorage (per origin, so per port) and
 * remove it from the address bar so it does not end up in bookmarks or screenshots.
 */
export const TOKEN_STORAGE_KEY = "etalon.studio.token";

let tabToken: string | null = null;

export function adoptToken(win: Window = window): string | null {
  const url = new URL(win.location.href);
  const fromUrl = url.searchParams.get("token");
  if (fromUrl) {
    tabToken = fromUrl;
    try {
      win.localStorage.setItem(TOKEN_STORAGE_KEY, fromUrl);
    } catch {
      // Storage blocked (private window, policy): the token lives for this tab only.
    }
    url.searchParams.delete("token");
    win.history.replaceState(win.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    return fromUrl;
  }
  if (tabToken) return tabToken;
  try {
    return win.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** For tests: forget the token held for this tab. */
export function forgetTabToken(): void {
  tabToken = null;
}
