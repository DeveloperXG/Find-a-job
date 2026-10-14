import createClient from "openapi-fetch";

import type { paths } from "../../../packages/contracts/schema";

export const api = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

// TODO(S1-08): GET /jobs does not exist in the OpenAPI schema yet. Until it
// does, the feed reads this mock page; swap these types for
// `paths["/jobs"]` and `getJobsPage` for `api.GET("/jobs", ...)`.
export type FilterStatus = "pending" | "passed" | "rejected";
export type WorkplaceType = "onsite" | "hybrid" | "remote";

export interface FeedJob {
  id: string;
  title: string;
  company: string;
  location: string;
  workplace_type: WorkplaceType;
  posted_at: string;
  filter_status: FilterStatus;
}

export interface JobsPage {
  items: FeedJob[];
  total: number;
  page: number;
  page_size: number;
}

const MOCK_TOTAL = 500;
const TITLES = [
  "Software Engineer, New Grad",
  "Machine Learning Engineer",
  "Backend Engineer Intern",
  "Data Engineer",
  "Frontend Engineer",
  "Research Engineer",
];
const COMPANIES = ["Acme Labs", "Globex", "Initech", "Umbrella Systems", "Hooli"];
const LOCATIONS = ["Remote", "Berlin", "Toronto", "Lagos", "Austin, TX"];
const WORKPLACES: WorkplaceType[] = ["remote", "hybrid", "onsite"];
const STATUSES: FilterStatus[] = ["passed", "pending", "rejected"];

function mockJob(i: number): FeedJob {
  const posted = new Date(Date.UTC(2026, 9, 1) - i * 3_600_000 * 5);
  return {
    id: `mock-${i}`,
    title: TITLES[i % TITLES.length],
    company: COMPANIES[i % COMPANIES.length],
    location: LOCATIONS[i % LOCATIONS.length],
    workplace_type: WORKPLACES[i % WORKPLACES.length],
    posted_at: posted.toISOString(),
    filter_status: STATUSES[i % STATUSES.length],
  };
}

export async function getJobsPage(
  page: number,
  pageSize: number,
): Promise<JobsPage> {
  const start = (page - 1) * pageSize;
  const count = Math.max(0, Math.min(pageSize, MOCK_TOTAL - start));
  return {
    items: Array.from({ length: count }, (_, k) => mockJob(start + k)),
    total: MOCK_TOTAL,
    page,
    page_size: pageSize,
  };
}
