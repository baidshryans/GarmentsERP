// frontend/src/services/api/masters.js
import apiClient from "../apiClient";

// ── Fetch Main Item / Shape / Group (legacy simple helpers) ───────────────────

export async function fetchMainItem({type="", page_size=10000}={}) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item/?item_type=${type}&page_size=${page_size}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch main item :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchShape() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/shape/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGroup() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item_group/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Purity ────────────────────────────────────────────────────────────────────

export async function fetchPurity() {
  try {
    const response = await apiClient.get(`/goldrates/api/purity/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch purity :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createPurity(data) {
  try {
    const response = await apiClient.post(`/goldrates/api/purity/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updatePurity(id, data) {
  try {
    const response = await apiClient.put(`/goldrates/api/purity/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deletePurity(id) {
  try {
    await apiClient.delete(`/goldrates/api/purity/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── HSN ───────────────────────────────────────────────────────────────────────

export async function fetchHSNs() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/hsn/?page_size=10000`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch HSN :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createHsn(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/hsn/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateHsn(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/hsn/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteHsn(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/hsn/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchMainItemsForHSN(hsnId) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item/?hsn_no=${hsnId}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch main item :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Colors ────────────────────────────────────────────────────────────────────

export async function fetchColors() {
  try {
    const response = await apiClient.get("/mastersconfig/api/color/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createColor(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/color/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateColor(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/color/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteColor(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/color/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Shapes ────────────────────────────────────────────────────────────────────

export async function fetchShapes() {
  try {
    const response = await apiClient.get("/mastersconfig/api/shape/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createShape(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/shape/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateShape(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/shape/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteShape(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/shape/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Items ─────────────────────────────────────────────────────────────────────

export async function fetchItems({ page_size = 10000 } = {}) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/item/?page_size=${page_size}`);
    const raw = response.data;
    const data = Array.isArray(raw) ? raw : raw?.results ?? [];
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createItem(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/item/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateItem(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/item/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteItem(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/item/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Item Groups ───────────────────────────────────────────────────────────────

export async function fetchItemGroups() {
  try {
    const response = await apiClient.get("/mastersconfig/api/item_group/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createItemGroup(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/item_group/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateItemGroup(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/item_group/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteItemGroup(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/item_group/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Packet Groups ─────────────────────────────────────────────────────────────

export async function fetchPacketGroups() {
  try {
    const response = await apiClient.get("/mastersconfig/api/packet_group/");
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createPacketGroup(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/packet_group/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updatePacketGroup(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/packet_group/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deletePacketGroup(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/packet_group/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Packets ───────────────────────────────────────────────────────────────────

export async function createPacket(data) {
  try {
    const response = await apiClient.post("/mastersconfig/api/packet/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updatePacket(id, data) {
  try {
    const response = await apiClient.put(`/mastersconfig/api/packet/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deletePacket(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/packet/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Karigar Making Master ─────────────────────────────────────────────────────

export async function fetchKarigarMaking() {
  try {
    const response = await apiClient.get(`/manufacturing/api/karigar-making/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createKarigarMaking(payload) {
  try {
    const response = await apiClient.post(`/manufacturing/api/karigar-making/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateKarigarMaking(id, payload) {
  try {
    const response = await apiClient.patch(`/manufacturing/api/karigar-making/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteKarigarMaking(id) {
  try {
    await apiClient.delete(`/manufacturing/api/karigar-making/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Company Master ────────────────────────────────────────────────────────────

export async function fetchCompanies() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/company/?page_size=100`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

/* Build a FormData payload when any value is a File/Blob (logo upload),
   otherwise pass the object through as JSON. Skips null/undefined and
   intentionally omits File-typed fields that were not changed. */
function buildCompanyPayload(payload) {
  const hasFile = Object.values(payload || {}).some(
    (v) => v instanceof File || v instanceof Blob
  );
  if (!hasFile) return { data: payload, headers: undefined };
  const fd = new FormData();
  Object.entries(payload).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    if (v instanceof File || v instanceof Blob) fd.append(k, v);
    else fd.append(k, v);
  });
  return { data: fd, headers: { "Content-Type": "multipart/form-data" } };
}

export async function createCompany(payload) {
  try {
    const { data, headers } = buildCompanyPayload(payload);
    const response = await apiClient.post(`/mastersconfig/api/company/`, data, { headers });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateCompany(id, payload) {
  try {
    const { data, headers } = buildCompanyPayload(payload);
    const response = await apiClient.patch(`/mastersconfig/api/company/${id}/`, data, { headers });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteCompany(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/company/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Branch Master ─────────────────────────────────────────────────────────────

export async function fetchBranches() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/branch/?page_size=100`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createBranch(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/branch/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateBranch(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/branch/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteBranch(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/branch/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchBranchAnalytics(id) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/branch/${id}/analytics/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRetailAnalytics(id) {
  try {
    const response = await apiClient.get(`/mastersconfig/api/retail/${id}/analytics/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── TDS Sections ──────────────────────────────────────────────────────────────

export async function fetchTDSSections() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/tds-section/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createTDSSection(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/tds-section/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateTDSSection(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/tds-section/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteTDSSection(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/tds-section/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── TCS Sections ──────────────────────────────────────────────────────────────

export async function fetchTCSSections() {
  try {
    const response = await apiClient.get(`/mastersconfig/api/tcs-section/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createTCSSection(payload) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/tcs-section/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateTCSSection(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/tcs-section/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteTCSSection(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/tcs-section/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Exhibition Profiles ───────────────────────────────────────────────────────

export async function fetchExhibitions() {
  try {
    const response = await apiClient.get('/mastersconfig/api/exhibition/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createExhibition(payload) {
  try {
    const response = await apiClient.post('/mastersconfig/api/exhibition/', payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateExhibition(id, payload) {
  try {
    const response = await apiClient.patch(`/mastersconfig/api/exhibition/${id}/`, payload);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteExhibition(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/exhibition/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function activateExhibition(id) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/exhibition/${id}/activate/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deactivateExhibition(id) {
  try {
    const response = await apiClient.post(`/mastersconfig/api/exhibition/${id}/deactivate/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── B2B Pricelist ─────────────────────────────────────────────────────────────

export async function fetchB2BPricelists() {
  try {
    const r = await apiClient.get('/mastersconfig/api/b2b-pricelist/');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getB2BPricelist(id) {
  try {
    const r = await apiClient.get(`/mastersconfig/api/b2b-pricelist/${id}/`);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createB2BPricelist(data) {
  try {
    const r = await apiClient.post('/mastersconfig/api/b2b-pricelist/', data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateB2BPricelist(id, data) {
  try {
    const r = await apiClient.put(`/mastersconfig/api/b2b-pricelist/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteB2BPricelist(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/b2b-pricelist/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchB2BPricelistForLedger(ledgerId) {
  try {
    const r = await apiClient.get(`/sales/api/b2b-pricelist/${ledgerId}/`);
    if (r.status === 204) return { success: true, data: null };
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Retail Discount Pricelist ─────────────────────────────────────────────────

export async function fetchRetailDiscountPricelists() {
  try {
    const r = await apiClient.get('/mastersconfig/api/retail-discount-pricelist/?page_size=10000');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createRetailDiscountPricelist(data) {
  try {
    const r = await apiClient.post('/mastersconfig/api/retail-discount-pricelist/', data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateRetailDiscountPricelist(id, data) {
  try {
    const r = await apiClient.put(`/mastersconfig/api/retail-discount-pricelist/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteRetailDiscountPricelist(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/retail-discount-pricelist/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRetailDiscountPricelistForLedger(ledgerId) {
  try {
    const r = await apiClient.get(`/sales/api/retail-discount-pricelist/${ledgerId}/`);
    if (r.status === 204) return { success: true, data: null };
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Sales Offers ──────────────────────────────────────────────────────────────

export async function fetchActiveOffer() {
  try {
    const r = await apiClient.get('/mastersconfig/api/sales-offer/active/');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesOffers() {
  try {
    const r = await apiClient.get('/mastersconfig/api/sales-offer/?page_size=10000');
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createSalesOffer(data) {
  try {
    const r = await apiClient.post('/mastersconfig/api/sales-offer/', data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesOffer(id, data) {
  try {
    const r = await apiClient.put(`/mastersconfig/api/sales-offer/${id}/`, data);
    return { success: true, data: r.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteSalesOffer(id) {
  try {
    await apiClient.delete(`/mastersconfig/api/sales-offer/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── CSV Uploads ───────────────────────────────────────────────────────────────

export async function downloadLedgerTemplate(type) {
  try {
    const response = await apiClient.get(`/contacts/api/ledger/template/?type=${type}`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ledger_template_${type.toLowerCase()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadLedgerCSV(file, type) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post(
      `/contacts/api/ledger/csv-upload/?type=${type}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" }, timeout: 120000 }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadHSNCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/hsn/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadItemGroupCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/item_group/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadItemCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/item/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadPacketGroupCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/packet_group/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadPacketCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/mastersconfig/api/packet/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function uploadKarigarMakingCSV(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/manufacturing/api/karigar-making/csv-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" }, timeout: 120000,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

// ── Packets ───────────────────────────────────────────────────────────────────

export async function fetchPackets() {
  try {
    const response = await apiClient.get(`mastersconfig/api/packet/?page_size=10000`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Main Item Details ─────────────────────────────────────────────────────────

export async function fetchMainItemDetails(ref_job_no, job_sl_no) {
  try {
    const response = await apiClient.get(`manufacturing/fetch-main-details/?job_sl_no=${job_sl_no}&ref_job_no=${ref_job_no}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}
