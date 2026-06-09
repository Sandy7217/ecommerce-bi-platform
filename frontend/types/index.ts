export type Role = "super_admin" | "admin" | "manager" | "analyst" | "md" | "viewer";

export type Kpi = {
  title: string;
  value: string | number;
  trend?: number;
  alert?: "green" | "orange" | "red";
};

export type StyleRow = {
  style_color: string;
  category_new?: string;
  cross_category?: string;
  inventory_status?: string;
  total_inventory?: number;
  ros?: number;
  ros_7d?: number;
  ros_30d?: number;
  doi?: number;
  priority?: string;
};

export type NavItem = {
  label: string;
  href: string;
  access: string;
};
