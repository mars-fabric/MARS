import { Skeleton } from '@/components/core'

export default function SessionsLoading() {
  return (
    <div className="flex h-full">
      <div className="w-full flex flex-col h-full">
        <div className="flex-shrink-0 px-6 py-4 border-b" style={{ borderColor: 'var(--mars-color-border)' }}>
          <div className="mb-3">
            <Skeleton width={120} height={28} />
            <div className="mt-2">
              <Skeleton width={80} height={14} />
            </div>
          </div>
          <Skeleton height={36} />
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-3">
            <Skeleton height={80} />
            <Skeleton height={80} />
            <Skeleton height={80} />
          </div>
        </div>
      </div>
    </div>
  )
}
