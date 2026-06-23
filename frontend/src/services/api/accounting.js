// frontend/src/services/api/accounting.js
import apiClient from "../apiClient";
import { deleteResource, handleDelete } from "./_helpers";

// ── Legacy data migration (Import Master Data → Transactions tab) ──────────
export async function downloadMigrationTemplate(name) {
  try {
    const response = await apiClient.get(`/accounting/api/migration/template/?name=${name}`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `legacy_${name}_template.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

/**
 * Run a transactional legacy import.
 * @param {string} kind  one of 'vouchers' | 'sales' | 'purchases' | 'allocations'
 * @param {Object} files map of field-name -> File (e.g. { main, details })
 * @param {boolean} apply  false = dry-run (default), true = persist
 */
export async function runMigrationImport(kind, files, apply = false) {
  try {
    const formData = new FormData();
    Object.entries(files).forEach(([field, file]) => {
      if (file) formData.append(field, file);
    });
    const response = await apiClient.post(
      `/accounting/api/migration/${kind}/?apply=${apply ? "true" : "false"}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" }, timeout: 600000 }
    );
    return { success: true, data: response.data };
  } catch (error) {
    const d = error.response?.data;
    return { success: false, error: d?.error || error.message, data: d };
  }
}

export async function getAccountGroup() {
  try {
    const response = await apiClient.get("/accounting/api/accounts/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getChartOfAccounts() {
  try {
    const response = await apiClient.get(`/accounting/account-tree/`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch chart of accounts :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getAccount(id) {
  try {
    const response = await apiClient.get(`/accounting/api/accounts/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createAccount(data) {
  try {
    const response = await apiClient.post(`/accounting/api/accounts/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateAccount(id, data) {
  try {
    const response = await apiClient.put(`/accounting/api/accounts/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteAccount(id) {
  try {
    await apiClient.delete(`/accounting/api/accounts/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getOpeningBalances() {
  try {
    const response = await apiClient.get('/accounting/api/open-balance/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createOpeningBalance(data) {
  try {
    const response = await apiClient.post('/accounting/api/open-balance/', data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateOpeningBalance(id, data) {
  try {
    const response = await apiClient.put(`/accounting/api/open-balance/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteOpeningBalance(id) {
  try {
    await apiClient.delete(`/accounting/api/open-balance/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchVoucherNoNext(vouType) {
  try {
    const response = await apiClient.get(`/accounting/api/vou-no/${vouType}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createJournalEntry(data) {
  try {
    const response = await apiClient.post("/accounting/api/journal/", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to create JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchJournalEntryForEdit(id) {
  try {
    const response = await apiClient.get(`/accounting/api/journal/${id}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateJournalEntryForEdit(data, id) {
  try {
    const response = await apiClient.put(`/accounting/api/journal/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to update JournalEntry:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function cancelJournalEntry(id) {
  try {
    const response = await apiClient.post(`/accounting/api/journal/${id}/cancel/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchtrial() {
  try {
    const response = await apiClient.get(`/accounting/api/trial/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order number :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDuePayments(id) {

  try {
    const response = await apiClient.get(`/accounting/api/due-payments/?ldgr_id=${id}&type=PMNT`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDuePaymentsSale(id) {

  try {
    const response = await apiClient.get(`/accounting/api/due-payments/sale/?ldgr_id=${id}`);

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch PurchaseVoucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

/**
 * Fetch the current running balance for a ledger (opening + all posted txns).
 * For Cash/Bank asset accounts a positive value means available funds.
 * Returns: { ledger_id, ledger_name, balance }
 */
export async function fetchLedgerBalance(ledgerId) {
  try {
    const response = await apiClient.get(`/accounting/api/ledger-balance/${ledgerId}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchLedgerStatement({ ledger_id, from_date, to_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/ledger-statement/?ledger_id=${ledger_id}&from_date=${from_date}&to_date=${to_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

/**
 * Fetch outstanding bills for a ledger, compact shape for the BillAllocationTable.
 * kind: 'sales' (for Receipt vouchers) | 'purchase' (for Payment vouchers)
 * Returns: [{id, billno, date, total, due_amt}, ...]
 */
export async function fetchOutstandingBills(ledgerId, kind) {
  try {
    const response = await apiClient.get(
      `/accounting/api/outstanding-bills/?ledger=${ledgerId}&type=${kind}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch outstanding bills:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

/**
 * Aged Receivables / Aged Payables report.
 * kind: 'sales' (receivable) | 'purchase' (payable)
 * Returns: { as_of, kind, rows: [{ldgr_id, ldgr_name, b0_30, b31_60, b61_90, b90_plus, total, bills:[…]}], totals: {…} }
 */
export async function fetchAgedReceivables(kind = "sales") {
  try {
    const response = await apiClient.get(
      `/accounting/api/aged-receivables/?kind=${kind}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch aged receivables:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

/**
 * Advance Register — every CustomerOrder with an advance receipt.
 * Returns: { rows: [{order_id, order_no, date, ldgr_name, status, received, reconciled, remaining}], totals: {…} }
 */
export async function fetchAdvanceRegister() {
  try {
    const response = await apiClient.get(`/accounting/api/advance-register/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch advance register:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchDayBook({ from_date, to_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/day-book/?from_date=${from_date}&to_date=${to_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchOutstandingReport({ type = "debtor", as_of_date }) {
  try {
    const response = await apiClient.get(
      `/accounting/api/outstanding/?type=${type}&as_of_date=${as_of_date}`
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
  }
}

export async function fetchBankBookReport(fromDate, toDate, selectedLedgerId) {
  try {
    const response = await apiClient.get(`/accounting/api/bank-book?from_date=${fromDate}&to_date=${toDate}&bank_ldgr=${selectedLedgerId}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch bankbookreport:", error.response?.data || error.message);
    // return { success: false, error: error.response?.data || error.message };
    throw error;
  }
}

export async function fetchCashBookReport(selectedLedgerId, fromDate, toDate) {
  try {
    const response = await apiClient.get(`/accounting/api/cash-book?ledger_id=${selectedLedgerId}&from_date=${(fromDate)}&to_date=${(toDate)}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch cashbookreport:", error.response?.data || error.message);
    // return { success: false, error: error.response?.data || error.message };
    throw error;
  }
}

// ── Bank Reconciliation ────────────────────────────────────────────────────────
export async function fetchBankStatements({ bank_ledger, from_date, to_date } = {}) {
  try {
    const p = new URLSearchParams();
    if (bank_ledger) p.append('bank_ledger', bank_ledger);
    if (from_date)   p.append('from_date', from_date);
    if (to_date)     p.append('to_date', to_date);
    const r = await apiClient.get(`/accounting/api/bank-statement/?${p}`);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function createBankStatement(data) {
  try {
    const r = await apiClient.post('/accounting/api/bank-statement/', data);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function deleteBankStatement(id) {
  try {
    await apiClient.delete(`/accounting/api/bank-statement/${id}/`);
    return { success: true };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function matchBankStatement(id, voucher_detail_id) {
  try {
    const r = await apiClient.post(`/accounting/api/bank-statement/${id}/match/`, { voucher_detail_id });
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

export async function fetchBankReconBookEntries({ bank_ledger, from_date, to_date } = {}) {
  try {
    const p = new URLSearchParams();
    if (bank_ledger) p.append('bank_ledger', bank_ledger);
    if (from_date)   p.append('from_date', from_date);
    if (to_date)     p.append('to_date', to_date);
    const r = await apiClient.get(`/accounting/api/bank-reconciliation/book-entries/?${p}`);
    return { success: true, data: r.data };
  } catch (e) { return { success: false, error: e.response?.data || e.message }; }
}

// ── Salesperson Commission ────────────────────────────────────────────────────
export async function fetchCommissionReport(params) {
  try {
    const response = await apiClient.get('/mastersconfig/api/commission/report/', { params });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createCommissionJV(entries) {
  try {
    const response = await apiClient.post('/mastersconfig/api/commission/create-jv/', { entries });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCommissionLedgerConfig() {
  try {
    const response = await apiClient.get('/mastersconfig/api/commission/ledger-config/');
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function setCommissionLedger(commission_ldgr_id) {
  try {
    const response = await apiClient.patch('/mastersconfig/api/commission/ledger-set/', { commission_ldgr_id });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGSTInputReport(startDate, endDate, gstinId) {
  try {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    if (gstinId) params.append('gstin', gstinId);
    const response = await apiClient.get(`/sales/api/gst-input?${params.toString()}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch gstinputreport:", error.response?.data || error.message);
    throw error;
  }
}

export async function fetchGSTOutputReport(startDate, endDate, gstinId) {
  try {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    if (gstinId) params.append('gstin', gstinId);
    const response = await apiClient.get(`/sales/api/gst-output?${params.toString()}`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch gstoutputreport:", error.response?.data || error.message);
    throw error;
  }
}

export async function fetchGSTR1Report({ from_date, to_date } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/gstr1/?from_date=${from_date}&to_date=${to_date}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGSTR3BReport({ from_date, to_date } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/gstr3b/?from_date=${from_date}&to_date=${to_date}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTDSRegister({ from_date, to_date, section } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append('from_date', from_date);
    if (to_date) params.append('to_date', to_date);
    if (section) params.append('section', section);
    const response = await apiClient.get(`/purchase/api/tds-register/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchTCSRegister({ from_date, to_date, section } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append('from_date', from_date);
    if (to_date) params.append('to_date', to_date);
    if (section) params.append('section', section);
    const response = await apiClient.get(`/sales/api/tcs-register/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function getNextGCno() {
  try {
    const response = await apiClient.get("/accounting/api/gc-no/");

    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch states :", error.response?.data || error.message);

    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Accounting Voucher ────────────────────────────────────────────────────────

export async function fetchAccountingVoucher({ search = "", page = 1, ordering = "", voucher_type = "" } = {}) {
  try {
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    if (voucher_type) params.append("voucher_type", voucher_type);
    params.append("page", page);

    const response = await apiClient.get(`/accounting/api/journal/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch voucher:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export const deleteJournalentry = async (id, toast) => {
  const result = await deleteResource("/accounting/api/journal", id);
  handleDelete(result, toast, "Accounting Voucher deleted successfully.");
};

// ── Voucher Attachments ───────────────────────────────────────────────────────

export async function getVoucherAttachments(voucherId) {
  try {
    const response = await apiClient.get(`/accounting/api/voucher-attachments/?voucher=${voucherId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function uploadVoucherAttachment(voucherId, file) {
  try {
    const formData = new FormData();
    formData.append("voucher", voucherId);
    formData.append("file", file);
    const response = await apiClient.post("/accounting/api/voucher-attachments/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteVoucherAttachment(id) {
  try {
    await apiClient.delete(`/accounting/api/voucher-attachments/${id}/`);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── Credit / Debit Notes ──────────────────────────────────────────────────────

export async function createCreditDebitNote(data) {
  try {
    const response = await apiClient.post("/accounting/api/credit-debit-notes/", data);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function cancelCreditDebitNote(id) {
  try {
    const response = await apiClient.post(`/accounting/api/credit-debit-notes/${id}/cancel/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCreditDebitNote(id) {
  try {
    const response = await apiClient.get(`/accounting/api/credit-debit-notes/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCreditDebitNotes(noteType) {
  try {
    const params = noteType ? `?note_type=${noteType}` : "";
    const response = await apiClient.get(`/accounting/api/credit-debit-notes/${params}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchCNDNPrintData(id) {
  try {
    const response = await apiClient.get(`/accounting/api/credit-debit-notes/${id}/print-data/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchNextCNDNNumber(noteType) {
  try {
    const response = await apiClient.get(`/accounting/api/cn-dn-no/${noteType}/`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── RCM / RCV Register ────────────────────────────────────────────────────────

export async function fetchRCVs() {
  try {
    const response = await apiClient.get(`manufacturing/api/fetch-rcv-slip-nos`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch order items :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchRcmRegister({ from_date, to_date } = {}) {
  try {
    const params = new URLSearchParams();
    if (from_date) params.append('from_date', from_date);
    if (to_date) params.append('to_date', to_date);
    const response = await apiClient.get(`/purchase/api/rcm-register/?${params.toString()}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

// ── GST Reports ───────────────────────────────────────────────────────────────

export async function fetchGSTinputReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/sales/api/gst-input?start_date=${fromDate}&end_date=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchGSToutputReport(fromDate, toDate) {
  try {
    const response = await apiClient.get(`/sales/api/api/gst-output?start_date=${fromDate}&end_date=${toDate}`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Failed to fetch shape :", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchUnlinkedReceipts(ldgrId) {
  try {
    const response = await apiClient.get(`/accounting/api/unlinked-receipts/?ldgr_id=${ldgrId}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function linkReceiptToOrder(voucherId, customerOrderId) {
  try {
    const response = await apiClient.patch(
      `/accounting/api/journal/${voucherId}/link-order/`,
      { customer_order: customerOrderId }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function releaseReceiptFromOrder(voucherId) {
  try {
    const response = await apiClient.patch(
      `/accounting/api/journal/${voucherId}/link-order/`,
      { customer_order: null }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchUnallocatedVouchers(type = 'receipt') {
  try {
    const response = await apiClient.get(`/accounting/api/unallocated-vouchers/?type=${type}`);
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function allocateVoucherBills(voucherId, kind, allocations) {
  try {
    const response = await apiClient.patch(
      `/accounting/api/journal/${voucherId}/allocate-bills/`,
      { kind, allocations }
    );
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data || error.message };
  }
}
