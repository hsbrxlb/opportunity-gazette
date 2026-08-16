export type EvidenceRef = {
  source: string;
  sourceType: string;
  originalTitle: string;
  url: string;
  observedAt: string;
  metrics: Record<string, number>;
  strength: '强' | '中';
  boundary: string;
};

export type Entry = {
  id: string;
  seriesId: string;
  kind: 'opportunity' | 'case';
  quality: 'feature' | 'editorial';
  title: string;
  plain: string;
  audience: string;
  pain: string;
  why: string;
  validation: string;
  risk: string;
  topics: string[];
  evidence: EvidenceRef[];
};

export type IssueSummary = {
  date: string;
  status: 'published' | 'no精品';
  counts: {
    collected: number;
    oldAccepted: number;
    published: number;
    features: number;
    editorial: number;
    rejected: number;
  };
  leadTitle: string;
  leadKind: Entry['kind'] | null;
  hasCover: boolean;
};

export type Issue = {
  schemaVersion: number;
  qualityVersion: string;
  date: string;
  generatedAt: string;
  status: IssueSummary['status'];
  counts: IssueSummary['counts'];
  failedSources: Array<{ source: string; status: string; detail: string }>;
  entries: Entry[];
};

export type Series = {
  id: string;
  title: string;
  kind: Entry['kind'];
  topics: string[];
  dates: string[];
  entryIds: string[];
};

export type Catalog = {
  schemaVersion: number;
  qualityVersion: string;
  generatedAt: string;
  issues: IssueSummary[];
  series: Series[];
  stats: {
    reportDays: number;
    historicalCandidates: number;
    publishedEntries: number;
    featureEntries: number;
    editorialEntries: number;
    excludedEntries: number;
  };
};

const issueModules = import.meta.glob('../data/issues/*.json', { eager: true, import: 'default' }) as Record<string, Issue>;
const catalogModule = import('../data/catalog.json');

export async function getCatalog(): Promise<Catalog> {
  const module = await catalogModule;
  return module.default as Catalog;
}

export function getIssues(): Issue[] {
  return Object.values(issueModules).sort((a, b) => b.date.localeCompare(a.date));
}

export function getIssue(date: string): Issue | undefined {
  return getIssues().find((issue) => issue.date === date);
}

export function getEntryMap(): Map<string, { issue: Issue; entry: Entry }> {
  const map = new Map<string, { issue: Issue; entry: Entry }>();
  for (const issue of getIssues()) {
    for (const entry of issue.entries) map.set(entry.id, { issue, entry });
  }
  return map;
}

export function formatDate(date: string, withYear = true): string {
  const value = new Date(`${date}T00:00:00+08:00`);
  return new Intl.DateTimeFormat('zh-CN', {
    year: withYear ? 'numeric' : undefined,
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    timeZone: 'Asia/Shanghai',
  }).format(value);
}

export function issueHref(date: string): string {
  return `/opportunity-gazette/issues/${date}/`;
}

export function topicHref(id: string): string {
  return `/opportunity-gazette/topics/${id}/`;
}
