import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { DEFAULT_KNOWLEDGE_BASE_ID } from "./constants";
import * as chatApi from "./api";
import type { KnowledgeBaseFile, KnowledgeFile } from "./types";

type LoadingOptions = {
  showLoading?: boolean;
};

type UseKnowledgeFileLibraryOptions = {
  hasCheckedAuth: boolean;
  selectedKnowledgeBaseId: string;
  selectedKnowledgeBaseStoredFileCount: number;
  onKnowledgeBaseFileCountChange: (
    knowledgeBaseId: string,
    fileCount: number,
  ) => void;
};

/** 合并指定知识库的文件响应，并保留全局列表中已有的 usage count。 */
export function mergeKnowledgeFilesForKnowledgeBase(
  previousFiles: KnowledgeFile[],
  loadedFiles: KnowledgeFile[],
) {
  const loadedFileIds = new Set(loadedFiles.map((file) => file.id));
  const previousFilesById = new Map(previousFiles.map((file) => [file.id, file]));
  const mergedLoadedFiles = loadedFiles.map((file) => ({
    ...file,
    usageCount:
      file.usageCount ?? previousFilesById.get(file.id)?.usageCount ?? null,
  }));

  return [
    ...mergedLoadedFiles,
    ...previousFiles.filter((file) => !loadedFileIds.has(file.id)),
  ];
}

/** 替换指定知识库的文件关联，同时保留其他知识库的关联缓存。 */
export function replaceKnowledgeBaseFileAssociations(
  previousAssociations: KnowledgeBaseFile[],
  knowledgeBaseId: string,
  loadedFiles: KnowledgeFile[],
) {
  return [
    ...previousAssociations.filter(
      (association) => association.knowledgeBaseId !== knowledgeBaseId,
    ),
    ...loadedFiles.map((file) => ({
      knowledgeBaseId,
      knowledgeFileId: file.id,
    })),
  ];
}

/** 管理知识文件列表、知识库关联缓存、刷新和派生集合。 */
export function useKnowledgeFileLibrary({
  hasCheckedAuth,
  selectedKnowledgeBaseId,
  selectedKnowledgeBaseStoredFileCount,
  onKnowledgeBaseFileCountChange,
}: UseKnowledgeFileLibraryOptions) {
  const [isLoadingKnowledgeFiles, setIsLoadingKnowledgeFiles] =
    useState(false);
  const [knowledgeFileLoadError, setKnowledgeFileLoadError] = useState("");
  const [isLoadingReusableFiles, setIsLoadingReusableFiles] =
    useState(false);
  const [reusableFileLoadError, setReusableFileLoadError] = useState("");
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState<
    KnowledgeBaseFile[]
  >([]);
  const selectedKnowledgeFileIds = useMemo(
    () =>
      new Set(
        knowledgeBaseFiles
          .filter(
            (association) =>
              association.knowledgeBaseId === selectedKnowledgeBaseId,
          )
          .map((association) => association.knowledgeFileId),
      ),
    [knowledgeBaseFiles, selectedKnowledgeBaseId],
  );
  const selectedKnowledgeFiles = useMemo(
    () => knowledgeFiles.filter((file) => selectedKnowledgeFileIds.has(file.id)),
    [knowledgeFiles, selectedKnowledgeFileIds],
  );
  const reusableKnowledgeFiles = useMemo(
    () => knowledgeFiles.filter((file) => !selectedKnowledgeFileIds.has(file.id)),
    [knowledgeFiles, selectedKnowledgeFileIds],
  );
  const selectedKnowledgeBaseFileCount =
    selectedKnowledgeFiles.length || selectedKnowledgeBaseStoredFileCount || 0;

  const loadKnowledgeBaseFiles = useCallback(
    async (knowledgeBaseId: string, options?: LoadingOptions) => {
      if (!knowledgeBaseId || knowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID) {
        return;
      }

      const shouldShowLoading = options?.showLoading !== false;

      if (shouldShowLoading) {
        setIsLoadingKnowledgeFiles(true);
      }

      setKnowledgeFileLoadError("");

      try {
        const loadedFiles = await chatApi.listKnowledgeBaseFiles(knowledgeBaseId);

        setKnowledgeFiles((previousFiles) =>
          mergeKnowledgeFilesForKnowledgeBase(previousFiles, loadedFiles),
        );
        setKnowledgeBaseFiles((previousAssociations) =>
          replaceKnowledgeBaseFileAssociations(
            previousAssociations,
            knowledgeBaseId,
            loadedFiles,
          ),
        );
        onKnowledgeBaseFileCountChange(knowledgeBaseId, loadedFiles.length);
      } catch (error) {
        setKnowledgeFileLoadError(
          error instanceof Error
            ? error.message
            : "读取知识库文件失败，请稍后再试。",
        );
      } finally {
        if (shouldShowLoading) {
          setIsLoadingKnowledgeFiles(false);
        }
      }
    },
    [onKnowledgeBaseFileCountChange],
  );

  const loadAllKnowledgeFiles = useCallback(async (options?: LoadingOptions) => {
    const shouldShowLoading = options?.showLoading !== false;

    if (shouldShowLoading) {
      setIsLoadingReusableFiles(true);
    }

    setReusableFileLoadError("");

    try {
      setKnowledgeFiles(await chatApi.listAllKnowledgeFiles());
    } catch (error) {
      setReusableFileLoadError(
        error instanceof Error
          ? error.message
          : "读取用户文件列表失败，请稍后再试。",
      );
    } finally {
      if (shouldShowLoading) {
        setIsLoadingReusableFiles(false);
      }
    }
  }, []);

  const refreshKnowledgeFiles = useCallback(
    async (options?: LoadingOptions) => {
      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId, options),
        loadAllKnowledgeFiles(options),
      ]);
    },
    [loadAllKnowledgeFiles, loadKnowledgeBaseFiles, selectedKnowledgeBaseId],
  );

  useEffect(() => {
    if (!hasCheckedAuth || !selectedKnowledgeBaseId) {
      return;
    }

    void loadKnowledgeBaseFiles(selectedKnowledgeBaseId);
  }, [hasCheckedAuth, loadKnowledgeBaseFiles, selectedKnowledgeBaseId]);

  return {
    isLoadingKnowledgeFiles,
    isLoadingReusableFiles,
    knowledgeBaseFiles,
    knowledgeFileLoadError,
    knowledgeFiles,
    loadAllKnowledgeFiles,
    loadKnowledgeBaseFiles,
    refreshKnowledgeFiles,
    reusableFileLoadError,
    reusableKnowledgeFiles,
    selectedKnowledgeBaseFileCount,
    selectedKnowledgeFiles,
  };
}
