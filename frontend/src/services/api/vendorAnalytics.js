// frontend/src/services/api/vendorAnalytics.js
import apiClient from "../apiClient";

function _buildVendorParams(filters = {}) {
  const params = new URLSearchParams();
  const { vendor_id, from_date, to_date, item_type, purity_id, design_code, retail_id } = filters;
  if (vendor_id)   params.set('vendor_id',   vendor_id);
  if (from_date)   params.set('from_date',   from_date);
  if (to_date)     params.set('to_date',     to_date);
  if (item_type)   params.set('item_type',   item_type);
  if (purity_id)   params.set('purity_id',   purity_id);
  if (design_code) params.set('design_code', design_code);
  if (retail_id)   params.set('retail_id',   retail_id);
  return params.toString();
}

export async function fetchVendorDashboard(filters = {}) {
  try {
    const qs = _buildVendorParams(filters);
    const response = await apiClient.get(`/vendor-analytics/api/vendor-dashboard/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVendorStockAgeing(filters = {}) {
  try {
    const qs = _buildVendorParams(filters);
    const response = await apiClient.get(`/vendor-analytics/api/stock-ageing/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVendorDesignPerformance(filters = {}) {
  try {
    const qs = _buildVendorParams(filters);
    const response = await apiClient.get(`/vendor-analytics/api/design-performance/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVendorInventoryTurnover(filters = {}) {
  try {
    const qs = _buildVendorParams(filters);
    const response = await apiClient.get(`/vendor-analytics/api/inventory-turnover/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVendorItemPerformance(filters = {}) {
  try {
    const qs = _buildVendorParams(filters);
    const response = await apiClient.get(`/vendor-analytics/api/item-performance/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVendorComparison(filters = {}) {
  try {
    const params = new URLSearchParams();
    const { vendor_ids, from_date, to_date, item_type, purity_id, design_code } = filters;
    // vendor_ids is an array; join to comma-separated string
    if (vendor_ids?.length) params.set('vendor_ids', vendor_ids.join(','));
    if (from_date)   params.set('from_date',   from_date);
    if (to_date)     params.set('to_date',     to_date);
    if (item_type)   params.set('item_type',   item_type);
    if (purity_id)   params.set('purity_id',   purity_id);
    if (design_code) params.set('design_code', design_code);
    const qs = params.toString();
    const response = await apiClient.get(`/vendor-analytics/api/vendor-comparison/${qs ? '?' + qs : ''}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
