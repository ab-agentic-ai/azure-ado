#!/usr/bin/env python3
"""Build the pinned LibreChat image with its model picker in the composer."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache" / "librechat-v0.8.9"
PATCHES = ROOT / "scripts" / "librechat_patches"
IMAGE = "ab-agentic-ai/librechat-composer:v0.8.9"
TAG = "v0.8.9"


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def replace_once(path: Path, before: str, after: str) -> None:
    source = path.read_text()
    count = source.count(before)
    if count != 1:
        raise SystemExit(f"Expected one patch anchor in {path.relative_to(SOURCE)}, found {count}.")
    path.write_text(source.replace(before, after, 1))


def apply_composer_picker_patch() -> None:
    header = SOURCE / "client/src/components/Chat/Header.tsx"
    bar = SOURCE / "client/src/components/Chat/Input/Composer/Bar.tsx"
    selector = SOURCE / "client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx"
    selector_context = SOURCE / "client/src/components/Chat/Menus/Endpoints/ModelSelectorContext.tsx"
    server_index = SOURCE / "api/server/index.js"
    endpoint_middleware = SOURCE / "api/server/middleware/buildEndpointOption.js"
    quota_component = SOURCE / "client/src/components/Chat/Input/GeminiQuotaIndicator.tsx"
    response_theme = SOURCE / "client/src/agentic-response-theme.css"
    code_block = SOURCE / "client/src/components/Messages/Content/CodeBlock.tsx"
    agent_grid = SOURCE / "client/src/components/Agents/AgentGrid.tsx"
    agent_queries = SOURCE / "client/src/data-provider/Agents/queries.ts"
    index_html = SOURCE / "client/index.html"
    logo = SOURCE / "client/public/assets/logo.svg"
    achat_icon = SOURCE / "client/public/assets/achat.svg"
    main_entry = SOURCE / "client/src/main.jsx"
    shutil.copyfile(PATCHES / "GeminiQuotaIndicator.tsx", quota_component)
    shutil.copyfile(PATCHES / "AgenticResponseTheme.css", response_theme)
    shutil.copyfile(PATCHES / "AChatLogo.svg", logo)
    shutil.copyfile(PATCHES / "AChatLogo.svg", achat_icon)

    replace_once(
        index_html,
        "<title>LibreChat</title>",
        "<title>AChat</title>",
    )

    replace_once(
        agent_grid,
        "import { useMarketplaceAgentsInfiniteQuery } from '~/data-provider/Agents';\n",
        "import { useMarketplaceAgentsInfiniteQuery } from '~/data-provider/Agents';\n"
        "import { useAuthContext } from '~/hooks/AuthContext';\n",
    )
    replace_once(
        agent_grid,
        "  const localize = useLocalize();\n",
        "  const localize = useLocalize();\n"
        "  const { user } = useAuthContext();\n",
    )
    replace_once(
        agent_grid,
        "  } = useMarketplaceAgentsInfiniteQuery(queryParams);\n",
        "  } = useMarketplaceAgentsInfiniteQuery(queryParams, undefined, user?.id ?? 'anonymous');\n",
    )
    replace_once(
        agent_queries,
        "export const useMarketplaceAgentsInfiniteQuery = (\n"
        "  params: t.AgentListParams,\n"
        "  config?: UseInfiniteQueryOptions<t.AgentListResponse, unknown>,\n"
        ") => {\n"
        "  const queryClient = useQueryClient();\n"
        "  const queryKey = [QueryKeys.marketplaceAgents, params] as const;\n",
        "export const useMarketplaceAgentsInfiniteQuery = (\n"
        "  params: t.AgentListParams,\n"
        "  config?: UseInfiniteQueryOptions<t.AgentListResponse, unknown>,\n"
        "  cacheScope = 'anonymous',\n"
        ") => {\n"
        "  const queryClient = useQueryClient();\n"
        "  const queryKey = [QueryKeys.marketplaceAgents, cacheScope, params] as const;\n",
    )
    replace_once(
        agent_queries,
        "    staleTime: 2 * 60 * 1000, // 2 minutes\n"
        "    cacheTime: 10 * 60 * 1000, // 10 minutes\n"
        "    refetchOnWindowFocus: false,\n",
        "    staleTime: 0,\n"
        "    cacheTime: 10 * 60 * 1000, // 10 minutes\n"
        "    refetchOnMount: true,\n"
        "    refetchOnWindowFocus: true,\n",
    )
    replace_once(
        index_html,
        '<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32x32.png" />',
        '<link rel="icon" type="image/svg+xml" href="assets/achat.svg" />',
    )

    replace_once(
        code_block,
        "type CodeBlockProps = Pick<\n",
        """const getCodeText = (node: React.ReactNode): string => {
  if (typeof node === 'string' || typeof node === 'number') {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(getCodeText).join('');
  }
  if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
    return getCodeText(node.props.children);
  }
  return '';
};

