import { browser } from '$app/environment';

export interface AccessibleBranch {
  id: string;
  company_id: string;
  name: string;
  code: string | null;
  is_active: boolean;
}

export interface OperationalContext {
  company_id: string;
  access_all_branches: boolean;
  last_branch_id: string | null;
  branches: AccessibleBranch[];
}

const STORAGE_KEY = 'erp_operational_branch';
const ALL_BRANCHES = '__all__';

function loadSelection(companyId: string): string | null | undefined {
  if (!browser) return undefined;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const saved = JSON.parse(raw) as { company_id: string; branch_id: string };
    if (saved.company_id !== companyId) return undefined;
    return saved.branch_id === ALL_BRANCHES ? null : saved.branch_id;
  } catch {
    return undefined;
  }
}

function createBranchStore() {
  let context = $state<OperationalContext | null>(null);
  let activeId = $state<string | null>(null);

  function persist() {
    if (!browser || !context) return;
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ company_id: context.company_id, branch_id: activeId ?? ALL_BRANCHES })
    );
  }

  return {
    get context() { return context; },
    get ready() { return context !== null; },
    get id() { return activeId; },
    get accessAllBranches() { return context?.access_all_branches ?? false; },
    get branches() { return context?.branches ?? []; },
    get active() { return context?.branches.find((item) => item.id === activeId) ?? null; },
    get label() { return activeId ? this.active?.name ?? 'Sucursal' : 'Todas las sucursales'; },
    configure(next: OperationalContext) {
      context = next;
      const saved = loadSelection(next.company_id);
      const candidate = saved !== undefined ? saved : next.last_branch_id;
      if (candidate === null && next.access_all_branches) activeId = null;
      else if (candidate && next.branches.some((item) => item.id === candidate)) activeId = candidate;
      else if (next.access_all_branches) activeId = null;
      else activeId = next.branches[0]?.id ?? null;
      persist();
    },
    select(branchId: string | null) {
      if (!context) return;
      if (branchId === null && !context.access_all_branches) return;
      if (branchId && !context.branches.some((item) => item.id === branchId)) return;
      activeId = branchId;
      persist();
    },
    clear() {
      context = null;
      activeId = null;
      if (browser) sessionStorage.removeItem(STORAGE_KEY);
    }
  };
}

export const branch = createBranchStore();
