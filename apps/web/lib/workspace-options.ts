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

export function nextMultiSelectValue(
  selected: string[],
  option: string,
  checked: boolean,
) {
  if (!checked) return selected.filter((item) => item !== option);
  return selected.includes(option) ? selected : [...selected, option];
}

export function documentAudiencesForCategory(
  category: string,
  selected: string[],
) {
  if (category === "external" || !selected.includes("general_public")) {
    return selected;
  }
  const protectedAudiences = selected.filter(
    (audience) => audience !== "general_public",
  );
  return protectedAudiences.length > 0 ? protectedAudiences : ["member"];
}
