import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Paperclip, Upload, Trash2, FileText, X } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  getVoucherAttachments,
  uploadVoucherAttachment,
  deleteVoucherAttachment,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const MAX_FILES = 3;

export default function VoucherAttachments({ voucherId, voucherNo }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = async () => {
    if (!voucherId) return;
    const res = await getVoucherAttachments(voucherId);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setAttachments(data);
    }
  };

  useEffect(() => {
    if (open && voucherId) load();
  }, [open, voucherId]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (attachments.length >= MAX_FILES) {
      toast({ title: `Maximum ${MAX_FILES} attachments allowed.` });
      return;
    }
    setUploading(true);
    const res = await uploadVoucherAttachment(voucherId, file);
    if (res.success) {
      toast({ title: "File uploaded." });
      await load();
    } else {
      const msg =
        typeof res.error === "string"
          ? res.error
          : res.error?.non_field_errors?.[0] || "Upload failed.";
      toast({ title: msg });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleDelete = async (id) => {
    const res = await deleteVoucherAttachment(id);
    if (res.success) {
      toast({ title: "Attachment removed." });
      setAttachments((prev) => prev.filter((a) => a.id !== id));
    } else {
      toast({ title: "Failed to remove attachment." });
    }
  };

  const baseUrl = window.location.origin.replace(":5173", ":8000");

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          title="Attachments"
          className="text-muted-foreground hover:text-foreground relative"
        >
          <Paperclip className="size-4" />
          {attachments.length > 0 && (
            <span className="absolute -top-1.5 -right-1.5 bg-primary text-primary-foreground text-[9px] font-bold rounded-full size-4 flex items-center justify-center">
              {attachments.length}
            </span>
          )}
        </button>
      </SheetTrigger>

      <SheetContent side="right" className="flex flex-col">
        <SheetHeader>
          <SheetTitle>Attachments � {voucherNo}</SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-4 flex-1 mt-4 overflow-y-auto">
          {/* Upload area */}
          {attachments.length < MAX_FILES && (
            <label className="flex items-center gap-2 justify-center border-2 border-dashed border-border rounded-lg p-4 cursor-pointer hover:bg-muted/30 transition-colors">
              <Upload className="size-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                {uploading ? "Uploading..." : "Click to upload a file"}
              </span>
              <input
                ref={fileRef}
                type="file"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          )}

          {attachments.length >= MAX_FILES && (
            <p className="text-xs text-muted-foreground text-center">
              Maximum {MAX_FILES} attachments reached.
            </p>
          )}

          {/* File list */}
          {attachments.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No attachments yet.
            </p>
          )}

          {attachments.map((att) => (
            <div
              key={att.id}
              className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/20"
            >
              <FileText className="size-5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <a
                  href={`${baseUrl}${att.file}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium hover:underline truncate block"
                >
                  {att.original_name}
                </a>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(att.uploaded_at).toLocaleDateString("en-GB")}
                </span>
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="size-7 text-destructive hover:text-destructive"
                onClick={() => handleDelete(att.id)}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>

        <p className="text-[10px] text-muted-foreground mt-auto pt-3 border-t border-border">
          {attachments.length}/{MAX_FILES} files attached
        </p>
      </SheetContent>
    </Sheet>
  );
}
