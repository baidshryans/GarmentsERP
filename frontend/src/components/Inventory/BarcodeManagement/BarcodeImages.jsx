import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ImageIcon, Upload, Trash2, X } from "lucide-react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import {
  getBarcodeImages, uploadBarcodeImages, deleteBarcodeImage,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;
};

export default function BarcodeImages({ barcodeId, barcodeText, open, onOpenChange }) {
  const { toast } = useToast();
  const [imgs, setImgs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const fileRef = useRef(null);

  const load = async () => {
    if (!barcodeId) return;
    const res = await getBarcodeImages(barcodeId);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setImgs(data);
    }
  };

  useEffect(() => { if (open && barcodeId) load(); }, [open, barcodeId]);

  const handleUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    const res = await uploadBarcodeImages(barcodeId, Array.from(files));
    if (res.success) {
      toast({ title: `${files.length} image${files.length > 1 ? "s" : ""} uploaded.` });
      await load();
    } else {
      const msg = typeof res.error === "string" ? res.error
        : res.error?.non_field_errors?.[0] || "Upload failed.";
      toast({ title: msg });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleDelete = async (id) => {
    const res = await deleteBarcodeImage(id);
    if (res.success) {
      toast({ title: "Image removed." });
      setImgs(prev => prev.filter(i => i.id !== id));
      if (preview?.id === id) setPreview(null);
    } else {
      toast({ title: "Failed to remove image." });
    }
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="flex flex-col w-[420px] sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Images — {barcodeText}</SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-4 flex-1 mt-4 overflow-y-auto">
            {/* Upload area */}
            <div className="flex flex-col gap-2 p-3 border-2 border-dashed border-border rounded-lg">
              <label className="flex items-center gap-2 cursor-pointer hover:bg-muted/30 rounded-md px-2 py-2 transition-colors">
                <Upload className="size-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {uploading ? "Uploading..." : "Choose images (multiple allowed)"}
                </span>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={handleUpload}
                  disabled={uploading}
                />
              </label>
            </div>

            {/* Image grid */}
            {imgs.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">No images yet.</p>
            )}
            <div className="grid grid-cols-2 gap-3">
              {imgs.map(img => (
                <div key={img.id} className="relative group rounded-lg border border-border overflow-hidden bg-muted/20">
                  <img
                    src={imgSrc(img.image)}
                    alt={img.original_name || "Barcode image"}
                    className="w-full h-32 object-cover cursor-pointer"
                    onClick={() => setPreview(img)}
                  />
                  <div className="absolute inset-x-0 bottom-0 bg-black/50 px-2 py-1">
                    <p className="text-[10px] text-white truncate">{img.original_name || "Image"}</p>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="absolute top-1 right-1 size-6 bg-black/40 text-white hover:bg-red-600 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => handleDelete(img.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-auto pt-3 border-t border-border">
            {imgs.length} image{imgs.length !== 1 ? "s" : ""} attached
          </p>
        </SheetContent>
      </Sheet>

      {/* Full-size preview overlay */}
      {preview && (
        <div
          className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center"
          onClick={() => setPreview(null)}
        >
          <Button
            size="icon"
            variant="ghost"
            className="absolute top-4 right-4 text-white hover:bg-white/20"
            onClick={() => setPreview(null)}
          >
            <X className="size-6" />
          </Button>
          <img
            src={imgSrc(preview.image)}
            alt={preview.original_name || "Preview"}
            className="max-h-[90vh] max-w-[90vw] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}
