import EntityImages from "./EntityImages";
import {
  getBarcodeImages, uploadBarcodeImages, deleteBarcodeImage, reorderBarcodeImages,
} from "@/services/apiService";

const barcodeImageApi = {
  list: (id) => getBarcodeImages(id),
  upload: (id, files) => uploadBarcodeImages(id, files),
  remove: (imgId) => deleteBarcodeImage(imgId),
  reorder: (id, orderedIds) => reorderBarcodeImages(id, orderedIds),
};

/** Photo manager for a barcode. Thin wrapper over the generic EntityImages. */
export default function BarcodeImages({
  barcodeId, barcodeText, open, onOpenChange,
  staged = false, stagedFiles = [], onStagedChange,
}) {
  return (
    <EntityImages
      api={barcodeImageApi}
      entityId={barcodeId}
      entityText={barcodeText}
      open={open}
      onOpenChange={onOpenChange}
      staged={staged}
      stagedFiles={stagedFiles}
      onStagedChange={onStagedChange}
    />
  );
}
