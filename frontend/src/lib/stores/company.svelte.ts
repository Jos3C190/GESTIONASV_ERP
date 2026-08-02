import { browser } from '$app/environment';

export interface ActiveCompany {
  id: string;
  name: string;
  commercial_name: string;
  logo: string | null;
}

const STORAGE_KEY = 'erp_active_company';

function load(): ActiveCompany | null {
  if (!browser) return null;
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value ? (JSON.parse(value) as ActiveCompany) : null;
  } catch {
    return null;
  }
}

function createCompanyStore() {
  let active = $state<ActiveCompany | null>(load());
  return {
    get active() { return active; },
    get id() { return active?.id ?? null; },
    select(company: ActiveCompany) {
      active = company;
      if (browser) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(company));
    },
    clear() {
      active = null;
      if (browser) sessionStorage.removeItem(STORAGE_KEY);
    }
  };
}

export const company = createCompanyStore();