type CodeBlockProps = Pick<
""",
    )
    replace_once(
        code_block,
        "  const localize = useLocalize();\n",
        "  const localize = useLocalize();\n"
        "  const lineCount = useMemo(() => Math.max(1, getCodeText(codeChildren).split('\\n').length), [codeChildren]);\n",
    )
    replace_once(
        code_block,
        """      <div dir="ltr" className={cn(classProp, 'bg-surface-code-body overflow-y-auto p-4')}>
        <code
          ref={codeRef}
          className={cn(
            isNonCode ? '!whitespace-pre-wrap' : `hljs language-${language} !whitespace-pre`,
          )}
        >
          {codeChildren}
        </code>
      </div>
""",
        """      <div dir="ltr" className={cn(classProp, 'bg-surface-code-body flex overflow-auto p-0')}>
        <div
          aria-hidden="true"
          className="border-border-inset bg-surface-code-body text-text-tertiary sticky left-0 z-10 min-w-10 shrink-0 border-r px-2 py-4 text-right font-mono leading-6 select-none"
        >
          {Array.from({ length: lineCount }, (_, index) => (
            <span className="block" key={index}>{index + 1}</span>
          ))}
        </div>
        <div className="min-w-0 flex-1 overflow-x-auto p-4">
          <code
            ref={codeRef}
            className={cn(
              'block min-w-max leading-6',
              isNonCode ? '!whitespace-pre-wrap' : `hljs language-${language} !whitespace-pre`,
            )}
          >
            {codeChildren}
          </code>
        </div>
      </div>
