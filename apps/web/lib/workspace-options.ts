export type WorkspaceOptionQueryState = {
  isPending: boolean;
  isError: boolean;
};

export function workspaceOptionQueryState(
  hasRemoteSource: boolean,
  query: WorkspaceOptionQueryState,
) {
  return {
    isLoading: hasRemoteSource && query.isPending,
    isError: hasRemoteSource && query.isError,
  };
}
