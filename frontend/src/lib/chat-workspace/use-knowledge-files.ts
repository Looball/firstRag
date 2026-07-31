import {
  type RefObject,
  useCallback,
  useState,
} from "react";
import { useKnowledgeFileIndexing } from "./use-knowledge-file-indexing";
import {
  useKnowledgeFileLibrary,
} from "./use-knowledge-file-library";
import {
  buildKnowledgeFileUploadMessage,
  useKnowledgeFileMutations,
} from "./use-knowledge-file-mutations";

type UseKnowledgeFilesOptions = {
  hasCheckedAuth: boolean;
  selectedKnowledgeBaseId: string;
  selectedKnowledgeBaseName: string;
  selectedKnowledgeBaseStoredFileCount: number;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onKnowledgeBaseFileCountChange: (
    knowledgeBaseId: string,
    fileCount: number,
  ) => void;
};

/** 组合知识文件 library 与 vector indexing，并编排跨域刷新和提示。 */
export function useKnowledgeFiles({
  hasCheckedAuth,
  selectedKnowledgeBaseId,
  selectedKnowledgeBaseName,
  selectedKnowledgeBaseStoredFileCount,
  fileInputRef,
  onKnowledgeBaseFileCountChange,
}: UseKnowledgeFilesOptions) {
  const [isFileManagerOpen, setIsFileManagerOpen] = useState(false);
  const [vectorIndexMessage, setVectorIndexMessage] = useState("");
  const [vectorIndexError, setVectorIndexError] = useState("");
  const {
    isLoadingKnowledgeFiles,
    isLoadingReusableFiles,
    knowledgeBaseFiles,
    knowledgeFileLoadError,
    knowledgeFiles,
    refreshKnowledgeFiles,
    reusableFileLoadError,
    reusableKnowledgeFiles,
    selectedKnowledgeBaseFileCount,
    selectedKnowledgeFiles,
  } = useKnowledgeFileLibrary({
    hasCheckedAuth,
    selectedKnowledgeBaseId,
    selectedKnowledgeBaseStoredFileCount,
    onKnowledgeBaseFileCountChange,
  });
  const {
    clearCompletedVectorIndexJobs,
    deletingVectorFileId,
    handleDeleteKnowledgeFileVectors,
    handleIndexKnowledgeBase,
    handleIndexKnowledgeFile,
    isIndexingKnowledgeBase,
    isLoadingVectorIndexHealth,
    loadVectorIndexHealth,
    removeVectorIndexJobsForFile,
    vectorIndexHealth,
    vectorIndexHealthError,
    vectorIndexingFileIds,
    vectorIndexQueue,
    vectorIndexRetryAfterSeconds,
  } = useKnowledgeFileIndexing({
    hasCheckedAuth,
    knowledgeFiles,
    refreshKnowledgeFiles,
    selectedKnowledgeBaseId,
    selectedKnowledgeBaseName,
    setVectorIndexError,
    setVectorIndexMessage,
  });
  const {
    attachingKnowledgeFileId,
    detachingKnowledgeFileId,
    handleAttachKnowledgeFile,
    handlePermanentlyDeleteKnowledgeFile: permanentlyDeleteKnowledgeFile,
    handleRemoveKnowledgeFile,
    handleSelectFiles: selectKnowledgeFiles,
    isUploadingKnowledgeFiles,
    knowledgeFileAttachError,
    knowledgeFileDeleteError,
    knowledgeFileDetachError,
    knowledgeFileUploadError,
    permanentlyDeletingFileId,
    uploadRetryAfterSeconds,
  } = useKnowledgeFileMutations({
    selectedKnowledgeBaseId,
    fileInputRef,
    refreshKnowledgeFiles,
  });

  const handleOpenFileManager = useCallback(async () => {
    setIsFileManagerOpen(true);
    await Promise.all([
      refreshKnowledgeFiles(),
      loadVectorIndexHealth(),
    ]);
  }, [loadVectorIndexHealth, refreshKnowledgeFiles]);

  const handleSelectFiles = useCallback(
    async (files: FileList | null) => {
      await selectKnowledgeFiles(files, {
        onStart: () => {
          setVectorIndexError("");
          setVectorIndexMessage("");
          setIsFileManagerOpen(true);
        },
        onUploaded: (uploadedFiles) => {
          setVectorIndexMessage(
            buildKnowledgeFileUploadMessage(uploadedFiles),
          );
        },
        refreshExternalState: loadVectorIndexHealth,
      });
    },
    [loadVectorIndexHealth, selectKnowledgeFiles],
  );

  const handlePermanentlyDeleteKnowledgeFile = useCallback(
    async (fileId: string) => {
      await permanentlyDeleteKnowledgeFile(fileId, {
        onStart: () => {
          setVectorIndexMessage("");
        },
        onDeleted: (deletedFileId) => {
          removeVectorIndexJobsForFile(deletedFileId);
          setVectorIndexMessage("知识文件及其索引数据已永久删除。");
        },
        refreshExternalState: loadVectorIndexHealth,
      });
    },
    [
      loadVectorIndexHealth,
      permanentlyDeleteKnowledgeFile,
      removeVectorIndexJobsForFile,
    ],
  );

  return {
    attachingKnowledgeFileId,
    clearCompletedVectorIndexJobs,
    deletingVectorFileId,
    detachingKnowledgeFileId,
    handleAttachKnowledgeFile,
    handleDeleteKnowledgeFileVectors,
    handlePermanentlyDeleteKnowledgeFile,
    handleIndexKnowledgeBase,
    handleIndexKnowledgeFile,
    handleOpenFileManager,
    handleRemoveKnowledgeFile,
    handleSelectFiles,
    isFileManagerOpen,
    isIndexingKnowledgeBase,
    isLoadingKnowledgeFiles,
    isLoadingReusableFiles,
    isLoadingVectorIndexHealth,
    isUploadingKnowledgeFiles,
    knowledgeBaseFiles,
    knowledgeFileAttachError,
    knowledgeFileDeleteError,
    knowledgeFileDetachError,
    knowledgeFileLoadError,
    knowledgeFileUploadError,
    loadVectorIndexHealth,
    permanentlyDeletingFileId,
    reusableFileLoadError,
    reusableKnowledgeFiles,
    selectedKnowledgeBaseFileCount,
    selectedKnowledgeFiles,
    setIsFileManagerOpen,
    vectorIndexError,
    vectorIndexHealth,
    vectorIndexHealthError,
    vectorIndexingFileIds,
    vectorIndexMessage,
    vectorIndexQueue,
    uploadRetryAfterSeconds,
    vectorIndexRetryAfterSeconds,
  };
}
