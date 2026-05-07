// frontend/src/services/apiService.js
// ─────────────────────────────────────────────────────────────────────────────
// Barrel re-export — all domain API modules re-exported here so existing code
// that imports from "@/services/apiService" continues to work without changes.
//
// New code should import directly from the domain module:
//   import { createSalesVoucher } from "@/services/api/sales"
// ─────────────────────────────────────────────────────────────────────────────
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
