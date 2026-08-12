// frontend/src/services/api/customerIntel.js
import apiClient from "../apiClient";

const BASE = "/customer-intel/api";

function _qs(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

async function _call(fn) {
  try {
    const response = await fn();
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

/** Paginated customer book. Filters: q, rfm_segment, lapse_band, confidence,
 *  tag, city, b2b, min_spend, max_spend, silent_days, has_dob, buyers_only,
 *  ordering, page, page_size. */
export async function fetchCustomers(filters = {}) {
  return _call(() => apiClient.get(`${BASE}/customers/${_qs(filters)}`));
}

export async function fetchCustomerProfile(ledgerId) {
  return _call(() => apiClient.get(`${BASE}/customers/${ledgerId}/profile/`));
}

export async function fetchCustomerTimeline(ledgerId, params = {}) {
  return _call(() =>
    apiClient.get(`${BASE}/customers/${ledgerId}/timeline/${_qs(params)}`),
  );
}

export async function logCustomerNote(ledgerId, payload) {
  return _call(() => apiClient.post(`${BASE}/customers/${ledgerId}/note/`, payload));
}

export async function fetchCustomerSocial(ledgerId) {
  return _call(() => apiClient.get(`${BASE}/customers/${ledgerId}/social/`));
}

/** Also accepts dob / anniversary, which live on the Ledger. */
export async function updateCustomerSocial(ledgerId, payload) {
  return _call(() => apiClient.patch(`${BASE}/customers/${ledgerId}/social/`, payload));
}

export async function setCustomerOptOut(ledgerId, payload = {}) {
  return _call(() => apiClient.post(`${BASE}/customers/${ledgerId}/opt-out/`, payload));
}

export async function fetchCustomerTags() {
  return _call(() => apiClient.get(`${BASE}/tags/`));
}

export async function createCustomerTag(payload) {
  return _call(() => apiClient.post(`${BASE}/tags/`, payload));
}

export async function assignCustomerTag(ledgerId, tagId) {
  return _call(() =>
    apiClient.post(`${BASE}/customers/${ledgerId}/tags/`, { tag_id: tagId }),
  );
}

export async function unassignCustomerTag(ledgerId, tagId) {
  return _call(() =>
    apiClient.delete(`${BASE}/customers/${ledgerId}/tags/`, { data: { tag_id: tagId } }),
  );
}

// ── Segments ────────────────────────────────────────────────────────────────

export async function fetchSegments() {
  return _call(() => apiClient.get(`${BASE}/segments/`));
}

export async function fetchSegment(id) {
  return _call(() => apiClient.get(`${BASE}/segments/${id}/`));
}

export async function createSegment(payload) {
  return _call(() => apiClient.post(`${BASE}/segments/`, payload));
}

export async function updateSegment(id, payload) {
  return _call(() => apiClient.patch(`${BASE}/segments/${id}/`, payload));
}

export async function deleteSegment(id) {
  return _call(() => apiClient.delete(`${BASE}/segments/${id}/`));
}

/** Live count + sample for an unsaved definition. */
export async function previewSegment(definition) {
  return _call(() => apiClient.post(`${BASE}/segments/preview/`, { definition }));
}

export async function fetchSegmentMembers(id, params = {}) {
  return _call(() => apiClient.get(`${BASE}/segments/${id}/members/${_qs(params)}`));
}

/** The filterable-field catalogue — backend is the source of truth. */
export async function fetchSegmentFields() {
  return _call(() => apiClient.get(`${BASE}/segments/fields/`));
}

export function segmentExportUrl(id) {
  return `${BASE}/segments/${id}/export/`;
}

// ── Campaigns ───────────────────────────────────────────────────────────────

export async function fetchCampaigns(params = {}) {
  return _call(() => apiClient.get(`${BASE}/campaigns/${_qs(params)}`));
}

export async function fetchCampaign(id) {
  return _call(() => apiClient.get(`${BASE}/campaigns/${id}/`));
}

export async function createCampaign(payload) {
  return _call(() => apiClient.post(`${BASE}/campaigns/`, payload));
}

export async function updateCampaign(id, payload) {
  return _call(() => apiClient.patch(`${BASE}/campaigns/${id}/`, payload));
}

export async function deleteCampaign(id) {
  return _call(() => apiClient.delete(`${BASE}/campaigns/${id}/`));
}

/** Recipient count, opt-out count and a rendered sample, before sending. */
export async function previewCampaign(id) {
  return _call(() => apiClient.post(`${BASE}/campaigns/${id}/preview/`, {}));
}

export async function launchCampaign(id) {
  return _call(() => apiClient.post(`${BASE}/campaigns/${id}/launch/`, {}));
}

export async function pauseCampaign(id) {
  return _call(() => apiClient.post(`${BASE}/campaigns/${id}/pause/`, {}));
}

export async function resumeCampaign(id) {
  return _call(() => apiClient.post(`${BASE}/campaigns/${id}/resume/`, {}));
}

export async function cancelCampaign(id) {
  return _call(() => apiClient.post(`${BASE}/campaigns/${id}/cancel/`, {}));
}

export async function fetchCampaignRecipients(id, params = {}) {
  return _call(() => apiClient.get(`${BASE}/campaigns/${id}/recipients/${_qs(params)}`));
}

export async function fetchMessageTemplates() {
  return _call(() => apiClient.get(`${BASE}/templates/`));
}

export async function createMessageTemplate(payload) {
  return _call(() => apiClient.post(`${BASE}/templates/`, payload));
}

// ── Worklist ────────────────────────────────────────────────────────────────

/** Today's ranked call list. Filters: reason, limit, include_contacted. */
export async function fetchWorklist(params = {}) {
  return _call(() => apiClient.get(`${BASE}/worklist/${_qs(params)}`));
}

export function metaAudienceUrl(segmentId) {
  return `${BASE}/segments/${segmentId}/meta-audience/`;
}
