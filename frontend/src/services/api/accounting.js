// frontend/src/services/api/accounting.js
import apiClient from "../apiClient";

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

export async function suggestAccounts(narration, voucherType = "JRNL", amount = 0) {
  try {
    const response = await apiClient.post("/ai/suggest-accounts/", {
      narration,
      voucher_type: voucherType,
      amount,
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.response?.data?.error || error.message };
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
