import { Skeleton } from '@/components/core'

export default function TasksLoading() {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <Skeleton width={100} height={28} />
        <div className="mt-2">
          <Skeleton width={260} height={14} />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton height={72} />
        <Skeleton height={72} />
        <Skeleton height={72} />
        <Skeleton height={72} />
      </div>
    </div>
  )
}