""",
    )

    replace_once(
        header,
        "import ModelSelector from './Menus/Endpoints/ModelSelector';\n",
        "",
    )
    replace_once(header, "        {!readOnly && <ModelSelector startupConfig={startupConfig} />}\n", "")

    replace_once(
        bar,
        "import { cn } from '~/utils';\n",
        "import { cn } from '~/utils';\n"
        "import ModelSelector from '~/components/Chat/Menus/Endpoints/ModelSelector';\n"
        "import GeminiQuotaIndicator from '~/components/Chat/Input/GeminiQuotaIndicator';\n"
        "import { useGetStartupConfig } from '~/data-provider';\n",
    )
    replace_once(
        bar,
        "  const localize = useLocalize();\n  const context = useBadgeRowContext();\n",
        "  const localize = useLocalize();\n"
        "  const { data: startupConfig } = useGetStartupConfig();\n"
        "  const context = useBadgeRowContext();\n",
    )
    replace_once(
        bar,
        "            anchorRef={anchorRef}\n          />\n        </span>\n"
        "        {/* A box rather than `contents` so it has something to move: the split\n",
        "            anchorRef={anchorRef}\n          />\n        </span>\n"
        "        <div className=\"flex min-w-0 shrink items-center gap-1.5\">\n"
        "          <ModelSelector startupConfig={startupConfig} />\n"
        "          <GeminiQuotaIndicator\n"
        "            endpoint={endpoint}\n"
        "            model={conversation?.model}\n"
        "            agentId={conversation?.agent_id}\n"
        "            isSubmitting={isSubmitting}\n"
        "          />\n"
        "        </div>\n"
        "        {/* A box rather than `contents` so it has something to move: the split\n",
    )
    replace_once(
        selector,
        "className=\"border-border-light bg-presentation text-text-primary hover:bg-surface-active-alt rounded-theme-control flex h-9 max-w-full items-center gap-2 border px-3 py-2 text-sm\"",
        "className=\"border-border-light bg-presentation text-text-primary hover:bg-surface-active-alt rounded-theme-control flex h-7 max-w-full items-center gap-1.5 border px-2 py-1 text-xs\"",
    )
    replace_once(
        selector,
        "import React, { useMemo } from 'react';\n",
        "import React, { useMemo } from 'react';\n"
        "import { isAgentsEndpoint } from 'librechat-data-provider';\n"
        "import { useAuthContext } from '~/hooks/AuthContext';\n",
    )
    replace_once(
        selector,
        "function ModelSelectorContent() {\n  const localize = useLocalize();\n",
        "function ModelSelectorContent() {\n"
        "  const { user } = useAuthContext();\n"
        "  const isAdmin = user?.role === 'ADMIN';\n"
        "  const localize = useLocalize();\n",
    )
    replace_once(
        selector,
        "  const selectedIcon = useMemo(\n",
        "  const visibleModelSpecs = useMemo(\n"
        "    () =>\n"
        "      isAdmin\n"
        "        ? modelSpecs\n"
        "        : modelSpecs.filter(\n"
        "            (spec) =>\n"
        "              isAgentsEndpoint(spec.preset?.endpoint ?? '') ||\n"
        "              Boolean(spec.preset?.agent_id),\n"
        "          ),\n"
        "    [isAdmin, modelSpecs],\n"
        "  );\n"
        "  const visibleEndpoints = useMemo(\n"
        "    () => (isAdmin ? mappedEndpoints : mappedEndpoints?.filter((endpoint) => isAgentsEndpoint(endpoint.value))),\n"
        "    [isAdmin, mappedEndpoints],\n"
        "  );\n"
        "  const visibleSearchResults = useMemo(\n"
        "    () =>\n"
        "      isAdmin\n"
        "        ? searchResults\n"
        "        : searchResults?.filter((item) => {\n"
        "            if ('preset' in item && item.preset) {\n"
        "              return (\n"
        "                isAgentsEndpoint(item.preset.endpoint ?? '') ||\n"
        "                Boolean(item.preset.agent_id)\n"
        "              );\n"
        "            }\n"
        "            return 'value' in item && isAgentsEndpoint(item.value);\n"
        "          }),\n"
        "    [isAdmin, searchResults],\n"
        "  );\n\n"
        "  const selectedIcon = useMemo(\n",
    )
    replace_once(
        selector,
        "        {searchResults ? (\n          renderSearchResults(searchResults, localize, searchValue)\n",
        "        {visibleSearchResults ? (\n          renderSearchResults(visibleSearchResults, localize, searchValue)\n",
    )
    replace_once(
        selector,
        "              modelSpecs?.filter((spec) => !spec.group) || [],\n",
        "              visibleModelSpecs?.filter((spec) => !spec.group) || [],\n",
    )
    replace_once(selector, "renderEndpoints(mappedEndpoints ?? [])", "renderEndpoints(visibleEndpoints ?? [])")
    replace_once(
        selector,
        "renderCustomGroups(modelSpecs || [], mappedEndpoints ?? [])",
        "renderCustomGroups(visibleModelSpecs || [], visibleEndpoints ?? [])",
    )

    replace_once(
        selector_context,
        "import React, { createContext, useContext, useState, useMemo, useCallback } from 'react';\n",
        "import React, { createContext, useContext, useState, useMemo, useCallback, useEffect } from 'react';\n",
    )
    replace_once(
        selector_context,
        "import { useGetEndpointsQuery, useListAgentsQuery } from '~/data-provider';\n",
        "import { useGetEndpointsQuery, useMarketplaceAgentsInfiniteQuery } from '~/data-provider';\n"
        "import { useAuthContext } from '~/hooks/AuthContext';\n"
        "import { mapAgents } from '~/utils/map';\n",
    )
    replace_once(
        selector_context,
        "  const agentsMap = useAgentsMapContext();\n",
        "  const agentsMapContext = useAgentsMapContext();\n",
    )
    replace_once(
        selector_context,
        "  useAgentDefaultPermissionLevel,\n",
        "",
    )
    replace_once(
        selector_context,
        "  const permissionLevel = useAgentDefaultPermissionLevel();\n"
        "  /**\n"
        "   * Always query the VIEW scope so this shares one cache entry (and one paginated walk)\n"
        "   * with `useAgentsMap` and `useMentions`. Asking for EDIT here spawned a second full\n"
        "   * fetch under its own key, holding a duplicate copy of the whole agent list. The\n"
        "   * marketplace's \"my agents\" framing is preserved by filtering on `isEditable`, which\n"
        "   * the list endpoint resolves from the same ACL read it already performs.\n"
        "   */\n"
        "  const wantsEditableOnly = permissionLevel === PermissionBits.EDIT;\n"
        "  const selectAgents = useCallback(\n"
        "    (data: t.AgentListResponse) => {\n"
        "      const list = data?.data;\n"
        "      if (!wantsEditableOnly) {\n"
        "        return list;\n"
        "      }\n"
        "      return list?.filter((agent) => agent.isEditable !== false);\n"
        "    },\n"
        "    [wantsEditableOnly],\n"
        "  );\n"
        "  const agentsQuery = useListAgentsQuery(\n"
        "    { requiredPermission: PermissionBits.VIEW },\n"
        "    { select: selectAgents, enabled: agentsReady },\n"
        "  );\n",
        "  const { user } = useAuthContext();\n"
        "  const agentsQuery = useMarketplaceAgentsInfiniteQuery(\n"
        "    { requiredPermission: PermissionBits.VIEW, limit: 100, sort: 'newest' },\n"
        "    { enabled: agentsReady },\n"
        "    user?.id ?? 'anonymous',\n"
        "  );\n"
        "  const agents = useMemo(() => {\n"
        "    if (!agentsQuery.data?.pages) return null;\n"
        "    const seen = new Set<string>();\n"
        "    return agentsQuery.data.pages.flatMap((page) => page.data ?? []).filter((agent) => {\n"
        "      if (seen.has(agent.id)) return false;\n"
        "      seen.add(agent.id);\n"
        "      return true;\n"
        "    });\n"
        "  }, [agentsQuery.data?.pages]);\n"
        "  useEffect(() => {\n"
        "    if (agentsReady && agentsQuery.hasNextPage && !agentsQuery.isFetching && !agentsQuery.isError) {\n"
        "      void agentsQuery.fetchNextPage({ cancelRefetch: false });\n"
        "    }\n"
        "  }, [agentsReady, agentsQuery.hasNextPage, agentsQuery.isFetching, agentsQuery.isError, agentsQuery.fetchNextPage]);\n"
        "  const marketplaceAgentsMap = useMemo(\n"
        "    () => (agents ? mapAgents(agents) : undefined),\n"
        "    [agents],\n"
        "  );\n"
        "  const agentsMap = useMemo(() => {\n"
        "    if (!marketplaceAgentsMap) return agentsMapContext;\n"
        "    return { ...(agentsMapContext ?? {}), ...marketplaceAgentsMap };\n"
        "  }, [agentsMapContext, marketplaceAgentsMap]);\n",
    )
    replace_once(
        selector_context,
        "    agents: agentsQuery.data ?? null,\n",
        "    agents,\n",
    )

    replace_once(
        server_index,
        "    await updateInterfacePermissions({\n"
        "      appConfig,\n"
        "      getRoleByName,\n"
        "      updateAccessPermissions,\n"
        "      recordAuditEntry,\n"
        "    });\n",
        "    await updateInterfacePermissions({\n"
        "      appConfig,\n"
        "      getRoleByName,\n"
        "      updateAccessPermissions,\n"
        "      recordAuditEntry,\n"
        "    });\n"
        "    // Enforce the deployment's Marketplace-only policy for every regular account,\n"
        "    // including when a USER role already exists in the persistent database.\n"
        "    await updateAccessPermissions('USER', {\n"
        "      AGENTS: { USE: true, CREATE: false, SHARE: false, SHARE_PUBLIC: false },\n"
        "      MARKETPLACE: { USE: true },\n"
        "    });\n",
    )
    replace_once(
        endpoint_middleware,
        "  const isAgents =\n"
        "    isAgentsEndpoint(endpoint) || req.baseUrl.startsWith(EndpointURLs[EModelEndpoint.agents]);\n\n",
        "  const isAgents =\n"
        "    isAgentsEndpoint(endpoint) || req.baseUrl.startsWith(EndpointURLs[EModelEndpoint.agents]);\n"
        "  if (req.user?.role && req.user.role !== 'ADMIN' && !isAgents) {\n"
        "    return res.status(403).json({\n"
        "      error: 'Forbidden',\n"
        "      message: 'This account can use Marketplace agents only.',\n"
        "    });\n"
        "  }\n\n",
    )
    replace_once(
        main_entry,
        "import './style.css';\n",
        "import './style.css';\nimport './agentic-response-theme.css';\n",
    )


def main() -> None:
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / ".git").exists():
        if SOURCE.exists():
            shutil.rmtree(SOURCE)
        run(
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            TAG,
            "https://github.com/LibreChat-AI/LibreChat.git",
            str(SOURCE),
        )
    else:
        current = subprocess.run(
            ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        expected = subprocess.run(
            ["git", "-C", str(SOURCE), "rev-parse", f"refs/tags/{TAG}^{{commit}}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if current != expected:
            raise SystemExit(
                f"LibreChat source commit {current} does not match pinned tag {TAG} ({expected})."
            )

    # Reset just the source files so rerunning this script never applies a patch twice.
    for relative in (
        "client/src/components/Chat/Header.tsx",
        "client/src/components/Chat/Input/Composer/Bar.tsx",
        "client/src/components/Chat/Menus/Endpoints/ModelSelector.tsx",
        "client/src/components/Chat/Menus/Endpoints/ModelSelectorContext.tsx",
        "client/src/main.jsx",
        "client/src/components/Messages/Content/CodeBlock.tsx",
        "client/src/components/Agents/AgentGrid.tsx",
        "client/src/data-provider/Agents/queries.ts",
        "client/index.html",
        "client/public/assets/logo.svg",
        "api/server/index.js",
        "api/server/middleware/buildEndpointOption.js",
    ):
        run("git", "-C", str(SOURCE), "checkout", "--", relative)
    apply_composer_picker_patch()
    run("docker", "build", "--tag", IMAGE, str(SOURCE))
    print(f"Built {IMAGE} with the model picker in the message composer.")


if __name__ == "__main__":
    main()
