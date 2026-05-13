import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Paperclip, Upload, Trash2, FileText } from "lucide-react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";
import {
  getLedgerDocuments, uploadLedgerDocument, deleteLedgerDocument,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const DOC_TYPES = [
  { value: "PAN", label: "PAN Card" },
  { value: "AADHAR", label: "Aadhar Card" },
  { value: "DL", label: "Driving License" },
  { value: "PASSPORT", label: "Passport" },
  { value: "VOTER", label: "Voter ID" },
  { value: "GST", label: "GST Certificate" },
  { value: "OTHER", label: "Other" },
];

/**
 * LedgerDocuments
 *
 * Two modes:
 *  - Edit mode  (ledgerId provided): uploads immediately to the API.
 *  - Pending mode (no ledgerId):     queues files locally; parent must call
 *    uploadLedgerDocument(newId, file, docType) for each entry returned via
 *    onPendingChange([{ file, docType }, ...]).
 */
export default function LedgerDocuments({ ledgerId, ledgerName, pendingDocs = [], onPendingChange }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState("OTHER");
  const fileRef = useRef(null);

  const isPending = !ledgerId;

  // ── Edit mode: load existing docs ────────────────────────────────────────
  const load = async () => {
    if (!ledgerId) return;
    const res = await getLedgerDocuments(ledgerId);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setDocs(data);
    }
  };

  useEffect(() => { if (open && ledgerId) load(); }, [open, ledgerId]);

  // ── Edit mode: upload immediately ────────────────────────────────────────
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (isPending) {
      // Pending mode � just queue
      const updated = [...pendingDocs, { file, docType }];
      onPendingChange?.(updated);
      toast({ title: `"${file.name}" queued � will upload after saving.` });
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    setUploading(true);
    const res = await uploadLedgerDocument(ledgerId, file, docType);
    if (res.success) { toast({ title: "Document uploaded." }); await load(); }
    else {
      const msg = typeof res.error === "string" ? res.error
        : res.error?.non_field_errors?.[0] || "Upload failed.";
      toast({ title: msg });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  // ── Edit mode: delete ────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    const res = await deleteLedgerDocument(id);
    if (res.success) { toast({ title: "Document removed." }); setDocs(prev => prev.filter(d => d.id !== id)); }
    else toast({ title: "Failed to remove document." });
  };

  // ── Pending mode: remove queued file ────────────────────────────────────
  const removePending = (index) => {
    const updated = pendingDocs.filter((_, i) => i !== index);
    onPendingChange?.(updated);
  };

  const baseUrl = window.location.origin.replace(":5173", ":8000");
  const typeLabel = (val) => DOC_TYPES.find(d => d.value === val)?.label || val;

  const totalCount = isPending ? pendingDocs.length : docs.length;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button title="Identity Documents" className="text-muted-foreground hover:text-foreground relative">
          <Paperclip className="size-4" />
          {totalCount > 0 && (
            <span className="absolute -top-1.5 -right-1.5 bg-primary text-primary-foreground text-[9px] font-bold rounded-full size-4 flex items-center justify-center">
              {totalCount}
            </span>
          )}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="flex flex-col">
        <SheetHeader><SheetTitle>Documents � {ledgerName || "New Ledger"}</SheetTitle></SheetHeader>

        {isPending && (
          <p className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mt-2">
            Files will be uploaded automatically after the ledger is saved.
          </p>
        )}

        <div className="flex flex-col gap-4 flex-1 mt-4 overflow-y-auto">
          {/* Upload area */}
          <div className="flex flex-col gap-2 p-3 border-2 border-dashed border-border rounded-lg">
            <div className="flex items-center gap-2">
              <Select value={docType} onValueChange={setDocType}>
                <SelectTrigger className="h-8 text-xs w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOC_TYPES.map(dt => (
                    <SelectItem key={dt.value} value={dt.value}>{dt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <label className="flex items-center gap-1.5 cursor-pointer hover:bg-muted/30 rounded-md px-2 py-1 transition-colors flex-1">
                <Upload className="size-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {uploading ? "Uploading..." : "Choose file"}
                </span>
                <input ref={fileRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
              </label>
            </div>
          </div>

          {/* Pending queue */}
          {isPending && pendingDocs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No documents queued yet.</p>
          )}
          {isPending && pendingDocs.map((entry, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/20">
              <FileText className="size-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium truncate block">{entry.file.name}</span>
                <span className="text-[10px] text-muted-foreground">{typeLabel(entry.docType)} � pending</span>
              </div>
              <Button size="icon" variant="ghost" className="size-7 text-destructive hover:text-destructive" onClick={() => removePending(i)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}

          {/* Saved docs (edit mode) */}
          {!isPending && docs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No documents yet.</p>
          )}
          {!isPending && docs.map(doc => (
            <div key={doc.id} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/20">
              <FileText className="size-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <a href={`${baseUrl}${doc.document}`} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline truncate block">
                  {doc.original_name || doc.document?.split("/").pop()}
                </a>
                <span className="text-[10px] text-muted-foreground">
                  {typeLabel(doc.document_type)}
                  {doc.uploaded_at && ` � ${new Date(doc.uploaded_at).toLocaleDateString("en-GB")}`}
                </span>
              </div>
              <Button size="icon" variant="ghost" className="size-7 text-destructive hover:text-destructive" onClick={() => handleDelete(doc.id)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-muted-foreground mt-auto pt-3 border-t border-border">
          {totalCount} document{totalCount !== 1 ? "s" : ""} {isPending ? "queued" : "attached"}
        </p>
      </SheetContent>
    </Sheet>
  );
}
