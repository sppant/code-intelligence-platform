export const HEALTH_QUERY = `
  query Health {
    health
  }
`;

export const ANALYZE_REPOSITORY_MUTATION = `
  mutation AnalyzeRepository($repoUrl: String!) {
    analyzeRepository(repoUrl: $repoUrl) {
      id
      status
      repositoryId
    }
  }
`;

export const ANALYSIS_JOB_STATUS_QUERY = `
  query AnalysisJobStatus($id: UUID!) {
    analysisJob(id: $id) {
      id
      status
      errorMessage
      repositoryId
    }
  }
`;

export const REPOSITORY_OVERVIEW_QUERY = `
  query RepositoryOverview($id: UUID!) {
    repository(id: $id) {
      id
      name
      owner
      url
      latestAnalysis {
        id
        createdAt
        statistics {
          totalFiles
          totalLines
          languages
          totalSymbols
          totalDependencyEdges
        }
      }
    }
  }
`;

export const REPOSITORY_FILES_QUERY = `
  query RepositoryFiles($id: UUID!) {
    repository(id: $id) {
      name
      latestAnalysis {
        id
        files {
          path
          language
          lineCount
          symbols {
            id
            name
            kind
            lineStart
            lineEnd
          }
        }
      }
    }
  }
`;

export const REPOSITORY_GRAPH_QUERY = `
  query RepositoryGraph($id: UUID!) {
    repository(id: $id) {
      name
      latestAnalysis {
        files {
          path
          language
        }
        dependencyEdges {
          sourcePath
          targetPath
          externalModule
          type
        }
      }
    }
  }
`;

export const SEARCH_SYMBOLS_QUERY = `
  query SearchSymbols($analysisId: UUID!, $query: String!, $kind: String) {
    searchSymbols(analysisId: $analysisId, query: $query, kind: $kind) {
      id
      name
      kind
      filePath
      lineStart
      lineEnd
    }
  }
`;

export interface AnalysisJob {
  id: string;
  status: string;
  errorMessage?: string | null;
  repositoryId: string;
}

export interface SymbolResult {
  id: string;
  name: string;
  kind: string;
  filePath?: string;
  lineStart: number;
  lineEnd: number;
}

export interface FileNode {
  path: string;
  language: string | null;
  lineCount: number;
  symbols: SymbolResult[];
}

export interface DependencyEdge {
  sourcePath: string;
  targetPath: string | null;
  externalModule: string | null;
  type: string;
}

export interface RepositoryStatistics {
  totalFiles: number;
  totalLines: number;
  languages: Record<string, number>;
  totalSymbols: number;
  totalDependencyEdges: number;
}

export interface Repository {
  id: string;
  name: string;
  owner: string;
  url: string;
  latestAnalysis: {
    id: string;
    createdAt: string;
    statistics: RepositoryStatistics;
  } | null;
}
