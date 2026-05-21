import React, { useState, useRef } from 'react';
import { Loader2, CheckCircle, XCircle, Download, Upload } from 'lucide-react';
import {
  downloadBarcodeMainTemplate,
  downloadBarcodeDetailsTemplate,
  validateBarcodeOpeningCSV,
  importBarcodeOpeningCSV,
} from '@/services/api/masters';

const STATUS = {
  IDLE: 'idle',
  VALIDATING: 'validating',
  PREVIEW: 'preview',
  IMPORTING: 'importing',
  SUCCESS: 'success',
  ERROR: 'error',
};

export default function BarcodeOpeningUploadCard() {
  const [fileMain, setFileMain] = useState(null);
  const [fileDetails, setFileDetails] = useState(null);
  const [status, setStatus] = useState(STATUS.IDLE);
  const [validationResult, setValidationResult] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [conflictAction, setConflictAction] = useState('error');
  const [errorMessage, setErrorMessage] = useState('');
  const [errorList, setErrorList] = useState([]);
  const [errorsTruncated, setErrorsTruncated] = useState(false);
  const [downloadingMain, setDownloadingMain] = useState(false);
  const [downloadingDetails, setDownloadingDetails] = useState(false);
  const fileMainInputRef = useRef(null);
  const fileDetailsInputRef = useRef(null);

  const handleDownloadMain = async () => {
    setDownloadingMain(true);
    const res = await downloadBarcodeMainTemplate();
    if (!res.success) alert(`Template download failed: ${res.error}`);
    setDownloadingMain(false);
  };

  const handleDownloadDetails = async () => {
    setDownloadingDetails(true);
    const res = await downloadBarcodeDetailsTemplate();
    if (!res.success) alert(`Template download failed: ${res.error}`);
    setDownloadingDetails(false);
  };

  const handleValidate = async () => {
    if (!fileMain || !fileDetails) return;
    setStatus(STATUS.VALIDATING);
    setErrorMessage('');
    setErrorList([]);
    setErrorsTruncated(false);
    try {
      const result = await validateBarcodeOpeningCSV(fileMain, fileDetails);
      if (result.success) {
        setValidationResult(result);
        setStatus(STATUS.PREVIEW);
      } else {
        setErrorMessage(result.error || 'Validation failed');
        setErrorList(result.errors || []);
        setErrorsTruncated(Boolean(result.errors_truncated));
        setStatus(STATUS.ERROR);
      }
    } catch (e) {
      setErrorMessage(`Validation error: ${e.message}`);
      setStatus(STATUS.ERROR);
    }
  };

  const handleImport = async () => {
    if (!fileMain || !fileDetails) return;
    setStatus(STATUS.IMPORTING);
    setErrorMessage('');
    setErrorList([]);
    setErrorsTruncated(false);
    try {
      const result = await importBarcodeOpeningCSV(fileMain, fileDetails, conflictAction);
      if (result.success) {
        setImportResult(result.data);
        setStatus(STATUS.SUCCESS);
      } else {
        setErrorMessage(result.error || 'Import failed');
        setErrorList(result.errors || []);
        setErrorsTruncated(Boolean(result.errors_truncated));
        setStatus(STATUS.ERROR);
      }
    } catch (e) {
      setErrorMessage(`Import error: ${e.message}`);
      setStatus(STATUS.ERROR);
    }
  };

  const handleReset = () => {
    setStatus(STATUS.IDLE);
    setValidationResult(null);
    setImportResult(null);
    setFileMain(null);
    setFileDetails(null);
    setConflictAction('error');
    setErrorMessage('');
    setErrorList([]);
    setErrorsTruncated(false);
    if (fileMainInputRef.current) fileMainInputRef.current.value = '';
    if (fileDetailsInputRef.current) fileDetailsInputRef.current.value = '';
  };

  // ── IDLE ───────────────────────────────────────────────────────────────────
  if (status === STATUS.IDLE) {
    return (
      <div className="space-y-3">
        {/* Barcode Main */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-gray-800">Barcode Main CSV</h3>
              <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                barcode, item_id, purity, gross_weight, net_weight, value, making_value, total_amount, retail_code…
              </p>
              {fileMain && (
                <p className="mt-1.5 text-xs text-green-700 flex items-center gap-1">
                  <CheckCircle size={11} /> {fileMain.name}
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={handleDownloadMain}
                disabled={downloadingMain}
                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border border-violet-300 bg-violet-50 hover:bg-violet-100 text-primary disabled:opacity-50 transition-colors"
              >
                {downloadingMain ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                {downloadingMain ? '…' : 'Template'}
              </button>
              <button
                type="button"
                onClick={() => fileMainInputRef.current?.click()}
                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary text-white hover:opacity-90 transition-colors"
              >
                <Upload size={14} /> Upload CSV
              </button>
              <input
                ref={fileMainInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => setFileMain(e.target.files?.[0] || null)}
              />
            </div>
          </div>
        </div>

        {/* Barcode Details */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-gray-800">Barcode Details CSV</h3>
              <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                barcode, item_id, purity, carat_weight, gross_weight, rate, amount, packet_number…
              </p>
              {fileDetails && (
                <p className="mt-1.5 text-xs text-green-700 flex items-center gap-1">
                  <CheckCircle size={11} /> {fileDetails.name}
                </p>
              )}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={handleDownloadDetails}
                disabled={downloadingDetails}
                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border border-violet-300 bg-violet-50 hover:bg-violet-100 text-primary disabled:opacity-50 transition-colors"
              >
                {downloadingDetails ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                {downloadingDetails ? '…' : 'Template'}
              </button>
              <button
                type="button"
                onClick={() => fileDetailsInputRef.current?.click()}
                className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-primary text-white hover:opacity-90 transition-colors"
              >
                <Upload size={14} /> Upload CSV
              </button>
              <input
                ref={fileDetailsInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => setFileDetails(e.target.files?.[0] || null)}
              />
            </div>
          </div>
        </div>

        {/* Validate trigger */}
        <button
          type="button"
          onClick={handleValidate}
          disabled={!fileMain || !fileDetails}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Upload size={14} /> Validate &amp; Preview
        </button>
      </div>
    );
  }

  // ── VALIDATING ─────────────────────────────────────────────────────────────
  if (status === STATUS.VALIDATING) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm flex items-center gap-2 text-sm">
        <Loader2 className="animate-spin text-primary" size={16} />
        <span>Parsing and validating files…</span>
      </div>
    );
  }

  // ── PREVIEW ────────────────────────────────────────────────────────────────
  if (status === STATUS.PREVIEW && validationResult) {
    const hasConflicts = validationResult.existing_barcodes_count > 0;
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="text-base font-semibold mb-3">Preview & Confirm Import</h3>

        <div className="space-y-2 mb-4">
          <div className="flex items-center gap-2 p-2 bg-green-50 rounded text-sm">
            <CheckCircle className="text-green-600" size={14} />
            <span>Main rows valid: {validationResult.main_rows_valid}</span>
          </div>
          <div className="flex items-center gap-2 p-2 bg-green-50 rounded text-sm">
            <CheckCircle className="text-green-600" size={14} />
            <span>Details rows valid: {validationResult.details_rows_valid}</span>
          </div>
          {hasConflicts && (
            <div className="flex items-start gap-2 p-2 bg-yellow-50 rounded text-sm">
              <span className="text-yellow-600 font-semibold">⚠</span>
              <div className="flex-1">
                <div className="font-medium">
                  Existing barcodes found: {validationResult.existing_barcodes_count}
                </div>
                {validationResult.existing_barcodes?.length > 0 && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {validationResult.existing_barcodes.slice(0, 10).join(', ')}
                    {validationResult.existing_barcodes.length > 10 &&
                      ` …and ${validationResult.existing_barcodes.length - 10} more`}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {hasConflicts && (
          <div className="mb-4 p-3 bg-gray-50 rounded text-sm">
            <div className="font-medium mb-2">How to handle existing barcodes?</div>
            {[
              { value: 'skip',   label: 'Skip — ignore existing barcodes, import new ones only' },
              { value: 'update', label: "Update — replace existing barcodes' data and details" },
              { value: 'error',  label: 'Error — reject the whole import if any barcode exists' },
            ].map((opt) => (
              <label key={opt.value} className="flex items-start gap-2 mb-1 cursor-pointer">
                <input
                  type="radio"
                  name="barcode-opening-conflict"
                  value={opt.value}
                  checked={conflictAction === opt.value}
                  onChange={(e) => setConflictAction(e.target.value)}
                />
                <span className="text-xs">{opt.label}</span>
              </label>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            className="px-3 py-1.5 text-sm rounded-md border border-gray-300 hover:bg-gray-50 transition-colors"
          >
            Go Back
          </button>
          <button
            type="button"
            onClick={handleImport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-primary text-white hover:opacity-90 transition-colors"
          >
            <Upload size={14} /> Import
          </button>
        </div>
      </div>
    );
  }

  // ── IMPORTING ──────────────────────────────────────────────────────────────
  if (status === STATUS.IMPORTING) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm flex items-center gap-2 text-sm">
        <Loader2 className="animate-spin text-primary" size={16} />
        <span>Importing…</span>
      </div>
    );
  }

  // ── SUCCESS ────────────────────────────────────────────────────────────────
  if (status === STATUS.SUCCESS && importResult) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle className="text-green-600" size={18} />
          <h3 className="text-base font-semibold text-green-700">Import complete</h3>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="p-2 bg-violet-50 rounded text-center">
            <div className="text-xs text-gray-600">Created</div>
            <div className="text-xl font-bold text-primary">{importResult.created ?? 0}</div>
          </div>
          <div className="p-2 bg-purple-50 rounded text-center">
            <div className="text-xs text-gray-600">Updated</div>
            <div className="text-xl font-bold text-purple-700">{importResult.updated ?? 0}</div>
          </div>
          <div className="p-2 bg-gray-50 rounded text-center">
            <div className="text-xs text-gray-600">Skipped</div>
            <div className="text-xl font-bold text-gray-700">{importResult.skipped ?? 0}</div>
          </div>
        </div>
        <div className="text-xs text-gray-600 mb-3">
          Details rows created: <strong>{importResult.details_created ?? 0}</strong>
          {(importResult.details_replaced ?? 0) > 0 && (
            <> &middot; replaced: <strong>{importResult.details_replaced}</strong></>
          )}
        </div>

        <button
          type="button"
          onClick={handleReset}
          className="px-3 py-1.5 text-sm rounded-md bg-primary text-white hover:opacity-90 transition-colors"
        >
          Import More Data
        </button>
      </div>
    );
  }

  // ── ERROR ──────────────────────────────────────────────────────────────────
  if (status === STATUS.ERROR) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-start gap-2 mb-3">
          <XCircle className="text-red-600 mt-0.5" size={18} />
          <div className="flex-1">
            <h3 className="text-base font-semibold text-red-700">Import failed</h3>
            {errorMessage && <p className="text-xs text-gray-700 mt-0.5">{errorMessage}</p>}
          </div>
        </div>

        {errorList.length > 0 && (
          <details className="mb-3 p-2 bg-gray-50 rounded">
            <summary className="text-xs font-medium cursor-pointer">
              Errors ({Math.min(errorList.length, 20)} shown{errorList.length > 20 ? ` of ${errorList.length}` : ''})
            </summary>
            <ul className="text-xs text-gray-700 mt-1.5 space-y-0.5 max-h-60 overflow-y-auto">
              {errorList.slice(0, 20).map((err, idx) => (
                <li key={idx} className="ml-3">• {err}</li>
              ))}
              {errorList.length > 20 && (
                <li className="ml-3 text-gray-500 italic">…and {errorList.length - 20} more errors</li>
              )}
            </ul>
            {errorsTruncated && (
              <p className="mt-1.5 text-xs text-amber-700 italic">
                The backend truncated the full error list — additional errors exist beyond the {errorList.length} shown here.
              </p>
            )}
          </details>
        )}

        <button
          type="button"
          onClick={handleReset}
          className="px-3 py-1.5 text-sm rounded-md border border-gray-300 hover:bg-gray-50 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return null;
}
