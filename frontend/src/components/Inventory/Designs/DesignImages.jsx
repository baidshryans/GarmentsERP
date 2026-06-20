import EntityImages from "../BarcodeManagement/EntityImages";
import {
  getDesignImages, uploadDesignImages, deleteDesignImage, reorderDesignImages,
} from "@/services/apiService";

const designImageApi = {
  list: (id) => getDesignImages(id),
  upload: (id, files) => uploadDesignImages(id, files),
  remove: (imgId) => deleteDesignImage(imgId),
  reorder: (id, orderedIds) => reorderDesignImages(id, orderedIds),
};

/** Photo manager for a design (catalog photos). Thin wrapper over EntityImages. */
export default function DesignImages({
  designId, designText, open, onOpenChange,
  staged = false, stagedFiles = [], onStagedChange,
}) {
  return (
    <EntityImages
      api={designImageApi}
      entityId={designId}
      entityText={designText}
      open={open}
      onOpenChange={onOpenChange}
      staged={staged}
      stagedFiles={stagedFiles}
      onStagedChange={onStagedChange}
    />
  );
}
