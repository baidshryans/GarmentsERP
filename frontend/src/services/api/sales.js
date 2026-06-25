// frontend/src/services/api/sales.js
import apiClient from "../apiClient";
import { deleteResource, handleDelete } from "./_helpers";

// ── Next-number helpers ────────────────────────────────────────────────────────

export async function fetchOrderNoNext() {
  try {
    const response = await apiClient.get(`/sales/api/order-no/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleRetNext() {
  try {
    const response = await apiClient.get(`/sales/api/next_sr_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextSaleNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sv_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextSaleAppNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sa_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextSARNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sar_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchNextSARNo:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalReturns({ search = "", page = 1, ordering = "", allFy = false } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval-return/`, {
      params: { search, page, ordering, ...(allFy ? { all_fy: "1" } : {}) },
    });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchSalesApprovalReturns:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalReturnById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval-return/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchSalesApprovalReturnById:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createSalesApprovalReturn(data) {
  try {
    const response = await apiClient.post(`/sales/api/sale-approval-return/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("createSalesApprovalReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesApprovalReturn(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-approval-return/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("updateSalesApprovalReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteSalesApprovalReturn(id, toast) {
  const result = await deleteResource("sales/api/sale-approval-return", id);
  handleDelete(result, toast, "Sales approval return deleted successfully.");
}

// ── Initial data ───────────────────────────────────────────────────────────────

// Cache key includes the active retail so different retails don't share data.
// 5-minute TTL keeps stale-data risk low while making subsequent loads instant.
const SVID_CACHE_TTL_MS = 5 * 60 * 1000;
const _svidInflight = { promise: null, retailKey: null };

function _svidCacheKey() {
  const retail = sessionStorage.getItem("retail_code") || "default";
  return `svid::${retail}`;
}

export function invalidateSaleVoucherInitialData() {
  try { sessionStorage.removeItem(_svidCacheKey()); } catch {}
}

export async function fetchSaleVoucherInitialData({ force = false } = {}) {
  const key = _svidCacheKey();
  // In-flight de-dupe — share a single network call across simultaneous callers
  if (!force && _svidInflight.promise && _svidInflight.retailKey === key) {
    return _svidInflight.promise;
  }
  // sessionStorage cache with TTL
  if (!force) {
    try {
      const raw = sessionStorage.getItem(key);
      if (raw) {
        const { ts, data } = JSON.parse(raw);
        if (Date.now() - ts < SVID_CACHE_TTL_MS) {
          return { success: true, data };
        }
      }
    } catch {}
  }
  const p = (async () => {
    try {
      const response = await apiClient.get(`/sales/api/sale-voucher-initial-data/`);
      try {
        sessionStorage.setItem(key, JSON.stringify({ ts: Date.now(), data: response.data }));
      } catch {}
      return { success: true, data: response.data };
    } catch (error) {
      console.error("Failed to fetch sale voucher initial data:", error.response?.data || error.message);
      return { success: false, error: error.response?.data || error.message };
    } finally {
      if (_svidInflight.retailKey === key) {
        _svidInflight.promise = null;
        _svidInflight.retailKey = null;
      }
    }
  })();
  _svidInflight.promise = p;
  _svidInflight.retailKey = key;
  return p;
}

export async function fetchSaleReturnInitialData() {
  try {
    const response = await apiClient.get(`/sales/api/sale-return-initial-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch sale return initial data:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDetailsforSaleReturn(billno) {
  try {
    const response = await apiClient.get(`sales/api/get-sale-vou-for-return/?bill_no=${billno}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── List fetchers ──────────────────────────────────────────────────────────────

export async function fetchSalesVoucher({ search = "", page = 1, ordering = "", allFy = false } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (allFy) params.append("all_fy", "1");
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/sale-voucher/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesReturn({ search = "", page = 1, ordering = "", allFy = false } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (allFy) params.append("all_fy", "1");
    params.append("page", page);

    const response = await apiClient.get(`/sales/api/sale-return/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApproval({ search = "", page = 1, ordering = "", pendingOnly = false, allFy = false } = {}) {
  try {
    const params = new URLSearchParams();

    // Add query parameters conditionally
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    params.append("page", page);
    if (pendingOnly) params.append("pending_only", "true");
    if (allFy) params.append("all_fy", "1");

    const response = await apiClient.get(`/sales/api/sale-approval/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sales Approval CRUD ────────────────────────────────────────────────────────

export async function createSalesApproval(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-approval/', data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesApproval(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-approval/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Approval:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function returnSalesApprovalItems(id, returnedItemIds) {
  try {
    const response = await apiClient.post(
      `/sales/api/sale-approval/${id}/return-items/`,
      { returned_item_ids: returnedItemIds }
    );
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to record approval return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sales Return CRUD ──────────────────────────────────────────────────────────

export async function createSalesReturn(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-return/', data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesReturn(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-return/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesReturnById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-return/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Return:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleReturnPrintData(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-return/${id}/print-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Failed to fetch sale return print data:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sales Voucher CRUD ─────────────────────────────────────────────────────────

export async function createSalesVoucher(data) {
  try {
    const response = await apiClient.post('/sales/api/sale-voucher/', data);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesVoucher(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-voucher/${id}/`, data);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesVoucherwithID(id) {
  try {
    const response = await apiClient.get('/sales/api/sale-voucher/' + `${id}/`);
    return { success: response.status < 300, data: response.data };
  } catch (error) {
    console.error('Failed to create Sales Voucher:', error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Delete actions ─────────────────────────────────────────────────────────────

export const deleteSalesReturn = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-return", id);
  handleDelete(result, toast, "Sales return deleted successfully.");
};

export const deleteSalesApproval = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-approval", id);
  handleDelete(result, toast, "Sales approval deleted successfully.");
};

export const deleteSalesVoucher = async (id, toast) => {
  const result = await deleteResource("sales/api/sale-voucher", id);
  handleDelete(result, toast, "Sales voucher deleted successfully.");
};

// ── Customer Order ─────────────────────────────────────────────────────────────

export const deleteCustomerOrder = async (id, toast) => {
  const result = await deleteResource("sales/api/customer-orders-vs", id);
  handleDelete(result, toast, "Customer order deleted successfully.");
};

export async function cancelCustomerOrder(id) {
  try {
    const res = await apiClient.post(`/sales/api/customer-orders-vs/${id}/cancel/`);
    return { success: true, data: res.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDeliveryOverview() {
  try {
    const res = await apiClient.get('/sales/api/customer-orders/delivery-overview/');
    return { success: true, data: res.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateOrderDeliveryStatus(id, delivery_status, actual_delivery_date) {
  try {
    const body = { delivery_status };
    if (actual_delivery_date) body.actual_delivery_date = actual_delivery_date;
    const res = await apiClient.patch(`/sales/api/customer-orders/${id}/update-delivery/`, body);
    return { success: true, data: res.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchPendingCustomerOrderItems() {
  try {
    const response = await apiClient.get(`/sales/api/customer-orders/pending-items/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch pending customer order items:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerOrderTimeline(orderId) {
  try {
    const response = await apiClient.get(`/sales/api/customer-orders/${orderId}/timeline/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch customer order timeline:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerOrderForEdit(id) {
  try {
    const response = await apiClient.get(`/sales/api/customer-orders-vs/${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateCustomerOrderForEdit(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/customer-orders-vs/${id}/`, data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createCustomerOrder(data) {
  try {
    const response = await apiClient.post("/sales/api/customer-orders-vs/", data);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create CustomerOrder:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getCustomerItemAsPurchaseStyle(order_no, sl_no) {
  try {
    const response = await apiClient.get(`sales/api/customer-item/${order_no}/${sl_no}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch CustomerOrderItem:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerCashReceived(customerId) {
  try {
    const response = await apiClient.get(`/sales/api/customer-cash-received/?customer_id=${customerId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateEwayTransport(id, data) {
  try {
    const response = await apiClient.patch(`/sales/api/sale-voucher/${id}/eway-transport/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Quotation ──────────────────────────────────────────────────────────────────

export async function fetchNextQuotationNo() {
  try {
    const r = await apiClient.get("/sales/api/next_qt_no");
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchQuotationInitialData() {
  try {
    const r = await apiClient.get("/sales/api/quotation-initial-data/");
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createQuotation(data) {
  try {
    const r = await apiClient.post("/sales/api/quotation/", data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchQuotations(params = "") {
  try {
    const r = await apiClient.get(`/sales/api/quotation/?${params}`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchQuotationById(id) {
  try {
    const r = await apiClient.get(`/sales/api/quotation/${id}/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateQuotation(id, data) {
  try {
    const r = await apiClient.put(`/sales/api/quotation/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function patchQuotation(id, data) {
  try {
    const r = await apiClient.patch(`/sales/api/quotation/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteQuotation(id) {
  try {
    await apiClient.delete(`/sales/api/quotation/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchQuotationPrintData(id) {
  try {
    const r = await apiClient.get(`/sales/api/quotation/${id}/print-data/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function duplicateQuotation(id) {
  try {
    const r = await apiClient.post(`/sales/api/quotation/${id}/duplicate/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function finalizeQuotation(id) {
  try {
    const r = await apiClient.post(`/sales/api/quotation/${id}/finalize/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Customer Orders ───────────────────────────────────────────────────────────

export async function fetchCustomerOrders({ search = "", page = 1, ordering = "", allFy = false } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (allFy) params.append("all_fy", "1");
    params.append("page", page);
    const response = await apiClient.get(`/sales/api/customer-orders-vs/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCustomerOrdersKanban({ search = "", allFy = false } = {}) {
  try {
    const params = new URLSearchParams({ page_size: 500, ordering: "-date1" });
    if (search) params.append("search", search);
    if (allFy) params.append("all_fy", "1");
    const response = await apiClient.get(`/sales/api/customer-orders-vs/?${params.toString()}`);
    return { success: true, data: response.data?.results ?? response.data ?? [] };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── E-Way Bills ───────────────────────────────────────────────────────────────

export async function fetchEWayBills({ search = "", status = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (status) params.append("status", status);
    const response = await apiClient.get(`/sales/api/eway-bills/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function cancelEWayBill(id, reason = "") {
  try {
    const response = await apiClient.post(`/sales/api/eway-bills/${id}/cancel/`, { reason });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteEWayBill(id) {
  try {
    await apiClient.delete(`/sales/api/eway-bills/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateEWayBillEBN(id, data) {
  try {
    const response = await apiClient.patch(`/sales/api/eway-bills/${id}/update-ebn/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sales Reports ─────────────────────────────────────────────────────────────

export async function fetchSalesRegister(params) {
  try {
    const response = await apiClient.get('/sales/api/reports/sales-register/', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSaleApprovalRegister(params) {
  try {
    const response = await apiClient.get('/sales/api/reports/sale-approval-register/', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSlNosOrders(id) {
  try {
    const response = await apiClient.get(`/manufacturing/fetch-sl-no/?order_no_id=${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch Serial numbers :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}
