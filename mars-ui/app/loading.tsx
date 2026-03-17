import { Skeleton } from '@/components/core'

export default function HomeLoading() {
  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex-1 min-h-0 overflow-auto p-8">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8 text-center">
            <Skeleton width={200} height={32} />
            <div className="mt-2 mx-auto" style={{ maxWidth: 300 }}>
              <Skeleton height={14} />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <Skeleton height={140} />
            <Skeleton height={140} />
            <Skeleton height={140} />
            <Skeleton height={140} />
            <Skeleton height={140} />
            <Skeleton height={140} />
          </div>
        </div>
      </div>
    </div>
  )
}
