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

export interface AnalysisJob {
  id: string;
  status: string;
  repositoryId: string;
}
