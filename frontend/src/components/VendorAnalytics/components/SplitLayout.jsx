import { Skeleton } from '@/components/ui/skeleton';

export default function SplitLayout({ title, filterBar, chart, table, loading, empty }) {
  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Page header */}
      <h1 className="text-xl font-semibold">{title}</h1>

      {/* Filter bar */}
      {filterBar}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : empty ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <p className="text-lg">No data found</p>
          <p className="text-sm">Try adjusting your filters</p>
        </div>
      ) : (
        <>
          {/* Chart panel */}
          {chart && (
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              {chart}
            </div>
          )}

          {/* Table panel */}
          {table && (
            <div className="rounded-lg border bg-white shadow-sm">
              {table}
            </div>
          )}
        </>
      )}
    </div>
  );
}
