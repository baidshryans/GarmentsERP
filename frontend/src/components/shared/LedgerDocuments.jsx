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

export default function LedgerDocuments({ ledgerId, ledgerName }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState("OTHER");
  const fileRef = useRef(null);

  const load = async () => {
    if (!ledgerId) return;
    const res = await getLedgerDocuments(ledgerId);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setDocs(data);
    }
  };

  useEffect(() => { if (open && ledgerId) load(); }, [open, ledgerId]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
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

  const handleDelete = async (id) => {
    const res = await deleteLedgerDocument(id);
    if (res.success) { toast({ title: "Document removed." }); setDocs(prev => prev.filter(d => d.id !== id)); }
    else toast({ title: "Failed to remove document." });
  };

  const baseUrl = window.location.origin.replace(":5173", ":8000");
  const typeLabel = (val) => DOC_TYPES.find(d => d.value === val)?.label || val;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button title="Identity Documents" className="text-muted-foreground hover:text-foreground relative">
          <Paperclip className="size-4" />
          {docs.length > 0 && (
            <span className="absolute -top-1.5 -right-1.5 bg-primary text-primary-foreground text-[9px] font-bold rounded-full size-4 flex items-center justify-center">
              {docs.length}
            </span>
          )}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="flex flex-col">
        <SheetHeader><SheetTitle>Documents — {ledgerName}</SheetTitle></SheetHeader>
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
                <span className="text-xs text-muted-foreground">{uploading ? "Uploading..." : "Choose file"}</span>
                <input ref={fileRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
              </label>
            </div>
          </div>

          {/* Document list */}
          {docs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No documents yet.</p>
          )}
          {docs.map(doc => (
            <div key={doc.id} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/20">
              <FileText className="size-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <a href={`${baseUrl}${doc.document}`} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:underline truncate block">
                  {doc.original_name || doc.document?.split("/").pop()}
                </a>
                <span className="text-[10px] text-muted-foreground">
                  {typeLabel(doc.document_type)}
                  {doc.uploaded_at && ` — ${new Date(doc.uploaded_at).toLocaleDateString("en-GB")}`}
                </span>
              </div>
              <Button size="icon" variant="ghost" className="size-7 text-destructive hover:text-destructive" onClick={() => handleDelete(doc.id)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-muted-foreground mt-auto pt-3 border-t border-border">{docs.length} document{docs.length !== 1 ? "s" : ""} attached</p>
      </SheetContent>
    </Sheet>
  );
}
