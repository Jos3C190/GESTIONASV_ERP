/**
 * Theme store with no-FOUC persistence.
 *
 * The initial theme is decided in app.html (inline script) BEFORE Svelte hydrates,
 * so we read the current state from the DOM at init time instead of computing it
 * here. This keeps a single source of truth and prevents flashes.
 */
import { browser } from '$app/environment';

type Theme = 'light' | 'dark';

const STORAGE_KEY = 'erp-theme';

function currentDomTheme(): Theme {
  if (!browser) return 'light';
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'dark' ? 'dark' : 'light';
}

function apply(theme: Theme): void {
  if (!browser) return;
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.style.colorScheme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore (private mode, quota, etc.)
  }
}

function makeThemeStore() {
  let value = $state<Theme>(currentDomTheme());

  return {
    get current(): Theme {
      return value;
    },
    toggle() {
      const next: Theme = value === 'dark' ? 'light' : 'dark';

      const doc = document as Document & {
        startViewTransition?: (callback: () => void) => void;
      };

      const switchTheme = () => {
        value = next;
        apply(value);
      };

      if (
        !browser ||
        !doc.startViewTransition ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ) {
        switchTheme();
        return;
      }

      doc.startViewTransition(switchTheme);
    },
    set(theme: Theme) {
      value = theme;
      apply(value);
    }
  };
}

export const theme = makeThemeStore();