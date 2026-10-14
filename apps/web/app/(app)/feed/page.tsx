import Link from "next/link";

import { getJobsPage } from "@/lib/api";

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_MAX = 500;

function intParam(value: string | string[] | undefined, fallback: number) {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

export default async function FeedPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const pageSize = Math.min(intParam(sp.size, PAGE_SIZE_DEFAULT), PAGE_SIZE_MAX);
  const data = await getJobsPage(intParam(sp.page, 1), pageSize);
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const href = (p: number) => `/feed?page=${p}&size=${data.page_size}`;

  return (
    <section aria-labelledby="feed-heading" className="flex flex-col gap-(--space-gap)">
      <h1 id="feed-heading" className="text-xl font-semibold">
        Feed
      </h1>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Job postings</caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Title</th>
              <th scope="col" className="px-3 py-2 font-medium">Company</th>
              <th scope="col" className="px-3 py-2 font-medium">Location</th>
              <th scope="col" className="px-3 py-2 font-medium">Workplace</th>
              <th scope="col" className="px-3 py-2 font-medium">Posted</th>
              <th scope="col" className="px-3 py-2 font-medium">Filter</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((job) => (
              <tr key={job.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">{job.title}</td>
                <td className="px-3 py-2">{job.company}</td>
                <td className="px-3 py-2">{job.location}</td>
                <td className="px-3 py-2 capitalize">{job.workplace_type}</td>
                <td className="px-3 py-2">
                  <time dateTime={job.posted_at}>{job.posted_at.slice(0, 10)}</time>
                </td>
                <td className="px-3 py-2 capitalize">{job.filter_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <nav aria-label="Pagination" className="flex items-center gap-(--space-gap) text-sm">
        {data.page > 1 && (
          <Link className="underline underline-offset-4" href={href(data.page - 1)}>
            Previous
          </Link>
        )}
        <span>
          Page {data.page} of {pages} ({data.total} jobs)
        </span>
        {data.page < pages && (
          <Link className="underline underline-offset-4" href={href(data.page + 1)}>
            Next
          </Link>
        )}
      </nav>
    </section>
  );
}
