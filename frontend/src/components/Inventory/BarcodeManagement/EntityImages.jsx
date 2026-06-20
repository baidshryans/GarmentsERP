import { useState, useEffect, useRef, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Upload, Trash2, X, Star, GripVertical } from "lucide-react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { useToast } from "@/hooks/use-toast";

const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const imgSrc = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;
};

/**
 * EntityImages — generic photo manager (drag-drop upload, drag-to-reorder, cover).
 * Used by BarcodeImages and DesignImages, which supply an `api` adapter:
 *   api = { list(id), upload(id, files), remove(imgId), reorder(id, orderedIds) }
 *
 * Modes:
 *  - Live   (entityId present): operations hit `api` immediately.
 *  - Staged (no entityId): files held by the parent (stagedFiles) and uploaded
 *    later by the parent; the first file is the cover.
 *
 * The FIRST image in the order is the cover. Drag a thumbnail to reorder, or use
 * the ★ button to send it to the front.
 */
export default function EntityImages({
  entityId,
  entityText,
  open,
  onOpenChange,
  api,
  staged = false,
  stagedFiles = [],
  onStagedChange,
}) {
  const isStaged = staged || !entityId;
  const { toast } = useToast();
  const [imgs, setImgs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [dragIndex, setDragIndex] = useState(null);
  const [overIndex, setOverIndex] = useState(null);
  const fileRef = useRef(null);

  // ── Live mode: load images ────────────────────────────────────────────────
  const load = async () => {
    if (!entityId) return;
    const res = await api.list(entityId);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setImgs(data);
    }
  };

  useEffect(() => { if (open && entityId) load(); }, [open, entityId]);

  // ── Staged mode: object-URL previews ──────────────────────────────────────
  const stagedPreviews = useMemo(
    () => (isStaged ? stagedFiles.map((f) => ({ file: f, url: URL.createObjectURL(f) })) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isStaged, stagedFiles]
  );
  useEffect(() => {
    return () => stagedPreviews.forEach((p) => URL.revokeObjectURL(p.url));
  }, [stagedPreviews]);

  // ── Add files ─────────────────────────────────────────────────────────────
  const addFiles = async (fileList) => {
    const picked = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    if (picked.length === 0) return;

    if (isStaged) {
      onStagedChange?.([...stagedFiles, ...picked]);
      return;
    }

    setUploading(true);
    const res = await api.upload(entityId, picked);
    if (res.success) {
      toast({ title: `${picked.length} image${picked.length > 1 ? "s" : ""} uploaded.` });
      await load();
    } else {
      const msg = typeof res.error === "string" ? res.error
        : res.error?.non_field_errors?.[0] || "Upload failed.";
      toast({ title: msg });
    }
    setUploading(false);
  };

  const handlePick = async (e) => {
    if (e.target.files?.length) await addFiles(e.target.files);
    if (fileRef.current) fileRef.current.value = "";
  };

  // ── File drop zone ────────────────────────────────────────────────────────
  const onZoneDragOver = (e) => { e.preventDefault(); setDragActive(true); };
  const onZoneDragLeave = (e) => { e.preventDefault(); setDragActive(false); };
  const onZoneDrop = async (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files?.length) await addFiles(e.dataTransfer.files);
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async (img) => {
    if (isStaged) {
      onStagedChange?.(stagedFiles.filter((f) => f !== img.file));
      if (preview?.url === img.url) setPreview(null);
      return;
    }
    const res = await api.remove(img.id);
    if (res.success) {
      toast({ title: "Image removed." });
      await load();
      if (preview?.id === img.id) setPreview(null);
    } else {
      toast({ title: "Failed to remove image." });
    }
  };

  // ── Reorder ───────────────────────────────────────────────────────────────
  const moveItem = (from, to) => {
    if (from == null || to == null || from === to) return;

    if (isStaged) {
      const next = [...stagedFiles];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      onStagedChange?.(next);
      return;
    }

    const next = [...imgs];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    setImgs(next);
    api.reorder(entityId, next.map((i) => i.id)).then((res) => {
      if (!res.success) {
        toast({ title: "Failed to save new order." });
        load();
      }
    });
  };

  const handleSetCover = (item, index) => moveItem(index, 0);

  const onThumbDragStart = (i) => (e) => {
    setDragIndex(i);
    e.dataTransfer.effectAllowed = "move";
  };
  const onThumbDragOver = (i) => (e) => {
    if (dragIndex == null) return;
    e.preventDefault();
    setOverIndex(i);
  };
  const onThumbDrop = (i) => (e) => {
    if (dragIndex == null) return;
    e.preventDefault();
    e.stopPropagation();
    moveItem(dragIndex, i);
    setDragIndex(null);
    setOverIndex(null);
  };
  const onThumbDragEnd = () => { setDragIndex(null); setOverIndex(null); };

  // ── Unified list — first item (index 0) is the cover ──────────────────────
  const items = isStaged
    ? stagedPreviews.map((p, i) => ({ key: `staged-${i}`, url: p.url, file: p.file, name: p.file.name }))
    : imgs.map((img) => ({ key: img.id, id: img.id, url: imgSrc(img.image), name: img.original_name || "Image" }));

  const count = items.length;

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="flex flex-col w-[420px] sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Images — {entityText}</SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-4 flex-1 mt-4 overflow-y-auto">
            <div
              onDragOver={onZoneDragOver}
              onDragLeave={onZoneDragLeave}
              onDrop={onZoneDrop}
              className={`flex flex-col gap-2 p-3 border-2 border-dashed rounded-lg transition-colors ${
                dragActive ? "border-primary bg-primary/10" : "border-border"
              }`}
            >
              <label className="flex flex-col items-center gap-1 cursor-pointer hover:bg-muted/30 rounded-md px-2 py-3 transition-colors">
                <Upload className="size-5 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">
                  {uploading ? "Uploading..." : dragActive ? "Drop images here" : "Drag & drop images here"}
                </span>
                <span className="text-[10px] text-muted-foreground">or click to choose (multiple allowed)</span>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={handlePick}
                  disabled={uploading}
                />
              </label>
            </div>

            {count === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">No images yet.</p>
            )}
            {count > 1 && (
              <p className="text-[10px] text-muted-foreground -mb-1">
                Drag tiles to reorder. The first image is the cover.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              {items.map((img, index) => (
                <div
                  key={img.key}
                  draggable
                  onDragStart={onThumbDragStart(index)}
                  onDragOver={onThumbDragOver(index)}
                  onDrop={onThumbDrop(index)}
                  onDragEnd={onThumbDragEnd}
                  className={`relative group rounded-lg border overflow-hidden bg-muted/20 cursor-move transition-all ${
                    overIndex === index && dragIndex !== index ? "ring-2 ring-primary" : "border-border"
                  } ${dragIndex === index ? "opacity-40" : ""}`}
                >
                  <img
                    src={img.url}
                    alt={img.name}
                    draggable={false}
                    className="w-full h-32 object-cover cursor-pointer"
                    onClick={() => setPreview(img)}
                  />
                  {index === 0 && (
                    <span className="absolute top-1 left-1 flex items-center gap-1 rounded bg-amber-500/90 px-1.5 py-0.5 text-[9px] font-semibold text-white">
                      <Star className="size-3 fill-white" /> Cover
                    </span>
                  )}
                  <span className="absolute bottom-1 left-1 rounded bg-black/50 px-1 text-[9px] text-white flex items-center gap-0.5">
                    <GripVertical className="size-3" /> {index + 1}
                  </span>
                  <div className="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {index !== 0 && (
                      <Button
                        size="icon"
                        variant="ghost"
                        title="Make cover (move to front)"
                        className="size-6 bg-black/40 text-white hover:bg-amber-500 hover:text-white"
                        onClick={() => handleSetCover(img, index)}
                      >
                        <Star className="size-4" />
                      </Button>
                    )}
                    <Button
                      size="icon"
                      variant="ghost"
                      title="Remove"
                      className="size-6 bg-black/40 text-white hover:bg-red-600 hover:text-white"
                      onClick={() => handleDelete(img)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-auto pt-3 border-t border-border">
            {count} image{count !== 1 ? "s" : ""} {isStaged ? "staged" : "attached"}
          </p>
        </SheetContent>
      </Sheet>

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
            src={preview.url}
            alt={preview.name || "Preview"}
            className="max-h-[90vh] max-w-[90vw] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}
