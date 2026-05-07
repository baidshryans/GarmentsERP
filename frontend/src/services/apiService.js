// frontend/src/services/apiService.js — barrel re-export
// All domain modules re-exported so existing imports keep working.
// New code: import directly from "@/services/api/<domain>"
export * from "./api/userauth";
export * from "./api/contacts";
export * from "./api/accounting";
export * from "./api/sales";
export * from "./api/purchase";
export * from "./api/inventory";
export * from "./api/manufacturing";
export * from "./api/masters";
export * from "./api/goldscheme";
export * from "./api/goldrates";
export * from "./api/hr";
export * from "./api/fixedAssets";
export * from "./api/carryforward";
export * from "./api/vendorAnalytics";
export * from "./api/ai";
