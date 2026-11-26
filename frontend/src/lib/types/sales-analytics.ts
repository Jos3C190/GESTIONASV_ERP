/** Análisis comercial (V9a). Montos sin IVA; costo y margen solo con `sales_costs:read`. */
export interface AnalysisTotals {
  net_sales: string;
  documents: number;
  average_ticket: string | null;
  returns: string;
  returns_percent: string | null;
  cost: string | null;
  margin: string | null;
  margin_percent: string | null;
}

export interface AnalysisBucket {
  key: string;
  label: string;
  net_sales: string;
  documents: number;
  quantity: string;
  cost: string | null;
  margin: string | null;
  margin_percent: string | null;
  goal: string | null;
  goal_percent: string | null;
}

export interface SalesAnalysis {
  start: string;
  end: string;
  costs_visible: boolean;
  totals: AnalysisTotals;
  by_day: AnalysisBucket[];
  by_hour: AnalysisBucket[];
  by_branch: AnalysisBucket[];
  by_category: AnalysisBucket[];
  top_customers: AnalysisBucket[];
  top_products: AnalysisBucket[];
  bottom_products: AnalysisBucket[];
}

export interface BranchGoal {
  branch_id: string;
  branch_name: string;
  amount: string | null;
}

export interface MonthGoals {
  period: string;
  goals: BranchGoal[];
}
