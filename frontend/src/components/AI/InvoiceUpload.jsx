import { useState, useRef } from "react";
import { Paperclip, Loader2, CheckCircle, XCircle } from "lucide-react";
import { parseInvoice } from "@/services/apiService";

/**
 * InvoiceUpload — a small "Parse Invoice" button for PurchaseVoucher forms.
 *
 * Props:
 *   onExtracted(data): called with the parsed invoice JSON when successful.
 *                      Caller maps fields into their form.
 */
export default function InvoiceUpload({ onExtracted }) {
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [message, setMessage] = useState("");
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset the input so the same file can be selected again
    e.target.value = "";

    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setStatus("error");
      setMessage("File too large (max 10 MB).");
      return;
    }

    const allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
    if (!allowed.includes(file.type)) {
      setStatus("error");
      setMessage("Unsupported file type. Use JPG, PNG, WEBP or PDF.");
      return;
    }

    setStatus("loading");
    setMessage(file.name);

    const result = await parseInvoice(file);

    if (result.success) {
      setStatus("success");
      setMessage("Fields extracted!");
      onExtracted?.(result.data);
      // Auto-reset after 3 seconds
      setTimeout(() => setStatus("idle"), 3000);
    } else {
      setStatus("error");
      setMessage(result.error || "Parsing failed. Try a clearer image.");
    }
  };

  const reset = () => {
    setStatus("idle");
    setMessage("");
  };

  return (
    <div className="flex items-center gap-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={handleFileChange}
        className="hidden"
      />

      {status === "idle" && (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-gray-300 bg-white hover:bg-gray-50 text-gray-600 transition-colors"
        >
          <Paperclip size={13} />
          Parse Invoice
        </button>
      )}

      {status === "loading" && (
        <div className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-violet-200 bg-violet-50 text-violet-700">
          <Loader2 size={13} className="animate-spin" />
          <span className="truncate max-w-36">{message}</span>
        </div>
      )}

      {status === "success" && (
        <div className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-green-200 bg-green-50 text-green-700">
          <CheckCircle size={13} />
          {message}
        </div>
      )}

      {status === "error" && (
        <div className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-md border border-red-200 bg-red-50 text-red-700">
          <XCircle size={13} />
          <span className="truncate max-w-48">{message}</span>
          <button
            type="button"
            onClick={reset}
            className="ml-1 underline whitespace-nowrap"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
